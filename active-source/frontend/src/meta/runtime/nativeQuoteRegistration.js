import { ref } from 'vue'
import request from '@/api/request.js'
import { readTabIdentity, getTabAuthEpoch } from './tabAuthenticationContext.js'
import { NATIVE_QUOTE_ACTIONS } from '../process/scm/nativeQuoteRegistrationActions.js'

export const nativeQuoteEndpoints = Object.freeze({
  comparison: '/api/procurement/scm-page-facts/quote-comparison/',
  preparation: '/api/procurement/price-approval-preparations/',
  inquiry: '/api/procurement/scm-page-facts/purchase-inquiry/',
  registration: '/api/procurement/quote-comparisons/register/',
})
export function quoteFailure(result, url) {
  const status = result?.meta?.status ?? result?.httpStatus ?? 0
  const prefix = ({ 400: '输入不符合合同', 401: '尚未认证', 403: '没有所需资格',
    404: '对象不存在或不在授权范围', 409: '来源或版本待核', 500: '服务读取或处理失败' })[status] || '请求未取得可靠结果'
  return { status, url, code: result?.error?.code || result?.errorCode || 'RESPONSE_CONTRACT_MISSING',
    message: `${prefix}：${result?.error?.message || result?.errorMessage || '未取得正式服务响应。'}` }
}
export function createNativeQuoteRegistration({ transport = request, storage = globalThis.sessionStorage,
  identity = readTabIdentity(), epoch = getTabAuthEpoch(), currentEpoch = getTabAuthEpoch } = {}) {
  const records = ref(null), count = ref(null), loadState = ref('idle'), loadError = ref(null)
  const inquiries = ref(null), requestLines = ref(null), requestBusy = ref(false), sourceError = ref(null), context = ref(null), contextBusy = ref(false)
  const pending = ref(null), receipt = ref(null), rejectedAction = ref(null), actionError = ref(null), actionBusy = ref(false)
  const scope = identity?.username || identity?.id
  // Persist only the original action key/source IDs, never authoritative facts or credentials.
  const storageKey = scope ? `pce-native-quote-action:${String(scope)}` : null
  if (storageKey) {
    try { const value = JSON.parse(storage?.getItem(storageKey) || 'null')
      if (value?.idempotencyKey && Number.isSafeInteger(value.inquiryId) && Number.isSafeInteger(value.requestItemId)) pending.value = value
    } catch { /* malformed UI preference conveys no facts or qualification */ }
  }
  function savePending(value) {
    pending.value = value
    if (storageKey) { if (value) storage?.setItem(storageKey, JSON.stringify(value)); else storage?.removeItem(storageKey) }
  }
  const sameIdentity = () => epoch === currentEpoch()
  async function read(url, params) {
    if (!sameIdentity()) throw { status: 401, code: 'AUTHENTICATION_CONTEXT_CHANGED', url, message: '标签页身份已变化，请在当前身份重新进入页面。' }
    const result = await transport({ url, params, meta: { module: 'SCM', readOnly: true } })
    if (!result?.success || result.data == null) throw quoteFailure(result, url)
    return result.data
  }
  async function load(mode) {
    loadState.value = 'loading'; loadError.value = null; records.value = null; count.value = null
    try { const data = await read(nativeQuoteEndpoints[mode])
      const list = mode === 'comparison' ? data.objects : data.records
      const total = mode === 'comparison' ? data.recordCount : data.resultCount
      if (!Array.isArray(list) || !Number.isInteger(total)) throw quoteFailure(null, nativeQuoteEndpoints[mode])
      records.value = list; count.value = total; loadState.value = list.length ? 'loaded' : 'empty_valid'
    } catch (error) { loadError.value = error; loadState.value = 'read_failed' }
  }
  async function loadInquiries() {
    if (pending.value) return
    inquiries.value = null; requestLines.value = null; context.value = null; sourceError.value = null
    try { const data = await read(nativeQuoteEndpoints.inquiry)
      if (!Array.isArray(data.objects)) throw quoteFailure(null, nativeQuoteEndpoints.inquiry)
      inquiries.value = data.objects
    } catch (error) { sourceError.value = error }
  }
  async function loadRequest(source) {
    if (pending.value || requestBusy.value) return
    requestLines.value = null; sourceError.value = null; context.value = null
    if (!source?.sourcePurchaseRequestId) return
    requestBusy.value = true
    const url = `/api/procurement/purchase-requests/${source.sourcePurchaseRequestId}/`
    try { const data = await read(url)
      if (String(data.id) !== String(source.sourcePurchaseRequestId) || !Array.isArray(data.items)) throw quoteFailure(null, url)
      requestLines.value = data.items
    } catch (error) { sourceError.value = error } finally { requestBusy.value = false }
  }
  async function loadContext(inquiryId, requestItemId) {
    if (pending.value || contextBusy.value) return
    context.value = null; actionError.value = null; contextBusy.value = true
    try { context.value = await read(nativeQuoteEndpoints.registration, { inquiryId, requestItemId }) }
    catch (error) { actionError.value = error } finally { contextBusy.value = false }
  }
  async function register(basisNote, reason) {
    if (actionBusy.value || pending.value || !sameIdentity() || !NATIVE_QUOTE_ACTIONS.register.allowed(context.value)) return
    const captured = context.value
    const original = { inquiryId: captured.sourceSnapshot.inquiry.id,
      requestItemId: captured.sourceSnapshot.requestItem.id, idempotencyKey: crypto.randomUUID() }
    // Save before sending. An uncertain response can never create a second POST.
    savePending(original); actionBusy.value = true; actionError.value = null; receipt.value = null
    try {
      const result = await transport({ url: nativeQuoteEndpoints.registration, method: 'POST',
        data: { ...original, expectedSourceFingerprint: captured.sourceFingerprint,
          expectedPreviousFactId: captured.expectedPreviousFactId, expectedPreviousVersion: captured.expectedPreviousVersion,
          basisNote, reason }, meta: { module: 'SCM', actionCode: NATIVE_QUOTE_ACTIONS.register.actionCode } })
      if (result?.success && result.data?.resultState === 'COMMITTED') receipt.value = result.data
      else {
        actionError.value = quoteFailure(result, nativeQuoteEndpoints.registration)
        // Only a definite validation/authorization rejection ends this attempt.
        const definiteRejection = [400, 401, 403, 404].includes(actionError.value.status)
          || (actionError.value.status === 409 && actionError.value.code.startsWith('COMPARISON_')
            && actionError.value.code !== 'COMPARISON_CONCURRENT_CHANGE')
        if (definiteRejection) {
          rejectedAction.value = { originalAction: original, rejection: actionError.value }
          savePending(null); context.value = null
        }
      }
    } catch (error) { actionError.value = { status: 0, code: 'RESULT_UNKNOWN', message: error?.message || '登记结果未知，请仅查询原动作。' } }
    finally { actionBusy.value = false }
  }
  async function queryOriginal() {
    if (!pending.value || actionBusy.value) return
    actionBusy.value = true; actionError.value = null
    try { const data = await read(nativeQuoteEndpoints.registration, pending.value)
      if (!['COMMITTED', 'UNKNOWN'].includes(data.resultState)) throw quoteFailure(null, nativeQuoteEndpoints.registration)
      receipt.value = data
    } catch (error) { actionError.value = error } finally { actionBusy.value = false }
  }
  function acknowledgeCommitted() {
    if (receipt.value?.resultState !== 'COMMITTED') return
    savePending(null); receipt.value = null; context.value = null
  }
  return { records, count, loadState, loadError, inquiries, requestLines, requestBusy, sourceError, context, contextBusy,
    pending, receipt, rejectedAction, actionError, actionBusy, load, loadInquiries, loadRequest, loadContext, register, queryOriginal, acknowledgeCommitted }
}

import { ref } from 'vue'
import request from '@/api/request.js'
import { readTabIdentity, getTabAuthEpoch } from './tabAuthenticationContext.js'
import { quoteFailure } from './nativeQuoteRegistration.js'

export const ORDER_APPROVAL_ROUTES = Object.freeze(Object.fromEntries(
  ['submit', 'approve', 'review', 'release'].map(step =>
    [`procurement.purchase_order.${step}`, `${step}-purchase-order`])))
const CONTRACT = 'PCE-NATIVE-PURCHASE-ORDER-FOUR-ACTIONS-V1'

export function createNativeOrderApproval({ transport = request, storage = globalThis.sessionStorage,
  identity = readTabIdentity(), epoch = getTabAuthEpoch(), currentEpoch = getTabAuthEpoch,
  newKey = () => crypto.randomUUID() } = {}) {
  const context = ref(null), readError = ref(null), busy = ref(false), actionError = ref(null)
  const pending = ref(null), receipt = ref(null)
  const account = identity?.username || identity?.id
  const storageKey = account ? `pce-native-order-approval:${String(account)}` : null
  let generation = 0
  const sameIdentity = () => epoch === currentEpoch()
  const url = (id, action) => `/api/procurement/scm-runtime-actions/${ORDER_APPROVAL_ROUTES[action]}/${id}/`
  function save(value) {
    // Only the original object/action/key are retained, never authorization or business facts.
    if (!storageKey) throw new Error('当前页签身份尚未取得，禁止提交。')
    if (value) storage?.setItem(storageKey, JSON.stringify(value))
    else storage?.removeItem(storageKey)
    pending.value = value
  }
  try {
    const saved = JSON.parse(storageKey && storage?.getItem(storageKey) || 'null')
    if (Number.isSafeInteger(saved?.orderId) && saved.orderId > 0 && ORDER_APPROVAL_ROUTES[saved.action]
      && typeof saved.idempotencyKey === 'string' && saved.idempotencyKey) pending.value = saved
  } catch { /* Invalid display context grants no authority. */ }
  async function read(id, action, params) {
    if (!sameIdentity()) throw new Error('页签身份已变化，请在当前身份重新进入页面。')
    const endpoint = url(id, action)
    const result = await transport({ url: endpoint, method: 'GET', params, meta: { module: 'SCM', readOnly: true } })
    if (!sameIdentity()) throw new Error('读取期间页签身份已变化。')
    if (!result?.success || result.data == null) throw quoteFailure(result, endpoint)
    return result.data
  }
  async function load(orderId) {
    const id = Number(orderId), current = ++generation
    context.value = null; readError.value = null; busy.value = true
    try {
      if (!Number.isSafeInteger(id) || id <= 0) throw new Error('采购订单定位无效。')
      const value = await read(id, 'procurement.purchase_order.submit')
      if (value.contractVersion !== CONTRACT || value.orderId !== id || !value.orderNo || !value.sourceFingerprint
        || !Number.isInteger(value.decisionVersion) || !Number.isInteger(value.workflowVersion)
        || !Array.isArray(value.availableActions) || !Array.isArray(value.blockedReasons)
        || !Array.isArray(value.actionContracts) || !Array.isArray(value.history)) throw quoteFailure(null, url(id, 'procurement.purchase_order.submit'))
      if (current === generation) context.value = value
    } catch (error) { if (current === generation) readError.value = error }
    finally { if (current === generation) busy.value = false }
  }
  async function execute(action, reason) {
    const captured = context.value
    if (busy.value || pending.value || !sameIdentity() || !ORDER_APPROVAL_ROUTES[action]
      || !captured?.availableActions.includes(action) || !captured.actionContracts.some(c => c.actionCode === action)
      || !String(reason || '').trim()) return
    const original = { orderId: captured.orderId, action, idempotencyKey: newKey() }
    const body = { sourceFingerprint: captured.sourceFingerprint, expectedDecisionVersion: captured.decisionVersion,
      expectedWorkflowVersion: captured.workflowVersion, reason: String(reason).trim(), idempotencyKey: original.idempotencyKey }
    busy.value = true; actionError.value = null; receipt.value = null; ++generation
    let saved = false
    try {
      save(original); saved = true
      const result = await transport({ url: url(original.orderId, action), method: 'POST', data: body,
        meta: { module: 'SCM', explicitBusinessAction: true, actionCode: action } })
      if (!sameIdentity()) throw new Error('提交期间页签身份已变化，原动作须由原身份查询。')
      if (result?.success && result.data?.resultState === 'COMMITTED') receipt.value = result.data
      else {
        actionError.value = quoteFailure(result, url(original.orderId, action))
        // A definite pre-execution rejection may be corrected; conflicts/unknown retain the original key.
        if ([400, 401, 403, 404].includes(actionError.value.status)) save(null)
      }
    } catch (error) {
      actionError.value = { code: saved ? 'RESULT_UNKNOWN' : 'ACTION_KEY_NOT_SAVED',
        message: saved ? `结果尚未确认，只可查询原动作。${error?.message || ''}` : `未提交：${error?.message || '原动作标识未能保存。'}` }
    } finally { context.value = null; busy.value = false }
  }
  async function queryOriginal() {
    if (!pending.value || busy.value) return
    busy.value = true; actionError.value = null
    try {
      const original = pending.value
      const result = await read(original.orderId, original.action, { idempotencyKey: original.idempotencyKey })
      if (!['COMMITTED', 'UNKNOWN'].includes(result.resultState)) throw quoteFailure(null, url(original.orderId, original.action))
      receipt.value = result
    } catch (error) { actionError.value = error } finally { busy.value = false }
  }
  async function acknowledgeCommitted(orderId) {
    if (receipt.value?.resultState !== 'COMMITTED' || !sameIdentity() || !pending.value) return
    save(null); receipt.value = null; await load(orderId)
  }
  return { context, readError, busy, actionError, pending, receipt, load, execute, queryOriginal, acknowledgeCommitted }
}

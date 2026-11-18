import { ref } from 'vue'
import request from '@/api/request.js'
import { readTabIdentity, getTabAuthEpoch } from './tabAuthenticationContext.js'
import { quoteFailure } from './nativeQuoteRegistration.js'
import { PREPARATION_REVIEW_ACTIONS } from '../process/scm/nativePreparationReviewActions.js'

export function createNativePreparationReview({ transport = request, storage = globalThis.sessionStorage,
  identity = readTabIdentity(), epoch = getTabAuthEpoch(), currentEpoch = getTabAuthEpoch } = {}) {
  const context = ref(null), readError = ref(null), busy = ref(false), actionError = ref(null)
  const pending = ref(null), receipt = ref(null), rejected = ref(null)
  let readGeneration = 0
  const scope = identity?.username || identity?.id
  const key = scope ? `pce-native-preparation-review-action:${String(scope)}` : null
  if (key) {
    try { const saved = JSON.parse(storage?.getItem(key) || 'null')
      if (Number.isSafeInteger(saved?.preparationId) && saved.idempotencyKey && PREPARATION_REVIEW_ACTIONS[saved.action]) pending.value = saved
    } catch { /* UI key is not a fact or authorization. */ }
  }
  const url = id => `/api/procurement/price-approval-preparations/${id}/transition/`
  const sameIdentity = () => epoch === currentEpoch()
  function save(value) {
    pending.value = value
    if (key) { if (value) storage?.setItem(key, JSON.stringify(value)); else storage?.removeItem(key) }
  }
  async function read(id, params) {
    if (!sameIdentity()) throw { status: 401, code: 'AUTHENTICATION_CONTEXT_CHANGED', message: '标签页身份已变化，请在当前身份重新进入页面。' }
    const result = await transport({ url: url(id), params, meta: { module: 'SCM', readOnly: true } })
    if (!sameIdentity()) throw { status: 401, code: 'AUTHENTICATION_CONTEXT_CHANGED', message: '读取期间标签页身份已变化，请在当前身份重新进入页面。' }
    if (!result?.success || result.data == null) throw quoteFailure(result, url(id))
    return result.data
  }
  async function load(id) {
    const generation = ++readGeneration
    context.value = null; readError.value = null; busy.value = true
    try {
      const data = await read(id)
      if (data.preparationId !== id || !data.sourceComparisonFactId || !data.sourceFingerprint
        || !Number.isInteger(data.sourceComparisonVersion) || !Number.isInteger(data.decisionVersion)
        || !Number.isInteger(data.workflowVersion) || !Array.isArray(data.availableActions)
        || !Array.isArray(data.blockedReasons) || !Array.isArray(data.history)) throw quoteFailure(null, url(id))
      if (generation === readGeneration) context.value = data
    } catch (error) { if (generation === readGeneration) readError.value = error }
    finally { if (generation === readGeneration) busy.value = false }
  }
  async function execute(action, { reason, reviewResult, opinion, selectedSupplierCode } = {}) {
    const captured = context.value, contract = PREPARATION_REVIEW_ACTIONS[action]
    if (busy.value || pending.value || !sameIdentity() || !contract?.allowed(captured)) return
    ++readGeneration
    const original = { preparationId: captured.preparationId, action, idempotencyKey: crypto.randomUUID() }
    const body = { action, sourceComparisonFactId: captured.sourceComparisonFactId,
      sourceComparisonVersion: captured.sourceComparisonVersion, sourceFingerprint: captured.sourceFingerprint,
      expectedDecisionVersion: captured.decisionVersion, expectedWorkflowVersion: captured.workflowVersion,
      reason, idempotencyKey: original.idempotencyKey,
      ...(action === 'SUBMIT_REVIEW' ? { reviewResult, opinion, selectedSupplierCode: selectedSupplierCode || '' } : {}) }
    save(original); busy.value = true; actionError.value = null; receipt.value = null
    try {
      const result = await transport({ url: url(original.preparationId), method: 'POST', data: body,
        meta: { module: 'SCM', actionCode: contract.actionCode } })
      if (result?.success && result.data?.resultState === 'COMMITTED') receipt.value = result.data
      else {
        actionError.value = quoteFailure(result, url(original.preparationId))
        if ([400, 401, 403, 404].includes(actionError.value.status)) {
          rejected.value = { original, error: actionError.value }; save(null)
        }
      }
    } catch (error) { actionError.value = { status: 0, code: 'RESULT_UNKNOWN', message: error?.message || '审核结果未知，请仅查询原动作。' } }
    finally { context.value = null; busy.value = false }
  }
  async function queryOriginal() {
    if (!pending.value || busy.value) return
    busy.value = true; actionError.value = null
    try {
      const data = await read(pending.value.preparationId, { idempotencyKey: pending.value.idempotencyKey })
      if (!['COMMITTED', 'UNKNOWN'].includes(data.resultState)) throw quoteFailure(null, url(pending.value.preparationId))
      receipt.value = data
    } catch (error) { actionError.value = error } finally { busy.value = false }
  }
  async function acknowledgeCommitted() {
    if (receipt.value?.resultState !== 'COMMITTED') return
    const id = pending.value.preparationId; save(null); receipt.value = null; await load(id)
  }
  return { context, readError, busy, actionError, pending, receipt, rejected, load, execute, queryOriginal, acknowledgeCommitted }
}

import { reactive } from 'vue'
import request from '@/api/request.js'
import { getTabAuthEpoch, readTabIdentity } from './tabAuthenticationContext.js'
import { PRODUCTION_MATERIAL_ACTIONS, materialActionAuthorization } from '../process/productionMaterialActions.js'

export const materialEndpoints = Object.freeze({ demand: '/api/planning/demands/', allocation: '/api/procurement/material-stock-allocations/', preparation: '/api/procurement/material-preparations/', issue: '/api/procurement/material-issues/', receive: '/api/procurement/material-receipts/' })
export const materialText = value => value == null || value === '' ? '未提供' : String(value)
export function materialFailure(response, url) {
  const status = response?.meta?.status ?? response?.status ?? 0
  const kind = ({ 400: '输入不符合合同', 401: '尚未认证或会话失效', 403: '没有本范围资格', 404: '对象不存在或不可读取', 409: '来源或版本冲突', 500: '服务读取或处理失败' })[status] || '未取得可靠响应'
  return { status, url, code: response?.error?.code || 'RESULT_UNKNOWN', message: `${kind}：${response?.error?.message || '事实和结果未知，请勿重复提交。'}` }
}
export function createProductionMaterialPage({ transport = request, mode, storage = globalThis.sessionStorage, identity = readTabIdentity(), epoch = getTabAuthEpoch(), currentEpoch = getTabAuthEpoch } = {}) {
  const delivery = mode === 'issue' || mode === 'receive'
  const module = mode === 'demand' ? 'PLAN' : mode === 'receive' ? 'MES' : 'WMS'
  const state = reactive({ facts: null, loadState: 'idle', error: null, busy: false, pending: null, receipt: null, rejected: null })
  const scope = identity?.username || identity?.userId || identity?.id
  let readGeneration = 0
  const storageKey = scope ? `pce-material-original-action:${mode}:${scope}` : null
  const validPending = value => value && value.mode === mode && value.idempotencyKey && (delivery ? value.action === mode : ['register', 'confirm', 'allocate', 'prepare'].includes(value.action)) && Number.isSafeInteger(value.objectId)
  const matchesDeliveryResult = (result, original) => Number.isSafeInteger(result?.issueId) &&
    (mode === 'issue' ? result.allocationId === original.objectId : result.issueId === original.objectId)
  try { const saved = JSON.parse(storage?.getItem(storageKey) || 'null'); if (storageKey && validPending(saved)) state.pending = saved } catch { /* no stored facts */ }
  const sameOwner = () => epoch === currentEpoch()
  function save(value) {
    state.pending = value
    if (storageKey) { if (value) storage?.setItem(storageKey, JSON.stringify(value)); else storage?.removeItem(storageKey) }
  }
  function invalidate() { readGeneration++; state.facts = null; state.loadState = 'idle'; state.error = null }
  async function read(params) {
    if (state.busy || state.pending) return
    invalidate(); state.loadState = 'loading'
    const generation = readGeneration
    try {
      if (!sameOwner()) throw materialFailure({ meta: { status: 401 } }, materialEndpoints[mode])
      const response = await transport({ url: materialEndpoints[mode], params, timeout: 90000, meta: { module, readOnly: true } })
      if (generation !== readGeneration) return
      if (!sameOwner()) return invalidate()
      if (!response?.success || !response.data || typeof response.data !== 'object') throw materialFailure(response, materialEndpoints[mode])
      if (mode === 'preparation' && (response.data.selected?.allocationId !== params.allocationId || !Array.isArray(response.data.selected.history) || response.data.selected.demandId !== response.data.demand?.demandId)) {
        throw materialFailure({ error: { message: '返回的备料对象或历史与原分配不一致。' } }, materialEndpoints[mode])
      }
      if (delivery) {
        const facts = response.data
        const expectedObject = mode === 'issue' ? facts.allocationId === params.allocationId && Array.isArray(facts.history)
          : params.issueId ? facts.issueId === params.issueId : Array.isArray(facts.rows) && facts.count === facts.rows.length
        if (facts.contractVersion !== 'PCE-PRODUCTION-MATERIAL-ISSUE-V1' || !expectedObject) {
          throw materialFailure({ error: { message: '交付事实与本次选择的原对象不一致。' } }, materialEndpoints[mode])
        }
      }
      state.facts = response.data; state.loadState = 'loaded'
    } catch (error) { if (generation === readGeneration) { state.facts = null; state.error = error; state.loadState = 'read_failed' } }
  }
  async function submit(action, payload, objectId) {
    if (state.busy || state.pending || !sameOwner() || !materialActionAuthorization(state.facts, action).enabled) return
    const contract = PRODUCTION_MATERIAL_ACTIONS[action]
    const original = { mode, action, objectId, idempotencyKey: crypto.randomUUID() }
    save(original); state.busy = true; state.error = null; state.receipt = null; state.rejected = null
    try {
      const data = mode === 'demand' ? { sourceType: 'production_material', action, ...payload, idempotencyKey: original.idempotencyKey } : { ...payload, idempotencyKey: original.idempotencyKey }
      const response = await transport({ url: materialEndpoints[mode], method: 'POST', data, meta: { module: contract.moduleCode, actionCode: contract.actionCode, explicitBusinessAction: true } })
      if (!sameOwner()) return invalidate()
      const result = response?.data
      const accepted = delivery ? matchesDeliveryResult(result, original) : mode === 'preparation'
        ? result?.allocationId === original.objectId && Number.isSafeInteger(result.preparationId)
        : result?.demandId || result?.allocationId
      if (response?.success && accepted) state.receipt = { resultState: 'COMMITTED', result, historicalReceiptOnly: true }
      else {
        state.error = materialFailure(response, materialEndpoints[mode])
        const rejectedCodes = ['MATERIAL_ALLOCATION_VERSION_CONFLICT', 'MATERIAL_STOCK_VERSION_CONFLICT', 'MATERIAL_ALLOCATION_UNIT_PRECISION', 'MATERIAL_DEMAND_ALLOCATION_EXCEEDED', 'MATERIAL_STOCK_ALLOCATION_EXCEEDED', 'MATERIAL_INTENT_CONFLICT', 'MATERIAL_SOURCE_CHANGED', 'MATERIAL_DEMAND_STATE_CONFLICT', 'MATERIAL_DEMAND_RANGE_OVERLAP']
        // The shared service marks uncertain concurrent commits separately from domain rejections.
        const preparationRejected = mode === 'preparation' && state.error.status === 409
          && /^MATERIAL_PREPARATION_/.test(state.error.code)
        if ([400, 401, 403, 404].includes(state.error.status) || preparationRejected || (state.error.status === 409 && rejectedCodes.includes(state.error.code))) { state.rejected = { original, error: state.error }; save(null) }
      }
    } catch (error) { state.error = { code: 'RESULT_UNKNOWN', message: error?.message || '结果未知，只能查询原动作。' } }
    finally { state.facts = null; state.loadState = 'idle'; state.busy = false }
  }
  async function queryOriginal() {
    if (state.busy || !state.pending || !sameOwner()) return
    state.busy = true; state.error = null
    const original = state.pending
    const params = { resultKey: original.idempotencyKey }
    if (mode === 'demand') Object.assign(params, { productionPlanId: original.objectId, action: original.action })
    else if (mode === 'preparation') params.allocationId = original.objectId
    else if (!delivery) params.demandId = original.objectId
    try {
      const response = await transport({ url: materialEndpoints[mode], params, timeout: 90000, meta: { readOnly: true, module } })
      if (!sameOwner()) return invalidate()
      if (!response?.success || !['COMMITTED', 'UNKNOWN'].includes(response.data?.resultState)) throw materialFailure(response, materialEndpoints[mode])
      if (mode === 'preparation' && response.data.resultState === 'COMMITTED' && response.data.result?.allocationId !== original.objectId) {
        throw materialFailure({ error: { message: '同次回执与原分配不一致。' } }, materialEndpoints[mode])
      }
      if (delivery && response.data.resultState === 'COMMITTED' && !matchesDeliveryResult(response.data.result, original)) {
        throw materialFailure({ error: { message: '同次交付回执与原办理对象不一致。' } }, materialEndpoints[mode])
      }
      state.receipt = response.data
    } catch (error) { state.error = error } finally { state.busy = false }
  }
  function acknowledge() { if (state.receipt?.resultState === 'COMMITTED') { save(null); state.receipt = null; invalidate() } }
  return { state, read, submit, queryOriginal, acknowledge, invalidate }
}

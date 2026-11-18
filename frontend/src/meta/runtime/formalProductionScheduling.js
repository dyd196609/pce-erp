export const FORMAL_SCHEDULING_CONTRACT = 'PCE-PRODUCTION-PLAN-FORMAL-SCHEDULING-V1'
const actions = new Set(['validate', 'commit', 'cancel', 'authorize-capacity-scope'])
const label = value => typeof value === 'string' && Boolean(value.trim())
const positiveId = value => Number.isSafeInteger(value) && value > 0
const canonical = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item)

export function validateFormalSchedulingResponse(response, expected) {
  if (response?.success === false) throw new Error(response.error?.message || '正式排程服务读取失败。')
  const data = response?.data ?? response
  const facts = data?.formalSchedulingFacts
  if (facts?.contractVersion !== FORMAL_SCHEDULING_CONTRACT || facts.factSource !== 'server' || facts.currentStateSource !== 'server'
    || !positiveId(expected.companyId) || !positiveId(expected.productionPlanId)
    || facts.companyId !== expected.companyId || facts.productionPlanId !== expected.productionPlanId
    || !label(facts.productionPlanNo) || !label(facts.statusLabel) || facts.actionAuthorization?.canRead !== true
    || ['savedStartDateLabel', 'requiredDateLabel', 'timezoneLabel', 'modeLabel'].some(key => !label(facts[key]))
    || ['scheduleCount', 'activeReservationCount'].some(key => !Number.isInteger(facts[key]) || facts[key] < 0)
    || !Array.isArray(facts.availableActions) || !Array.isArray(facts.history) || !Array.isArray(facts.scopeGrantRequests)
    || facts.availableActions.some(action => !actions.has(action.actionCode) || !label(action.displayName) || typeof action.enabled !== 'boolean'
      || !label(action.availabilityCode) || !label(action.availabilityLabel))
    || !(facts.admission === null || facts.admission && typeof facts.admission.ready === 'boolean'
      && label(facts.admission.statusLabel) && label(facts.admission.startLabel) && label(facts.admission.endLabel)
      && Array.isArray(facts.admission.blockers) && Array.isArray(facts.admission.conflicts))
    || !(facts.activeSchedule === null || facts.activeSchedule && positiveId(facts.activeSchedule.id))) {
    throw new Error('正式排程返回的公司、生产计划或服务端事实合同不一致，当前结果未知。')
  }
  if (facts.scopeGrantRequests.some(request => request.exactScope?.companyId !== facts.companyId
    || request.exactScope?.productionPlanId !== facts.productionPlanId || !/^[a-f\d]{64}$/i.test(request.referenceHash || '')
    || ['scopeLabel', 'statusLabel', 'referenceLabel', 'effectiveFromLabel', 'effectiveToLabel'].some(key => !label(request[key])))) {
    throw new Error('精确用途依据的正式范围、引用或展示字段不一致，禁止提交。')
  }
  for (const schedule of [...facts.history, ...(facts.activeSchedule ? [facts.activeSchedule] : [])]) {
    if (!positiveId(schedule.id) || !Number.isInteger(schedule.version) || !label(schedule.statusLabel)
      || !Array.isArray(schedule.steps) || !Array.isArray(schedule.reservations)
      || !label(schedule.startLabel) || !label(schedule.endLabel)
      || schedule.steps.some(step => !positiveId(step.stepId) || ['stepLabel', 'statusLabel', 'startLabel', 'endLabel',
        'processingTimeLabel', 'preparationTimeLabel', 'transferTimeLabel', 'totalWorkTimeLabel'].some(key => !label(step[key])))
      || schedule.reservations.some(row => !positiveId(row.id) || ['primaryLabel', 'workCenterLabel', 'stepLabel',
        'statusLabel', 'startLabel', 'endLabel', 'minutesLabel'].some(key => !label(row[key])))) {
      throw new Error('正式排程版本、步骤或资源占用展示合同不完整，当前结果未知。')
    }
  }
  for (const key of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    if (data[key] !== undefined) {
      const surface = data[key]?.formalSchedulingFacts ?? data[key]
      if (canonical(surface) !== canonical(facts)) throw new Error('正式排程的服务端事实表面不一致，禁止使用本次结果。')
    }
  }
  return facts
}

export function createFormalSchedulingState() {
  return { selectedPlanId: '', facts: null, readState: 'idle', writing: false, awaitingReadback: false,
    reason: '', instructionReference: '', selectedScopeIndex: '', selectedScheduleId: '', error: '', message: '', writeReceipt: null }
}

export function createFormalSchedulingController({ state, api, companyId, owner,
  newIdempotencyKey = () => globalThis.crypto.randomUUID() }) {
  let readSequence = 0, generation = 0
  const expected = () => ({ companyId: Number(companyId()), productionPlanId: Number(state.selectedPlanId) })
  const current = (scope, planId, selectedGeneration) => scope === owner() && planId === state.selectedPlanId && selectedGeneration === generation
  function invalidate() {
    readSequence += 1; generation += 1
    Object.assign(state, createFormalSchedulingState())
  }
  async function load({ admission = false, afterWrite = false } = {}) {
    const request = ++readSequence, selectedGeneration = generation, scope = owner(), planId = state.selectedPlanId
    const previousVersion = state.selectedScheduleId
    state.facts = null; state.error = ''; state.message = ''
    if (!planId) { state.readState = 'idle'; return false }
    state.readState = 'loading'
    try {
      const response = await (admission ? api.validateProductionPlanFormalScheduling(Number(planId))
        : api.getProductionPlanFormalScheduling(Number(planId)))
      if (request !== readSequence || !current(scope, planId, selectedGeneration)) return false
      state.facts = validateFormalSchedulingResponse(response, expected())
      const versions = state.facts.history
      state.selectedScheduleId = afterWrite && state.facts.activeSchedule ? String(state.facts.activeSchedule.id)
        : versions.some(row => String(row.id) === previousVersion) ? previousVersion
          : String(state.facts.activeSchedule?.id || versions[0]?.id || '')
      state.selectedScopeIndex = state.facts.scopeGrantRequests.length === 1 ? '0' : ''
      state.awaitingReadback = false
      state.readState = 'loaded'
      return true
    } catch (error) {
      if (request !== readSequence || !current(scope, planId, selectedGeneration)) return false
      state.facts = null; state.readState = 'read_failed'
      state.error = (afterWrite ? '操作已提交，但正式回读未完成；请先刷新正式结果，不要重复提交。' : '正式排程读取失败，当前版本、步骤及占用均未知。')
        + (error?.response?.data?.error?.message || error?.message || '')
      return false
    }
  }
  async function select(planId) {
    invalidate(); state.selectedPlanId = String(planId || '')
    return load()
  }
  async function execute(actionCode) {
    const action = state.facts?.availableActions.find(item => item.actionCode === actionCode)
    if (!action?.enabled || state.writing || state.readState !== 'loaded' || state.awaitingReadback) return false
    if (actionCode === 'validate') return load({ admission: true })
    if (!state.reason.trim()) { state.error = '请填写本次操作原因。'; return false }
    const scope = owner(), planId = state.selectedPlanId, selectedGeneration = generation
    const idempotencyKey = newIdempotencyKey(), reason = state.reason.trim()
    let submit
    if (actionCode === 'commit') {
      const admissionToken = state.facts.admission?.admissionToken
      if (!label(admissionToken)) { state.error = '请先执行本计划的正式准入与冲突检查。'; return false }
      submit = () => api.saveProductionPlanFormalScheduling(Number(planId), { admissionToken, idempotencyKey, reason })
    } else if (actionCode === 'cancel') {
      const schedule = state.facts.activeSchedule
      if (!schedule) return false
      submit = () => api.cancelProductionPlanFormalSchedule(Number(planId), schedule.id,
        { expectedVersion: schedule.version, idempotencyKey, reason })
    } else if (actionCode === 'authorize-capacity-scope') {
      const request = state.facts.scopeGrantRequests[Number(state.selectedScopeIndex)]
      if (state.selectedScopeIndex === '' || !request || !state.instructionReference.trim()) {
        state.error = '请选择本次精确用途依据，并填写指令依据及操作原因。'; return false
      }
      const payload = { exactScope: request.exactScope, referenceHash: request.referenceHash,
        effectiveFrom: request.effectiveFrom, effectiveTo: request.effectiveTo,
        instructionReference: state.instructionReference.trim(), reason, idempotencyKey }
      submit = () => api.authorizeProductionPlanSchedulingScope(Number(planId), payload)
    } else return false
    state.writing = true; state.awaitingReadback = true; state.error = ''; state.message = ''; state.writeReceipt = null
    try {
      const response = await submit()
      if (!current(scope, planId, selectedGeneration)) return false
      validateFormalSchedulingResponse(response, expected())
      state.writeReceipt = response.data ?? response
      const loaded = await load({ admission: actionCode === 'authorize-capacity-scope', afterWrite: true })
      if (!current(scope, planId, selectedGeneration) || !loaded) return false
      state.reason = ''
      state.message = `${action.displayName}已提交，已重新读取正式结果。`
      return true
    } catch (error) {
      if (!current(scope, planId, selectedGeneration)) return false
      state.facts = null; state.readState = 'read_failed'
      state.error = '操作结果尚未核实；请先刷新正式结果，再决定是否重新提交。'
        + (error?.response?.data?.error?.message || error?.message || '')
      return false
    } finally {
      if (current(scope, planId, selectedGeneration)) state.writing = false
    }
  }
  return { invalidate, load, select, execute }
}

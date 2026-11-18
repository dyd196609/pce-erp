import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { resolvePceServerBusinessActions } from './pceBusinessActionRegistry.js'

export const WORK_ORDER_RECEPTION_CONTRACT = 'PCE-PRODUCTION-WORK-ORDER-RECEPTION-V1'
export const WORK_ORDER_RELEASE_ADMISSION_CONTRACT = 'PCE-PRODUCTION-WORK-ORDER-RELEASE-ADMISSION-V1'
export const WORK_ORDER_RECEPTION_CONTRACT_V2 = 'PCE-PRODUCTION-WORK-ORDER-RECEPTION-V2'
export const WORK_ORDER_RELEASE_ADMISSION_CONTRACT_V2 = 'PCE-PRODUCTION-WORK-ORDER-RELEASE-ADMISSION-V2'
export const WORK_ORDER_EXECUTION_CONTRACT = 'PCE-PRODUCTION-WORK-ORDER-EXECUTION-V1'
const admissionIdentity = Object.freeze({ actionCode: 'production.order.release', moduleCode: 'production-work-order',
  requiredPermission: 'production.order.release', requiredResponsibility: 'RESP_PMC_PLAN_001',
  processCode: 'MES_PRODUCTION_OPERATION', workflowNodeCode: 'PRODUCTION_WORK_ORDER_RELEASE', navigationNodeCode: 'production-work-order' })
const text = value => typeof value === 'string' && Boolean(value.trim())
const id = value => Number.isSafeInteger(value) && value > 0
const count = value => Number.isSafeInteger(value) && value >= 0
const canonical = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item)
const issuesValid = value => Array.isArray(value) && value.every(issue => text(issue.code) && text(issue.statusLabel)
  && (issue.stepId === undefined || id(issue.stepId)))
const remediationValid = value => value && text(value.statusLabel) && text(value.pathLabel)
  && (value.path === undefined || text(value.path))
export const workOrderReceptionApiUrl = planId => `/api/planning/production-plans/${encodeURIComponent(planId)}/work-order-reception/`
export const workOrderExecutionApiUrl = (planId, key) => `/api/planning/production-plans/${encodeURIComponent(planId)}/work-order/${key}/`
export const projectWorkOrderExecutionActions = facts => facts?.contractVersion === WORK_ORDER_RECEPTION_CONTRACT_V2
  ? resolvePceServerBusinessActions({ currentModule: facts.moduleCode, productionPlanId: facts.productionPlanId,
    actionContracts: facts.execution?.actionContracts, availableActions: facts.execution?.availableActions }) : []
const nullableId = value => value === null || id(value)
const hash = value => /^[a-f\d]{64}$/i.test(value || '')

function validateWorkOrderExecutionFacts(facts) {
  const order = facts.workOrder, execution = facts.execution
  if (!execution || execution.contractVersion !== WORK_ORDER_EXECUTION_CONTRACT || execution.factSource !== 'server'
    || !Array.isArray(execution.actionContracts) || !Array.isArray(execution.availableActions)
    || execution.actionContracts.length !== 2 || execution.availableActions.length !== 2
    || new Set(execution.actionContracts.map(row => row.key)).size !== 2
    || new Set(execution.availableActions.map(row => row.key)).size !== 2) {
    throw new Error('生产工单执行动作合同不完整，禁止提交。')
  }
  projectWorkOrderExecutionActions(facts)
  if (!order || typeof order.generated !== 'boolean' || typeof order.released !== 'boolean' || !text(order.statusLabel)
    || !Array.isArray(order.operations) || order.operationCount !== order.operations.length
    || !Array.isArray(order.routeProvenance) || !Array.isArray(order.stateTransitionHistory)
    || order.statusTransitionCount !== order.stateTransitionHistory.length || typeof order.stateMachineConsistent !== 'boolean') {
    throw new Error('正式生产工单的状态、工序或来源事实不完整，当前工单未知。')
  }
  if (!order.generated) {
    if (order.released || order.id !== null || order.no !== null || order.version !== null
      || order.operations.length || order.stateTransitionHistory.length || order.routeProvenance.length) {
      throw new Error('尚未生成的生产工单与服务端持久化事实冲突。')
    }
    return
  }
  if (!id(order.id) || !text(order.no) || !count(order.version) || !text(order.quantityLabel)
    || !id(order.uomId) || !text(order.uomCode) || !text(order.uomLabel)
    || !id(order.materialId) || !text(order.materialCode) || !text(order.materialName)
    || !id(order.sourceScheduleId) || !id(order.sourceScheduleRevision) || !count(order.sourceScheduleVersion)
    || !hash(order.sourceScheduleSnapshotHash) || !hash(order.snapshotHash)
    || !id(order.createdById) || !text(order.createdAtLabel) || !text(order.releasedAtLabel)
    || (order.released && (!id(order.releasedById) || !text(order.releasedAt)))) {
    throw new Error('正式生产工单编号、数量单位、来源版本或生成下达事实不完整。')
  }
  if (order.operations.some(row => !id(row.id) || !id(row.sequence) || !id(row.rootStepId) || !id(row.effectiveStepId)
    || !nullableId(row.rootRoutingVersionId) || !nullableId(row.effectiveRoutingVersionId)
    || !nullableId(row.originalManufacturingOutputId) || !nullableId(row.effectiveManufacturingOutputId)
    || !nullableId(row.operationId) || !text(row.operationName) || !nullableId(row.workCenterId)
    || !(row.workCenterName === null || text(row.workCenterName)) || typeof row.dependencyOnly !== 'boolean'
    || ['workloadLabel', 'startLabel', 'endLabel'].some(key => !text(row[key]))
    || ['predecessorSequences', 'allocationIds', 'reservationIds'].some(key => !Array.isArray(row[key]) || !row[key].every(id)))
    || order.routeProvenance.some(row => !text(row.statusLabel)
      || ['originalManufacturingOutputId', 'effectiveManufacturingOutputId', 'rootRoutingVersionId', 'effectiveRoutingVersionId'].some(key => !nullableId(row[key])))
    || order.stateTransitionHistory.some(row => !id(row.id) || !id(row.version) || !id(row.operatorId)
      || ['sourceStateLabel', 'targetStateLabel', 'actionLabel', 'reason', 'timestampLabel'].some(key => !text(row[key])))) {
    throw new Error('正式生产工单工序、路线逐项来源或状态迁移回读字段不完整。')
  }
}

export function validateWorkOrderReceptionResponse(response, expected) {
  const envelope = readPceFactLoadEnvelope(response, workOrderReceptionApiUrl(expected.productionPlanId), '生产工单接收与准入')
  const { data, factLoadFacts } = envelope
  const facts = data.workOrderReceptionFacts
  const executable = facts?.contractVersion === WORK_ORDER_RECEPTION_CONTRACT_V2
  if (!['loaded', 'empty_valid'].includes(factLoadFacts.factLoadStatus)
    || ![WORK_ORDER_RECEPTION_CONTRACT, WORK_ORDER_RECEPTION_CONTRACT_V2].includes(facts?.contractVersion) || facts.factSource !== 'server' || facts.currentStateSource !== 'server'
    || facts.moduleCode !== 'production-work-order' || !id(expected.companyId) || !id(expected.productionPlanId)
    || facts.companyId !== expected.companyId || facts.productionPlanId !== expected.productionPlanId
    || ['productionPlanNo', 'modeLabel', 'timezoneLabel', 'statusLabel'].some(key => !text(facts[key]))
    || typeof facts.reception?.ready !== 'boolean' || !text(facts.reception.statusLabel) || !issuesValid(facts.reception.issues)
    || typeof facts.releaseAdmission?.ready !== 'boolean' || !text(facts.releaseAdmission.statusLabel) || !issuesValid(facts.releaseAdmission.issues)
    || !Array.isArray(facts.releaseAdmission.checks) || facts.releaseAdmission.checks.some(check => !text(check.checkCode)
      || !text(check.statusLabel) || typeof check.complete !== 'boolean' || !(check.eligible === null || typeof check.eligible === 'boolean'))
    || typeof facts.currentSourceChecks?.ready !== 'boolean' || !text(facts.currentSourceChecks.statusLabel)
    || !issuesValid(facts.currentSourceChecks.issues) || !Array.isArray(facts.currentSourceChecks.steps)
    || facts.currentSourceChecks.steps.some(step => !id(step.stepId) || !text(step.statusLabel) || !count(step.allocationCount)
      || !Array.isArray(step.allocationIds) || !step.allocationIds.every(id))
    || ['preparationRoleLabel', 'executionRoleLabel', 'statusLabel'].some(key => !text(facts.responsibility?.[key]))
    || typeof facts.responsibility.qualificationProven !== 'boolean'
    || (!executable && (facts.workOrder?.generated !== false || facts.workOrder.released !== false || !text(facts.workOrder.statusLabel)))
    || facts.businessWriteCount !== 0 || facts.auditWriteCount !== 0) {
    throw new Error('生产工单接收的公司、计划或只读事实合同不一致，当前接收及下达资格未知。')
  }
  const admission = facts.releaseAdmission
  const admissionVersion = executable ? WORK_ORDER_RELEASE_ADMISSION_CONTRACT_V2 : WORK_ORDER_RELEASE_ADMISSION_CONTRACT
  if ((executable || admission.contractVersion !== undefined) && (admission.contractVersion !== admissionVersion
    || admission.issues.some(issue => !text(issue.categoryCode) || !text(issue.categoryLabel) || !remediationValid(issue.remediation))
    || !Array.isArray(admission.remediations) || !admission.remediations.every(remediationValid)
    || (!admission.ready && admission.issues.length === 0)
    || Object.entries(admissionIdentity).some(([key, value]) => admission.actionContract?.[key] !== value)
    || !text(admission.actionContract.serverValidator)
    || (executable
      ? admission.actionContract.readOnly !== false || admission.actionContract.executionEnabled !== true
        || admission.actionContract.qualificationReadOnly !== true || admission.actionContract.manualExecutionSupported !== true
        || admission.actionContract.executionAvailabilitySource !== 'execution.availableActions'
      : admission.actionContract.readOnly !== true || admission.actionContract.executionEnabled !== false))) {
    throw new Error('生产工单下达准入的服务端动作、阻断分类或处理路径合同不完整，当前资格未知。')
  }
  const actor = facts.responsibility.currentActorEvidence
  if ([WORK_ORDER_RELEASE_ADMISSION_CONTRACT, WORK_ORDER_RELEASE_ADMISSION_CONTRACT_V2].includes(admission.contractVersion) && (!actor
    || !id(actor.userId) || !id(actor.companyId) || actor.companyId !== facts.companyId
    || ['username', 'companyName', 'companyCode'].some(key => !text(actor[key])))) {
    throw new Error('生产工单本次核定的后台账号或公司身份事实不完整或不一致，当前资格未知。')
  }
  // Validate a server conclusion's completeness; never derive eligibility here.
  if (admission.ready && (admission.contractVersion !== admissionVersion
    || admission.issues.length !== 0 || admission.checks.length === 0
    || admission.checks.some(check => !check.complete || check.eligible !== true)
    || !facts.sourceSchedule || !facts.reception.ready || !facts.currentSourceChecks.ready || !facts.responsibility.qualificationProven)) {
    throw new Error('生产工单下达准入通过结论与服务端检查事实冲突，禁止使用本次结果。')
  }
  if (executable) validateWorkOrderExecutionFacts(facts)
  const source = facts.sourceSchedule
  if (!(source === null || source && id(source.id) && source.productionPlanId === facts.productionPlanId
    && id(source.revision) && count(source.version) && /^[a-f\d]{64}$/i.test(source.snapshotHash || '')
    && ['statusLabel', 'startLabel', 'endLabel'].every(key => text(source[key]))
    && ['stepCount', 'processingSegmentCount', 'activeReservationCount'].every(key => count(source[key]))
    && Array.isArray(source.steps) && Array.isArray(source.reservations)
    && source.stepCount === source.steps.length && source.processingSegmentCount === source.reservations.length
    && source.steps.every(step => id(step.stepId) && ['stepLabel', 'statusLabel', 'startLabel', 'endLabel',
      'processingTimeLabel', 'preparationTimeLabel', 'transferTimeLabel', 'totalWorkTimeLabel'].every(key => text(step[key])))
    && source.reservations.every(row => id(row.id) && ['primaryLabel', 'workCenterLabel', 'stepLabel', 'statusLabel',
      'startLabel', 'endLabel', 'minutesLabel'].every(key => text(row[key]))))) {
    throw new Error('正式排程来源版本、快照、步骤或资源占用展示字段不完整，当前来源未知。')
  }
  for (const key of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    if (canonical(data[key]?.workOrderReceptionFacts) !== canonical(facts)) {
      throw new Error('生产工单接收的服务端五表面事实不一致，禁止使用本次结果。')
    }
  }
  return { facts, factLoadFacts }
}

export function createWorkOrderReceptionState() {
  return { selectedPlanId: '', facts: null, lastReadDisplay: null, factLoadFacts: null, readState: 'idle', error: '', reason: '',
    executionState: 'idle', executionMessage: '' }
}

export function createWorkOrderReceptionController({ state, api, companyId, owner }) {
  let sequence = 0, generation = 0, pending = null, writing = false, factOwner = null, inFlight = null
  function invalidate() {
    sequence += 1; generation += 1
    pending = null; factOwner = null
    Object.assign(state, createWorkOrderReceptionState())
  }
  function load() {
    const key=JSON.stringify([owner(),generation,state.selectedPlanId,pending?.key])
    if(inFlight?.key===key)return inFlight.promise
    const promise=loadCurrent(),item={key,promise};inFlight=item
    promise.then(()=>{if(inFlight===item)inFlight=null},()=>{if(inFlight===item)inFlight=null})
    return promise
  }
  async function loadCurrent() {
    if (state.executionState === 'writing') return false
    if (factOwner && factOwner !== owner()) { invalidate(); return false }
    if (pending && pending.scope !== owner()) { invalidate(); return false }
    const request = ++sequence, selectedGeneration = generation, scope = owner(), planId = state.selectedPlanId
    const expected = { companyId: Number(companyId()), productionPlanId: Number(planId) }
    const previousContext = state.factLoadFacts
    const current = () => request === sequence && selectedGeneration === generation && scope === owner() && planId === state.selectedPlanId
    state.facts = null; state.factLoadFacts = null; state.error = ''
    if (!planId) { state.readState = 'idle'; return false }
    state.readState = 'loading'
    try {
      const response = await api.getProductionPlanWorkOrderReception(Number(planId))
      if (!current()) return false
      Object.assign(state, validateWorkOrderReceptionResponse(response, expected), { readState: 'loaded' })
      state.lastReadDisplay = null
      factOwner = scope
      if (pending) {
        const order = state.facts.workOrder
        if (order.generated && (pending.key === 'generate' || order.id === pending.workOrderId && order.released && order.version > pending.expectedVersion)) {
          state.executionState = 'verified'
          state.executionMessage = `${pending.displayName}的当前结果已独立回读核实；本次未自动执行其他动作。`
          pending = null
        } else {
          state.executionState = 'readback_pending'
          state.executionMessage = '已读取当前工单，但尚未核实此前执行结果；请先仅重新读取。若持续尚未生成，请整页刷新后再由用户明确提交；服务端按一计划一工单防重，不自动重试。'
        }
      }
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.readState = 'read_failed'
      state.factLoadFacts = factLoadFailureFromError(error, workOrderReceptionApiUrl(planId), previousContext)
      state.error = '生产工单接收读取失败，来源版本、步骤、占用及下达资格均未知。'
        + (error?.response?.data?.error?.message || error?.message || '')
      if (pending) {
        state.executionState = 'readback_pending'
        state.executionMessage = '执行提交后独立回读未通过，执行结果尚未确认；请仅重新读取，勿重复提交。'
      }
      return false
    }
  }
  async function select(planId) {
    if(String(planId||'')===state.selectedPlanId&&state.readState==='loading')return load()
    invalidate(); state.selectedPlanId = String(planId || '')
    return load()
  }
  async function execute(key) {
    if (writing || state.readState === 'loading') return false
    if (pending) return load()
    const facts = state.facts, action = projectWorkOrderExecutionActions(facts).find(row => row.key === key)
    if (facts && factOwner !== owner()) { invalidate(); return false }
    if (facts?.contractVersion !== WORK_ORDER_RECEPTION_CONTRACT_V2 || !['generate', 'release'].includes(key)
      || !action?.enabled || action.apiPath !== workOrderExecutionApiUrl(facts.productionPlanId, key)) return false
    if (!state.reason.trim()) { state.executionMessage = '请填写本次操作原因后，再明确点击业务动作。'; return false }
    const scope = owner(), selectedGeneration = generation, planId = state.selectedPlanId
    const current = () => scope === owner() && selectedGeneration === generation && planId === state.selectedPlanId
    const item = { key, scope, displayName: action.displayName, workOrderId: facts.workOrder.id, expectedVersion: facts.workOrder.version }
    const body = { executionToken: action.executionToken,
      idempotencyKey: globalThis.crypto?.randomUUID?.() || `work-order-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      reason: state.reason.trim(), ...(key === 'release' ? { workOrderId: item.workOrderId, expectedVersion: item.expectedVersion } : {}) }
    writing = true; sequence += 1; pending = item
    state.executionState = 'writing'; state.executionMessage = `正在提交${action.displayName}；完成后将独立读取正式工单。`
    state.lastReadDisplay = facts
    state.facts = null; state.factLoadFacts = null; state.readState = 'write_pending'; state.error = ''
    try {
      let response
      try {
        response = await (key === 'generate'
          ? api.generateProductionPlanWorkOrder(Number(planId), body) : api.releaseProductionPlanWorkOrder(Number(planId), body))
      } catch (error) {
        if (!current()) return false
        if (error?.response?.data?.success === false) response = error.response.data
        else {
          state.executionState = 'readback_pending'
          state.executionMessage = '执行响应未确认，可能已写入；请仅重新读取当前工单，勿重复提交。'
          return false
        }
      }
      if (!current()) return false
      if (response?.success === false) {
        pending = null; state.executionState = 'rejected'; state.readState = 'write_rejected'
        state.executionMessage = response?.error?.message || '服务端未接受本次业务动作，请刷新当前工单与准入后核对。'
        return false
      }
      if (response?.success !== true) {
        state.executionState = 'readback_pending'
        state.executionMessage = '执行响应格式未确认，可能已写入；请仅重新读取当前工单，勿重复提交。'
        return false
      }
      state.executionState = 'reading'
      state.executionMessage = '执行已获服务端成功响应，正在独立读取当前正式工单。'
      return await load()
    } finally { writing = false }
  }
  return { invalidate, load, select, execute }
}

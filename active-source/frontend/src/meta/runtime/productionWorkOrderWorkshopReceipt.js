import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { resolvePceWorkshopReceiptAction } from './pceBusinessActionRegistry.js'
import { latestOwnFormalLocation } from './operationSelectedDetailContract.js'

export const WORK_ORDER_WORKSHOP_RECEIPT_CONTRACT = 'PCE-PRODUCTION-WORK-ORDER-WORKSHOP-RECEIPT-V1'
export const workshopReceptionApiUrl = '/api/planning/work-order-workshop-reception/'
const text = value => typeof value === 'string' && Boolean(value.trim())
const id = value => Number.isSafeInteger(value) && value > 0
const count = value => Number.isSafeInteger(value) && value >= 0
const hash = value => typeof value === 'string' && /^[a-f\d]{64}$/i.test(value)
const same = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item)
const requireFact = (condition, message) => { if (!condition) throw new Error(message) }
const actorValid = (actor, companyId) => actor && id(actor.userId) && actor.companyId === companyId
  && ['username', 'companyName', 'companyCode'].every(key => text(actor[key]))
const actorBaseKeys = Object.freeze(['userId','username','companyId','companyCode','companyName',
  'employeeId','employeeNo','employeeName','positionId','positionCode','positionName','departmentId','workshopId','workshopCode','workshopName'])
const operationValid = row => row && id(row.id) && id(row.sequence) && text(row.operationName)
  && (row.workCenterId === null || id(row.workCenterId)) && (row.workCenterName === null || text(row.workCenterName))
  && typeof row.dependencyOnly === 'boolean' && ['workloadLabel', 'startLabel', 'endLabel'].every(key => text(row[key]))
const historyValid = rows => Array.isArray(rows) && rows.every(row => id(row.id) && id(row.version) && id(row.operatorId)
  && ['sourceStateLabel', 'targetStateLabel', 'actionLabel', 'reason', 'timestampLabel'].every(key => text(row[key])))

export function validateWorkshopReceptionResponse(response, expected) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(response, workshopReceptionApiUrl, '生产工单车间接收')
  const facts = data.workshopReceptionFacts
  const suggested=facts?latestOwnFormalLocation(facts,expected,{group:true}):null
  const expectedPlanId=expected.productionPlanId??suggested?.productionPlanId??null
  requireFact(['loaded', 'empty_valid'].includes(factLoadFacts.factLoadStatus)
    && facts?.contractVersion === WORK_ORDER_WORKSHOP_RECEIPT_CONTRACT && facts.moduleCode === 'production-work-order'
    && facts.factSource === 'server' && facts.currentStateSource === 'server' && id(expected.companyId)
    && facts.companyId === expected.companyId && actorValid(facts.currentActorEvidence, facts.companyId)
    && facts.productionPlanId === expectedPlanId && (!expected.userId||facts.currentActorEvidence.userId===expected.userId) && text(facts.statusLabel)
    && count(facts.visibleOperationCount) && text(facts.scopeVisibilityLabel)
    && Array.isArray(facts.workOrderOptions) && Array.isArray(facts.scopes) && Array.isArray(facts.unassignedOperations)
    && facts.businessWriteCount === 0 && facts.auditWriteCount === 0, '车间接收的后台账号、公司、计划或只读事实合同不一致。')
  requireFact(facts.workOrderOptions.every(row => id(row.workOrderId) && id(row.productionPlanId)
    && ['workOrderNo', 'productionPlanNo', 'quantityLabel', 'statusLabel'].every(key => text(row[key]))
    && Array.isArray(row.workshopIds) && row.workshopIds.every(id))
    && new Set(facts.workOrderOptions.map(row => row.workOrderId)).size === facts.workOrderOptions.length,
  '当前可见已下达工单目录不完整；不能使用计划物控目录代替。')
  const summary = facts.scopeSummary
  requireFact(summary && ['scopeCount', 'assignedOperationCount', 'unassignedOperationCount', 'dependencyOnlyUnassignedCount', 'receivedScopeCount'].every(key => count(summary[key]))
    && text(summary.statusLabel) && summary.scopeCount === facts.scopes.length
    && summary.unassignedOperationCount === facts.unassignedOperations.length
    && facts.unassignedOperations.every(row => operationValid(row) && text(row.statusLabel)), '车间范围或未归属工序事实不完整。')
  if (expectedPlanId === null) {
    requireFact(facts.workOrder === null && facts.productionPlanNo === null && facts.scopes.length === 0 && facts.unassignedOperations.length === 0,
      '尚未明确选择工单，不得默认载入某一工单或车间。')
  } else {
    const order = facts.workOrder
    requireFact(id(expectedPlanId) && text(facts.productionPlanNo) && order?.generated === true && order.released === true
      && id(order.id) && text(order.no) && count(order.version) && hash(order.snapshotHash)
      && ['statusLabel', 'quantityLabel', 'uomCode', 'uomLabel', 'materialCode', 'materialName'].every(key => text(order[key]))
      && id(order.materialId) && id(order.uomId) && order.productionPlanId === facts.productionPlanId && id(order.sourceScheduleId) && count(order.operationCount),
    '所选已下达工单的编号、数量单位、版本或正式工序事实不完整。')
    requireFact(new Set(facts.scopes.map(scope => scope.workshopId)).size === facts.scopes.length, '车间范围身份重复，禁止使用。')
    for (const scope of facts.scopes) {
      const qualification = scope.qualification, receipt = scope.receipt
      requireFact(id(scope.workshopId) && text(scope.workshopCode) && text(scope.workshopName) && hash(scope.scopeSnapshotHash)
        && Array.isArray(scope.operations) && scope.operations.every(operationValid)
        && count(scope.operationCount) && scope.operationCount === scope.operations.length
        && Array.isArray(scope.operationIds) && scope.operationIds.every(id)
        && same(scope.operationIds) === same(scope.operations.map(row => row.id))
        && Array.isArray(scope.workCenterIds) && scope.workCenterIds.every(id), '车间范围与正式工序身份不一致。')
      requireFact(qualification && typeof qualification.ready === 'boolean' && text(qualification.statusLabel)
        && actorValid(qualification.currentActorEvidence, facts.companyId)
        && actorBaseKeys.every(key => qualification.currentActorEvidence[key] === facts.currentActorEvidence[key])
        && Array.isArray(qualification.issues) && qualification.issues.every(issue => ['code', 'categoryCode', 'categoryLabel', 'statusLabel'].every(key => text(issue[key]))
          && text(issue.remediation?.statusLabel) && text(issue.remediation?.pathLabel))
        && Array.isArray(qualification.checks) && qualification.checks.every(check => text(check.checkCode)
          && typeof check.complete === 'boolean' && typeof check.eligible === 'boolean' && text(check.statusLabel)), '本次车间接收资格、身份或处理路径事实不完整。')
      requireFact(receipt && typeof receipt.received === 'boolean' && text(receipt.statusLabel)
        && historyValid(receipt.stateTransitionHistory) && receipt.statusTransitionCount === receipt.stateTransitionHistory.length
        && typeof receipt.stateMachineConsistent === 'boolean'
        && (!receipt.received || id(receipt.id) && count(receipt.version) && id(receipt.receivedById)
          && text(receipt.receivedByLabel) && text(receipt.receivedAtLabel) && text(receipt.receivedAt) && text(receipt.timezoneLabel) && hash(receipt.snapshotHash)),
      '车间接收记录、操作人或审计状态历史不完整。')
      const action = resolvePceWorkshopReceiptAction({ workOrderId: order.id, workshopId: scope.workshopId,
        actionContract: scope.actionContract, availableAction: scope.availableAction })
      requireFact(!action.enabled || qualification.ready && !receipt.received, '车间接收服务端动作可用性与本次结论冲突。')
    }
  }
  for (const surface of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    requireFact(same(data[surface]?.workshopReceptionFacts) === same(facts), '车间接收服务端五表面事实不一致。')
  }
  return { facts, factLoadFacts }
}

export function projectWorkshopReceiptAction(facts, workshopId) {
  const scope = facts?.scopes.find(row => String(row.workshopId) === String(workshopId))
  return scope && facts.workOrder ? resolvePceWorkshopReceiptAction({ workOrderId: facts.workOrder.id, workshopId: scope.workshopId,
    actionContract: scope.actionContract, availableAction: scope.availableAction }) : null
}

export function createWorkshopReceptionState() {
  return { selectedPlanId: '', selectedWorkshopId: '', facts: null, lastReadDisplay: null, factLoadFacts: null,
    readState: 'idle', executionState: 'idle', reason: '', error: '', message: '' }
}

export function createWorkshopReceptionController({ state, api, owner, companyId, userId=()=>null,allowLatestFormalLocation=()=>false,externalLocked = () => false }) {
  let sequence = 0, generation = 0, factOwner = null, pending = null, writing = false, inFlight = null
  function invalidate() { sequence += 1; generation += 1; factOwner = null; pending = null; Object.assign(state, createWorkshopReceptionState()) }
  function load({ force = false } = {}) {
    const key = JSON.stringify([owner(), generation, state.selectedPlanId, pending?.scopeSnapshotHash,allowLatestFormalLocation()])
    if (!force && inFlight?.key === key) return inFlight.promise
    const promise = loadCurrent(), item = { key, promise }; inFlight = item
    promise.then(() => { if (inFlight === item) inFlight = null }, () => { if (inFlight === item) inFlight = null })
    return promise
  }
  async function loadCurrent() {
    // Other sections' write locks block writes and retargeting, never GET-only
    // recovery. A failed sibling read must not strand this section's reader.
    if (state.executionState === 'writing') return false
    if (factOwner && factOwner !== owner() || pending && pending.owner !== owner()) { invalidate(); return false }
    const request = ++sequence, epoch = generation, identity = owner(), planId = state.selectedPlanId,allowLatest=allowLatestFormalLocation()&&!pending
    const current = () => request === sequence && epoch === generation && identity === owner() && planId === state.selectedPlanId
    const previousContext = state.factLoadFacts
    if(state.facts)state.lastReadDisplay=state.facts
    state.facts = null; state.factLoadFacts = null; state.error = ''; state.readState = 'loading';if(!pending)state.message=''
    try {
      const response = await api.getWorkOrderWorkshopReception({...(planId?{productionPlanId:Number(planId)}:{}),...(allowLatest?{locateOwnLatestFormalAction:1}:{})})
      if (!current()) return false
      const validated=validateWorkshopReceptionResponse(response, { companyId: Number(companyId()),userId:Number(userId())||null,allowLatestFormalLocation:allowLatest,productionPlanId: planId ? Number(planId) : null })
      if(!planId&&validated.facts.viewLocationSuggestion)state.selectedPlanId=String(validated.facts.productionPlanId)
      Object.assign(state,validated,{ readState: 'loaded' })
      if(allowLatest)state.message=validated.facts.viewLocationStatusLabel||validated.facts.viewLocationSuggestion?.statusLabel||''
      state.lastReadDisplay = null; factOwner = identity
      if (pending) {
        const scope = state.facts.scopes.find(row => row.workshopId === pending.workshopId)
        if (state.facts.workOrder?.id === pending.workOrderId && scope?.receipt.received
          && scope.scopeSnapshotHash === pending.scopeSnapshotHash) {
          state.executionState = 'verified'; state.message = '本车间范围的当前接收记录已独立回读核实；未自动接收其他车间，也未开工或报工。'; pending = null
        } else {
          state.executionState = 'readback_pending'; state.message = '已读取当前范围，但此前整组接收结果尚未核实；单次未查到不代表确定失败，请仅重新读取，不重复提交。'
        }
      }
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.readState = 'read_failed'; state.factLoadFacts = factLoadFailureFromError(error, workshopReceptionApiUrl, previousContext)
      state.error = `车间接收读取失败，当前范围、资格及接收结果未知。${error?.response?.data?.error?.message || error?.message || ''}`
      if (pending) { state.executionState = 'readback_pending'; state.message = '接收提交后的独立回读未通过；可能已保存，请仅重新读取，不要重复提交。' }
      return false
    }
  }
  async function selectPlan(planId) {
    // Identity changes revoke the old context immediately, including an old ACK.
    // Within the same identity, an unknown result cannot be retargeted.
    const previousOwnerCurrent = (!factOwner || factOwner === owner()) && (!pending || pending.owner === owner())
    if ((state.executionState === 'writing' || pending) && previousOwnerCurrent || externalLocked()) return false
    invalidate(); state.selectedPlanId = String(planId || ''); return load()
  }
  function selectWorkshop(workshopId) {
    if (writing || pending || externalLocked()) return false
    state.selectedWorkshopId = String(workshopId || ''); state.reason = ''; state.message = ''; return true
  }
  async function receive() {
    if (writing || state.readState === 'loading' || externalLocked()) return false
    if (pending) return load()
    if (factOwner !== owner()) { invalidate(); return false }
    const facts = state.facts, action = projectWorkshopReceiptAction(facts, state.selectedWorkshopId)
    if (!action?.enabled) return false
    if (!state.reason.trim()) { state.message = '请填写本次接收原因后，再明确接收所选车间的工序。'; return false }
    const scope = facts.scopes.find(row => String(row.workshopId) === state.selectedWorkshopId)
    const epoch = generation, identity = owner(), planId = state.selectedPlanId
    const current = () => epoch === generation && identity === owner() && planId === state.selectedPlanId
    pending = { owner: identity, workOrderId: facts.workOrder.id, workshopId: scope.workshopId, scopeSnapshotHash: scope.scopeSnapshotHash }
    const payload = { expectedWorkOrderVersion: facts.workOrder.version, expectedWorkOrderSnapshotHash: facts.workOrder.snapshotHash,
      expectedScopeSnapshotHash: scope.scopeSnapshotHash, executionToken: action.executionToken,
      idempotencyKey: globalThis.crypto?.randomUUID?.() || `workshop-receipt-${Date.now()}-${Math.random().toString(36).slice(2)}`, reason: state.reason.trim() }
    writing = true; sequence += 1; state.lastReadDisplay = facts; state.facts = null; state.factLoadFacts = null
    state.readState = 'write_pending'; state.executionState = 'writing'; state.error = ''; state.message = '正在提交所选车间接收意图，完成后独立读取实际记录。'
    try {
      let response
      try { response = await api.receiveWorkOrderWorkshop(pending.workOrderId, pending.workshopId, payload) } catch (error) {
        if (!current()) return false
        if (error?.response?.data?.success === false) response = error.response.data
        else { state.executionState = 'readback_pending'; state.message = '接收响应未确认，可能已保存；请仅重新读取当前范围，勿重复提交。'; return false }
      }
      if (!current()) return false
      if (response?.success === false) {
        pending = null; state.executionState = 'rejected'; state.readState = 'write_rejected'; state.message = response.error?.message || '服务端未接受本次接收；请重新读取当前范围与资格。'; return false
      }
      if (response?.success !== true) { state.executionState = 'readback_pending'; state.message = '接收响应格式未确认，可能已保存；请仅重新读取，勿重复提交。'; return false }
      state.executionState = 'reading'; state.message = '接收已获成功响应，正在独立读取当前范围记录。'; return await load()
    } finally { writing = false }
  }
  return { invalidate, load, selectPlan, selectWorkshop, receive }
}

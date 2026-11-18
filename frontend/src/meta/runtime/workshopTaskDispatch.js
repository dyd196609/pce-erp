import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { resolvePceWorkshopTaskActions } from './pceBusinessActionRegistry.js'
import { WORKSHOP_TASK_PAGE } from './workshopTaskDispatchContract.js'
import { readOperationExecutionMode } from './operationExecutionMode.js'

const same = value => JSON.stringify(value)
const id = value => Number.isSafeInteger(value) && value > 0
const text = value => typeof value === 'string' && value.trim().length > 0
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
function requireFact(value, message) { if (!value) throw new Error(message) }

export function validateWorkshopTaskResponse(response, expected = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(response, expected.apiUrl || WORKSHOP_TASK_PAGE.apiUrl, '车间任务／派工')
  requireFact(factLoadFacts.factLoadStatus !== 'read_failed', factLoadFacts.errorMessage)
  const facts = data.workshopTaskFacts
  requireFact(facts && facts.contractVersion === WORKSHOP_TASK_PAGE.factContractVersion
    && facts.moduleCode === WORKSHOP_TASK_PAGE.moduleId, '任务事实合同或业务对象身份不一致。')
  requireFact(facts.factSource === 'server' && facts.currentStateSource === 'server', '任务事实来源不完整。')
  requireFact(Array.isArray(facts.operationOptions) && Array.isArray(facts.candidatePositions)
    && Array.isArray(facts.candidateEmployees) && Array.isArray(facts.tasks), '任务目录或人员候选事实不完整。')
  requireFact(Number.isSafeInteger(data.resultCount) && data.resultCount >= 0
    && data.resultCount === facts.tasks.length, '任务服务端数量与正式列表不一致。')
  const actor = facts.currentActorEvidence
  requireFact(actor && id(actor.userId) && id(actor.companyId) && text(actor.username), '本次后台身份未核实。')
  if (expected.companyId) requireFact(actor.companyId === expected.companyId, '本次公司与后台任务事实不一致。')
  for (const row of facts.operationOptions) {
    const mode = readOperationExecutionMode(row)
    const blockedSource = row.sourceConsistent === false && Array.isArray(row.resourceSource?.blockingReasons)
      && row.resourceSource.blockingReasons.length > 0 && row.resourceSource.blockingReasons.every(text)
    requireFact(id(row.id) && id(row.workOrderId) && text(row.workOrderNo) && text(row.operationName)
      && text(row.workloadLabel) && (hash(row.sourceSnapshotHash) || !mode.quantified && blockedSource), '已接收工序来源事实不完整。')
    if ((!row.workCenterId || !row.workshopId || !row.receiptId) && !mode.quantified) {
      requireFact(blockedSource, '未取得资源或接收证明的工序必须保留具体阻断，不能使用目录默认资源冒充。')
      if (facts.selectedOperation?.id === row.id) requireFact(facts.availableActions?.saveDraft?.enabled === false
        && facts.availableActions?.dispatch?.enabled === false && facts.candidateEmployees.length === 0,
      '受阻无量工序不得保存任务、派工或扩展为全公司人员候选。')
    }
    if ((mode.pending || mode.exempt) && facts.selectedOperation?.id === row.id)
      requireFact(facts.availableActions?.saveDraft?.enabled === false && facts.availableActions?.dispatch?.enabled === false,
        '执行模式待核实或正式免执行时不得保存执行任务或派工；现有正式范围候选不代表已获准执行。')
  }
  if (expected.operationId) requireFact(facts.selectedOperation?.id === expected.operationId, '所选正式工序身份不一致。')
  if (expected.workOrderId) requireFact(facts.operationOptions.every(row => row.workOrderId === expected.workOrderId), '工单范围不一致。')
  requireFact(facts.candidatePositions.every(row => id(row.id) && text(row.name)), '执行岗位候选事实不完整。')
  requireFact(facts.candidateEmployees.every(row => id(row.employeeId || row.id) && id(row.positionId)
    && text(row.employeeName) && id(row.userId) && text(row.username)), '执行人员任职或账号候选事实不完整。')
  for (const task of facts.tasks) {
    readOperationExecutionMode(task)
    requireFact(id(task.id) && text(task.no) && text(task.statusLabel) && Number.isInteger(task.version)
      && Array.isArray(task.statusTransitionHistory) && task.statusTransitionHistory.length > 0
      && task.statusTransitionCount === task.statusTransitionHistory.length
      && task.stateMachineConsistent === true, '任务状态、版本或审计历史不完整。')
  }
  if (facts.selectedTask) requireFact(facts.tasks.some(task => task.id === facts.selectedTask.id), '所选任务不属于本次正式列表。')
  resolvePceWorkshopTaskActions(facts)
  for (const surface of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    requireFact(same(data[surface]?.workshopTaskFacts) === same(facts), '任务服务端五表面事实不一致。')
    requireFact(data[surface]?.resultCount === data.resultCount, '任务服务端五表面数量不一致。')
  }
  return { facts, factLoadFacts, serverSurface: data.strictFacts }
}

export function createWorkshopTaskState() {
  return { workOrderId: '', operationId: '', positionId: '', employeeId: '', reason: '', facts: null,
    lastDisplayFacts: null, factLoadFacts: null, serverSurface: null, readState: 'idle', writeState: 'idle',
    formDirty: false, error: '', message: '' }
}

export function createWorkshopTaskController({ state, api, owner, companyId }) {
  let sequence = 0, generation = 0, factOwner = null, writing = false, pending = null
  function invalidate() {
    sequence += 1; generation += 1; factOwner = null; pending = null
    Object.assign(state, createWorkshopTaskState())
  }
  function syncForm() {
    const task = state.facts?.selectedTask
    state.positionId = task?.positionId ? String(task.positionId) : ''
    state.employeeId = task?.employeeId ? String(task.employeeId) : ''
    state.formDirty = false
  }
  async function load() {
    if (writing) return false
    if (factOwner && factOwner !== owner() || pending && pending.owner !== owner()) { invalidate(); return false }
    const request = ++sequence, epoch = generation, identity = owner()
    const workOrderId = state.workOrderId, operationId = state.operationId
    const current = () => {
      if (identity !== owner() && epoch === generation) invalidate()
      return request === sequence && epoch === generation && identity === owner()
        && workOrderId === state.workOrderId && operationId === state.operationId
    }
    const previous = state.factLoadFacts
    if (state.facts) state.lastDisplayFacts = state.facts
    state.facts = null; state.factLoadFacts = null; state.serverSurface = null; state.error = ''; state.readState = 'loading'
    try {
      const params = { ...(workOrderId ? { workOrderId: Number(workOrderId) } : {}), ...(operationId ? { operationId: Number(operationId) } : {}) }
      const response = await api.read(params)
      if (!current()) return false
      Object.assign(state, validateWorkshopTaskResponse(response, { companyId: Number(companyId()),
        workOrderId: workOrderId ? Number(workOrderId) : null, operationId: operationId ? Number(operationId) : null }), { readState: 'loaded' })
      state.lastDisplayFacts = null; factOwner = identity
      if (pending) {
        const task = state.facts.selectedTask
        const event = task?.statusTransitionHistory.at(-1)
        if (task && (!pending.taskId || task.id === pending.taskId)
          && task.operationId === pending.operationId && task.sourceSnapshotHash === pending.sourceSnapshotHash
          && task.version === pending.nextVersion && event?.operatorId === pending.actorId
          && event?.actionCode === pending.actionCode && event?.reason === pending.reason
          && (pending.kind === 'saveDraft' ? (task.positionId ?? null) === pending.positionId && (task.employeeId ?? null) === pending.employeeId
            : task.statusCode === 'dispatched')) {
          pending = null; syncForm(); state.writeState = 'verified'; state.message = '保存结果已独立只读回读核实；未执行开工或报工。'
        } else { state.writeState = 'readback_pending'; state.message = '本次提交结果尚未核实，请仅重新读取，不要重复提交。' }
      }
      if (!state.formDirty && !pending) syncForm()
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.serverSurface = null; state.readState = 'read_failed'
      state.factLoadFacts = factLoadFailureFromError(error, WORKSHOP_TASK_PAGE.apiUrl, previous)
      state.error = `任务事实读取失败，当前资格及结果未知。${error?.message || ''}`
      if (pending) state.writeState = 'readback_pending'
      return false
    }
  }
  async function select(workOrderId, operationId = '') {
    if (writing || pending) return false
    const reason = state.reason
    invalidate(); state.workOrderId = String(workOrderId || ''); state.operationId = String(operationId || ''); state.reason = reason
    return load()
  }
  function choosePosition(value) { state.positionId = String(value || ''); state.employeeId = ''; state.formDirty = true }
  function chooseEmployee(value) { state.employeeId = String(value || ''); state.formDirty = true }
  async function execute(kind) {
    if (writing || pending || state.readState !== 'loaded' || factOwner !== owner()) return false
    const facts = state.facts, action = resolvePceWorkshopTaskActions(facts)[kind], operation = facts.selectedOperation, task = facts.selectedTask
    if (!action?.enabled || !operation || !state.reason.trim() || kind === 'dispatch' && state.formDirty) return false
    const identity = owner(), epoch = generation
    const current = () => {
      if (identity !== owner() && epoch === generation) invalidate()
      return identity === owner() && epoch === generation
    }
    const common = { expectedVersion: task?.version ?? null, expectedSourceSnapshotHash: operation.sourceSnapshotHash,
      reason: state.reason.trim(), idempotencyKey: globalThis.crypto?.randomUUID?.() || `workshop-task-${Date.now()}-${Math.random().toString(36).slice(2)}` }
    const payload = kind === 'saveDraft' ? { ...common, operationId: operation.id, taskId: task?.id ?? null,
      positionId: state.positionId ? Number(state.positionId) : null, employeeId: state.employeeId ? Number(state.employeeId) : null } : common
    pending = { owner: identity, kind, taskId: task?.id ?? null,
      operationId: operation.id, sourceSnapshotHash: operation.sourceSnapshotHash,
      nextVersion: task ? task.version + 1 : 0, actorId: facts.currentActorEvidence.userId,
      actionCode: action.actionCode, reason: common.reason,
      positionId: payload.positionId ?? null, employeeId: payload.employeeId ?? null }
    writing = true; sequence += 1; state.writeState = 'writing'; state.error = ''; state.message = '正在提交本次明确意图，随后独立读取保存结果。'
    state.lastDisplayFacts = facts; state.facts = null; state.serverSurface = null
    try {
      const response = kind === 'saveDraft' ? await api.saveDraft(payload) : await api.dispatch(task.id, payload)
      if (!current()) return false
      if (response?.success === false) {
        const failed = response.factLoadFacts || response.data?.factLoadFacts || response
        const status = Number(failed.httpStatus || response.meta?.status || 0)
        const code = response.error?.code || failed.errorCode || ''
        if (status >= 400 && status < 500 && ![408, 429].includes(status) && code !== 'AUTHENTICATION_CONTEXT_CHANGED') {
          pending = null; state.writeState = 'rejected'; state.readState = 'write_rejected'
          state.message = response.error?.message || '服务端拒绝本次意图，请重新读取后核对；未自动重试。'
          return false
        }
        throw new Error(response.error?.message || '提交响应不明确，保存结果未知。')
      }
      const acknowledged = validateWorkshopTaskResponse(response, { apiUrl: action.apiPath, companyId: Number(companyId()), operationId: operation.id }).facts.selectedTask
      if (acknowledged) pending.taskId = acknowledged.id
      state.writeState = 'readback_pending'
    } catch (error) {
      if (!current()) return false
      state.message = `提交结果未核实，可能已保存；请仅重新读取，不自动重试。${error?.message || ''}`
      state.writeState = 'readback_pending'
    } finally { writing = false }
    if (current()) return load()
    return false
  }
  return { invalidate, load, select, choosePosition, chooseEmployee, execute }
}

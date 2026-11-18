import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { OPERATION_START_PAGE } from './operationStartContract.js'
import { resolvePceOperationStartAction } from './pceBusinessActionRegistry.js'
import { readOperationExecutionMode } from './operationExecutionMode.js'

const same = value => JSON.stringify(value)
const positiveId = value => Number.isSafeInteger(value) && value > 0
const nonempty = value => typeof value === 'string' && !!value.trim()
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
function requireFact(value, message) { if (!value) throw new Error(message) }

export function validateOperationStartResponse(response, expected = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(response, expected.apiUrl || OPERATION_START_PAGE.apiUrl, '工序开工')
  requireFact(factLoadFacts.factLoadStatus !== 'read_failed', factLoadFacts.errorMessage)
  const facts = data.operationStartFacts
  requireFact(facts?.contractVersion === OPERATION_START_PAGE.factContractVersion
    && facts.moduleCode === OPERATION_START_PAGE.moduleId && facts.factSource === 'server'
    && facts.currentStateSource === 'server', '开工事实合同、业务对象或权威来源不一致。')
  requireFact(Array.isArray(facts.tasks) && Number.isSafeInteger(data.resultCount)
    && data.resultCount >= 0 && data.resultCount === facts.tasks.length, '开工任务服务端数量与列表不一致。')
  requireFact(Number.isSafeInteger(facts.operationStartRecordCount) && facts.operationStartRecordCount >= 0,
    '实际开工记录数量未由服务端核实。')
  const actor = facts.currentActorEvidence
  requireFact(actor && positiveId(actor.userId) && positiveId(actor.companyId) && nonempty(actor.username), '本次后台身份未核实。')
  if (expected.companyId) requireFact(actor.companyId === expected.companyId, '当前公司与开工事实不一致。')
  if (expected.userId) requireFact(actor.userId === expected.userId, '当前账号与开工事实不一致。')
  for (const row of facts.tasks) {
    const mode = readOperationExecutionMode(row)
    requireFact(positiveId(row.taskId) && row.id === row.taskId && nonempty(row.no)
      && nonempty(row.workOrderNo) && nonempty(row.operationName) && nonempty(row.workloadLabel)
      && nonempty(row.executionStatusLabel) && Number.isSafeInteger(row.version)
      && hash(row.sourceSnapshotHash) && hash(row.assignmentHash), '获派任务来源、版本或正式作业量不完整。')
    requireFact(positiveId(actor.employeeId) && row.employeeId === actor.employeeId
      && row.employeeUsername === actor.username, '列表出现非本人获派任务，已停止加载。')
    requireFact(Array.isArray(row.statusTransitionHistory) && row.statusTransitionCount === row.statusTransitionHistory.length
      && typeof row.stateMachineConsistent === 'boolean', '开工状态及审计历史不完整。')
    if (row.executionRecord) {
      const record = row.executionRecord
      requireFact(record.taskId === row.taskId && record.statusCode === 'started'
        && positiveId(record.id) && positiveId(record.startedById) && nonempty(record.startedAtLabel)
        && nonempty(record.auditReference) && row.statusTransitionCount > 0, '正式开工记录或审计不完整。')
    } else requireFact(row.executionStatusCode === 'waiting' && row.statusTransitionCount === 0, '无开工记录时执行状态不一致。')
    const predecessors = row.predecessorFacts
    if (predecessors?.items) for (const item of predecessors.items) {
      if (item.proofType === 'FORMAL_EXEMPTION' || item.formalExemptionFact) requireFact(item.completed === false
        && item.actualExecution === false && item.prerequisiteSatisfied === true
        && item.formalExemptionFact?.actualExecution === false && item.formalCompletionFact === null,
      '正式免执行前序不能显示成已实际完工。')
    }
    if ((mode.pending || mode.exempt) && facts.selectedTask?.taskId === row.taskId) requireFact(facts.availableActions?.start?.enabled === false,
      '正式执行模式待核实时不能开工。')
  }
  if (facts.selectedTask) requireFact(facts.tasks.some(row => same(row) === same(facts.selectedTask)), '所选任务不属于本次本人任务列表。')
  if (expected.taskId) requireFact(facts.selectedTask?.taskId === expected.taskId, '所选任务身份与服务端事实不一致。')
  resolvePceOperationStartAction(facts)
  for (const surface of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    requireFact(same(data[surface]?.operationStartFacts) === same(facts)
      && data[surface]?.resultCount === data.resultCount, '开工服务端五表面事实或数量不一致。')
  }
  return { facts, factLoadFacts, serverSurface: data.strictFacts }
}

export function createOperationStartState() {
  return { taskId: '', reason: '', facts: null, lastDisplayFacts: null, factLoadFacts: null, serverSurface: null,
    readState: 'idle', writeState: 'idle', message: '', error: '' }
}
export function createOperationStartController({ state, api, owner, companyId, userId }) {
  let sequence = 0, generation = 0, factOwner = null, writing = false, pending = null
  function invalidate() {
    sequence += 1; generation += 1; factOwner = null; pending = null
    Object.assign(state, createOperationStartState())
  }
  async function load() {
    if (writing) return false
    if (factOwner && factOwner !== owner() || pending && pending.owner !== owner()) { invalidate(); return false }
    const request = ++sequence, epoch = generation, identity = owner(), taskId = state.taskId
    const current = () => {
      if (identity !== owner() && epoch === generation) invalidate()
      return request === sequence && epoch === generation && identity === owner() && taskId === state.taskId
    }
    const previous = state.factLoadFacts
    if (state.facts) state.lastDisplayFacts = state.facts
    state.facts = null; state.factLoadFacts = null; state.serverSurface = null; state.error = ''; state.readState = 'loading'
    try {
      const response = await api.read(taskId ? { taskId: Number(taskId) } : {})
      if (!current()) return false
      Object.assign(state, validateOperationStartResponse(response, { companyId: Number(companyId()),
        userId: Number(userId?.()), taskId: taskId ? Number(taskId) : null }), { readState: 'loaded' })
      factOwner = identity; state.lastDisplayFacts = null
      if (pending) {
        const task = state.facts.selectedTask, record = task?.executionRecord, event = record?.statusTransitionHistory?.at(-1)
        if (record && task.taskId === pending.taskId && task.version === pending.version
          && record.taskVersion === pending.version && record.sourceSnapshotHash === pending.sourceSnapshotHash
          && record.assignmentHash === pending.assignmentHash && record.startedById === pending.actorId
          && record.reason === pending.reason && (!pending.recordId || record.id === pending.recordId)
          && record.stateMachineConsistent && event?.operatorId === pending.actorId
          && event?.actionCode === 'production.operation.start' && event?.reason === pending.reason
          && event?.auditReference === record.auditReference) {
          pending = null; state.writeState = 'verified'
          state.message = '开工结果已独立只读回查核实；请核对本人、实际开工时间和审计。本页不执行报工。'
        } else {
          state.writeState = 'readback_pending'
          state.message = '本次开工结果仍未核实，请仅重新读取，不要重复点击开工。'
        }
      }
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.serverSurface = null; state.readState = 'read_failed'
      state.factLoadFacts = factLoadFailureFromError(error, OPERATION_START_PAGE.apiUrl, previous)
      state.error = `开工事实读取失败，当前任务数量、资格及提交结果未知。${error?.message || ''}`
      if (pending) state.writeState = 'readback_pending'
      return false
    }
  }
  async function select(taskId = '') {
    if (writing || pending) return false
    invalidate(); state.taskId = String(taskId || '')
    return load()
  }
  async function execute() {
    if (writing || pending || state.readState !== 'loaded' || factOwner !== owner()) return false
    const facts = state.facts, task = facts?.selectedTask
    if (!task || !resolvePceOperationStartAction(facts).enabled || !state.reason.trim()) return false
    const identity = owner(), epoch = generation
    const current = () => {
      if (identity !== owner() && epoch === generation) invalidate()
      return epoch === generation && identity === owner()
    }
    const payload = { expectedVersion: task.version, expectedSourceSnapshotHash: task.sourceSnapshotHash,
      expectedAssignmentHash: task.assignmentHash, reason: state.reason.trim(),
      idempotencyKey: globalThis.crypto?.randomUUID?.() || `operation-start-${Date.now()}-${Math.random().toString(36).slice(2)}` }
    pending = { owner: identity, taskId: task.taskId, version: task.version,
      sourceSnapshotHash: task.sourceSnapshotHash, assignmentHash: task.assignmentHash,
      actorId: facts.currentActorEvidence.userId, reason: payload.reason, recordId: null }
    writing = true; sequence += 1; state.writeState = 'writing'; state.error = ''; state.lastDisplayFacts = facts
    state.facts = null; state.serverSurface = null; state.message = '正在提交本人明确开工意图，随后只读回查；请勿重复点击。'
    try {
      const response = await api.start(task.taskId, payload)
      if (!current()) return false
      if (response?.success === false) {
        const failed = response.factLoadFacts || response.data?.factLoadFacts || response
        const status = Number(failed.httpStatus || response.meta?.status || 0), code = response.error?.code || failed.errorCode || ''
        if (status >= 400 && status < 500 && ![408, 429].includes(status) && code !== 'AUTHENTICATION_CONTEXT_CHANGED') {
          pending = null; state.writeState = 'rejected'; state.readState = 'write_rejected'
          state.message = response.error?.message || '服务端拒绝本次开工意图，请重新读取后核对；未自动重试。'
          return false
        }
        throw new Error(response.error?.message || '开工响应不明确。')
      }
      const acknowledged = validateOperationStartResponse(response, { apiUrl: `${OPERATION_START_PAGE.apiUrl}${task.taskId}/start/`,
        companyId: Number(companyId()), userId: Number(userId?.()), taskId: task.taskId }).facts.selectedTask?.executionRecord
      if (acknowledged) pending.recordId = acknowledged.id
      state.writeState = 'readback_pending'
    } catch (error) {
      if (!current()) return false
      state.writeState = 'readback_pending'
      state.message = `开工结果尚未核实，可能已保存；请仅重新读取，不自动重试。${error?.message || ''}`
    } finally { writing = false }
    return current() ? load() : false
  }
  return { invalidate, load, select, execute }
}

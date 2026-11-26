import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { OPERATION_COMPLETION_PAGE } from './operationCompletionContract.js'
import { resolvePceOperationCompletionAction } from './pceBusinessActionRegistry.js'
import { readOperationExecutionMode, validateExecutionConfirmation } from './operationExecutionMode.js'
import { isCompletionV3, validateCompletionV3Context, createCompletionV3Controller } from './operationCompletionV3.js'
import { createOperationIntentRecovery } from './operationIntentRecovery.js'

const same = value => JSON.stringify(value)
const positive = value => Number.isSafeInteger(value) && value > 0
const text = value => typeof value === 'string' && !!value.trim()
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const decimal = value => typeof value === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)
function requireFact(value, message) { if (!value) throw new Error(message) }

function validateRecordProgress(task, companyId, availableActions) {
  const progress = task.recordProgress, overall = task.overallCompletion, completion = task.completionFact
  requireFact(progress?.contractVersion === 'PCE-OPERATION-COMPLETION-PROGRESS-V1'
    && typeof progress.submitted === 'boolean' && typeof progress.reviewed === 'boolean'
    && text(progress.submissionLabel) && text(progress.reviewLabel) && text(progress.noticeLabel)
    && text(progress.reviewResponsibilityLabel) && Array.isArray(progress.admissionIssues)
    && progress.admissionIssues.every(issue => text(typeof issue === 'string' ? issue : issue?.statusLabel)),
  '本次申请的正式提交、审核进度或真实准入提示未完整读取。')
  requireFact(overall?.source === 'verified_completion_projection'
    && typeof overall.completionProven === 'boolean' && overall.completionProven === task.completionProven
    && overall.statusCode === task.completionStatusCode && overall.statusLabel === task.completionStatusLabel,
  '工序整体正式完工状态与服务端权威投影不一致。')
  requireFact(progress.requestButtonLabel === (progress.submitted ? '已提交' : '提交完工申请')
    && progress.approveButtonLabel === (progress.reviewed ? '已审核' : '审核完工数据'),
  '本次申请按钮名称与正式提交或审核进度不一致。')
  requireFact((!progress.submitted || availableActions?.request?.enabled === false)
    && (!progress.reviewed || availableActions?.approve?.enabled === false),
  '正式动作已完成时服务端仍允许重复操作，已停止加载。')
  if (!completion) {
    requireFact(progress.recordId === null && progress.recordKey === null && progress.recordIdentity === null
      && progress.submitted === false && progress.reviewed === false,
    '尚无正式申请时不能显示其他记录的已提交或已审核进度。')
    return
  }
  const first = completion.statusTransitionHistory[0], identity = progress.recordIdentity
  requireFact(positive(first?.id) && positive(progress.recordId) && progress.recordId === first.id
    && progress.recordKey === `ProductionOperationCompletion:${companyId}:${task.taskId}:${first.id}`
    && identity?.companyId === companyId && identity.taskId === task.taskId
    && identity.requestTransitionId === first.id && identity.workflowInstanceId === completion.workflowInstanceId
    && identity.requestAuditReference === completion.requestAuditReference && progress.submitted === true
    && progress.reviewed === (positive(completion.approvalDecisionId) && text(completion.approvalAuditReference)),
  '提交及审核进度未准确归属当前正式申请记录。')
}

export function validateOperationCompletionResponse(response, expected = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(response, expected.apiUrl || OPERATION_COMPLETION_PAGE.apiUrl, '工序完工')
  requireFact(factLoadFacts.factLoadStatus !== 'read_failed', factLoadFacts.errorMessage)
  const facts = data.operationCompletionFacts, actor = facts?.currentActorEvidence
  requireFact(facts?.contractVersion === OPERATION_COMPLETION_PAGE.factContractVersion
    && facts.moduleCode === OPERATION_COMPLETION_PAGE.moduleId && facts.factSource === 'server'
    && facts.currentStateSource === 'server', '工序完工事实合同、对象或权威来源不一致。')
  requireFact(actor && positive(actor.userId) && positive(actor.companyId) && text(actor.username), '本次后台账号与公司未核实。')
  if (expected.companyId) requireFact(actor.companyId === expected.companyId, '当前公司与完工事实不一致。')
  if (expected.userId) requireFact(actor.userId === expected.userId, '当前账号与完工事实不一致。')
  requireFact(Array.isArray(facts.tasks) && Number.isSafeInteger(data.resultCount)
    && data.resultCount === facts.tasks.length, '工序完工任务服务端数量与列表不一致。')
  for (const task of facts.tasks) {
    const mode = readOperationExecutionMode(task)
    requireFact(positive(task.taskId) && task.id === task.taskId && text(task.no) && text(task.workOrderNo)
      && text(task.operationName) && text(task.workshopName) && text(task.workCenterName)
      && Number.isSafeInteger(task.version) && hash(task.sourceSnapshotHash) && hash(task.assignmentHash), '完工任务正式来源或身份未核实。')
    requireFact(typeof task.formalFactsComplete === 'boolean', '服务端未明确核实完工所需正式事实是否齐备。')
    if (task.formalFactsComplete) {
      requireFact((mode.quantified || mode.nonquantified) && positive(task.startId) && hash(task.startSnapshotHash) && hash(task.reportSetHash),
        '完工任务的正式开工及执行事实集合尚未核实。')
      if (mode.quantified) requireFact(decimal(task.workloadQuantity) && decimal(task.reportedQuantity) && decimal(task.remainingQuantity)
        && text(task.workloadUomLabel) && Number.isSafeInteger(task.quantityPrecision)
        && task.quantityPrecision >= 0, '完工任务正式开工、报工集合、数量或单位精度未核实。')
      else {
        requireFact(['workloadQuantity', 'reportedQuantity', 'remainingQuantity', 'quantityPrecision', 'workloadUomLabel']
          .every(key => task[key] === null), '无统计量完工不得虚构数量、单位或精度。')
        requireFact(!!validateExecutionConfirmation(task), '无统计量完工须先核实本次正式实际经过登记，非空报工集不能替代。')
      }
    } else {
      const available = facts.selectedTask?.taskId === task.taskId ? facts.availableActions : task.availableActions
      requireFact(available?.request?.enabled === false && available?.approve?.enabled === false,
        '正式事实不齐备时必须明确禁止申请和审核。')
    }
    requireFact(Number.isSafeInteger(task.completionProjectionVersion)
      && task.completionProjectionVersion >= 0 && ['unrequested', 'pending_review', 'completed'].includes(task.completionStatusCode)
      && text(task.completionStatusLabel), '完工数量、单位精度或正式状态未核实。')
    const completion = task.completionFact
    if (task.completionStatusCode === 'unrequested') requireFact(completion === null, '尚未申请状态与完工事实不一致。')
    else {
      requireFact(completion && positive(completion.workflowInstanceId) && positive(completion.approvalTaskId)
        && text(completion.applicantLabel) && text(completion.requestedAtLabel) && text(completion.requestReason)
        && text(completion.requestAuditReference) && completion.stateMachineConsistent === true
        && Array.isArray(completion.statusTransitionHistory) && completion.statusTransitionCount > 0
        && completion.statusTransitionCount === completion.statusTransitionHistory.length,
      '完工申请、共享审批或状态审计不完整。')
      if (task.completionStatusCode === 'completed') requireFact(positive(completion.approvalDecisionId)
        && text(completion.reviewerLabel) && text(completion.completedAtLabel) && text(completion.reviewReason)
        && text(completion.approvalAuditReference), '完工生效缺少正式审核决定、责任人或审计。')
    }
    if (isCompletionV3(task)) validateCompletionV3Context(task, actor.companyId)
    else validateRecordProgress(task, actor.companyId,
      facts.selectedTask?.taskId === task.taskId ? facts.availableActions : task.availableActions)
  }
  if (facts.selectedTask) requireFact(facts.tasks.some(task => same(task) === same(facts.selectedTask)), '所选任务不属于本次正式职责范围。')
  if (isCompletionV3(facts.selectedTask)) requireFact(same(facts.availableActions)===same(facts.selectedTask.completionV3.availableActions), 'V3页面动作与所选正式代次不一致。')
  if (expected.taskId) requireFact(facts.selectedTask?.taskId === expected.taskId, '所选任务与服务端返回身份不一致。')
  for (const key of ['request', 'approve']) resolvePceOperationCompletionAction(facts, key)
  if (isCompletionV3(facts.selectedTask)) resolvePceOperationCompletionAction(facts, 'withdrawReplace')
  for (const surface of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    requireFact(same(data[surface]?.operationCompletionFacts) === same(facts)
      && data[surface]?.resultCount === data.resultCount, '工序完工五表面事实或数量不一致。')
  }
  return { facts, factLoadFacts, serverSurface: data.strictFacts }
}

export function createOperationCompletionState() {
  return { taskId: '', reason: '', facts: null, lastDisplayFacts: null, factLoadFacts: null, serverSurface: null,
    readState: 'idle', writeState: 'idle', message: '', error: '', withdrawReason: '', pendingIntent: null,
    recoveryError: '', selectionSummary: null, verifiedRecovery: null }
}
// This presentation never consumes the retained display snapshot as current
// authority. Record progress and whole-operation state remain distinct server
// facts; local clicking, disabled buttons and the viewer's role prove neither.
export function presentOperationCompletionProgress(state, context = {}) {
  const current = state.readState === 'loaded' && !!state.facts && context.factOwnerCurrent !== false
    && !context.writing && !context.pending && !['writing', 'readback_pending'].includes(state.writeState)
  if (!current) return { current: false, selected: false, recordId: null, recordKey: null,
    submitted: null, reviewed: null, requestButtonLabel: '结果待核实', approveButtonLabel: '结果待核实',
    submissionLabel: '结果待核实', reviewLabel: '结果待核实', admissionIssues: [],
    noticeLabel: '结果待核实，请仅重新读取完工事实，不重复提交或审核。',
    overallCompletion: { statusLabel: '结果待核实' } }
  const task = state.facts.selectedTask
  if (!task) return { current: true, selected: false, recordId: null, recordKey: null,
    submitted: false, reviewed: false, requestButtonLabel: '提交完工申请', approveButtonLabel: '审核完工数据',
    submissionLabel: '请选择正式任务', reviewLabel: '请选择正式任务', admissionIssues: [],
    noticeLabel: '请选择正式任务后查看其对应申请记录。', overallCompletion: { statusLabel: '请选择正式任务' } }
  return { ...task.recordProgress, current: true, selected: true, overallCompletion: task.overallCompletion }
}
export function assessOperationCompletionSubmission(state, key, context = {}) {
  let action = null
  try { if (state.facts) action = resolvePceOperationCompletionAction(state.facts, key) } catch { /* reject below */ }
  const reason = typeof state.reason === 'string' ? state.reason.trim() : ''
  const checks = { actionKnown: ['request', 'approve'].includes(key), notReading: state.readState !== 'loading',
    notWriting: !context.writing && state.writeState !== 'writing',
    noPendingReadback: !context.pending && state.writeState !== 'readback_pending',
    factsCurrent: !!state.facts && state.readState === 'loaded', taskSelected: !!state.facts?.selectedTask,
    factOwnerCurrent: context.factOwnerCurrent !== false, secureSubmissionAvailable: context.secureSubmissionAvailable !== false,
    actionNotCompleted: key === 'request' ? state.facts?.selectedTask?.recordProgress?.submitted !== true
      : state.facts?.selectedTask?.recordProgress?.reviewed !== true,
    serverActionAllowed: action?.enabled === true, reasonLengthValid: reason.length >= 2 && reason.length <= 240 }
  const blockers = [
    ['actionKnown', '操作未注册，不能提交。'], ['notReading', '正在读取工序完工事实，请等待读取完成。'],
    ['notWriting', '正在提交本次操作，请勿重复点击。'],
    ['noPendingReadback', '本次操作结果待核实，请仅点击“重新读取完工事实”，不要重复提交。'],
    ['factsCurrent', '当前完工事实尚未核实，请重新读取。'],
    ['factOwnerCurrent', '当前登录身份已变化，请重新读取本人的正式职责及任务。'],
    ['secureSubmissionAvailable', '当前浏览器无法安全生成及核对操作意图，请从系统正常入口重新进入。'],
    ['taskSelected', '请选择需要核对的正式任务。'],
    ['actionNotCompleted', key === 'request' ? state.facts?.selectedTask?.recordProgress?.submissionLabel
      : state.facts?.selectedTask?.recordProgress?.reviewLabel],
    ['serverActionAllowed', action?.disabledReason || '当前账号或任务不满足此操作准入，请核对服务端准入说明。'],
    ['reasonLengthValid', key === 'approve' ? '请填写2至240字的审核确认原因。' : '请填写2至240字的完工申请原因。'],
  ]
  const blocker = blockers.find(([check]) => !checks[check])
  return { enabled: !blocker, blockingCode: blocker?.[0] || '', disabledReason: blocker?.[1] || '', checks }
}
async function keyHash(key) {
  const bytes = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(key))
  return Array.from(new Uint8Array(bytes), value => value.toString(16).padStart(2, '0')).join('')
}
export function createOperationCompletionController({ state, api, owner, companyId, userId, journal }) {
  const recovery = createOperationIntentRecovery({ state, api, owner, companyId, userId, journal, domain: 'completionLegacy',
    apiUrl: OPERATION_COMPLETION_PAGE.apiUrl, validator: validateOperationCompletionResponse,
    methods: { request: 'request', approve: 'approve' } })
  api = recovery.api
  let sequence = 0, generation = 0, factOwner = null, writing = false, pending = null
  const v3 = createCompletionV3Controller({ state, api, owner, companyId, userId, validator: validateOperationCompletionResponse })
  const context = () => ({ writing, pending: !!pending || !!state.pendingIntent || !!state.recoveryError, factOwnerCurrent: factOwner === owner() || v3.ownsFacts(),
    secureSubmissionAvailable: !!globalThis.crypto?.randomUUID && !!globalThis.crypto?.subtle })
  const submission = key => pending ? assessOperationCompletionSubmission(state, key, context())
    : key === 'withdrawReplace' || isCompletionV3(state.facts?.selectedTask) || state.pendingIntent || state.recoveryError
    ? v3.submission(key) : assessOperationCompletionSubmission(state, key, context())
  const progress = () => presentOperationCompletionProgress(state, context())
  function invalidate() {
    v3.invalidate()
    sequence += 1; generation += 1; factOwner = null; pending = null
    Object.assign(state, createOperationCompletionState())
  }
  function verifiedIntent(task, facts) {
    if (!pending || !task || task.taskId !== pending.taskId || task.version !== pending.version
      || task.sourceSnapshotHash !== pending.sourceSnapshotHash || task.assignmentHash !== pending.assignmentHash
      || task.startId !== pending.startId || task.startSnapshotHash !== pending.startSnapshotHash
      || task.reportSetHash !== pending.reportSetHash || facts.currentActorEvidence.userId !== pending.actorId) return false
    if (pending.executionMode === 'NON_QUANTIFIED_REQUIRED' && (task.modeSourceHash !== pending.modeSourceHash
      || task.executionConfirmation?.proofHash !== pending.executionConfirmationHash
      || task.executionConfirmationVersion !== pending.executionConfirmationVersion)) return false
    const completion = task.completionFact
    if (!completion?.stateMachineConsistent) return false
    if (pending.action === 'request') return completion.requestKeyHash === pending.requestKeyHash
      && completion.applicantId === pending.actorId && completion.requestReason === pending.reason
      && task.completionProjectionVersion >= pending.completionVersion + 1
    return task.completionStatusCode === 'completed' && completion.approvalRequestKeyHash === pending.requestKeyHash
      && completion.reviewerId === pending.actorId && completion.reviewReason === pending.reason
      && task.completionProjectionVersion === pending.completionVersion + 1
  }
  async function load() {
    // An existing V2 in-flight intent keeps its original proof protocol even
    // when another tab has since bridged the task into a V3 generation.
    if (!pending && (v3.restore() || isCompletionV3(state.facts?.selectedTask))) return v3.load()
    if (writing) return false
    if (factOwner && factOwner !== owner() || pending && pending.owner !== owner()) { invalidate(); return false }
    const request = ++sequence, epoch = generation, identity = owner(), taskId = state.taskId
    const current = () => {
      if (identity !== owner() && epoch === generation) invalidate()
      return request === sequence && epoch === generation && identity === owner() && taskId === state.taskId
    }
    const previous = state.factLoadFacts
    if (state.facts) state.lastDisplayFacts = state.facts
    Object.assign(state, { facts: null, factLoadFacts: null, serverSurface: null, error: '', readState: 'loading',
      message: pending ? '结果待核实，请仅重新读取完工事实，不重复提交或审核。' : '' })
    try {
      const response = await api.read(taskId ? { taskId: Number(taskId) } : {})
      if (!current()) return false
      Object.assign(state, validateOperationCompletionResponse(response, { companyId: Number(companyId()),
        userId: Number(userId?.()), taskId: taskId ? Number(taskId) : null }), { readState: 'loaded' })
      factOwner = identity; state.lastDisplayFacts = null
      if (state.facts?.selectedTask?.completionV3) v3.adopt()
      if (pending) {
        if (verifiedIntent(state.facts.selectedTask, state.facts)) {
          const approval = pending.action === 'approve'
          pending = null; state.writeState = 'verified'; state.reason = ''
          const confirmed = state.facts.selectedTask.recordProgress
          state.message = approval ? `${confirmed.reviewLabel}；工序整体状态请见正式完工状态，未执行转移或后序放行。`
            : `${confirmed.submissionLabel}；${confirmed.reviewLabel}。`
        } else {
          state.writeState = 'readback_pending'
          state.message = '本次操作意图仍未核实，请仅重新读取；状态变化不能单独证明本次提交成功，请勿重复提交。'
        }
      } else {
        state.writeState = 'idle'
        state.message = state.facts.selectedTask?.recordProgress.noticeLabel || ''
      }
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.serverSurface = null; state.readState = 'read_failed'
      state.factLoadFacts = factLoadFailureFromError(error, OPERATION_COMPLETION_PAGE.apiUrl, previous)
      state.error = `完工事实读取失败，当前数量、责任、审核及操作结果未知。${error?.message || ''}`
      if (pending) state.writeState = 'readback_pending'
      return false
    }
  }
  async function select(taskId = '') {
    if (writing || pending) return false
    if (v3.restore()) return v3.load()
    invalidate(); state.taskId = String(taskId || '')
    return load()
  }
  async function execute(action) {
    if (pending || writing) return false
    if (action === 'withdrawReplace' || isCompletionV3(state.facts?.selectedTask) || state.pendingIntent || state.recoveryError) return v3.execute(action)
    if (!submission(action).enabled) return false
    const facts = state.facts, task = facts.selectedTask, identity = owner(), epoch = generation
    const current = () => {
      if (identity !== owner() && epoch === generation) invalidate()
      return epoch === generation && identity === owner()
    }
    const reason = state.reason.trim(), payload = { expectedVersion: task.version,
      expectedSourceSnapshotHash: task.sourceSnapshotHash, expectedAssignmentHash: task.assignmentHash,
      expectedStartId: task.startId, expectedStartSnapshotHash: task.startSnapshotHash,
      expectedReportSetHash: task.reportSetHash, expectedCompletionVersion: task.completionProjectionVersion,
      reason, idempotencyKey: globalThis.crypto.randomUUID() }
    if (action === 'approve') {
      payload.expectedWorkflowVersion = task.completionFact.workflowVersion
      payload.expectedApprovalTaskVersion = task.completionFact.approvalTaskVersion
    }
    writing = true; sequence += 1; state.writeState = 'writing'; state.error = ''
    try {
      const requestKeyHash = await keyHash(payload.idempotencyKey)
      if (!current()) return false
      pending = { owner: identity, taskId: task.taskId, version: task.version, sourceSnapshotHash: task.sourceSnapshotHash,
        assignmentHash: task.assignmentHash, startId: task.startId, startSnapshotHash: task.startSnapshotHash,
        reportSetHash: task.reportSetHash, completionVersion: task.completionProjectionVersion,
        actorId: facts.currentActorEvidence.userId, reason, action, requestKeyHash,
        executionMode: task.executionMode, modeSourceHash: task.modeSourceHash,
        executionConfirmationHash: task.executionConfirmation?.proofHash,
        executionConfirmationVersion: task.executionConfirmationVersion }
      state.lastDisplayFacts = facts; state.facts = null; state.serverSurface = null
      state.message = '正在提交本次明确操作，随后独立只读回查，请勿重复点击。'
      const response = await api[action](task.taskId, payload)
      if (!current()) return false
      if (response?.success === false) {
        const failed = response.factLoadFacts || response.data?.factLoadFacts || response
        const status = Number(failed.httpStatus || response.meta?.status || 0), code = response.error?.code || failed.errorCode || ''
        if (status >= 400 && status < 500 && ![408, 429].includes(status) && code !== 'AUTHENTICATION_CONTEXT_CHANGED') {
          pending = null; state.writeState = 'rejected'; state.readState = 'write_rejected'
          state.message = response.error?.message || '服务端拒绝本次操作，请重新读取并核对准入说明。'
          return false
        }
        throw new Error(response.error?.message || '操作响应不明确。')
      }
      validateOperationCompletionResponse(response, { apiUrl: `${OPERATION_COMPLETION_PAGE.apiUrl}${task.taskId}/${action}/`,
        companyId: Number(companyId()), userId: Number(userId?.()), taskId: task.taskId })
      state.writeState = 'readback_pending'
    } catch (error) {
      if (!current()) return false
      state.writeState = pending ? 'readback_pending' : 'rejected'
      state.message = pending ? `本次操作可能已保存，请仅重新读取核实，不自动重试。${error?.message || ''}` : error.message
    } finally { writing = false }
    return current() && pending ? load() : false
  }
  return recovery.attach({ invalidate, load, select, execute, submission, progress })
}

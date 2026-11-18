import { createHandoverIntentJournal, canonicalHandoverIntent, hashHandoverText } from './operationHandoverIntent.js'
import { factLoadFailureFromError } from './pceFactLoadContract.js'
import { OPERATION_COMPLETION_PAGE } from './operationCompletionContract.js'
import { resolvePceOperationCompletionAction } from './pceBusinessActionRegistry.js'

const integer = value => Number.isSafeInteger(value) && value >= 0
const text = value => typeof value === 'string' && !!value.trim()
const digest = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const requireFact = (condition, message) => { if (!condition) throw new Error(message) }
export const isCompletionV3 = task => task?.completionProtocolVersion === 3

export function validateCompletionV3Context(task, companyId) {
  const v3 = task.completionV3
  requireFact(task.quantityApplicable === true && v3?.contractVersion === 'PCE-PRODUCTION-OPERATION-COMPLETION-V3'
    && integer(v3.generationId) && integer(v3.generationVersion) && integer(v3.productionRevision)
    && digest(v3.productionHash) && Array.isArray(v3.blockingIssues) && Array.isArray(v3.generationHistory)
    && v3.availableActions && typeof v3.availableActions === 'object', 'V3真实完工代次、生产事实版本或阻断依据不完整。')
  requireFact(JSON.stringify(task.availableActions)===JSON.stringify(v3.availableActions), 'V3任务动作与对应代次动作不一致。')
  const progress = task.recordProgress, completion = task.completionFact
  requireFact(progress?.contractVersion === 'PCE-OPERATION-COMPLETION-PROGRESS-V3'
    && typeof progress.submitted === 'boolean' && typeof progress.reviewed === 'boolean'
    && ['submissionLabel', 'reviewLabel', 'noticeLabel', 'reviewResponsibilityLabel', 'requestButtonLabel', 'approveButtonLabel'].every(key => text(progress[key]))
    && Array.isArray(progress.admissionIssues), 'V3本次申请提交及审核进度未读取。')
  requireFact(task.overallCompletion?.source === 'verified_completion_projection'
    && task.overallCompletion.completionProven === task.completionProven
    && task.overallCompletion.statusCode === task.completionStatusCode
    && task.overallCompletion.statusLabel === task.completionStatusLabel, 'V3工序整体状态与正式投影不一致。')
  if (completion) {
    const identity = progress.recordIdentity, id = completion.statusTransitionHistory?.[0]?.id
    requireFact(identity?.companyId === companyId && identity.taskId === task.taskId
      && identity.protocolVersion === 3 && identity.generationId === v3.generationId
      && identity.generationVersion === v3.generationVersion && Number.isSafeInteger(identity.generationSequence) && identity.generationSequence>0
      && identity.workflowInstanceId === completion.workflowInstanceId && identity.requestAuditReference === completion.requestAuditReference
      && identity.requestTransitionId === id && progress.recordId === id
      && progress.recordKey === `OperationCompletionGeneration:${companyId}:${v3.generationId}:${id}`
      && progress.submitted === true && progress.reviewed === (!!completion.approvalDecisionId && text(completion.approvalAuditReference)),
    'V3进度未准确归属真实代次和原申请证明。')
  } else requireFact(progress.recordId === null && progress.recordIdentity === null && progress.recordKey === null
    && !progress.submitted && !progress.reviewed, 'V3尚无申请时不能借用历史代次进度。')
  for (const row of v3.generationHistory) requireFact(Number.isSafeInteger(row.id ?? row.generationId)
    && text(row.statusLabel), 'V3历史代次缺少真实标识或中文状态。')
}

// Only the explicit V3 branch uses this journal. The V2/NonQ transport remains in
// operationCompletion.js, including its original payload and proof algorithm.
export function createCompletionV3Controller({ state, api, owner, companyId, userId, validator,
  journal = createHandoverIntentJournal() }) {
  let generation = 0, sequence = 0, factOwner = null, writeLock = null, sessionOwner = null
  const who = () => ({ actorId: Number(userId?.()), companyId: Number(companyId()) })
  const writing = () => writeLock?.owner === owner()
  function ensureOwner() {
    const next = owner()
    if (sessionOwner && sessionOwner !== next) {
      generation++; sequence++; factOwner = null
      Object.assign(state,{facts:null,lastDisplayFacts:null,factLoadFacts:null,serverSurface:null,pendingIntent:null,
        recoveryError:'',selectionSummary:null,verifiedRecovery:null,reason:'',withdrawReason:'',writeState:'idle',readState:'idle',message:'',error:''})
    }
    sessionOwner = next
  }
  function restore(strict = false) {
    ensureOwner()
    try {
      const current = who(), stored = journal.read(current.actorId, current.companyId, 'completion')
      if (!stored && state.pendingIntent) throw new Error('V3原请求恢复标识缺失；不能解除原操作锁。')
      state.pendingIntent = stored
      if (stored) { state.taskId = String(stored.taskId); state.writeState = 'readback_pending' }
    } catch (error) {
      // A legacy V2/NonQ read does not acquire a new storage dependency. Once a
      // V3 task or original intent is known, storage faults keep V3 write-locked.
      const principal=who(), legacyContext=!strict && !isCompletionV3(state.facts?.selectedTask) && !state.pendingIntent && !state.recoveryError
      const legacyUnavailable=legacyContext && (error.code==='INTENT_STORAGE_UNAVAILABLE' || !(principal.actorId>0 && principal.companyId>0))
      if (!legacyUnavailable) {
        state.recoveryError = error.message; state.writeState = 'recovery_blocked'
      }
    }
    return !!state.pendingIntent || !!state.recoveryError
  }
  function invalidate() { sequence++; generation++; factOwner = null; sessionOwner = null }
  function adopt() { if (state.facts?.selectedTask?.completionV3) { factOwner = owner(); restore(isCompletionV3(state.facts.selectedTask)) } }
  function submission(key) {
    let action
    try { if (state.facts) action = resolvePceOperationCompletionAction(state.facts, key) } catch (error) {
      return { enabled: false, disabledReason: error.message }
    }
    const reason = state.reason?.trim() || '', withdraw = state.withdrawReason?.trim() || ''
    const disabledReason = writing() ? '正在提交原操作，请勿重复点击。'
      : state.pendingIntent ? 'V3原操作结果待核实，请仅重新读取，不重复提交或换标识。'
        : state.recoveryError || (!globalThis.crypto?.randomUUID || !globalThis.crypto?.subtle ? '当前环境不能安全建立原请求标识，本次不能提交。'
          : !state.facts || state.readState !== 'loaded' || factOwner !== owner() ? '当前正式完工事实尚未核实，请重新读取。'
          : !(isCompletionV3(state.facts.selectedTask) || key === 'withdrawReplace' && state.facts.selectedTask?.completionV3) ? '当前任务未启用本次V3代次动作。'
            : !action?.enabled ? action?.disabledReason || '服务端未允许本动作。'
              : reason.length < 2 || reason.length > 240 ? '请填写2至240字本次申请或审核真实原因。'
                : key === 'withdrawReplace' && (withdraw.length < 2 || withdraw.length > 240) ? '请另填写2至240字撤回原申请的真实原因。' : '')
    return { enabled: !disabledReason, disabledReason, action }
  }
  async function load() {
    if (writing()) return false
    restore(true)
    const intent = state.pendingIntent, identity = owner(), epoch = generation, request = ++sequence
    const taskId = state.taskId, current = () => { if(identity !== owner() && sessionOwner === identity) ensureOwner(); return epoch === generation && request === sequence && identity === owner() && taskId === state.taskId }
    const params = taskId ? { taskId: Number(taskId) } : {}
    if (intent) Object.assign(params, { actionCode: intent.actionCode, requestHash: intent.requestHash,
      requestKeyHash: intent.requestKeyHash, generationId: intent.generationId })
    const previous = state.factLoadFacts
    if (state.facts) state.lastDisplayFacts = state.facts
    Object.assign(state, { facts: null, serverSurface: null, factLoadFacts: null, readState: 'loading', error: '' })
    try {
      const response = await api.read(params)
      if (!current()) return false
      const result = validator(response, { userId: Number(userId()), companyId: Number(companyId()), taskId: Number(taskId) || null })
      if (intent) {
        const proof = result.facts.readbackResult
        requireFact(proof && ['verified', 'unknown'].includes(proof.status) && proof.actionCode === intent.actionCode
          && proof.requestHash === intent.requestHash && proof.requestKeyHash === intent.requestKeyHash
          && proof.submittedGenerationId === intent.generationId, 'V3回查未准确绑定原动作、原代次及原请求。')
        if (proof.status === 'verified') requireFact(text(proof.proofRef) && text(proof.auditReference), 'V3对应动作正式证明未完整读取。')
      }
      Object.assign(state, result, { readState: 'loaded', lastDisplayFacts: null }); factOwner = identity
      if (intent) {
        if (result.facts.readbackResult.status === 'verified') {
          state.verifiedRecovery = result.facts.readbackResult
          try { journal.remove(intent); state.pendingIntent = null; state.recoveryError = '' }
          catch (error) { state.recoveryError = error.message }
          state.writeState = state.recoveryError ? 'verified_locked' : 'verified'
          state.message = '本次原动作已按原代次及请求证明核实。请核对对应申请、关闭或审核事实；未自动提交下一动作。'
          state.reason = ''; state.withdrawReason = ''
        } else {
          state.writeState = 'readback_pending'
          state.message = '本次V3结果仍待核实；单次未见记录不代表失败。请仅重新读取，不重复提交或换标识。'
        }
      } else if (!state.recoveryError) state.writeState = 'idle'
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.serverSurface = null; state.readState = 'read_failed'
      state.factLoadFacts = factLoadFailureFromError(error, OPERATION_COMPLETION_PAGE.apiUrl, previous)
      state.error = `本次正式完工事实未读回；当前代次、资格及结果待核实。${error.message}`
      if (intent) state.writeState = 'readback_pending'
      return false
    }
  }
  async function execute(key) {
    restore(true)
    const assessment = submission(key)
    if (!assessment.enabled) return false
    const task = state.facts.selectedTask, v3 = task.completionV3, principal = who(), identity = owner(), epoch = generation
    const current = () => { if(identity !== owner() && sessionOwner === identity) ensureOwner(); return epoch === generation && identity === owner() }
    const payload = { expectedVersion: task.version, expectedSourceSnapshotHash: task.sourceSnapshotHash,
      expectedAssignmentHash: task.assignmentHash, expectedStartId: task.startId, expectedStartSnapshotHash: task.startSnapshotHash,
      expectedReportSetHash: task.reportSetHash, expectedCompletionVersion: task.completionProjectionVersion,
      completionProtocolVersion: 3, expectedGenerationId: v3.generationId, expectedGenerationVersion: v3.generationVersion,
      expectedProductionRevision: v3.productionRevision, expectedProductionHash: v3.productionHash,
      reason: state.reason.trim(), idempotencyKey: globalThis.crypto.randomUUID() }
    if (key !== 'request') Object.assign(payload, { expectedWorkflowVersion: task.completionFact?.workflowVersion,
      expectedApprovalTaskVersion: task.completionFact?.approvalTaskVersion })
    if (key === 'withdrawReplace') Object.assign(payload, { expectedLegacyRequestId: v3.requestRecordId,
      withdrawReason: state.withdrawReason.trim() })
    const lock = { owner: identity }; writeLock = lock; sequence++
    state.writeState = 'writing'; state.error = ''; state.verifiedRecovery=null; let sent = false, intent
    state.selectionSummary = [{ label: '原任务', value: task.no }, { label: '原代次', value: String(v3.generationId) },
      { label: '原动作', value: assessment.action.displayName }]
    try {
      const [requestHash, requestKeyHash] = await Promise.all([
        hashHandoverText(canonicalHandoverIntent({ actorId: principal.actorId, actionCode: assessment.action.actionCode, objectId: task.taskId, payload })),
        hashHandoverText(payload.idempotencyKey),
      ])
      if (!current()) return false
      intent = journal.save({ domain: 'completion', ...principal, actionKey: key, actionCode: assessment.action.actionCode,
        objectId: task.taskId, taskId: task.taskId, generationId: v3.generationId, expectedVersion: v3.generationVersion, requestHash, requestKeyHash })
      state.pendingIntent = intent; state.lastDisplayFacts = state.facts; state.facts = null; state.serverSurface = null
      state.message = '正在提交本次V3原意图，随后仅独立GET回查。请勿重复提交。'
      sent = true
      const response = await api[key](task.taskId, payload)
      if (!current()) return false
      if (response?.success === false) throw { response: { data: response, status: response.meta?.status } }
      state.writeState = 'readback_pending'
    } catch (error) {
      if (!current()) return false
      const body = error.response?.data, status = Number(error.response?.status || body?.factLoadFacts?.httpStatus || body?.meta?.status)
      if (sent && body?.success === false && status >= 400 && status < 500 && ![408,429].includes(status)
        && body.error?.code !== 'AUTHENTICATION_CONTEXT_CHANGED') {
        try { journal.remove(intent); state.pendingIntent = null } catch (failure) { state.recoveryError = failure.message }
        state.writeState = state.recoveryError ? 'rejected_locked' : 'rejected'; state.readState = 'write_rejected'
        state.message = `本次V3提交已被明确拒绝。${body.error?.message || ''}请重新读取后核对，未自动重试。`
        return false
      }
      if (sent) { state.writeState = 'readback_pending'; state.message = `V3原操作可能已保存，请仅重新读取，不重复提交。${error.message || ''}` }
      else { state.recoveryError = error.message; state.writeState = 'recovery_blocked'; state.message = '技术恢复标识未安全建立，本次尚未提交。' }
    } finally { if (writeLock === lock) writeLock = null }
    return current() && state.pendingIntent ? load() : false
  }
  return { restore, invalidate, adopt, submission, load, execute, ownsFacts: () => factOwner === owner() }
}

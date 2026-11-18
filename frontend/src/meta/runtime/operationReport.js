import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { OPERATION_REPORT_PAGE } from './operationReportContract.js'
import { resolvePceOperationReportAction } from './pceBusinessActionRegistry.js'
import { readOperationExecutionMode, validateExecutionConfirmation, canonicalExecutionIntent } from './operationExecutionMode.js'
import { createOperationIntentRecovery } from './operationIntentRecovery.js'

const same = value => JSON.stringify(value)
const positiveId = value => Number.isSafeInteger(value) && value > 0
const nonempty = value => typeof value === 'string' && !!value.trim()
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const decimal = value => typeof value === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)
export const isExplicitReportQuantity = value => decimal(value) && value.length <= 100 && /[1-9]/.test(value)
export const OPERATION_REPORT_FORM_VERSION = '20261027-R1'

// Compare already validated non-negative decimal text without rounding, floating
// point conversion or changing the explicitly entered quantity.
function compareReportQuantities(left, right) {
  const [leftWhole, leftFraction = ''] = left.split('.')
  const [rightWhole, rightFraction = ''] = right.split('.')
  if (leftWhole.length !== rightWhole.length) return leftWhole.length > rightWhole.length ? 1 : -1
  if (leftWhole !== rightWhole) return leftWhole > rightWhole ? 1 : -1
  const places = Math.max(leftFraction.length, rightFraction.length)
  const leftDigits = leftFraction.padEnd(places, '0'), rightDigits = rightFraction.padEnd(places, '0')
  return leftDigits === rightDigits ? 0 : leftDigits > rightDigits ? 1 : -1
}

// One form decision is shared by the visible button, its Chinese explanation,
// diagnostics and the controller's final preflight. Server facts remain intact.
export function assessOperationReportSubmission(state, context = {}) {
  const facts = state.facts, task = facts?.selectedTask
  let action = null
  try { if (facts) action = resolvePceOperationReportAction(facts) } catch { /* fail closed below */ }
  let mode = null
  try { if (task) mode = readOperationExecutionMode(task) } catch { /* explicit blocker below */ }
  const nonquantified = mode?.nonquantified === true
  const quantity = state.quantity, reason = typeof state.reason === 'string' ? state.reason.trim() : ''
  const quantitySyntaxValid = decimal(quantity) && quantity.length <= 100
  const precisionAvailable = Number.isSafeInteger(task?.quantityPrecision) && task.quantityPrecision >= 0
  const remainingAvailable = decimal(task?.remainingQuantity)
  const checks = {
    readingComplete: state.readState === 'loaded',
    notReading: state.readState !== 'loading',
    notWriting: !context.writing && state.writeState !== 'writing',
    noPendingReadback: !context.pending && state.writeState !== 'readback_pending',
    factsPresent: !!facts,
    taskSelected: !!task,
    modeProven: !!mode && (mode.quantified || mode.nonquantified),
    factOwnerCurrent: context.factOwnerCurrent !== false,
    secureSubmissionAvailable: context.secureSubmissionAvailable !== false,
    serverQualificationReady: facts?.qualification?.ready === true,
    serverActionAllowed: action?.enabled === true,
    precisionAvailable: nonquantified || precisionAvailable,
    remainingAvailable: nonquantified || remainingAvailable,
    quantityPresent: nonquantified || typeof quantity === 'string' && quantity.length > 0,
    quantitySyntaxValid: nonquantified || quantitySyntaxValid,
    quantityPositive: nonquantified || quantitySyntaxValid && /[1-9]/.test(quantity),
    quantityWithinPrecision: nonquantified || quantitySyntaxValid && precisionAvailable
      && (quantity.split('.')[1]?.length || 0) <= task.quantityPrecision,
    quantityWithinRemaining: nonquantified || quantitySyntaxValid && remainingAvailable
      && compareReportQuantities(quantity, task.remainingQuantity) <= 0,
    reasonLengthValid: reason.length >= 2 && reason.length <= 300,
  }
  const blockers = [
    ['notReading', 'READING', '正在读取报工事实，请等待读取完成。'],
    ['notWriting', 'WRITING', nonquantified ? '正在登记本次实际经过，请勿重复操作。' : '正在提交本次报工，请勿重复操作。'],
    ['noPendingReadback', 'PENDING_READBACK', nonquantified ? '本次实际经过登记结果待核实，请点击“重新读取报工事实”，不要重复登记。'
      : '本次报工结果待核实，请点击“重新读取报工事实”，不要重复提交。'],
    ['factsPresent', 'FACTS_MISSING', state.readState === 'read_failed'
      ? '报工事实读取失败，请点击“重新读取报工事实”后再填写。' : '尚未取得当前报工事实，请点击“重新读取报工事实”。'],
    ['readingComplete', 'FACTS_NOT_CURRENT', '当前报工事实尚未核实，请点击“重新读取报工事实”。'],
    ['factOwnerCurrent', 'IDENTITY_CHANGED', '当前登录身份已变化，请重新读取本人报工事实。'],
    ['secureSubmissionAvailable', 'SECURE_SUBMISSION_UNAVAILABLE', '当前浏览器无法安全提交报工，请从系统正常入口重新进入。'],
    ['taskSelected', 'TASK_NOT_SELECTED', '请选择本人已开工任务。'],
    ['modeProven', 'EXECUTION_MODE_UNPROVEN', task?.executionModeLabel || '正式执行模式或来源尚未核实，请重新读取。'],
    ['serverQualificationReady', 'SERVER_QUALIFICATION_BLOCKED', action?.disabledReason || (facts?.qualification
      ? '当前本人报工准入未通过，请重新读取并核对准入说明。' : '本人报工准入事实尚未核实，请重新读取报工事实。')],
    ['serverActionAllowed', 'SERVER_ACTION_BLOCKED', action?.disabledReason || '当前任务不满足本人报工准入，请重新读取并核对准入说明。'],
    ['precisionAvailable', 'PRECISION_MISSING', '正式计量单位精度尚未核实，请重新读取报工事实。'],
    ['remainingAvailable', 'REMAINING_MISSING', '剩余可报量尚未核实，请重新读取报工事实。'],
    ['quantityPresent', 'QUANTITY_REQUIRED', '请输入本次实际完成数量。'],
    ['quantitySyntaxValid', 'QUANTITY_FORMAT', '本次实际完成数量须为不超过100字符的十进制数字，请勿填写空格、符号或科学计数。'],
    ['quantityPositive', 'QUANTITY_NOT_POSITIVE', '本次实际完成数量必须大于0。'],
    ['quantityWithinPrecision', 'QUANTITY_PRECISION', `本次数量超过正式计量单位允许的${task?.quantityPrecision ?? ''}位小数，请核对实际量后重新填写。`],
    ['quantityWithinRemaining', 'QUANTITY_EXCEEDS_REMAINING', '本次数量超过剩余可报量，请核对本次实际完成数量。'],
    ['reasonLengthValid', 'REASON_LENGTH', nonquantified ? '请填写2至300字的本次实际经过登记原因。' : '请填写2至300字的本次报工原因。'],
  ]
  const blocker = blockers.find(([check]) => !checks[check])
  return { formVersion: OPERATION_REPORT_FORM_VERSION, enabled: !blocker,
    blockingCode: blocker?.[1] || '', disabledReason: blocker?.[2] || '', quantityApplicable: mode?.quantityApplicable ?? null, checks }
}
function requireFact(value, message) { if (!value) throw new Error(message) }
export async function hashReportRequestKey(key) {
  requireFact(globalThis.crypto?.subtle, '当前浏览器无法安全核对本次报工意图，请使用支持安全加密的正式运行环境。')
  const bytes = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(key))
  return Array.from(new Uint8Array(bytes), value => value.toString(16).padStart(2, '0')).join('')
}

export function validateOperationReportResponse(response, expected = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(response, expected.apiUrl || OPERATION_REPORT_PAGE.apiUrl, '工序报工')
  requireFact(factLoadFacts.factLoadStatus !== 'read_failed', factLoadFacts.errorMessage)
  const facts = data.operationReportFacts
  requireFact(facts?.contractVersion === OPERATION_REPORT_PAGE.factContractVersion
    && facts.moduleCode === OPERATION_REPORT_PAGE.moduleId && facts.factSource === 'server'
    && facts.currentStateSource === 'server', '报工事实合同、业务对象或权威来源不一致。')
  requireFact(Array.isArray(facts.tasks) && Number.isSafeInteger(data.resultCount)
    && data.resultCount >= 0 && data.resultCount === facts.tasks.length, '报工任务服务端数量与列表不一致。')
  requireFact(Number.isSafeInteger(facts.operationReportRecordCount) && facts.operationReportRecordCount >= 0,
    '正式报工记录数量未由服务端核实。')
  const actor = facts.currentActorEvidence
  requireFact(actor && positiveId(actor.userId) && positiveId(actor.companyId) && nonempty(actor.username), '本次后台身份未核实。')
  if (expected.companyId) requireFact(actor.companyId === expected.companyId, '当前公司与报工事实不一致。')
  if (expected.userId) requireFact(actor.userId === expected.userId, '当前账号与报工事实不一致。')
  for (const row of facts.tasks) {
    const mode = readOperationExecutionMode(row)
    requireFact(positiveId(row.taskId) && row.id === row.taskId && nonempty(row.no)
      && nonempty(row.workOrderNo) && nonempty(row.operationName) && nonempty(row.workloadLabel)
      && Number.isSafeInteger(row.version) && hash(row.sourceSnapshotHash) && hash(row.assignmentHash)
      && positiveId(row.startRecordId) && hash(row.startSnapshotHash) && nonempty(row.startAuditReference),
    '本人已开工任务来源、版本或开工审计不完整。')
    requireFact(positiveId(actor.employeeId) && row.employeeId === actor.employeeId
      && row.employeeUsername === actor.username && row.executionRecord?.startedById === actor.userId,
    '列表出现非本人获派或非本人实际开工任务，已停止加载。')
    if (mode.quantified) requireFact(decimal(row.workloadQuantity) && decimal(row.reportedQuantity) && decimal(row.remainingQuantity)
      && nonempty(row.workloadUomLabel) && nonempty(row.reportedQuantityLabel) && nonempty(row.remainingQuantityLabel)
      && Number.isSafeInteger(row.quantityPrecision) && decimal(row.minimumReportQuantity)
      && typeof row.remainingBelowUnitPrecision === 'boolean' && typeof row.precisionNotice === 'string'
      && nonempty(row.quantityStatusLabel) && row.completionProven === false && row.downstreamReleased === false,
    '正式数量、单位精度、累计或剩余量服务端事实不完整。')
    else if (mode.nonquantified) {
      requireFact(['workloadQuantity', 'reportedQuantity', 'remainingQuantity', 'quantityPrecision', 'minimumReportQuantity', 'workloadUomId', 'workloadUomLabel']
        .every(key => row[key] === null) && nonempty(row.quantityStatusLabel)
        && nonempty(row.reportedQuantityLabel) && nonempty(row.remainingQuantityLabel)
        && row.completionProven === false && row.downstreamReleased === false,
      '无统计量任务必须保留正式空值，不得虚构数量、单位、精度或正式完工。')
      validateExecutionConfirmation(row, { actorId: actor.userId })
      requireFact(Array.isArray(row.reports) && row.reports.length === 0 && row.operationReportRecordCount === 0,
        '实际经过登记不能以数量报工记录替代。')
    }
    else if (facts.selectedTask?.taskId === row.taskId) requireFact(facts.qualification?.ready === false
      && facts.availableActions?.report?.enabled === false && facts.availableActions?.confirmExecution?.enabled !== true,
    '执行模式待核实时必须明确阻止数量报工和实际经过登记。')
    requireFact(Array.isArray(row.reports) && row.operationReportRecordCount === row.reports.length
      && row.stateMachineConsistent === true, '报工记录与服务端审计数量不一致。')
    for (const record of row.reports) {
      requireFact(positiveId(record.id) && record.taskId === row.taskId && record.startRecordId === row.startRecordId
        && record.taskVersion === row.version && record.sourceSnapshotHash === row.sourceSnapshotHash
        && record.assignmentHash === row.assignmentHash && record.startSnapshotHash === row.startSnapshotHash
        && record.reportedById === actor.userId && isExplicitReportQuantity(record.quantity) && nonempty(record.quantityLabel)
        && hash(record.requestKeyHash) && nonempty(record.reason) && nonempty(record.reportedAtLabel)
        && nonempty(record.auditReference) && nonempty(record.statusLabel) && record.completionProven === false
        && record.stateMachineConsistent === true && Array.isArray(record.statusTransitionHistory)
        && record.statusTransitionCount === record.statusTransitionHistory.length && record.statusTransitionCount > 0,
      '正式报工数量、本人、来源或状态审计不完整。')
    }
  }
  if (facts.selectedTask) requireFact(facts.tasks.some(row => same(row) === same(facts.selectedTask)), '所选任务不属于本次本人已开工任务列表。')
  if (expected.taskId) requireFact(facts.selectedTask?.taskId === expected.taskId, '所选任务身份与服务端事实不一致。')
  resolvePceOperationReportAction(facts)
  for (const surface of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    requireFact(same(data[surface]?.operationReportFacts) === same(facts)
      && data[surface]?.resultCount === data.resultCount, '报工服务端五表面事实或数量不一致。')
  }
  return { facts, factLoadFacts, serverSurface: data.strictFacts }
}

export function createOperationReportState() {
  return { taskId: '', quantity: '', reason: '', facts: null, lastDisplayFacts: null, factLoadFacts: null, serverSurface: null,
    readState: 'idle', writeState: 'idle', message: '', error: '' }
}
export function createOperationReportController({ state, api, owner, companyId, userId, journal }) {
  const recovery = createOperationIntentRecovery({ state, api, owner, companyId, userId, journal, domain: 'report',
    apiUrl: OPERATION_REPORT_PAGE.apiUrl, validator: validateOperationReportResponse,
    methods: { report: 'report', confirmExecution: 'confirmExecution' } })
  api = recovery.api
  let sequence = 0, generation = 0, factOwner = null, writing = false, pending = null
  function submission() {
    return assessOperationReportSubmission(state, { writing, pending: !!pending, factOwnerCurrent: factOwner === owner(),
      secureSubmissionAvailable: !!globalThis.crypto?.randomUUID && !!globalThis.crypto?.subtle })
  }
  function invalidate() {
    sequence += 1; generation += 1; factOwner = null; pending = null
    Object.assign(state, createOperationReportState())
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
      Object.assign(state, validateOperationReportResponse(response, { companyId: Number(companyId()),
        userId: Number(userId?.()), taskId: taskId ? Number(taskId) : null }), { readState: 'loaded' })
      factOwner = identity; state.lastDisplayFacts = null
      if (pending) {
        const task = state.facts.selectedTask
        if (pending.kind === 'confirmExecution') {
          const proof = task?.executionConfirmation, event = proof?.statusTransitionHistory?.at(-1)
          if (proof && task.taskId === pending.taskId && task.version === pending.version
            && task.modeSourceHash === pending.modeSourceHash && proof.modeSourceHash === pending.modeSourceHash
            && proof.projectionVersion === pending.executionVersion + 1
            && proof.startRecordId === pending.startRecordId && proof.sourceSnapshotHash === pending.sourceSnapshotHash
            && proof.assignmentHash === pending.assignmentHash && proof.startSnapshotHash === pending.startSnapshotHash
            && proof.confirmedById === pending.actorId && proof.reason === pending.reason
            && proof.requestKeyHash === pending.requestKeyHash && proof.requestHash === pending.requestHash
            && (!pending.confirmationRef || proof.ref === pending.confirmationRef)
            && event?.operatorId === pending.actorId && event?.reason === pending.reason && event?.auditReference === proof.auditReference) {
            pending = null; state.writeState = 'verified'; state.quantity = ''; state.reason = ''
            state.message = '本次实际经过已独立只读回查核实；未创建数量报工。下一正式节点为完工申请及生产跟单员独立审核。'
          } else {
            state.writeState = 'readback_pending'
            state.message = '本次实际经过登记意图仍未核实，请仅重新读取；其他人员或其他意图的证明不能替代本次结果。'
          }
        } else {
        const record = task?.reports.find(row => row.requestKeyHash === pending.requestKeyHash)
        const event = record?.statusTransitionHistory?.at(-1)
        if (record && task.taskId === pending.taskId && task.version === pending.version
          && record.taskVersion === pending.version && record.startRecordId === pending.startRecordId
          && record.sourceSnapshotHash === pending.sourceSnapshotHash && record.assignmentHash === pending.assignmentHash
          && record.startSnapshotHash === pending.startSnapshotHash && record.reportedById === pending.actorId
          && record.quantity === pending.quantity && record.reason === pending.reason
          && (!pending.recordId || record.id === pending.recordId) && record.stateMachineConsistent
          && event?.operatorId === pending.actorId && event?.actionCode === 'production.operation.report'
          && event?.reason === pending.reason && event?.auditReference === record.auditReference) {
          pending = null; state.writeState = 'verified'; state.quantity = ''; state.reason = ''
          state.message = '本次报工已独立只读回查核实，请核对数量、本人、实际时间与审计。下一次报工须重新填写数量和原因；报工量不证明工序完工。'
        } else {
          state.writeState = 'readback_pending'
          state.message = '本次报工意图仍未核实，请仅重新读取，不要重复报工；累计数量变化不能证明本次提交成功。'
        }
        }
      }
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.serverSurface = null; state.readState = 'read_failed'
      state.factLoadFacts = factLoadFailureFromError(error, OPERATION_REPORT_PAGE.apiUrl, previous)
      state.error = `报工事实读取失败，当前任务数量、累计、剩余量、资格及提交结果未知。${error?.message || ''}`
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
    if (!submission().enabled) return false
    const facts = state.facts, task = facts?.selectedTask, reason = state.reason.trim(), quantity = state.quantity
    const nonquantified = readOperationExecutionMode(task).nonquantified
    const identity = owner(), epoch = generation
    const current = () => {
      if (identity !== owner() && epoch === generation) invalidate()
      return epoch === generation && identity === owner()
    }
    if (!globalThis.crypto?.randomUUID || !globalThis.crypto?.subtle) {
      state.error = '当前浏览器无法安全生成及核对报工意图，请使用支持安全加密的正式运行环境。'; return false
    }
    const payload = { expectedVersion: task.version, expectedSourceSnapshotHash: task.sourceSnapshotHash,
      expectedAssignmentHash: task.assignmentHash, expectedStartId: task.startRecordId,
      expectedStartSnapshotHash: task.startSnapshotHash,
      ...(nonquantified ? { expectedExecutionVersion: task.executionConfirmationVersion } : { quantity }), reason,
      idempotencyKey: globalThis.crypto.randomUUID() }
    writing = true; sequence += 1; state.writeState = 'writing'; state.error = ''
    try {
      const requestKeyHash = await hashReportRequestKey(payload.idempotencyKey)
      const requestHash = nonquantified ? await hashReportRequestKey(canonicalExecutionIntent({ actorId: facts.currentActorEvidence.userId,
        action: 'production.operation.confirm_execution', taskId: task.taskId, payload })) : null
      if (!current()) return false
      pending = { owner: identity, taskId: task.taskId, version: task.version, startRecordId: task.startRecordId,
        sourceSnapshotHash: task.sourceSnapshotHash, assignmentHash: task.assignmentHash, startSnapshotHash: task.startSnapshotHash,
        actorId: facts.currentActorEvidence.userId, quantity, reason, requestKeyHash, recordId: null,
        kind: nonquantified ? 'confirmExecution' : 'report', requestHash, modeSourceHash: task.modeSourceHash,
        executionVersion: task.executionConfirmationVersion, confirmationRef: null }
      state.lastDisplayFacts = facts; state.facts = null; state.serverSurface = null
      state.message = nonquantified ? '正在提交本人本次实际经过登记，随后独立只读回查；不创建数量报工。'
        : '正在提交本人本次实际完成数量，随后独立只读回查；请勿重复报工。'
      const response = await api[nonquantified ? 'confirmExecution' : 'report'](task.taskId, payload)
      if (!current()) return false
      if (response?.success === false) {
        const failed = response.factLoadFacts || response.data?.factLoadFacts || response
        const status = Number(failed.httpStatus || response.meta?.status || 0), code = response.error?.code || failed.errorCode || ''
        if (status >= 400 && status < 500 && ![408, 429].includes(status) && code !== 'AUTHENTICATION_CONTEXT_CHANGED') {
          pending = null; state.writeState = 'rejected'; state.readState = 'write_rejected'
          state.message = response.error?.message || (nonquantified ? '服务端拒绝本次实际经过登记，请重新读取后核对；未自动重试。'
            : '服务端拒绝本次报工，请重新读取后核对；未自动重试。')
          return false
        }
        throw new Error(response.error?.message || (nonquantified ? '实际经过登记响应不明确。' : '报工响应不明确。'))
      }
      const acknowledgedTask = validateOperationReportResponse(response, { apiUrl: `${OPERATION_REPORT_PAGE.apiUrl}${task.taskId}/${nonquantified ? 'confirm-execution' : 'report'}/`,
        companyId: Number(companyId()), userId: Number(userId?.()), taskId: task.taskId }).facts.selectedTask
      if (nonquantified) pending.confirmationRef = acknowledgedTask?.executionConfirmation?.ref || null
      else {
        const acknowledged = acknowledgedTask?.reports.find(row => row.requestKeyHash === pending.requestKeyHash)
        if (acknowledged) pending.recordId = acknowledged.id
      }
      state.writeState = 'readback_pending'
    } catch (error) {
      if (!current()) return false
      state.writeState = pending ? 'readback_pending' : 'rejected'
      state.message = pending ? `${nonquantified ? '本次实际经过登记' : '本次报工'}结果尚未核实，可能已保存；请仅重新读取，不自动重试。${error?.message || ''}` : error.message
    } finally { writing = false }
    return current() && pending ? load() : false
  }
  return recovery.attach({ invalidate, load, select, execute, submission })
}

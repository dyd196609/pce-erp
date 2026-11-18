// Execution mode is a formal server fact, never inferred from a zero, missing
// quantity, capacity flag, dependency label or current viewer.
export const QUANTIFIED_EXECUTION = 'QUANTIFIED'
export const NONQUANTIFIED_EXECUTION = 'NON_QUANTIFIED_REQUIRED'
const text = value => typeof value === 'string' && !!value.trim()
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const id = value => Number.isSafeInteger(value) && value > 0
const decimal = value => typeof value === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)
function requireFact(value, message) { if (!value) throw new Error(message) }

export function readOperationExecutionMode(row) {
  requireFact(row && Object.hasOwn(row, 'executionMode') && text(row.executionModeLabel), '正式执行模式尚未读取。')
  const quantified = row.executionMode === QUANTIFIED_EXECUTION
  const nonquantified = row.executionMode === NONQUANTIFIED_EXECUTION
  const pending = row.executionMode === 'PENDING'
  const exempt = row.executionMode === 'NOT_APPLICABLE'
  requireFact((quantified && row.quantityApplicable === true || nonquantified && row.quantityApplicable === false)
    && hash(row.modeSourceHash) || pending && row.quantityApplicable === null && (row.modeSourceHash === null || hash(row.modeSourceHash))
    || exempt && row.quantityApplicable === null && hash(row.modeSourceHash),
  '正式执行模式、数量适用性或来源哈希不一致。')
  const reference = row.referenceWorkload
  requireFact(reference && typeof reference === 'object' && !Array.isArray(reference)
    && (reference.quantity === null || decimal(reference.quantity))
    && (reference.uomId === null || id(reference.uomId))
    && (reference.uomLabel === null || typeof reference.uomLabel === 'string'), '工程参考作业量及其单位事实不完整。')
  return { code: row.executionMode, statusLabel: row.executionModeLabel, quantified, nonquantified, pending, exempt,
    quantityApplicable: row.quantityApplicable, sourceHash: row.modeSourceHash, referenceWorkload: reference }
}

export function validateExecutionConfirmation(task, { actorId = null } = {}) {
  const proof = task.executionConfirmation
  requireFact(Number.isSafeInteger(task.executionConfirmationVersion) && task.executionConfirmationVersion >= 0,
    '实际经过登记版本尚未由正式服务核实。')
  if (!proof) {
    requireFact(task.executionConfirmationVersion === 0, '没有正式经过证明时不能显示已登记版本。')
    return null
  }
  requireFact(task.executionConfirmationVersion === 1 && proof.projectionVersion === task.executionConfirmationVersion
    && proof.contractVersion === 'PCE-PRODUCTION-OPERATION-EXECUTION-CONFIRMATION-V1'
    && proof.proofType === 'ACTUAL_EXECUTION_CONFIRMATION' && proof.statusCode === 'confirmed'
    && proof.quantityApplicable === false && proof.completionProven === false
    && proof.taskId === task.taskId && proof.startRecordId === (task.startRecordId ?? task.startId)
    && proof.sourceSnapshotHash === task.sourceSnapshotHash && proof.assignmentHash === task.assignmentHash
    && proof.startSnapshotHash === task.startSnapshotHash && proof.modeSourceHash === task.modeSourceHash
    && id(proof.confirmedById) && (!actorId || proof.confirmedById === actorId)
    && ['ref', 'confirmedByLabel', 'confirmedAt', 'confirmedAtLabel', 'reason', 'auditReference', 'statusLabel'].every(key => text(proof[key]))
    && ['proofHash', 'requestKeyHash', 'requestHash'].every(key => hash(proof[key]))
    && proof.stateMachineConsistent === true && Array.isArray(proof.statusTransitionHistory)
    && proof.statusTransitionCount === proof.statusTransitionHistory.length && proof.statusTransitionCount === 1
    && proof.statusTransitionHistory[0].actionCode === 'production.operation.confirm_execution'
    && proof.statusTransitionHistory[0].operatorId === proof.confirmedById
    && proof.statusTransitionHistory[0].reason === proof.reason
    && proof.statusTransitionHistory[0].auditReference === proof.auditReference,
  '实际经过证明与本任务、本人开工、模式来源或正式审计不一致。')
  return proof
}

export const canonicalExecutionIntent = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item)

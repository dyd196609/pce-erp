import { buildBusinessActionIdempotencyKey, resolveBusinessActionIdempotency } from './businessActionIdempotency.js'
import { buildBusinessDocumentNumberReservationPlan } from './businessDocumentNumberPolicy.js'
import { cloneBusinessActionTransactionValue, sealBusinessActionTransactionResult, stableBusinessActionTransactionHash, validateBusinessActionTransactionIntegrity } from './businessActionTransactionIntegrity.js'
import { businessActionTransactionTerminalStates } from './businessActionTransactionStates.js'

const text = (value) => String(value ?? '').trim()

export function buildBusinessActionFormalGenerationCommand(input = {}) {
  const core = {
    commandPolicyVersion: text(input.commandPolicyVersion), actionCode: text(input.actionCode), sourceKey: text(input.sourceKey),
    sourceSupplierSettlementNo: text(input.sourceSupplierSettlementNo), sourceCandidateId: text(input.sourceCandidateId),
    simulationRequestId: text(input.simulationRequestId), simulationResultId: text(input.simulationResultId), simulationResultHash: text(input.simulationResultHash),
    reviewId: text(input.reviewId), reviewHash: text(input.reviewHash), expectedSourceSnapshotHash: text(input.expectedSourceSnapshotHash),
    expectedTargetExistenceStatus: text(input.expectedTargetExistenceStatus), expectedTargetCount: Number(input.expectedTargetCount || 0),
    formalExecutionAllowed: false, transactionMode: 'canary_isolated_transaction_design',
  }
  const idempotencyKey = buildBusinessActionIdempotencyKey({ ...core, transactionPolicyVersion: input.transactionPolicyVersion })
  const transactionLockKey = `${core.actionCode}::${core.sourceKey}`
  const numberReservationScope = cloneBusinessActionTransactionValue(input.numberReservationScope || {})
  const commandId = `BAC-${stableBusinessActionTransactionHash({ ...core, idempotencyKey, transactionLockKey, numberReservationScope })}`
  const payload = { commandId, ...core, idempotencyKey, transactionLockKey, numberReservationScope }
  return { ...payload, commandHash: stableBusinessActionTransactionHash(payload) }
}

export function buildBusinessActionTransactionPlan({ command, transactionPolicyVersion, transactionSteps = [], compensationSteps = [], accountingPeriod = '' } = {}) {
  const numberReservationPlan = buildBusinessDocumentNumberReservationPlan({
    ...command.numberReservationScope, accountingPeriod, idempotencyKey: command.idempotencyKey,
  })
  const core = {
    transactionPolicyVersion, commandId: command.commandId, actionCode: command.actionCode, sourceKey: command.sourceKey,
    reviewId: command.reviewId, reviewHash: command.reviewHash, idempotencyKey: command.idempotencyKey,
    transactionLockKey: command.transactionLockKey, numberReservationPlan,
    transactionSteps: cloneBusinessActionTransactionValue(transactionSteps), compensationSteps: cloneBusinessActionTransactionValue(compensationSteps),
    expectedSourceSnapshotHash: command.expectedSourceSnapshotHash, expectedTargetCount: command.expectedTargetCount,
    formalExecutionAllowed: false,
  }
  const transactionPlanId = `BATP-${stableBusinessActionTransactionHash(core)}`
  const payload = { transactionPlanId, ...core }
  return { ...payload, planHash: stableBusinessActionTransactionHash(payload) }
}

export function authorizeBusinessActionTransactionExecution({ command, plan } = {}) {
  return {
    allowed: false, commandId: command?.commandId || '', transactionPlanId: plan?.transactionPlanId || '',
    formalExecutionAllowed: false, errorCode: 'BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED',
    formalBusinessWriteCount: 0, formalNumberAllocationCount: 0,
  }
}

export function recoverBusinessActionTransactionOutcome(evidence = {}) {
  if (evidence.integrityValid === false) return { classification: 'integrity_failed', safeToRetry: false, requiresManualIntervention: true }
  const targets = evidence.targets || []
  if (targets.length > 1 || (targets[0] && (targets[0].sourceKey !== evidence.sourceKey || targets[0].reviewId !== evidence.expectedReviewId || targets[0].reviewHash !== evidence.expectedReviewHash))) {
    return { classification: 'conflict', safeToRetry: false, requiresManualIntervention: true }
  }
  const complete = evidence.idempotencyStatus === 'committed' && targets.length === 1 && evidence.numberReservationStatus === 'consumed'
    && evidence.sourceTargetRelationPresent === true && evidence.auditRecordPresent === true
  if (complete) return { classification: 'committed', safeToRetry: false, requiresManualIntervention: false, targetNo: targets[0].targetNo }
  const partial = targets.length || evidence.numberReservationStatus === 'consumed' || evidence.sourceTargetRelationPresent || evidence.auditRecordPresent
  if (partial) return { classification: 'partial_commit_requires_intervention', safeToRetry: false, requiresManualIntervention: true }
  return { classification: 'not_committed_safe_to_retry', safeToRetry: true, requiresManualIntervention: false }
}

export function restoreBusinessActionTransactionResult(result = {}) {
  const integrity = validateBusinessActionTransactionIntegrity(result)
  if (!integrity.integrityValid) return { restored: false, result: null, ...integrity }
  return { restored: true, result: { ...cloneBusinessActionTransactionValue(result), resultSource: 'existing_transaction_result' }, ...integrity }
}

export function classifyBusinessActionTransactionArtifacts(artifacts = {}) {
  return Object.fromEntries([
    'isolatedCommandCount', 'isolatedTransactionPlanCount', 'isolatedIdempotencyRecordCount', 'isolatedNumberReservationCount',
    'isolatedStagedObjectCount', 'isolatedCommitRecordCount', 'isolatedRollbackRecordCount', 'isolatedRecoveryRecordCount',
    'formalBusinessWriteCount',
  ].map((key) => [key, Number(artifacts[key] || 0)]))
}

export { resolveBusinessActionIdempotency, sealBusinessActionTransactionResult, businessActionTransactionTerminalStates }

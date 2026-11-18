import {
  buildBusinessActionFormalGenerationCommand, buildBusinessActionTransactionPlan,
  authorizeBusinessActionTransactionExecution, recoverBusinessActionTransactionOutcome,
  restoreBusinessActionTransactionResult, classifyBusinessActionTransactionArtifacts,
  resolveBusinessActionIdempotency, sealBusinessActionTransactionResult,
} from '../core/action-transaction/businessActionTransaction.js'
import { stableBusinessActionTransactionHash, cloneBusinessActionTransactionValue } from '../core/action-transaction/businessActionTransactionIntegrity.js'
import { validateBusinessDocumentNumberReservation } from '../core/action-transaction/businessDocumentNumberPolicy.js'
import { validatePurchaseReconciliationFinalReviewIntegrity } from './purchaseReconciliationFinalReview.js'

export const PURCHASE_RECONCILIATION_TRANSACTION_VERSION = 'V1.14.2.8.4.7.39'
export const PURCHASE_RECONCILIATION_COMMAND_POLICY_VERSION = 'prc-formal-command-policy-v1'
export const PURCHASE_RECONCILIATION_TRANSACTION_POLICY_VERSION = 'prc-transaction-policy-v1'

const step = (sequence, stepCode, name, phase, compensationCode = '') => ({
  stepCode, sequence, name, phase, status: 'not_started', blocking: true,
  inputHash: '', outputHash: '', failureCode: `${stepCode}_FAILED`, compensationCode,
  formalWriteCount: 0, simulationArtifactWriteCount: 0,
})

export const purchaseReconciliationTransactionStepDefinitions = [
  step(1, 'PRC_TX_VALIDATE_FINAL_REVIEW', '验证最终评审', 'preflight'),
  step(2, 'PRC_TX_BUILD_COMMAND', '构建正式生成命令', 'preflight'),
  step(3, 'PRC_TX_ACQUIRE_SOURCE_LOCK', '获取来源事务锁', 'concurrency', 'PRC_TX_RELEASE_SOURCE_LOCK'),
  step(4, 'PRC_TX_REREAD_SOURCE_SNAPSHOT', '锁内重读来源快照', 'concurrency'),
  step(5, 'PRC_TX_RECHECK_TARGET_UNIQUENESS', '锁内复核目标唯一性', 'concurrency'),
  step(6, 'PRC_TX_CHECK_IDEMPOTENCY', '检查幂等登记', 'idempotency', 'PRC_TX_RELEASE_IDEMPOTENCY_PLACEHOLDER'),
  step(7, 'PRC_TX_PLAN_NUMBER_RESERVATION', '规划编号预留', 'numbering'),
  step(8, 'PRC_TX_RESERVE_DOCUMENT_NUMBER', '预留隔离编号', 'numbering', 'PRC_TX_ABORT_NUMBER_RESERVATION'),
  step(9, 'PRC_TX_STAGE_FORMAL_OBJECT', '暂存采购对账对象', 'staging', 'PRC_TX_COMPENSATE_FORMAL_OBJECT_STAGE'),
  step(10, 'PRC_TX_STAGE_SOURCE_TARGET_RELATION', '暂存来源目标关系', 'staging', 'PRC_TX_COMPENSATE_SOURCE_TARGET_RELATION'),
  step(11, 'PRC_TX_STAGE_SUPPLIER_SETTLEMENT_WRITEBACK', '暂存供应商结算回写', 'staging', 'PRC_TX_COMPENSATE_SOURCE_WRITEBACK'),
  step(12, 'PRC_TX_STAGE_AUDIT_RECORD', '暂存审计记录', 'staging', 'PRC_TX_COMPENSATE_AUDIT_STAGE'),
  step(13, 'PRC_TX_VALIDATE_STAGED_TRANSACTION', '验证全部暂存内容', 'staging'),
  step(14, 'PRC_TX_COMMIT', '提交隔离 copy-on-write 快照', 'commit'),
  step(15, 'PRC_TX_RELEASE_SOURCE_LOCK', '释放来源事务锁', 'cleanup'),
]

export const purchaseReconciliationCompensationDefinitions = [
  ['PRC_TX_COMPENSATE_AUDIT_STAGE', 'PRC_TX_STAGE_AUDIT_RECORD'],
  ['PRC_TX_COMPENSATE_SOURCE_WRITEBACK', 'PRC_TX_STAGE_SUPPLIER_SETTLEMENT_WRITEBACK'],
  ['PRC_TX_COMPENSATE_SOURCE_TARGET_RELATION', 'PRC_TX_STAGE_SOURCE_TARGET_RELATION'],
  ['PRC_TX_COMPENSATE_FORMAL_OBJECT_STAGE', 'PRC_TX_STAGE_FORMAL_OBJECT'],
  ['PRC_TX_ABORT_NUMBER_RESERVATION', 'PRC_TX_RESERVE_DOCUMENT_NUMBER'],
  ['PRC_TX_RELEASE_IDEMPOTENCY_PLACEHOLDER', 'PRC_TX_CHECK_IDEMPOTENCY'],
  ['PRC_TX_RELEASE_SOURCE_LOCK', 'PRC_TX_ACQUIRE_SOURCE_LOCK'],
].map(([compensationCode, originalStepCode], index) => ({ compensationCode, originalStepCode, sequence: index + 1 }))

const zeroWrites = () => ({
  formalBusinessWriteCount: 0, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0,
  supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0, paymentVoucherWriteCount: 0,
  localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0,
})

export function buildPurchaseReconciliationFormalGenerationCommand(review = {}, context = {}) {
  return buildBusinessActionFormalGenerationCommand({
    commandPolicyVersion: PURCHASE_RECONCILIATION_COMMAND_POLICY_VERSION,
    transactionPolicyVersion: PURCHASE_RECONCILIATION_TRANSACTION_POLICY_VERSION,
    actionCode: 'purchase_reconciliation_generation', sourceKey: review.sourceKey,
    sourceSupplierSettlementNo: review.sourceSupplierSettlementNo, sourceCandidateId: review.sourceCandidateId,
    simulationRequestId: review.simulationRequestId, simulationResultId: review.simulationResultId,
    simulationResultHash: review.simulationResultHash, reviewId: review.reviewId, reviewHash: review.reviewHash,
    expectedSourceSnapshotHash: review.currentSourceSnapshotHash || review.sourceSnapshotHash,
    expectedTargetExistenceStatus: review.targetExistenceStatus, expectedTargetCount: review.currentTargetCount,
    numberReservationScope: {
      documentType: 'purchase_reconciliation', legalEntityId: context.legalEntityId || '',
      ledgerBookId: context.ledgerBookId || '', sequenceScope: 'accounting_period',
    },
  })
}

export function buildPurchaseReconciliationTransactionPlan(command = {}, context = {}) {
  return buildBusinessActionTransactionPlan({
    command, transactionPolicyVersion: PURCHASE_RECONCILIATION_TRANSACTION_POLICY_VERSION,
    transactionSteps: purchaseReconciliationTransactionStepDefinitions,
    compensationSteps: purchaseReconciliationCompensationDefinitions,
    accountingPeriod: context.accountingPeriod || '',
  })
}

export function buildPurchaseReconciliationTransactionDesign(review = {}, context = {}) {
  const command = buildPurchaseReconciliationFormalGenerationCommand(review, context)
  const transactionPlan = buildPurchaseReconciliationTransactionPlan(command, context)
  return { command, transactionPlan }
}

function resultStep(definition, status, context = {}) {
  const inputHash = stableBusinessActionTransactionHash({ stepCode: definition.stepCode, transactionPlanId: context.transactionPlanId })
  return {
    ...definition, status, inputHash,
    outputHash: status === 'succeeded' ? stableBusinessActionTransactionHash({ inputHash, status, isolated: true }) : '',
    failureCode: status === 'failed' || status === 'blocked' ? definition.failureCode : '',
    simulationArtifactWriteCount: status === 'succeeded' && ['numbering', 'staging', 'commit'].includes(definition.phase) ? 1 : 0,
  }
}

function compensationResults(completedSteps, failureAtStep, rollbackFailureAt = '') {
  return [...completedSteps].reverse().filter((item) => item.compensationCode).map((item, index) => {
    const failed = item.compensationCode === rollbackFailureAt
    return {
      compensationCode: item.compensationCode, originalStepCode: item.stepCode, sequence: index + 1,
      status: failed ? 'compensation_failed' : 'compensated', actual: failed ? 'residual_present' : 'removed',
      expected: 'removed', residualCount: failed ? 1 : 0,
      errorCode: failed ? `${item.compensationCode}_FAILED` : '', failureAtStep,
    }
  })
}

function blockedResult({ command, transactionPlan, reasonCode, existingTargetNos = [], sourceChanged = false }) {
  const executedSteps = purchaseReconciliationTransactionStepDefinitions.map((definition, index) => resultStep(definition, index === 0 ? 'blocked' : 'not_started', transactionPlan))
  return sealBusinessActionTransactionResult({
    command, transactionPlan, transactionState: 'transaction_blocked', outcome: 'blocked', committed: false, rolledBack: false,
    commitUnknown: false, requiresRecovery: false, requiresManualIntervention: false, blockingReasonCodes: [reasonCode],
    existingTargetNos, sourceChanged, executedSteps, compensationResults: [], residualBusinessEntityCount: 0,
    numberReservationStatus: 'not_reserved', simulatedFormalTargetNo: '', idempotencyStatus: 'not_found', lockStatus: 'not_acquired',
    formalExecutionAllowed: false, resultSource: 'new_transaction_result', ...zeroWrites(),
  })
}

export function executePurchaseReconciliationIsolatedTransaction(input = {}) {
  const review = input.review || {}
  const { command, transactionPlan } = buildPurchaseReconciliationTransactionDesign(review, input.context)
  const reviewIntegrity = validatePurchaseReconciliationFinalReviewIntegrity(review)
  if (review.reviewDecision !== 'approved' || review.reviewState !== 'review_passed' || !reviewIntegrity.integrityValid) {
    return blockedResult({ command, transactionPlan, reasonCode: !reviewIntegrity.integrityValid ? 'PRC_TX_FINAL_REVIEW_INTEGRITY_INVALID' : `PRC_TX_FINAL_REVIEW_${String(review.reviewState || 'MISSING').toUpperCase()}` })
  }
  if (input.currentSourceSnapshotHash && input.currentSourceSnapshotHash !== command.expectedSourceSnapshotHash) {
    return blockedResult({ command, transactionPlan, reasonCode: 'PRC_TX_SOURCE_SNAPSHOT_CHANGED', sourceChanged: true })
  }
  const targets = input.currentTargetEvidence || []
  if (targets.length) return blockedResult({ command, transactionPlan, reasonCode: targets.length === 1 ? 'PRC_TX_EXISTING_TARGET' : 'PRC_TX_MULTIPLE_TARGETS', existingTargetNos: targets.map((item) => item.targetNo) })
  if (input.lockConflict) {
    const executedSteps = purchaseReconciliationTransactionStepDefinitions.map((definition) => resultStep(definition, definition.stepCode === 'PRC_TX_ACQUIRE_SOURCE_LOCK' ? 'failed' : definition.sequence < 3 ? 'succeeded' : 'not_started', transactionPlan))
    return sealBusinessActionTransactionResult({ command, transactionPlan, transactionState: 'transaction_failed', outcome: 'lock_conflict', committed: false, rolledBack: false, commitUnknown: false, requiresRecovery: true, requiresManualIntervention: false, blockingReasonCodes: ['PRC_TX_SOURCE_LOCK_CONFLICT'], existingTargetNos: [], sourceChanged: false, executedSteps, compensationResults: [], residualBusinessEntityCount: 0, numberReservationStatus: 'not_reserved', simulatedFormalTargetNo: '', idempotencyStatus: 'in_progress', lockStatus: 'conflict', formalExecutionAllowed: false, resultSource: 'new_transaction_result', ...zeroWrites() })
  }
  const idem = resolveBusinessActionIdempotency({ idempotencyKey: command.idempotencyKey, records: input.idempotencyRecords || [] })
  if (idem.status === 'committed') {
    const reused = cloneBusinessActionTransactionValue(idem.record.transactionResult)
    return sealBusinessActionTransactionResult({ ...reused, resultSource: 'existing_transaction_result', idempotencyStatus: 'committed', formalExecutionAllowed: false, ...zeroWrites() })
  }
  if (['in_progress', 'commit_unknown'].includes(idem.status)) {
    return sealBusinessActionTransactionResult({ ...blockedResult({ command, transactionPlan, reasonCode: `PRC_TX_IDEMPOTENCY_${idem.status.toUpperCase()}` }), transactionState: idem.status === 'commit_unknown' ? 'commit_unknown' : 'transaction_blocked', commitUnknown: idem.status === 'commit_unknown', requiresRecovery: idem.status === 'commit_unknown', idempotencyStatus: idem.status })
  }
  if (input.numberCollision) {
    const executedSteps = purchaseReconciliationTransactionStepDefinitions.map((definition) => resultStep(definition, definition.sequence < 8 ? 'succeeded' : definition.sequence === 8 ? 'failed' : 'not_started', transactionPlan))
    return sealBusinessActionTransactionResult({ command, transactionPlan, transactionState: 'transaction_failed', outcome: 'number_collision', committed: false, rolledBack: false, commitUnknown: false, requiresRecovery: false, requiresManualIntervention: false, blockingReasonCodes: ['PRC_TX_NUMBER_RESERVATION_CONFLICT'], existingTargetNos: [], sourceChanged: false, executedSteps, compensationResults: [], residualBusinessEntityCount: 0, numberReservationStatus: 'conflict', simulatedFormalTargetNo: '', idempotencyStatus: 'failed_retryable', lockStatus: 'released', formalExecutionAllowed: false, resultSource: 'new_transaction_result', ...zeroWrites() })
  }
  const reservationValidation = validateBusinessDocumentNumberReservation(transactionPlan.numberReservationPlan)
  if (!reservationValidation.valid) throw new Error('invalid isolated number reservation plan')
  const failureAtStep = input.failureAtStep || ''
  const completed = []
  const executedSteps = []
  for (const definition of purchaseReconciliationTransactionStepDefinitions) {
    if (failureAtStep && definition.stepCode === failureAtStep) {
      executedSteps.push(resultStep(definition, 'failed', transactionPlan))
      for (const rest of purchaseReconciliationTransactionStepDefinitions.slice(definition.sequence)) executedSteps.push(resultStep(rest, 'not_started', transactionPlan))
      break
    }
    executedSteps.push(resultStep(definition, 'succeeded', transactionPlan))
    completed.push(definition)
  }
  if (input.commitAcknowledgementLoss || failureAtStep === 'PRC_TX_COMMIT_ACKNOWLEDGEMENT_LOSS') {
    return sealBusinessActionTransactionResult({ command, transactionPlan, transactionState: 'commit_unknown', outcome: 'unknown', committed: false, rolledBack: false, commitUnknown: true, requiresRecovery: true, requiresManualIntervention: false, blockingReasonCodes: ['PRC_TX_COMMIT_ACKNOWLEDGEMENT_LOST'], existingTargetNos: [], sourceChanged: false, executedSteps, compensationResults: [], residualBusinessEntityCount: 0, numberReservationStatus: 'consumed', simulatedFormalTargetNo: transactionPlan.numberReservationPlan.simulatedReservationResult, idempotencyStatus: 'commit_unknown', lockStatus: 'retained_for_recovery', formalExecutionAllowed: false, resultSource: 'new_transaction_result', recoveryEvidence: { idempotencyStatus: 'committed', targets: [{ sourceKey: command.sourceKey, reviewId: command.reviewId, reviewHash: command.reviewHash, targetNo: transactionPlan.numberReservationPlan.simulatedReservationResult }], numberReservationStatus: 'consumed', sourceTargetRelationPresent: true, auditRecordPresent: true, integrityValid: true }, ...zeroWrites() })
  }
  if (failureAtStep === 'PRC_TX_RELEASE_SOURCE_LOCK') {
    return sealBusinessActionTransactionResult({
      command, transactionPlan, transactionState: 'committed', outcome: 'succeeded_with_cleanup_failure',
      committed: true, rolledBack: false, commitUnknown: false, requiresRecovery: false, requiresManualIntervention: true,
      blockingReasonCodes: ['PRC_TX_RELEASE_SOURCE_LOCK_FAILED'], existingTargetNos: [], sourceChanged: false,
      executedSteps, compensationResults: [], residualBusinessEntityCount: 0, numberReservationStatus: 'consumed',
      simulatedFormalTargetNo: transactionPlan.numberReservationPlan.simulatedReservationResult,
      idempotencyStatus: 'committed', lockStatus: 'release_failed', formalExecutionAllowed: false,
      resultSource: 'new_transaction_result', ...zeroWrites(),
    })
  }
  if (failureAtStep) {
    const compensations = compensationResults(completed, failureAtStep, input.rollbackFailureAt || '')
    const rollbackFailed = compensations.some((item) => item.status === 'compensation_failed')
    const hadReservation = completed.some((item) => item.stepCode === 'PRC_TX_RESERVE_DOCUMENT_NUMBER')
    const hadStaging = completed.some((item) => item.phase === 'staging')
    return sealBusinessActionTransactionResult({
      command, transactionPlan,
      transactionState: rollbackFailed ? 'rollback_failed' : hadReservation || hadStaging || failureAtStep === 'PRC_TX_COMMIT' ? 'rolled_back' : 'transaction_failed',
      outcome: rollbackFailed ? 'rollback_failed' : 'failed', committed: false, rolledBack: !rollbackFailed && (hadReservation || hadStaging || failureAtStep === 'PRC_TX_COMMIT'),
      commitUnknown: false, requiresRecovery: false, requiresManualIntervention: rollbackFailed,
      blockingReasonCodes: [`${failureAtStep}_FAILED`], existingTargetNos: [], sourceChanged: false, executedSteps,
      compensationResults: compensations, residualBusinessEntityCount: compensations.reduce((sum, item) => sum + item.residualCount, 0),
      numberReservationStatus: hadReservation ? 'aborted' : 'not_reserved', simulatedFormalTargetNo: hadReservation ? transactionPlan.numberReservationPlan.simulatedReservationResult : '',
      idempotencyStatus: rollbackFailed ? 'failed_terminal' : 'failed_retryable', lockStatus: rollbackFailed ? 'release_failed' : 'released',
      formalExecutionAllowed: false, resultSource: 'new_transaction_result', ...zeroWrites(),
    })
  }
  return sealBusinessActionTransactionResult({
    command, transactionPlan, transactionState: 'committed', outcome: 'succeeded', committed: true, rolledBack: false,
    commitUnknown: false, requiresRecovery: false, requiresManualIntervention: false, blockingReasonCodes: [], existingTargetNos: [], sourceChanged: false,
    executedSteps, compensationResults: [], residualBusinessEntityCount: 0, numberReservationStatus: 'consumed',
    simulatedFormalTargetNo: transactionPlan.numberReservationPlan.simulatedReservationResult, idempotencyStatus: 'committed', lockStatus: 'released',
    formalExecutionAllowed: false, resultSource: 'new_transaction_result', ...zeroWrites(),
  })
}

export function recoverPurchaseReconciliationTransactionOutcome(transactionResult = {}) {
  return recoverBusinessActionTransactionOutcome({
    ...(transactionResult.recoveryEvidence || {}), sourceKey: transactionResult.command?.sourceKey,
    expectedReviewId: transactionResult.command?.reviewId, expectedReviewHash: transactionResult.command?.reviewHash,
  })
}

export function restorePurchaseReconciliationTransactionResult(result = {}) {
  return restoreBusinessActionTransactionResult(result)
}

export function authorizePurchaseReconciliationFormalTransaction(result = {}) {
  return authorizeBusinessActionTransactionExecution({ command: result.command, plan: result.transactionPlan })
}

export function classifyPurchaseReconciliationTransactionArtifacts(artifacts = {}) {
  return classifyBusinessActionTransactionArtifacts(artifacts)
}

export function createPurchaseReconciliationIsolatedTransactionAdapter(seed = {}) {
  const snapshot = cloneBusinessActionTransactionValue({
    locks: seed.locks || [], idempotencyRecords: seed.idempotencyRecords || [],
    numberReservations: seed.numberReservations || [], stagedObjects: seed.stagedObjects || [],
    sourceTargetRelations: seed.sourceTargetRelations || [], sourceWritebacks: seed.sourceWritebacks || [],
    auditRecords: seed.auditRecords || [], commitRecords: seed.commitRecords || [], rollbackRecords: seed.rollbackRecords || [],
  })
  return Object.freeze({
    beginTransaction: (input) => executePurchaseReconciliationIsolatedTransaction({ ...input, idempotencyRecords: snapshot.idempotencyRecords }),
    acquireLock: (lockKey) => ({ acquired: !snapshot.locks.some((item) => item.lockKey === lockKey && item.status === 'acquired'), lockKey, isolated: true }),
    checkIdempotency: (idempotencyKey) => resolveBusinessActionIdempotency({ idempotencyKey, records: snapshot.idempotencyRecords }),
    reserveNumber: (plan) => ({ reserved: validateBusinessDocumentNumberReservation(plan).valid, reservationKey: plan.numberReservationKey, simulatedNumber: plan.simulatedReservationResult, formalNumberAllocated: false }),
    stageFormalObject: (value) => ({ staged: true, isolated: true, artifactHash: stableBusinessActionTransactionHash(value) }),
    stageSourceTargetRelation: (value) => ({ staged: true, isolated: true, artifactHash: stableBusinessActionTransactionHash(value) }),
    stageSourceWriteback: (value) => ({ staged: true, isolated: true, artifactHash: stableBusinessActionTransactionHash(value) }),
    stageAuditRecord: (value) => ({ staged: true, isolated: true, artifactHash: stableBusinessActionTransactionHash(value) }),
    commit: (input) => ({ committed: true, isolated: true, copyOnWrite: true, transactionPlanId: input.transactionPlanId }),
    rollback: (input) => ({ rolledBack: true, isolated: true, compensationResults: cloneBusinessActionTransactionValue(input.compensationResults || []) }),
    recoverCommitOutcome: recoverPurchaseReconciliationTransactionOutcome,
    releaseLock: (lockKey) => ({ released: true, lockKey, isolated: true }),
    snapshot: () => cloneBusinessActionTransactionValue(snapshot),
  })
}

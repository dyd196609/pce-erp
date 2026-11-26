import { buildBusinessExecutionGate, buildTransactionCapabilityGate, authorizeControlledBusinessExecution } from '../core/action-transaction/businessActionDualGate.js'
import { createCanaryIsolatedPersistenceAdapter, createDisabledProductionPersistenceAdapter } from '../core/action-transaction/businessActionPersistenceAdapters.js'
import { stableBusinessActionTransactionHash, cloneBusinessActionTransactionValue } from '../core/action-transaction/businessActionTransactionIntegrity.js'
import { buildPurchaseReconciliationTransactionDesign } from './purchaseReconciliationFormalGenerationTransaction.js'

export const PURCHASE_RECONCILIATION_CONTROLLED_VERSION = 'V1.14.2.8.4.7.40'
export const CONTROLLED_GENERATION_WRITE_STEPS = [
  'PRC_CONTROLLED_WRITE_IDEMPOTENCY', 'PRC_CONTROLLED_RESERVE_NUMBER', 'PRC_CONTROLLED_WRITE_FORMAL_OBJECT',
  'PRC_CONTROLLED_WRITE_SOURCE_TARGET_RELATION', 'PRC_CONTROLLED_WRITE_SOURCE_BACK_REFERENCE',
  'PRC_CONTROLLED_WRITE_AUDIT', 'PRC_CONTROLLED_VALIDATE_STAGED_STATE', 'PRC_CONTROLLED_COMMIT_COPY_ON_WRITE',
  'PRC_CONTROLLED_MARK_IDEMPOTENCY_COMMITTED', 'PRC_CONTROLLED_MARK_NUMBER_CONSUMED', 'PRC_CONTROLLED_RELEASE_SOURCE_LOCK',
]

export function validateTrustedCanaryExecutionContext(input = {}) {
  const record = input.runnerContextRecord || {}
  const trusted = Boolean(input.canaryBatchId) && record.controlledByRunner === true
    && record.canaryBatchId === input.canaryBatchId && record.adapterType === 'canary_isolated'
    && record.environmentFlag === 'PCE_CONTROLLED_CANARY_EXECUTION' && Boolean(record.storageStateId)
  return { trustedExecutionContext: trusted, adapterType: trusted ? 'canary_isolated' : 'untrusted', productionFormalExecutionEnabled: false, denialCodes: trusted ? [] : ['CONTROLLED_EXECUTION_UNTRUSTED_CONTEXT'] }
}

export function buildPurchaseReconciliationFormalEquivalentObject({ review, command, transactionPlan, numberReservation, source, infrastructureMetadata = {} } = {}) {
  const core = {
    reconciliationNo: numberReservation.number, status: 'draft', sourceKey: command.sourceKey,
    sourceSupplierSettlementNo: command.sourceSupplierSettlementNo, sourcePayableCheckNo: source.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: source.sourcePayablePrepareNo || '', purchaseOrderNo: source.purchaseOrderNo || '',
    priceApprovalNo: source.priceApprovalNo || '', supplierId: source.supplierId || '', supplierName: source.supplierName || '',
    legalEntityId: source.legalEntityId || '', ledgerBookId: source.ledgerBookId || '', currency: source.currency || '',
    exchangeRate: Number(source.exchangeRate || 0), quantity: Number(source.quantity || 0), unit: source.unit || '',
    settlementAmount: Number(source.settlementAmount || 0), sourceCandidateId: command.sourceCandidateId,
    simulationRequestId: command.simulationRequestId, simulationResultId: command.simulationResultId,
    reviewId: review.reviewId, reviewHash: review.reviewHash, commandId: command.commandId,
    transactionPlanId: transactionPlan.transactionPlanId, idempotencyKey: command.idempotencyKey,
    numberReservationId: numberReservation.id, auditRecordId: `PRC-AUD-${stableBusinessActionTransactionHash({ commandId: command.commandId, reviewHash: review.reviewHash })}`,
  }
  const id = `PRC-EQ-${stableBusinessActionTransactionHash(core)}`
  return { id, ...core, createdInfrastructureMetadata: cloneBusinessActionTransactionValue(infrastructureMetadata), businessHash: stableBusinessActionTransactionHash({ id, ...core }) }
}

function validatePlanIntegrity(plan = {}) {
  const { planHash, ...payload } = plan
  return Boolean(planHash) && planHash === stableBusinessActionTransactionHash(payload)
}

function counts(state) {
  return {
    objectCount: state.formalObjects.length, idempotencyCount: state.idempotencyRecords.length,
    reservationCount: state.numberReservations.length, relationCount: state.sourceTargetRelations.length,
    backReferenceCount: state.sourceBackReferences.length, auditCount: state.auditRecords.length,
    commitCount: state.commitRecords.length, rollbackCount: state.rollbackRecords.length, recoveryCount: state.recoveryRecords.length,
  }
}

function executionHash(result) {
  const { executionHash: ignored, infrastructureMetadata, ...payload } = result
  return stableBusinessActionTransactionHash(payload)
}

function finish(result) {
  return { ...result, executionHash: executionHash(result) }
}

function blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes, outcome = 'blocked' }) {
  return finish({
    executionId, commandId: command.commandId, transactionPlanId: transactionPlan.transactionPlanId,
    idempotencyKey: command.idempotencyKey,
    businessGateResult, transactionGateResult, authorizationResult, transactionState: 'transaction_blocked', outcome,
    formalEquivalentObjectId: '', canaryReconciliationNo: '', idempotencyStatus: 'not_found', numberReservationStatus: 'not_reserved',
    sourceRelationStatus: 'not_written', sourceBackReferenceStatus: 'not_written', auditStatus: 'not_written', commitStatus: 'not_started', recoveryStatus: 'not_required',
    formalEquivalentObjectCountBefore: before.objectCount, formalEquivalentObjectCountAfter: before.objectCount,
    formalEquivalentObjectCountAfterRetry: before.objectCount, productionFormalObjectCount: 0, paymentObjectCount: 0, paymentVoucherCount: 0,
    supplierSettlementLifecycleStatusBefore: 'reconciling', supplierSettlementLifecycleStatusAfter: 'reconciling',
    supplierSettlementLifecycleStatusWriteCount: 0, supplierSettlementRelationWriteCount: 0,
    canaryBusinessWriteCount: 0, productionBusinessWriteCount: 0, productionFormalNumberAllocationCount: 0,
    lockAcquireCount: 0, numberReservationCount: 0, formalObjectWriteCount: 0, auditWriteCount: 0,
    denialCodes, failedStepCode: '', compensationResults: [], residualObjectCount: 0, residualRelationCount: 0,
    residualAuditCount: 0, requiresRecovery: false, requiresManualIntervention: false, safeToRetry: false,
  })
}

export function executePurchaseReconciliationControlledGeneration(input = {}) {
  const adapter = input.adapter || createDisabledProductionPersistenceAdapter()
  const state = adapter.state || { formalObjects: [], idempotencyRecords: [], numberReservations: [], sourceTargetRelations: [], sourceBackReferences: [], auditRecords: [], commitRecords: [], rollbackRecords: [], recoveryRecords: [], locks: [] }
  const before = counts(state)
  const { command, transactionPlan } = buildPurchaseReconciliationTransactionDesign(input.review, {
    legalEntityId: input.source?.legalEntityId, ledgerBookId: input.source?.ledgerBookId, accountingPeriod: input.source?.accountingPeriod,
  })
  const trusted = validateTrustedCanaryExecutionContext(input.executionContext)
  const businessGateResult = buildBusinessExecutionGate(input.review)
  const transactionGateResult = buildTransactionCapabilityGate({ adapter, transactionPlanIntegrityValid: validatePlanIntegrity(transactionPlan) })
  if (input.forceTransactionGateFailure) {
    transactionGateResult.atomicTransactionSupported = false
    transactionGateResult.passed = false
    transactionGateResult.denialCodes = ['TRANSACTION_GATE_ATOMIC_TRANSACTION_UNSUPPORTED']
  }
  const authorizationResult = authorizeControlledBusinessExecution({
    businessGateResult, transactionGateResult, trustedExecutionContext: trusted.trustedExecutionContext,
    runtimeSwitchEnabled: input.canaryRuntimeSwitchEnabled === true, explicitUserAction: input.explicitUserAction === true,
    productionMode: adapter.adapterType !== 'canary_isolated',
  })
  const executionId = `PRC-EXEC-${stableBusinessActionTransactionHash({ commandId: command.commandId, transactionPlanId: transactionPlan.transactionPlanId, gateIds: [businessGateResult.gateId, transactionGateResult.gateId] })}`
  if (!authorizationResult.allowed) return blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: authorizationResult.denialCodes })
  const lock = adapter.acquireSourceLock(command.transactionLockKey, executionId)
  if (!lock.acquired) return blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: ['PRC_CONTROLLED_SOURCE_LOCK_CONFLICT'], outcome: 'in_progress' })
  if (input.currentSourceSnapshotHash && input.currentSourceSnapshotHash !== command.expectedSourceSnapshotHash) {
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: ['PRC_CONTROLLED_SOURCE_CHANGED'] }), lockAcquireCount: 1 })
  }
  const targets = input.currentTargetEvidence || adapter.readExistingTargets(command.sourceKey)
  if (targets.length) {
    const idempotentTarget = targets.length === 1 && targets[0].idempotencyKey === command.idempotencyKey ? targets[0] : null
    if (idempotentTarget) {
      adapter.releaseSourceLock(command.transactionLockKey)
      return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: [], outcome: 'existing_result' }), transactionState: 'committed', formalEquivalentObjectId: idempotentTarget.id, canaryReconciliationNo: idempotentTarget.reconciliationNo, idempotencyStatus: 'committed', numberReservationStatus: 'consumed', sourceRelationStatus: 'written', sourceBackReferenceStatus: 'written', auditStatus: 'written', commitStatus: 'committed', formalEquivalentObjectCountAfter: before.objectCount, formalEquivalentObjectCountAfterRetry: before.objectCount, lockAcquireCount: 1 })
    }
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: [targets.length === 1 ? 'PRC_CONTROLLED_EXISTING_TARGET' : 'PRC_CONTROLLED_TARGET_CONFLICT'], outcome: targets.length === 1 ? 'existing_target' : 'conflict' }), lockAcquireCount: 1, existingTargetNos: targets.map((item) => item.reconciliationNo || item.targetNo) })
  }
  const existing = adapter.readIdempotencyRecord(command.idempotencyKey)
  if (existing?.status === 'committed') {
    const object = state.formalObjects.find((item) => item.idempotencyKey === command.idempotencyKey)
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: [], outcome: 'existing_result' }), transactionState: 'committed', formalEquivalentObjectId: object.id, canaryReconciliationNo: object.reconciliationNo, idempotencyStatus: 'committed', numberReservationStatus: 'consumed', sourceRelationStatus: 'written', sourceBackReferenceStatus: 'written', auditStatus: 'written', commitStatus: 'committed', formalEquivalentObjectCountAfter: before.objectCount, formalEquivalentObjectCountAfterRetry: before.objectCount, lockAcquireCount: 1 })
  }
  if (existing?.status === 'in_progress') return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: ['PRC_CONTROLLED_IDEMPOTENCY_IN_PROGRESS'], outcome: 'in_progress' }), lockAcquireCount: 1, idempotencyStatus: 'in_progress' })
  const working = adapter.beginTransaction()
  const failure = input.failureAtStep || ''
  const compensationResults = []
  const reservation = { id: transactionPlan.numberReservationPlan.numberReservationKey, number: transactionPlan.numberReservationPlan.simulatedReservationResult, idempotencyKey: command.idempotencyKey, status: 'reserved', reusable: false }
  const failKnown = (stepCode, hadReservation = false) => {
    if (hadReservation) {
      const aborted = { ...reservation, status: 'aborted', reusable: false }
      if (!state.numberReservations.some((item) => item.id === aborted.id)) state.numberReservations.push(aborted)
      compensationResults.push({ compensationCode: 'PRC_CONTROLLED_ABORT_NUMBER', status: 'compensated', residualCount: 0 })
    }
    if (input.rollbackFailure === true) {
      state.formalObjects.push(...working.formalObjects)
      state.sourceTargetRelations.push(...working.sourceTargetRelations)
      state.sourceBackReferences.push(...working.sourceBackReferences)
      state.auditRecords.push(...working.auditRecords)
      adapter.rollback({ executionId, failedStepCode: stepCode, status: 'failed' })
      const residual = counts(state)
      return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: [`${stepCode}_FAILED`, 'PRC_CONTROLLED_ROLLBACK_FAILED'], outcome: 'rollback_failed' }), transactionState: 'rollback_failed', idempotencyStatus: 'failed_requires_intervention', numberReservationStatus: hadReservation ? 'aborted' : 'not_reserved', commitStatus: 'rollback_failed', formalEquivalentObjectCountAfter: residual.objectCount, formalEquivalentObjectCountAfterRetry: residual.objectCount, lockAcquireCount: 1, failedStepCode: stepCode, compensationResults: [{ compensationCode: 'PRC_CONTROLLED_ROLLBACK', status: 'failed', residualCount: residual.objectCount + residual.relationCount + residual.auditCount }], residualObjectCount: residual.objectCount, residualRelationCount: residual.relationCount + residual.backReferenceCount, residualAuditCount: residual.auditCount, safeToRetry: false, requiresManualIntervention: true })
    }
    adapter.rollback({ executionId, failedStepCode: stepCode, status: 'rolled_back' })
    const after = counts(state)
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: [`${stepCode}_FAILED`], outcome: 'failed' }), transactionState: hadReservation ? 'rolled_back' : 'transaction_failed', idempotencyStatus: 'failed_retryable', numberReservationStatus: hadReservation ? 'aborted' : 'not_reserved', commitStatus: 'rolled_back', formalEquivalentObjectCountAfter: after.objectCount, formalEquivalentObjectCountAfterRetry: after.objectCount, lockAcquireCount: 1, failedStepCode: stepCode, compensationResults, safeToRetry: true })
  }
  if (failure === 'PRC_CONTROLLED_WRITE_IDEMPOTENCY') return failKnown(failure)
  adapter.createIdempotencyRecord(working, { idempotencyKey: command.idempotencyKey, status: 'in_progress', executionId })
  if (failure === 'PRC_CONTROLLED_RESERVE_NUMBER') return failKnown(failure)
  if (input.numberCollision) working.numberReservations.push({ ...reservation, idempotencyKey: 'OTHER', number: reservation.number })
  const reserved = adapter.reserveDocumentNumber(working, reservation)
  if (!reserved.reserved) return failKnown('PRC_CONTROLLED_RESERVE_NUMBER')
  if (failure === 'PRC_CONTROLLED_WRITE_FORMAL_OBJECT') return failKnown(failure, true)
  const formalObject = buildPurchaseReconciliationFormalEquivalentObject({ review: input.review, command, transactionPlan, numberReservation: reservation, source: input.source || {}, infrastructureMetadata: input.infrastructureMetadata || {} })
  adapter.writeFormalObject(working, formalObject)
  if (failure === 'PRC_CONTROLLED_WRITE_SOURCE_TARGET_RELATION') return failKnown(failure, true)
  const relation = { id: `PRC-REL-${stableBusinessActionTransactionHash({ sourceKey: command.sourceKey, targetId: formalObject.id })}`, sourceKey: command.sourceKey, targetId: formalObject.id, targetNo: formalObject.reconciliationNo }
  adapter.writeSourceTargetRelation(working, relation)
  if (failure === 'PRC_CONTROLLED_WRITE_SOURCE_BACK_REFERENCE') return failKnown(failure, true)
  adapter.writeSourceRelationBackReference(working, { sourceSupplierSettlementNo: command.sourceSupplierSettlementNo, purchaseReconciliationId: formalObject.id, purchaseReconciliationNo: formalObject.reconciliationNo, sourceTargetRelationId: relation.id, targetExistenceStatus: 'single_target', lifecycleStatusBefore: 'reconciling', lifecycleStatusAfter: 'reconciling' })
  if (failure === 'PRC_CONTROLLED_WRITE_AUDIT') return failKnown(failure, true)
  adapter.writeAuditRecord(working, { id: formalObject.auditRecordId, executionId, reviewId: input.review.reviewId, reviewHash: input.review.reviewHash, commandId: command.commandId, transactionPlanId: transactionPlan.transactionPlanId })
  if (failure === 'PRC_CONTROLLED_VALIDATE_STAGED_STATE' || !adapter.validateStagedState(working).valid) return failKnown('PRC_CONTROLLED_VALIDATE_STAGED_STATE', true)
  if (failure === 'PRC_CONTROLLED_COMMIT_COPY_ON_WRITE') return failKnown(failure, true)
  working.commitRecords.push({ executionId, status: 'committed' })
  working.idempotencyRecords.find((item) => item.idempotencyKey === command.idempotencyKey).status = 'committed'
  working.numberReservations.find((item) => item.id === reservation.id).status = 'consumed'
  if (input.partialCommit === true) {
    state.formalObjects.push(cloneBusinessActionTransactionValue(formalObject))
    state.numberReservations.push(cloneBusinessActionTransactionValue({ ...reservation, status: 'consumed' }))
    const after = counts(state)
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: ['PRC_CONTROLLED_PARTIAL_COMMIT'], outcome: 'partial_commit_requires_intervention' }), transactionState: 'partial_commit_requires_intervention', idempotencyStatus: 'missing', numberReservationStatus: 'consumed', commitStatus: 'partial', formalEquivalentObjectId: formalObject.id, canaryReconciliationNo: formalObject.reconciliationNo, formalEquivalentObjectCountAfter: after.objectCount, formalEquivalentObjectCountAfterRetry: after.objectCount, lockAcquireCount: 1, residualObjectCount: after.objectCount, residualRelationCount: 0, residualAuditCount: 0, requiresRecovery: true, requiresManualIntervention: true, safeToRetry: false })
  }
  if (input.commitAcknowledgementLoss === 'not_committed') {
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: ['PRC_CONTROLLED_COMMIT_ACK_LOST'], outcome: 'unknown' }), transactionState: 'commit_unknown', idempotencyStatus: 'commit_unknown', numberReservationStatus: 'reserved', commitStatus: 'unknown', requiresRecovery: true, lockAcquireCount: 1 })
  }
  adapter.commit(working)
  if (failure === 'PRC_CONTROLLED_MARK_IDEMPOTENCY_COMMITTED' || failure === 'PRC_CONTROLLED_MARK_NUMBER_CONSUMED') {
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: [`${failure}_FAILED`], outcome: 'unknown' }), transactionState: 'commit_unknown', idempotencyStatus: 'commit_unknown', numberReservationStatus: 'consumed', commitStatus: 'unknown', requiresRecovery: true, formalEquivalentObjectId: formalObject.id, canaryReconciliationNo: formalObject.reconciliationNo, formalEquivalentObjectCountAfter: state.formalObjects.length, formalEquivalentObjectCountAfterRetry: state.formalObjects.length, lockAcquireCount: 1, failedStepCode: failure })
  }
  if (input.commitAcknowledgementLoss === 'committed') {
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: ['PRC_CONTROLLED_COMMIT_ACK_LOST'], outcome: 'unknown' }), transactionState: 'commit_unknown', idempotencyStatus: 'commit_unknown', numberReservationStatus: 'consumed', commitStatus: 'unknown', requiresRecovery: true, formalEquivalentObjectId: formalObject.id, canaryReconciliationNo: formalObject.reconciliationNo, formalEquivalentObjectCountAfter: state.formalObjects.length, formalEquivalentObjectCountAfterRetry: state.formalObjects.length, lockAcquireCount: 1 })
  }
  if (failure === 'PRC_CONTROLLED_RELEASE_SOURCE_LOCK') {
    return finish({ ...blockedBase({ executionId, command, transactionPlan, businessGateResult, transactionGateResult, authorizationResult, before, denialCodes: [`${failure}_FAILED`], outcome: 'succeeded_with_cleanup_failure' }), transactionState: 'committed', idempotencyStatus: 'committed', numberReservationStatus: 'consumed', sourceRelationStatus: 'written', sourceBackReferenceStatus: 'written', auditStatus: 'written', commitStatus: 'committed', requiresManualIntervention: true, formalEquivalentObjectId: formalObject.id, canaryReconciliationNo: formalObject.reconciliationNo, formalEquivalentObjectCountAfter: state.formalObjects.length, formalEquivalentObjectCountAfterRetry: state.formalObjects.length, lockAcquireCount: 1, numberReservationCount: 1, formalObjectWriteCount: 1, auditWriteCount: 1, supplierSettlementRelationWriteCount: 1, canaryBusinessWriteCount: 4, failedStepCode: failure })
  }
  adapter.releaseSourceLock(command.transactionLockKey)
  return finish({
    executionId, commandId: command.commandId, transactionPlanId: transactionPlan.transactionPlanId, idempotencyKey: command.idempotencyKey,
    businessGateResult, transactionGateResult, authorizationResult, transactionState: 'committed', outcome: 'succeeded',
    formalEquivalentObjectId: formalObject.id, canaryReconciliationNo: formalObject.reconciliationNo,
    idempotencyStatus: 'committed', numberReservationStatus: 'consumed', sourceRelationStatus: 'written', sourceBackReferenceStatus: 'written',
    auditStatus: 'written', commitStatus: 'committed', recoveryStatus: 'not_required',
    formalEquivalentObjectCountBefore: before.objectCount, formalEquivalentObjectCountAfter: state.formalObjects.length,
    formalEquivalentObjectCountAfterRetry: state.formalObjects.length, productionFormalObjectCount: 0, paymentObjectCount: 0, paymentVoucherCount: 0,
    supplierSettlementLifecycleStatusBefore: 'reconciling', supplierSettlementLifecycleStatusAfter: 'reconciling',
    supplierSettlementLifecycleStatusWriteCount: 0, supplierSettlementRelationWriteCount: 1,
    canaryBusinessWriteCount: 4, productionBusinessWriteCount: 0, productionFormalNumberAllocationCount: 0,
    lockAcquireCount: 1, numberReservationCount: 1, formalObjectWriteCount: 1, auditWriteCount: 1,
    denialCodes: [], failedStepCode: '', compensationResults: [], residualObjectCount: 0, residualRelationCount: 0,
    residualAuditCount: 0, requiresRecovery: false, requiresManualIntervention: false, safeToRetry: false,
  })
}

export function recoverPurchaseReconciliationControlledGeneration({ adapter, result } = {}) {
  const expectedHash = executionHash(result || {})
  if (!result?.executionHash || result.executionHash !== expectedHash) return { classification: 'integrity_failed', productionFormalObjectCount: 0, productionFormalNumberAllocationCount: 0, automaticRetryCount: 0 }
  const recovery = adapter.recoverCommitOutcome({ idempotencyKey: result.idempotencyKey || '' })
  if (adapter.state) adapter.state.recoveryRecords.push({ executionId: result.executionId, classification: recovery.classification })
  return { ...recovery, productionFormalObjectCount: 0, productionFormalNumberAllocationCount: 0, automaticRetryCount: 0 }
}

export { createCanaryIsolatedPersistenceAdapter, createDisabledProductionPersistenceAdapter }

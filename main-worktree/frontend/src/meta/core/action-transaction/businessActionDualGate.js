import { stableBusinessActionTransactionHash } from './businessActionTransactionIntegrity.js'

export const BUSINESS_ACTION_GATE_VERSION = 'business-action-execution-gate-v1'
export const BUSINESS_TRANSACTION_GATE_VERSION = 'business-transaction-capability-gate-v1'

export function buildBusinessExecutionGate(review = {}) {
  const denialCodes = []
  if (review.reviewState !== 'review_passed') denialCodes.push('BUSINESS_GATE_REVIEW_NOT_PASSED')
  if (review.reviewDecision !== 'approved') denialCodes.push('BUSINESS_GATE_REVIEW_NOT_APPROVED')
  if (review.freshnessResult?.status !== 'fresh') denialCodes.push('BUSINESS_GATE_SOURCE_STALE')
  if (review.integrityResult !== 'valid') denialCodes.push('BUSINESS_GATE_SIMULATION_INTEGRITY_INVALID')
  if ((review.auditRequirements || []).some((item) => item.required && !item.present)) denialCodes.push('BUSINESS_GATE_AUDIT_INCOMPLETE')
  if (Number(review.currentTargetCount || 0) !== 0) denialCodes.push('BUSINESS_GATE_TARGET_EXISTS')
  if ((review.riskItems || []).some((item) => item.severity === 'fatal')) denialCodes.push('BUSINESS_GATE_FATAL_RISK')
  if ((review.unmetConditions || []).length) denialCodes.push('BUSINESS_GATE_CONDITIONS_UNMET')
  const core = {
    gateVersion: BUSINESS_ACTION_GATE_VERSION, reviewId: review.reviewId || '', reviewHash: review.reviewHash || '',
    reviewState: review.reviewState || '', reviewDecision: review.reviewDecision || '',
    sourceFreshnessValid: review.freshnessResult?.status === 'fresh', simulationIntegrityValid: review.integrityResult === 'valid',
    auditEvidenceComplete: !(review.auditRequirements || []).some((item) => item.required && !item.present),
    targetExistenceStatus: review.targetExistenceStatus || '', targetCount: Number(review.currentTargetCount || 0),
    fatalRiskCount: (review.riskItems || []).filter((item) => item.severity === 'fatal').length,
    passed: denialCodes.length === 0, denialCodes,
  }
  const gateId = `BAG-${stableBusinessActionTransactionHash(core)}`
  return { gateId, ...core, gateHash: stableBusinessActionTransactionHash({ gateId, ...core }) }
}

export function buildTransactionCapabilityGate({ adapter, transactionPlanIntegrityValid = false } = {}) {
  const capabilities = adapter?.capabilities || {}
  const checks = {
    atomicTransactionSupported: capabilities.supportsAtomicTransaction === true,
    idempotencyConstraintSupported: capabilities.supportsUniqueIdempotencyKey === true,
    sourceUniqueConstraintSupported: capabilities.supportsUniqueSourceKey === true,
    documentNumberUniqueConstraintSupported: capabilities.supportsUniqueDocumentNumber === true,
    sourceLockSupported: capabilities.supportsDurableSourceLock === true,
    commitRecoverySupported: capabilities.supportsCommitOutcomeRecovery === true,
    auditAtomicitySupported: capabilities.supportsAtomicAuditWrite === true,
    serverAuthorizationSupported: capabilities.supportsServerSideAuthorization === true,
    transactionPlanIntegrityValid: transactionPlanIntegrityValid === true,
  }
  const denialCodes = Object.entries(checks).filter(([, passed]) => !passed).map(([key]) => `TRANSACTION_GATE_${key.replace(/[A-Z]/g, (value) => `_${value}`).toUpperCase()}`)
  const core = {
    gateVersion: BUSINESS_TRANSACTION_GATE_VERSION, persistenceAdapterType: adapter?.adapterType || 'missing',
    ...checks, passed: denialCodes.length === 0, denialCodes,
  }
  const gateId = `BTG-${stableBusinessActionTransactionHash(core)}`
  return { gateId, ...core, gateHash: stableBusinessActionTransactionHash({ gateId, ...core }) }
}

export function authorizeControlledBusinessExecution(input = {}) {
  const denialCodes = []
  if (!input.businessGateResult?.passed) denialCodes.push('CONTROLLED_EXECUTION_BUSINESS_GATE_DENIED')
  if (!input.transactionGateResult?.passed) denialCodes.push('CONTROLLED_EXECUTION_TRANSACTION_GATE_DENIED')
  if (input.trustedExecutionContext !== true) denialCodes.push('CONTROLLED_EXECUTION_UNTRUSTED_CONTEXT')
  if (input.runtimeSwitchEnabled !== true) denialCodes.push('CONTROLLED_EXECUTION_RUNTIME_SWITCH_DISABLED')
  if (input.explicitUserAction !== true) denialCodes.push('CONTROLLED_EXECUTION_EXPLICIT_ACTION_REQUIRED')
  if (input.productionMode === true) denialCodes.push('BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED')
  return {
    businessGatePassed: input.businessGateResult?.passed === true,
    transactionGatePassed: input.transactionGateResult?.passed === true,
    trustedExecutionContext: input.trustedExecutionContext === true,
    runtimeSwitchEnabled: input.runtimeSwitchEnabled === true,
    explicitUserAction: input.explicitUserAction === true,
    productionMode: input.productionMode === true, allowed: denialCodes.length === 0, denialCodes,
  }
}

import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
} from './paymentVoucherPreparePrecheckContract.js'
import {
  PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
} from './paymentVoucherPreparePrecheckEngine.js'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
  paymentVoucherPrepareSimulationResultContractInternals,
} from './paymentVoucherPrepareSimulationResultContract.js'

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION = 'PVPP-SIM-LIFECYCLE-1.0.0'

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_STATUSES = [
  'not_created',
  'created',
  'calculated',
  'validated',
  'frozen',
  'invalidated',
  'superseded',
  'cancelled',
  'archived',
]

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_VALIDITY_STATUSES = [
  'unknown',
  'pending_validation',
  'valid',
  'invalid',
  'stale',
  'superseded',
  'cancelled',
]

export const PAYMENT_VOUCHER_PREPARE_SOURCE_CONSISTENCY_STATUSES = [
  'unknown',
  'matched',
  'changed',
  'no_reference',
  'source_not_found',
]

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ALLOWED_TRANSITIONS = {
  not_created: ['created'],
  created: ['calculated', 'cancelled'],
  calculated: ['validated', 'invalidated', 'cancelled'],
  validated: ['frozen', 'invalidated', 'superseded'],
  frozen: ['invalidated', 'superseded', 'archived'],
  invalidated: ['superseded', 'archived'],
  superseded: ['archived'],
  cancelled: ['archived'],
  archived: [],
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_INVALIDATION_TRIGGERS = [
  'sourceDataFingerprint',
  'requestPackageFingerprint',
  'ruleSetVersion',
  'inputContractVersion',
  'accountingTemplateVersion',
  'accountingPeriod',
  'currencyCode',
  'executionAmount',
  'paymentMethod',
  'precheckDecisionBlocked',
  'paymentExecutionPrepareCancelled',
  'formalPaymentVoucherGenerated',
  'paymentWrittenOff',
  'ledgerWritten',
  'posted',
]

const { stableStringify, stableHash } = paymentVoucherPrepareSimulationResultContractInternals

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function knownStatus(status) {
  return PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_STATUSES.includes(status)
}

function validityForLifecycle(status, currentValidityStatus = 'unknown') {
  if (status === 'created' || status === 'calculated') return 'pending_validation'
  if (status === 'validated' || status === 'frozen') return 'valid'
  if (status === 'invalidated') return 'invalid'
  if (status === 'superseded') return 'superseded'
  if (status === 'cancelled') return 'cancelled'
  if (status === 'archived') return currentValidityStatus
  return 'unknown'
}

function reasonForBlockedTransition(currentStatus, requestedStatus) {
  if (!knownStatus(currentStatus) || !knownStatus(requestedStatus)) return ['STATUS_UNKNOWN', '当前状态或请求状态未识别。']
  if (currentStatus === requestedStatus) return ['SAME_STATUS_NOT_ALLOWED', '同状态重复转换不允许。']
  if (currentStatus === 'archived') return ['ARCHIVED_IS_TERMINAL', '已归档结果为终态，不允许再转换。']
  if (currentStatus === 'invalidated' && requestedStatus === 'validated') return ['INVALIDATED_CANNOT_RETURN_VALID', '已失效结果不能回到已验证。']
  if (currentStatus === 'superseded' && requestedStatus === 'validated') return ['SUPERSEDED_CANNOT_RETURN_VALIDATED', '已替代结果不能回到已验证。']
  if (currentStatus === 'frozen' && requestedStatus === 'calculated') return ['FROZEN_CANNOT_RETURN_CALCULATED', '已冻结结果不能回到已计算。']
  if (currentStatus === 'validated' && requestedStatus === 'created') return ['VALIDATED_CANNOT_RETURN_CREATED', '已验证结果不能回到已创建。']
  return ['TRANSITION_NOT_ALLOWED', '该生命周期转换不在允许表内。']
}

export function evaluatePaymentVoucherPrepareSimulationResultLifecycleTransition(input = {}) {
  const currentStatus = input.currentStatus || input.lifecycleStatus || 'not_created'
  const requestedStatus = input.requestedStatus || 'created'
  const currentValidityStatus = input.currentValidityStatus || input.resultValidityStatus || 'unknown'
  const transitionAllowed = Boolean(
    knownStatus(currentStatus)
    && knownStatus(requestedStatus)
    && currentStatus !== requestedStatus
    && PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ALLOWED_TRANSITIONS[currentStatus]?.includes(requestedStatus),
  )
  const blockedReason = transitionAllowed ? ['TRANSITION_ALLOWED', '生命周期转换符合允许表。'] : reasonForBlockedTransition(currentStatus, requestedStatus)
  const nextStatus = transitionAllowed ? requestedStatus : currentStatus
  return {
    lifecycleVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
    currentStatus,
    requestedStatus,
    transitionEvaluated: true,
    transitionAllowed,
    transitionReasonCode: blockedReason[0],
    transitionReasonText: blockedReason[1],
    nextStatus,
    currentValidityStatus,
    nextValidityStatus: transitionAllowed ? validityForLifecycle(requestedStatus, currentValidityStatus) : currentValidityStatus,
    requiresNewResultVersion: transitionAllowed && (requestedStatus === 'superseded' || (currentStatus === 'validated' && requestedStatus === 'invalidated') || (currentStatus === 'frozen' && requestedStatus === 'invalidated')),
    modifiesExistingRecord: false,
    businessTransitionExecuted: false,
  }
}

export function createPaymentVoucherPrepareSimulationResultLifecycleSummary() {
  const legalTransitionCount = Object.values(PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ALLOWED_TRANSITIONS).reduce((sum, list) => sum + list.length, 0)
  const fingerprint = createPaymentVoucherPrepareSimulationResultLifecyclePolicyFingerprint()
  const locked = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION]
  return {
    lifecycleVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
    lifecycleStatusCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_STATUSES.length,
    validityStatusCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_VALIDITY_STATUSES.length,
    sourceConsistencyStatusCount: PAYMENT_VOUCHER_PREPARE_SOURCE_CONSISTENCY_STATUSES.length,
    legalTransitionCount,
    invalidationTriggerCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_INVALIDATION_TRIGGERS.length,
    lifecyclePolicyFingerprint: fingerprint,
    lifecyclePolicyLockedFingerprint: locked,
    lifecyclePolicyFingerprintMatched: fingerprint === locked,
    archivedTerminal: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ALLOWED_TRANSITIONS.archived.length === 0,
    validatedInPlaceOverwriteAllowed: false,
    frozenInPlaceOverwriteAllowed: false,
  }
}

function valueChanged(original = {}, current = {}, field) {
  return original[field] !== current[field]
}

export function evaluatePaymentVoucherPrepareSimulationResultInvalidationPreview(original = {}, current = {}) {
  const triggerReasons = []
  const staleFields = [
    'sourceDataFingerprint',
    'requestPackageFingerprint',
    'ruleSetVersion',
    'inputContractVersion',
    'accountingTemplateVersion',
    'accountingPeriod',
    'currencyCode',
    'executionAmount',
    'paymentMethod',
  ]
  staleFields.forEach((field) => {
    if (valueChanged(original, current, field)) triggerReasons.push({ trigger: field, recommendedValidityStatus: 'stale' })
  })
  if (current.precheckDecision === 'blocked' && original.precheckDecision !== 'blocked') triggerReasons.push({ trigger: 'precheckDecisionBlocked', recommendedValidityStatus: 'invalid' })
  if (current.paymentExecutionPrepareStatus === 'cancelled') triggerReasons.push({ trigger: 'paymentExecutionPrepareCancelled', recommendedValidityStatus: 'invalid' })
  if (current.formalPaymentVoucherStatus === 'generated') triggerReasons.push({ trigger: 'formalPaymentVoucherGenerated', recommendedValidityStatus: 'invalid' })
  if (current.writeOffStatus === 'written_off') triggerReasons.push({ trigger: 'paymentWrittenOff', recommendedValidityStatus: 'invalid' })
  if (current.ledgerStatus === 'written_ledger') triggerReasons.push({ trigger: 'ledgerWritten', recommendedValidityStatus: 'invalid' })
  if (current.postingStatus === 'posted') triggerReasons.push({ trigger: 'posted', recommendedValidityStatus: 'invalid' })
  const invalidReason = triggerReasons.find((item) => item.recommendedValidityStatus === 'invalid')
  return {
    lifecycleVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
    resultInvalidationPreviewEvaluated: true,
    shouldInvalidateResultPreview: triggerReasons.length > 0,
    recommendedValidityStatus: invalidReason ? 'invalid' : (triggerReasons.length ? 'stale' : 'valid'),
    sourceConsistencyStatus: triggerReasons.length ? 'changed' : 'matched',
    invalidationTriggerCount: triggerReasons.length,
    invalidationTriggers: triggerReasons,
    actualResultInvalidated: false,
    actualBusinessObjectModified: false,
  }
}

export function evaluatePaymentVoucherPrepareSimulationResultSupersedePreview(current = {}, replacement = {}) {
  const currentReference = current.resultReferenceNo || null
  const replacementReference = replacement.resultReferenceNo || null
  const replacementAvailable = Boolean(replacementReference)
  return {
    lifecycleVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
    supersedePreviewEvaluated: true,
    currentResultReferenceNo: currentReference,
    replacementResultReferenceNo: replacementReference,
    shouldSupersedePreview: Boolean(currentReference && replacementAvailable && currentReference !== replacementReference),
    requiresNewResultVersion: Boolean(replacementAvailable),
    actualResultSuperseded: false,
    modifiesExistingRecord: false,
  }
}

export function createPaymentVoucherPrepareSimulationResultLifecyclePolicyFingerprint() {
  const payload = {
    resultContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
    ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
    inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
    lifecycleStatuses: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_STATUSES,
    validityStatuses: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_VALIDITY_STATUSES,
    sourceConsistencyStatuses: PAYMENT_VOUCHER_PREPARE_SOURCE_CONSISTENCY_STATUSES,
    allowedTransitions: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ALLOWED_TRANSITIONS,
    invalidTransitions: [
      'archived-return',
      'invalidated-return-valid',
      'superseded-return-validated',
      'frozen-return-calculated',
      'validated-return-created',
      'same-status',
    ],
    invalidationTriggers: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_INVALIDATION_TRIGGERS,
    supersedePrinciple: 'new_result_version_required',
    archivePrinciple: 'terminal_status',
  }
  return `PVPP-SIM-LIFECYCLE-POLICY-FP-${stableHash(payload)}`
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT = createPaymentVoucherPrepareSimulationResultLifecyclePolicyFingerprint()

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION]: 'PVPP-SIM-LIFECYCLE-POLICY-FP-409774B4',
}

export function verifyPaymentVoucherPrepareSimulationResultLifecyclePurity(input = {}) {
  const before = stableStringify(input)
  const first = evaluatePaymentVoucherPrepareSimulationResultLifecycleTransition(input)
  const second = evaluatePaymentVoucherPrepareSimulationResultLifecycleTransition(clone(input))
  const after = stableStringify(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: before !== after,
    businessTransitionExecuted: false,
    modifiesExistingRecord: false,
    resultInvalidated: false,
    resultSuperseded: false,
    resultArchived: false,
    businessDataWritten: false,
  }
}

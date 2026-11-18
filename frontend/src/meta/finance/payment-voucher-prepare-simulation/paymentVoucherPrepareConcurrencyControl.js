import {
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
} from './paymentVoucherPrepareSimulationRequestPackage.js'

export const PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION = 'PVPP-CONCURRENCY-1.0.0'

export const PAYMENT_VOUCHER_PREPARE_LOCK_SCOPE_FIELDS = [
  'requestPackageContractVersion',
  'operationType',
  'legalEntityId',
  'accountingBookId',
  'paymentExecutionPrepareNo',
]

export const PAYMENT_VOUCHER_PREPARE_LOCK_STATUS = [
  'active',
  'released',
  'expired',
  'unknown',
]

export const PAYMENT_VOUCHER_PREPARE_CONCURRENCY_STATUS = [
  'lock_available_preview',
  'same_request_in_flight_preview',
  'other_request_conflict_preview',
  'expired_lock_recoverable_preview',
  'no_runtime_state',
  'incomplete',
  'source_not_found',
  'invalid',
]

export const PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_MANIFEST = {
  concurrencyVersion: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
  requestPackageContractVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
  lockScopeFields: PAYMENT_VOUCHER_PREPARE_LOCK_SCOPE_FIELDS,
  lockStatusEnum: PAYMENT_VOUCHER_PREPARE_LOCK_STATUS,
  concurrencyStatusEnum: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_STATUS,
  excludedFields: [
    'sourceDataFingerprint',
    'accountingTemplateVersion',
    'accountingPeriod',
    'transportRequestId',
    'requestedAt',
    'requesterId',
    'pageVersion',
    'randomValue',
  ],
  priority: [
    'source_not_found',
    'incomplete',
    'no_runtime_state',
    'same_request_in_flight_preview',
    'other_request_conflict_preview',
    'expired_lock_recoverable_preview',
    'lock_available_preview',
  ],
  businessMeaning: '并发锁范围用于阻止同一法人、账套、付款执行准备和操作类型被并行模拟。',
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function stableStringify(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`
  if (typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function stableHash(value) {
  const text = typeof value === 'string' ? value : stableStringify(value)
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = (hash * 16777619) >>> 0
  }
  return hash.toString(16).toUpperCase().padStart(8, '0').slice(0, 8)
}

function isBlank(value) {
  return value === null || value === undefined || value === ''
}

function asPackage(input = {}) {
  if (input && Object.prototype.hasOwnProperty.call(input, 'requestPackage')) return input.requestPackage
  return input || {}
}

export function createPaymentVoucherPrepareLockScopeMaterial(input = {}) {
  const requestPackage = asPackage(input)
  const sourceFound = Boolean(input?.sourceFound !== false && requestPackage?.paymentExecutionPrepareNo)
  if (!sourceFound) {
    return {
      concurrencyVersion: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
      sourceFound: false,
      lockScopeMaterialPreviewGenerated: false,
      material: null,
      requiredFieldCount: PAYMENT_VOUCHER_PREPARE_LOCK_SCOPE_FIELDS.length,
      presentRequiredFieldCount: 0,
      missingRequiredFieldCount: PAYMENT_VOUCHER_PREPARE_LOCK_SCOPE_FIELDS.length,
      missingRequiredFields: PAYMENT_VOUCHER_PREPARE_LOCK_SCOPE_FIELDS,
      inputMutated: false,
    }
  }
  const material = PAYMENT_VOUCHER_PREPARE_LOCK_SCOPE_FIELDS.map((field) => ({
    field,
    value: field === 'requestPackageContractVersion'
      ? (input.requestPackageContractVersion || PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION)
      : requestPackage[field],
  }))
  const missingRequiredFields = material.filter((item) => isBlank(item.value) || item.value === 'unknown').map((item) => item.field)
  return {
    concurrencyVersion: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
    sourceFound: true,
    lockScopeMaterialPreviewGenerated: true,
    material,
    requiredFieldCount: PAYMENT_VOUCHER_PREPARE_LOCK_SCOPE_FIELDS.length,
    presentRequiredFieldCount: PAYMENT_VOUCHER_PREPARE_LOCK_SCOPE_FIELDS.length - missingRequiredFields.length,
    missingRequiredFieldCount: missingRequiredFields.length,
    missingRequiredFields,
    inputMutated: false,
  }
}

export function createPaymentVoucherPrepareLockScopeKey(input = {}) {
  const before = stableStringify(input)
  const materialResult = createPaymentVoucherPrepareLockScopeMaterial(input)
  if (!materialResult.sourceFound) {
    return {
      concurrencyVersion: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
      sourceFound: false,
      lockScopeMaterialPreviewGenerated: false,
      lockScopeKeyPreviewGenerated: false,
      lockScopeKey: null,
      missingRequiredFieldCount: materialResult.missingRequiredFieldCount,
      missingRequiredFields: materialResult.missingRequiredFields,
      sourceFingerprintExcluded: true,
      accountingPeriodExcluded: true,
      runtimeFieldsExcluded: true,
      inputMutated: before !== stableStringify(input),
    }
  }
  const key = materialResult.missingRequiredFieldCount === 0 ? `PVPP-LOCK-SCOPE-${stableHash(materialResult.material)}` : null
  return {
    concurrencyVersion: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
    sourceFound: true,
    lockScopeMaterialPreviewGenerated: true,
    lockScopeKeyPreviewGenerated: Boolean(key),
    lockScopeKey: key,
    missingRequiredFieldCount: materialResult.missingRequiredFieldCount,
    missingRequiredFields: materialResult.missingRequiredFields,
    sourceFingerprintExcluded: true,
    accountingPeriodExcluded: true,
    runtimeFieldsExcluded: true,
    inputMutated: before !== stableStringify(input),
  }
}

export function evaluatePaymentVoucherPrepareConcurrencyPreview(input = {}, runtimeState = null, idempotencyKey = null) {
  const keyResult = createPaymentVoucherPrepareLockScopeKey(input)
  if (!keyResult.sourceFound) {
    return {
      ...baseConcurrencyResult(keyResult),
      sourceFound: false,
      concurrencyPreviewEvaluated: false,
      concurrencyStatus: 'source_not_found',
    }
  }
  if (!keyResult.lockScopeKeyPreviewGenerated) {
    return {
      ...baseConcurrencyResult(keyResult),
      concurrencyStatus: 'incomplete',
    }
  }
  if (!runtimeState || runtimeState.runtimeStateAvailable !== true || !Array.isArray(runtimeState.activeLockRecords)) {
    return {
      ...baseConcurrencyResult(keyResult),
      runtimeStateAvailable: false,
      concurrencyStatus: 'no_runtime_state',
    }
  }

  const lockRecords = runtimeState.activeLockRecords
  const scopedLocks = lockRecords.filter((record) => record.lockScopeKey === keyResult.lockScopeKey && record.active !== false)
  const activeLocks = scopedLocks.filter((record) => record.lockStatus === 'active' && record.expired !== true)
  const expiredLocks = scopedLocks.filter((record) => record.expired === true || record.lockStatus === 'expired')
  const sameIdempotencyLocks = activeLocks.filter((record) => idempotencyKey && record.holderIdempotencyKey === idempotencyKey)
  const otherConflictLocks = activeLocks.filter((record) => !idempotencyKey || record.holderIdempotencyKey !== idempotencyKey)
  const status = sameIdempotencyLocks.length
    ? 'same_request_in_flight_preview'
    : otherConflictLocks.length
      ? 'other_request_conflict_preview'
      : expiredLocks.length
        ? 'expired_lock_recoverable_preview'
        : 'lock_available_preview'
  return {
    ...baseConcurrencyResult(keyResult),
    runtimeStateAvailable: true,
    activeRequestCount: Array.isArray(runtimeState.activeRequestRecords) ? runtimeState.activeRequestRecords.length : 0,
    activeLockCount: activeLocks.length,
    expiredLockCount: expiredLocks.length,
    sameIdempotencyRequestCount: sameIdempotencyLocks.length,
    otherRequestConflictCount: otherConflictLocks.length,
    concurrencyStatus: status,
    canAcquireLockPreview: status === 'lock_available_preview',
    shouldReuseExistingRequestPreview: status === 'same_request_in_flight_preview',
    shouldBlockNewRequestPreview: status === 'other_request_conflict_preview',
    recoverableExpiredLockPreview: status === 'expired_lock_recoverable_preview',
    actualLockAcquired: false,
    businessConcurrencyMechanismReady: false,
  }
}

function baseConcurrencyResult(keyResult) {
  return {
    concurrencyVersion: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
    sourceFound: true,
    concurrencyPreviewEvaluated: true,
    lockScopeMaterialPreviewGenerated: keyResult.lockScopeMaterialPreviewGenerated,
    lockScopeKeyPreviewGenerated: keyResult.lockScopeKeyPreviewGenerated,
    lockScopeKey: keyResult.lockScopeKey,
    runtimeStateAvailable: false,
    activeRequestCount: 0,
    activeLockCount: 0,
    expiredLockCount: 0,
    sameIdempotencyRequestCount: 0,
    otherRequestConflictCount: 0,
    concurrencyStatus: 'invalid',
    canAcquireLockPreview: false,
    shouldReuseExistingRequestPreview: false,
    shouldBlockNewRequestPreview: false,
    recoverableExpiredLockPreview: false,
    actualLockAcquired: false,
    businessConcurrencyMechanismReady: false,
    keyPreview: keyResult,
  }
}

export function createPaymentVoucherPrepareConcurrencyPolicyFingerprint(policy = PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_MANIFEST) {
  return `PVPP-CONCURRENCY-POLICY-FP-${stableHash(policy)}`
}

export const PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT = createPaymentVoucherPrepareConcurrencyPolicyFingerprint()

export const PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION]: 'PVPP-CONCURRENCY-POLICY-FP-00E92740',
}

export function verifyPaymentVoucherPrepareConcurrencyPurity(input = {}) {
  const before = stableStringify(input)
  const first = evaluatePaymentVoucherPrepareConcurrencyPreview(input, null, null)
  const second = evaluatePaymentVoucherPrepareConcurrencyPreview(clone(input), null, null)
  const after = stableStringify(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    sameInputSameLockScopeKey: first.lockScopeKey === second.lockScopeKey,
    inputMutated: before !== after,
    actualLockAcquired: false,
    lockRecordCreated: false,
    lockReleased: false,
    businessDataWritten: false,
    stateMachineStarted: false,
  }
}

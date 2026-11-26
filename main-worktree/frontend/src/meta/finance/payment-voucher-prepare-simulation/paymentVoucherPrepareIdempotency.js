import {
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
} from './paymentVoucherPrepareSimulationRequestPackage.js'

export const PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION = 'PVPP-IDEMPOTENCY-1.0.0'

export const PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUIRED_FIELDS = [
  'requestPackageContractVersion',
  'operationType',
  'legalEntityId',
  'accountingBookId',
  'paymentExecutionPrepareNo',
  'sourceDataFingerprint',
  'ruleSetVersion',
  'inputContractVersion',
  'accountingTemplateVersion',
  'accountingPeriod',
  'currencyCode',
]

export const PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUEST_STATUS = [
  'pending',
  'processing',
  'completed',
  'failed',
  'cancelled',
  'unknown',
]

export const PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_RESULT_STATUS = [
  'not_created',
  'valid',
  'invalid',
  'superseded',
  'frozen',
  'cancelled',
  'unknown',
]

export const PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_RESOLUTION_STATUS = [
  'no_registry',
  'incomplete_key',
  'new_request_preview',
  'processing_duplicate_preview',
  'reuse_completed_preview',
  'conflict_preview',
  'source_not_found',
  'invalid',
]

export const PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_MANIFEST = {
  idempotencyVersion: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
  requestPackageContractVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
  requiredFields: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUIRED_FIELDS,
  requestStatusEnum: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUEST_STATUS,
  resultStatusEnum: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_RESULT_STATUS,
  resolutionStatusEnum: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_RESOLUTION_STATUS,
  excludedFields: [
    'transportRequestId',
    'requestedAt',
    'requesterId',
    'pageVersion',
    'routeUrl',
    'buttonState',
    'currentTime',
    'randomValue',
    'displayText',
  ],
  priority: [
    'source_not_found',
    'incomplete_key',
    'no_registry',
    'processing_duplicate_preview',
    'reuse_completed_preview',
    'conflict_preview',
    'new_request_preview',
  ],
  businessMeaning: '业务幂等键用于识别完全相同的付款凭证准备模拟动作，不等于传输请求号。',
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

export function createPaymentVoucherPrepareIdempotencyMaterial(input = {}) {
  const requestPackage = asPackage(input)
  const sourceFound = Boolean(input?.sourceFound !== false && requestPackage?.paymentExecutionPrepareNo)
  if (!sourceFound) {
    return {
      idempotencyVersion: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
      sourceFound: false,
      idempotencyMaterialPreviewGenerated: false,
      material: null,
      requiredFieldCount: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUIRED_FIELDS.length,
      presentRequiredFieldCount: 0,
      missingRequiredFieldCount: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUIRED_FIELDS.length,
      missingRequiredFields: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUIRED_FIELDS,
      inputMutated: false,
    }
  }
  const material = PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUIRED_FIELDS.map((field) => ({
    field,
    value: field === 'requestPackageContractVersion'
      ? (input.requestPackageContractVersion || PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION)
      : requestPackage[field],
  }))
  const missingRequiredFields = material.filter((item) => isBlank(item.value) || item.value === 'unknown').map((item) => item.field)
  return {
    idempotencyVersion: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
    sourceFound: true,
    idempotencyMaterialPreviewGenerated: true,
    material,
    requiredFieldCount: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUIRED_FIELDS.length,
    presentRequiredFieldCount: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_REQUIRED_FIELDS.length - missingRequiredFields.length,
    missingRequiredFieldCount: missingRequiredFields.length,
    missingRequiredFields,
    inputMutated: false,
  }
}

export function createPaymentVoucherPrepareIdempotencyKey(input = {}) {
  const before = stableStringify(input)
  const materialResult = createPaymentVoucherPrepareIdempotencyMaterial(input)
  if (!materialResult.sourceFound) {
    return {
      idempotencyVersion: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
      sourceFound: false,
      idempotencyMaterialPreviewGenerated: false,
      idempotencyKeyPreviewGenerated: false,
      idempotencyKeyStatus: 'source_not_found',
      idempotencyKey: null,
      requiredFieldCount: materialResult.requiredFieldCount,
      presentRequiredFieldCount: 0,
      missingRequiredFieldCount: materialResult.missingRequiredFieldCount,
      missingRequiredFields: materialResult.missingRequiredFields,
      sameInputSameKey: true,
      nonBusinessFieldsExcluded: true,
      inputMutated: before !== stableStringify(input),
      businessIdempotencyMechanismReady: false,
    }
  }
  const key = materialResult.missingRequiredFieldCount === 0 ? `PVPP-IDEMP-${stableHash(materialResult.material)}` : null
  const withNonBusiness = clone(input)
  if (withNonBusiness.requestPackage) {
    withNonBusiness.requestPackage.transportRequestId = 'TRANSPORT-CHANGED'
    withNonBusiness.requestPackage.requestedAt = '2099-01-01T00:00:00.000Z'
    withNonBusiness.requestPackage.requesterId = 'USER-CHANGED'
  }
  const nonBusinessMaterial = createPaymentVoucherPrepareIdempotencyMaterial(withNonBusiness)
  return {
    idempotencyVersion: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
    sourceFound: true,
    idempotencyMaterialPreviewGenerated: true,
    idempotencyKeyPreviewGenerated: Boolean(key),
    idempotencyKeyStatus: key ? 'ready_preview' : 'incomplete',
    idempotencyKey: key,
    requiredFieldCount: materialResult.requiredFieldCount,
    presentRequiredFieldCount: materialResult.presentRequiredFieldCount,
    missingRequiredFieldCount: materialResult.missingRequiredFieldCount,
    missingRequiredFields: materialResult.missingRequiredFields,
    sameInputSameKey: key ? key === `PVPP-IDEMP-${stableHash(createPaymentVoucherPrepareIdempotencyMaterial(input).material)}` : true,
    nonBusinessFieldsExcluded: stableStringify(materialResult.material) === stableStringify(nonBusinessMaterial.material),
    inputMutated: before !== stableStringify(input),
    businessIdempotencyMechanismReady: false,
  }
}

export function evaluatePaymentVoucherPrepareIdempotencyPreview(input = {}, registryRecords = null) {
  const keyResult = createPaymentVoucherPrepareIdempotencyKey(input)
  if (!keyResult.sourceFound) {
    return {
      ...baseRegistryResult(keyResult),
      idempotencyResolutionStatus: 'source_not_found',
    }
  }
  if (!keyResult.idempotencyKeyPreviewGenerated) {
    return {
      ...baseRegistryResult(keyResult),
      idempotencyResolutionStatus: 'incomplete_key',
    }
  }
  if (!Array.isArray(registryRecords)) {
    return {
      ...baseRegistryResult(keyResult),
      registryAvailable: false,
      idempotencyResolutionStatus: 'no_registry',
    }
  }

  const matching = registryRecords.filter((record) => record.idempotencyKey === keyResult.idempotencyKey)
  const activeMatching = matching.filter((record) => record.active !== false)
  const processing = activeMatching.filter((record) => record.requestStatus === 'pending' || record.requestStatus === 'processing')
  const reusableCompleted = activeMatching.filter((record) => record.requestStatus === 'completed' && record.resultStatus === 'valid' && record.reusable === true)
  const completed = activeMatching.filter((record) => record.requestStatus === 'completed')
  const conflicts = activeMatching.filter((record) => record.conflictReason || (record.requestStatus === 'completed' && record.resultStatus !== 'valid'))
  const status = processing.length
    ? 'processing_duplicate_preview'
    : reusableCompleted.length
      ? 'reuse_completed_preview'
      : conflicts.length
        ? 'conflict_preview'
        : 'new_request_preview'
  return {
    ...baseRegistryResult(keyResult),
    registryAvailable: true,
    registryRecordCount: registryRecords.length,
    matchingRecordCount: matching.length,
    activeMatchingRecordCount: activeMatching.length,
    completedMatchingRecordCount: completed.length,
    reusableMatchingRecordCount: reusableCompleted.length,
    conflictingRecordCount: conflicts.length,
    idempotencyResolutionStatus: status,
    shouldCreateNewRequestPreview: status === 'new_request_preview',
    shouldReuseExistingRequestPreview: status === 'reuse_completed_preview',
    shouldBlockDuplicateRequestPreview: status === 'processing_duplicate_preview' || status === 'conflict_preview',
    matchedRequestReferenceNo: reusableCompleted[0]?.requestReferenceNo || processing[0]?.requestReferenceNo || null,
    matchedResultReferenceNo: reusableCompleted[0]?.resultReferenceNo || null,
    businessIdempotencyMechanismReady: false,
  }
}

function baseRegistryResult(keyResult) {
  return {
    registryAvailable: false,
    registryRecordCount: 0,
    matchingRecordCount: 0,
    activeMatchingRecordCount: 0,
    completedMatchingRecordCount: 0,
    reusableMatchingRecordCount: 0,
    conflictingRecordCount: 0,
    idempotencyResolutionStatus: 'invalid',
    shouldCreateNewRequestPreview: false,
    shouldReuseExistingRequestPreview: false,
    shouldBlockDuplicateRequestPreview: false,
    matchedRequestReferenceNo: null,
    matchedResultReferenceNo: null,
    businessIdempotencyMechanismReady: false,
    keyPreview: keyResult,
  }
}

export function createPaymentVoucherPrepareIdempotencyPolicyFingerprint(policy = PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_MANIFEST) {
  return `PVPP-IDEMPOTENCY-POLICY-FP-${stableHash(policy)}`
}

export const PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT = createPaymentVoucherPrepareIdempotencyPolicyFingerprint()

export const PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION]: 'PVPP-IDEMPOTENCY-POLICY-FP-A15191B2',
}

export function verifyPaymentVoucherPrepareIdempotencyPurity(input = {}) {
  const before = stableStringify(input)
  const first = createPaymentVoucherPrepareIdempotencyKey(input)
  const second = createPaymentVoucherPrepareIdempotencyKey(clone(input))
  const after = stableStringify(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    sameInputSameKey: first.idempotencyKey === second.idempotencyKey,
    inputMutated: before !== after,
    idempotencyRegistryWritten: false,
    idempotencyKeySaved: false,
    businessDataWritten: false,
    stateMachineStarted: false,
    simulationRequestCreated: false,
  }
}

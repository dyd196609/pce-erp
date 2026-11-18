import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS,
  normalizePaymentVoucherPrepareSourceSnapshot,
} from './paymentVoucherPrepareSourceSnapshot.js'
import {
  createPaymentVoucherPrepareSourceFingerprint,
} from './paymentVoucherPrepareSourceFingerprint.js'

export const PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION = 'PVPP-CHANGE-DETECTOR-1.0.0'

export const PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION = {
  identity: 'identity',
  sourceChain: 'source_chain',
  organizationAccounting: 'organization_accounting',
  payment: 'payment',
  currency: 'currency',
  accountingTemplate: 'accounting_template',
  accountingPeriod: 'accounting_period',
  bankAccount: 'bank_account',
  businessStatus: 'business_status',
  sourceRevision: 'source_revision',
}

const classificationByField = {
  sourceObjectType: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.identity,
  paymentExecutionPrepareNo: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.identity,
  sourcePaymentInstructionPrepareNo: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceChain,
  sourcePaymentApplicationNo: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceChain,
  sourcePayableConfirmNo: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceChain,
  sourceInvoicePrepareNo: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceChain,
  sourceSettlementNo: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceChain,
  sourceChainComplete: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceChain,
  reviewStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.businessStatus,
  supplierId: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.identity,
  legalEntityId: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.organizationAccounting,
  accountingBookId: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.organizationAccounting,
  executionAmount: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.payment,
  paymentMethod: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.payment,
  plannedPaymentDate: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.payment,
  currencyCode: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  baseCurrencyCode: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  foreignCurrencyPayment: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  exchangeRateType: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  exchangeRateDate: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  exchangeRate: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  exchangeRateSource: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  currencyPrecision: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  roundingMode: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.currency,
  accountingTemplateId: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.accountingTemplate,
  accountingTemplateVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.accountingTemplate,
  accountingTemplateStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.accountingTemplate,
  accountingPeriod: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.accountingPeriod,
  accountingPeriodStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.accountingPeriod,
  enterpriseBankAccountId: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.bankAccount,
  supplierBankAccountId: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.bankAccount,
  paymentExecutionStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.businessStatus,
  paymentVoucherStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.businessStatus,
  formalPaymentVoucherStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.businessStatus,
  writeOffStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.businessStatus,
  ledgerStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.businessStatus,
  postingStatus: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.businessStatus,
  sourceRevision: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceRevision,
  sourceUpdatedAt: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceRevision,
  sourceDataVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceRevision,
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

function asSnapshotResult(input = {}) {
  if (input && Object.prototype.hasOwnProperty.call(input, 'snapshotPreviewCreated')) return input
  return normalizePaymentVoucherPrepareSourceSnapshot(input)
}

function emptyResult(changeStatus, currentSnapshotAvailable = false, currentFingerprint = null) {
  return {
    changeDetectorVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION,
    referenceSnapshotAvailable: false,
    currentSnapshotAvailable,
    changeDetectionPreviewExecuted: changeStatus !== 'source_not_found',
    changeStatus,
    referenceFingerprint: null,
    currentFingerprint,
    fingerprintMatched: false,
    changedFieldCount: 0,
    criticalChangedFieldCount: 0,
    referenceChangedFieldCount: 0,
    addedFieldCount: 0,
    removedFieldCount: 0,
    modifiedFieldCount: 0,
    changedFields: [],
    businessSourceUnchanged: false,
    shouldInvalidateSimulationResultPreview: false,
    businessChangeDetectionMechanismReady: false,
  }
}

function changedField(field, previousValue, currentValue, changeType) {
  const classification = classificationByField[field.field] || PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_CLASSIFICATION.sourceRevision
  return {
    field: field.field,
    chineseName: field.chineseName,
    previousValue,
    currentValue,
    changeType,
    critical: field.critical,
    classification,
    invalidatesSimulationResult: field.critical,
  }
}

export function detectPaymentVoucherPrepareSourceChanges(referenceSnapshotInput = null, currentSnapshotInput = null) {
  const currentSnapshotResult = asSnapshotResult(currentSnapshotInput || {})
  if (!currentSnapshotResult.sourceFound || !currentSnapshotResult.snapshotPreviewCreated || !currentSnapshotResult.snapshot) {
    return emptyResult('source_not_found', false, null)
  }
  const currentFingerprintResult = createPaymentVoucherPrepareSourceFingerprint(currentSnapshotResult)
  if (!referenceSnapshotInput) {
    return emptyResult('no_reference', true, currentFingerprintResult.sourceDataFingerprint)
  }
  const referenceSnapshotResult = asSnapshotResult(referenceSnapshotInput)
  if (!referenceSnapshotResult.sourceFound || !referenceSnapshotResult.snapshotPreviewCreated || !referenceSnapshotResult.snapshot) {
    return emptyResult('source_not_found', true, currentFingerprintResult.sourceDataFingerprint)
  }

  const referenceFingerprintResult = createPaymentVoucherPrepareSourceFingerprint(referenceSnapshotResult)
  const changedFields = []
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.forEach((field) => {
    const previousHasField = Object.prototype.hasOwnProperty.call(referenceSnapshotResult.snapshot, field.field)
    const currentHasField = Object.prototype.hasOwnProperty.call(currentSnapshotResult.snapshot, field.field)
    const previousValue = previousHasField ? referenceSnapshotResult.snapshot[field.field] : null
    const currentValue = currentHasField ? currentSnapshotResult.snapshot[field.field] : null
    if (!previousHasField && currentHasField) changedFields.push(changedField(field, null, currentValue, 'added'))
    if (previousHasField && !currentHasField) changedFields.push(changedField(field, previousValue, null, 'removed'))
    if (previousHasField && currentHasField && stableStringify(previousValue) !== stableStringify(currentValue)) {
      changedFields.push(changedField(field, previousValue, currentValue, 'modified'))
    }
  })

  const fingerprintMatched = referenceFingerprintResult.sourceDataFingerprint === currentFingerprintResult.sourceDataFingerprint
  const criticalChangedFieldCount = changedFields.filter((field) => field.critical).length
  return {
    changeDetectorVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION,
    referenceSnapshotAvailable: true,
    currentSnapshotAvailable: true,
    changeDetectionPreviewExecuted: true,
    changeStatus: changedFields.length ? 'changed' : 'unchanged',
    referenceFingerprint: referenceFingerprintResult.sourceDataFingerprint,
    currentFingerprint: currentFingerprintResult.sourceDataFingerprint,
    fingerprintMatched,
    changedFieldCount: changedFields.length,
    criticalChangedFieldCount,
    referenceChangedFieldCount: changedFields.length,
    addedFieldCount: changedFields.filter((field) => field.changeType === 'added').length,
    removedFieldCount: changedFields.filter((field) => field.changeType === 'removed').length,
    modifiedFieldCount: changedFields.filter((field) => field.changeType === 'modified').length,
    changedFields,
    businessSourceUnchanged: changedFields.length === 0,
    shouldInvalidateSimulationResultPreview: criticalChangedFieldCount > 0,
    businessChangeDetectionMechanismReady: false,
  }
}

export function summarizePaymentVoucherPrepareSourceChanges(result = {}) {
  return {
    changeStatus: result.changeStatus || 'invalid',
    changedFieldCount: result.changedFieldCount || 0,
    criticalChangedFieldCount: result.criticalChangedFieldCount || 0,
    businessSourceUnchanged: Boolean(result.businessSourceUnchanged),
    shouldInvalidateSimulationResultPreview: Boolean(result.shouldInvalidateSimulationResultPreview),
    businessChangeDetectionMechanismReady: false,
  }
}

export function verifyPaymentVoucherPrepareSourceChangeDetectorPurity(referenceSnapshot = null, currentSnapshot = {}) {
  const referenceBefore = stableStringify(referenceSnapshot)
  const currentBefore = stableStringify(currentSnapshot)
  const first = detectPaymentVoucherPrepareSourceChanges(referenceSnapshot, currentSnapshot)
  const second = detectPaymentVoucherPrepareSourceChanges(referenceSnapshot ? clone(referenceSnapshot) : null, clone(currentSnapshot))
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    referenceInputMutated: referenceBefore !== stableStringify(referenceSnapshot),
    currentInputMutated: currentBefore !== stableStringify(currentSnapshot),
    businessChangeDetectionMechanismReady: false,
  }
}


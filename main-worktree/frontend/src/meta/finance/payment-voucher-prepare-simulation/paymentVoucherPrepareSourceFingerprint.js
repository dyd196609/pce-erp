import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS,
  normalizePaymentVoucherPrepareSourceSnapshot,
} from './paymentVoucherPrepareSourceSnapshot.js'

export const PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION = 'PVPP-SOURCE-FP-1.0.0'

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
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).toUpperCase().padStart(8, '0')
}

function asSnapshotResult(input = {}) {
  if (input && Object.prototype.hasOwnProperty.call(input, 'snapshotPreviewCreated')) return input
  return normalizePaymentVoucherPrepareSourceSnapshot(input)
}

export function createPaymentVoucherPrepareSourceCanonicalPayload(input = {}) {
  const snapshotResult = asSnapshotResult(input)
  if (!snapshotResult.sourceFound || !snapshotResult.snapshotPreviewCreated || !snapshotResult.snapshot) {
    return {
      fingerprintVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
      snapshotContractVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
      sourceFound: false,
      canonicalFieldCount: 0,
      fields: [],
    }
  }
  const fields = PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS
    .filter((field) => field.includedInFingerprint)
    .map((field) => ({
      field: field.field,
      value: snapshotResult.snapshot[field.field],
    }))
  return {
    fingerprintVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
    snapshotContractVersion: snapshotResult.snapshotContractVersion,
    sourceFound: true,
    canonicalFieldCount: fields.length,
    fields,
  }
}

export function createPaymentVoucherPrepareSourceFingerprint(input = {}) {
  const before = stableStringify(input)
  const snapshotResult = asSnapshotResult(input)
  if (!snapshotResult.sourceFound || !snapshotResult.snapshotPreviewCreated || !snapshotResult.snapshot) {
    return {
      fingerprintVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
      snapshotContractVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
      sourceFound: false,
      fingerprintPreviewGenerated: false,
      fingerprintStatus: 'source_not_found',
      sourceDataFingerprint: null,
      canonicalFieldCount: 0,
      missingCriticalFieldCount: snapshotResult.missingCriticalFieldCount || 0,
      sameInputSameFingerprint: true,
      objectKeyOrderIndependent: true,
      nonBusinessFieldsExcluded: true,
      inputMutated: before !== stableStringify(input),
      businessFingerprintMechanismReady: false,
      canonicalPayload: createPaymentVoucherPrepareSourceCanonicalPayload(snapshotResult),
    }
  }
  const canonicalPayload = createPaymentVoucherPrepareSourceCanonicalPayload(snapshotResult)
  const sourceDataFingerprint = `PVPP-SOURCE-DATA-FP-${stableHash(canonicalPayload)}`
  const repeatedFingerprint = `PVPP-SOURCE-DATA-FP-${stableHash(createPaymentVoucherPrepareSourceCanonicalPayload(snapshotResult))}`
  const reversedSnapshot = {}
  Object.keys(snapshotResult.snapshot).reverse().forEach((key) => {
    reversedSnapshot[key] = snapshotResult.snapshot[key]
  })
  const reversedPayload = createPaymentVoucherPrepareSourceCanonicalPayload({ ...snapshotResult, snapshot: reversedSnapshot })
  const withNonBusiness = createPaymentVoucherPrepareSourceCanonicalPayload({
    ...snapshotResult,
    snapshot: {
      ...snapshotResult.snapshot,
      pageVersion: 'V0.00.00',
      routeUrl: '/changed-route',
      displayText: '仅展示字段',
    },
  })
  return {
    fingerprintVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
    snapshotContractVersion: snapshotResult.snapshotContractVersion,
    sourceFound: true,
    fingerprintPreviewGenerated: true,
    fingerprintStatus: snapshotResult.missingCriticalFieldCount ? 'partial_preview' : 'complete_preview',
    sourceDataFingerprint,
    canonicalFieldCount: canonicalPayload.canonicalFieldCount,
    missingCriticalFieldCount: snapshotResult.missingCriticalFieldCount,
    sameInputSameFingerprint: sourceDataFingerprint === repeatedFingerprint,
    objectKeyOrderIndependent: sourceDataFingerprint === `PVPP-SOURCE-DATA-FP-${stableHash(reversedPayload)}`,
    nonBusinessFieldsExcluded: sourceDataFingerprint === `PVPP-SOURCE-DATA-FP-${stableHash(withNonBusiness)}`,
    inputMutated: before !== stableStringify(input),
    businessFingerprintMechanismReady: false,
    canonicalPayload,
  }
}

export function verifyPaymentVoucherPrepareSourceFingerprintPurity(input = {}) {
  const frozen = clone(input)
  const before = stableStringify(input)
  const first = createPaymentVoucherPrepareSourceFingerprint(input)
  const second = createPaymentVoucherPrepareSourceFingerprint(clone(frozen))
  const after = stableStringify(input)
  return {
    sameInputSameFingerprint: first.sourceDataFingerprint === second.sourceDataFingerprint,
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: before !== after,
    objectKeyOrderIndependent: first.objectKeyOrderIndependent,
    nonBusinessFieldsExcluded: first.nonBusinessFieldsExcluded,
    businessFingerprintMechanismReady: false,
  }
}


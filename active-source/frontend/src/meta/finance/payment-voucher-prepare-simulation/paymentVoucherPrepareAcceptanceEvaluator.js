import {
  getPaymentVoucherPrepareAcceptanceManifest,
  PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION,
} from './paymentVoucherPrepareAcceptanceManifest.js'

function stableStringify(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`
  if (typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function readPath(source, path) {
  if (!path) return undefined
  return path.split('.').reduce((current, key) => {
    if (current === null || current === undefined) return undefined
    return current[key]
  }, source)
}

function valueMatches(actual, expected, mode) {
  if (mode === 'exists') return actual !== undefined && actual !== null && actual !== ''
  if (mode === 'includes') return String(actual ?? '').includes(String(expected ?? ''))
  if (mode === 'gte') return Number(actual) >= Number(expected)
  if (mode === 'lte') return Number(actual) <= Number(expected)
  if (mode === 'notEquals') return actual !== expected
  if (mode === 'equals') return actual === expected
  return actual === expected
}

function typeMatches(actual, expectedType) {
  if (!expectedType) return true
  if (expectedType === 'array') return Array.isArray(actual)
  return typeof actual === expectedType
}

export function validatePaymentVoucherPrepareAcceptanceManifest(manifest = getPaymentVoucherPrepareAcceptanceManifest()) {
  const ids = new Set()
  const failures = []
  manifest.forEach((item) => {
    if (!item.checkId) failures.push({ checkId: item.checkId, reason: 'missing_check_id' })
    if (ids.has(item.checkId)) failures.push({ checkId: item.checkId, reason: 'duplicate_check_id' })
    ids.add(item.checkId)
    if (!item.version) failures.push({ checkId: item.checkId, reason: 'missing_version' })
    if (!item.routeType) failures.push({ checkId: item.checkId, reason: 'missing_route_type' })
    if (!item.sectionId) failures.push({ checkId: item.checkId, reason: 'missing_section_id' })
    if (!item.fieldId) failures.push({ checkId: item.checkId, reason: 'missing_field_id' })
    if (!item.dataPath) failures.push({ checkId: item.checkId, reason: 'missing_data_path' })
    if (!item.failureLocationDescription) failures.push({ checkId: item.checkId, reason: 'missing_failure_location' })
    if (!item.failureRemediationHint) failures.push({ checkId: item.checkId, reason: 'missing_remediation_hint' })
  })
  return {
    manifestVersion: PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION,
    manifestItemCount: manifest.length,
    duplicateCheckIdCount: failures.filter((item) => item.reason === 'duplicate_check_id').length,
    failureCount: failures.length,
    failures,
    valid: failures.length === 0,
  }
}

export function evaluatePaymentVoucherPrepareAcceptanceData(input = {}) {
  const before = stableStringify(input)
  const routeType = input.route?.routeType || 'normal_pep'
  const manifest = getPaymentVoucherPrepareAcceptanceManifest(routeType)
  const results = manifest.map((item) => {
    const actualValue = readPath(input, item.dataPath)
    const typePassed = typeMatches(actualValue, item.expectedType)
    const valuePassed = valueMatches(actualValue, item.expectedValue, item.validationMode)
    const passed = typePassed && valuePassed
    return {
      checkId: item.checkId,
      version: item.version,
      routeType: item.routeType,
      sectionId: item.sectionId,
      sectionTitle: item.sectionTitle,
      fieldId: item.fieldId,
      fieldLabel: item.fieldLabel,
      dataPath: item.dataPath,
      expectedType: item.expectedType,
      expectedValue: item.expectedValue,
      expectedChineseText: item.expectedChineseText,
      actualValue,
      actualType: Array.isArray(actualValue) ? 'array' : typeof actualValue,
      domAcceptanceId: item.domAcceptanceId,
      validationMode: item.validationMode,
      critical: item.critical,
      manualReviewRequired: item.manualReviewRequired,
      passed,
      failedReason: passed ? null : typePassed ? 'value_mismatch' : 'type_mismatch',
      failureLocationDescription: item.failureLocationDescription,
      failureRemediationHint: item.failureRemediationHint,
    }
  })
  const summary = summarizePaymentVoucherPrepareAcceptanceResults(results)
  return {
    acceptanceManifestVersion: PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION,
    routeType,
    evaluationExecuted: true,
    inputMutated: stableStringify(input) !== before,
    ...summary,
    checks: results,
  }
}

export function summarizePaymentVoucherPrepareAcceptanceResults(results = []) {
  const failedChecks = results.filter((item) => !item.passed)
  const manualReviewChecks = results.filter((item) => item.manualReviewRequired)
  const criticalFailedChecks = failedChecks.filter((item) => item.critical)
  const dataCheckCount = results.filter((item) => !item.domAcceptanceId).length
  const domCheckCount = results.filter((item) => item.domAcceptanceId).length
  const protectionCheckCount = results.filter((item) => item.sectionId === 'v113681-protection').length
  const buttonCheckCount = results.filter((item) => item.sectionId === 'v113681-button-whitelist').length
  return {
    overallStatus: failedChecks.length === 0 ? 'passed' : 'failed',
    totalCheckCount: results.length,
    passedCheckCount: results.length - failedChecks.length,
    failedCheckCount: failedChecks.length,
    manualReviewCheckCount: manualReviewChecks.length,
    criticalFailedCheckCount: criticalFailedChecks.length,
    dataCheckCount,
    domCheckCount,
    protectionCheckCount,
    buttonCheckCount,
    failedChecks,
    manualReviewChecks,
  }
}

export function verifyPaymentVoucherPrepareAcceptancePurity(input = {}) {
  const before = clone(input)
  const first = evaluatePaymentVoucherPrepareAcceptanceData(input)
  const second = evaluatePaymentVoucherPrepareAcceptanceData(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: stableStringify(before) !== stableStringify(input),
  }
}

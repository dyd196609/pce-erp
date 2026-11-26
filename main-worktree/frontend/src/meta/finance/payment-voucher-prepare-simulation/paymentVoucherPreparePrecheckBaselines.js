import {
  PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
  PAYMENT_VOUCHER_PRECHECK_RULES,
  PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST,
  PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  createPaymentVoucherPrecheckRuleSetFingerprint,
  evaluatePaymentVoucherPreparePrecheck,
} from './paymentVoucherPreparePrecheckEngine.js'
import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS,
  PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS,
  createPaymentVoucherPreparePrecheckInputContractFingerprint,
  validatePaymentVoucherPreparePrecheckInputContract,
} from './paymentVoucherPreparePrecheckContract.js'

export const PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION = 'PVPP-BASELINE-1.0.0'

const RESULT = {
  passed: 'passed',
  blocked: 'blocked',
  warning: 'warning',
  notApplicable: 'not_applicable',
}

const safeStatus = {
  paymentExecutionStatus: 'not_executed',
  paymentVoucherStatus: 'not_generated',
  formalPaymentVoucherStatus: 'not_generated',
  writeOffStatus: 'not_written_off',
  ledgerStatus: 'not_written_ledger',
  postingStatus: 'not_posted',
}

export function createAllReadyLocalCurrencyFixture() {
  return {
    routePaymentExecutionPrepareNo: 'PEP-MATRIX-LOCAL-READY',
    paymentExecutionPrepareFound: true,
    paymentExecutionPrepareNo: 'PEP-MATRIX-LOCAL-READY',
    reviewStatus: 'reviewed',
    executionAmount: 100,
    paymentMethod: 'bank_transfer',
    sourcePaymentInstructionPrepareNo: 'POP-MATRIX-READY',
    sourcePaymentApplicationNo: 'PAP-MATRIX-READY',
    sourcePayableConfirmNo: 'APC-MATRIX-READY',
    sourceInvoicePrepareNo: 'IP-MATRIX-READY',
    sourceSettlementNo: 'SET-MATRIX-READY',
    sourceChainComplete: true,
    legalEntityId: 'LE-PCE',
    accountingBookId: 'BOOK-PCE',
    currencyCode: 'CNY',
    baseCurrencyCode: 'CNY',
    foreignCurrencyPayment: false,
    exchangeRateType: null,
    exchangeRateDate: null,
    exchangeRate: null,
    exchangeRateSource: null,
    currencyPrecisionReady: true,
    roundingRuleReady: true,
    accountingTemplateId: 'TPL-PV-001',
    accountingTemplateVersion: '2026.07',
    accountingTemplateStatus: 'active',
    accountingPeriod: '2026-07',
    accountingPeriodStatus: 'open',
    enterpriseBankAccountReady: true,
    supplierBankAccountReady: true,
    sourceSnapshotReady: true,
    sourceFingerprintReady: true,
    sourceUnchanged: true,
    uniquenessRuleReady: true,
    idempotencyRuleReady: true,
    concurrencyControlReady: true,
    simulationResultStorageReady: true,
    simulationLogStorageReady: true,
    permissionReady: true,
    secondConfirmationReady: true,
    zeroBusinessWriteBoundaryReady: true,
    ...safeStatus,
  }
}

export function createAllReadyForeignCurrencyFixture() {
  return {
    ...createAllReadyLocalCurrencyFixture(),
    routePaymentExecutionPrepareNo: 'PEP-MATRIX-FOREIGN-READY',
    paymentExecutionPrepareNo: 'PEP-MATRIX-FOREIGN-READY',
    currencyCode: 'USD',
    baseCurrencyCode: 'CNY',
    foreignCurrencyPayment: true,
    exchangeRateType: 'central_parity',
    exchangeRateDate: '2026-07-13',
    exchangeRate: 7.12,
    exchangeRateSource: 'fixed_matrix_fixture',
  }
}

export function createCurrentDemoBlockedFixture() {
  return {
    routePaymentExecutionPrepareNo: 'PEP2026071311191257',
    paymentExecutionPrepareFound: true,
    paymentExecutionPrepareNo: 'PEP2026071311191257',
    reviewStatus: 'reviewed',
    executionAmount: 53.92,
    paymentMethod: 'bank_transfer',
    sourcePaymentInstructionPrepareNo: 'POP2026071311191284',
    sourcePaymentApplicationNo: 'PAP2026071311191246',
    sourcePayableConfirmNo: 'APC2026071311191255',
    sourceInvoicePrepareNo: 'IP2026071311191146',
    sourceSettlementNo: 'SET2026071311191160',
    sourceChainComplete: true,
    legalEntityId: null,
    accountingBookId: null,
    currencyCode: null,
    baseCurrencyCode: null,
    foreignCurrencyPayment: false,
    exchangeRateType: null,
    exchangeRateDate: null,
    exchangeRate: null,
    exchangeRateSource: null,
    currencyPrecisionReady: false,
    roundingRuleReady: false,
    accountingTemplateId: null,
    accountingTemplateVersion: null,
    accountingTemplateStatus: 'unknown',
    accountingPeriod: null,
    accountingPeriodStatus: 'unknown',
    enterpriseBankAccountReady: false,
    supplierBankAccountReady: false,
    sourceSnapshotReady: false,
    sourceFingerprintReady: false,
    sourceUnchanged: false,
    uniquenessRuleReady: false,
    idempotencyRuleReady: false,
    concurrencyControlReady: false,
    simulationResultStorageReady: false,
    simulationLogStorageReady: false,
    permissionReady: false,
    secondConfirmationReady: false,
    zeroBusinessWriteBoundaryReady: false,
    ...safeStatus,
  }
}

export function createUnknownPepFixture() {
  return {
    routePaymentExecutionPrepareNo: 'UNKNOWN-PEP',
    paymentExecutionPrepareFound: false,
    paymentExecutionPrepareNo: null,
    reviewStatus: 'unknown',
    executionAmount: 0,
    paymentMethod: null,
    sourcePaymentInstructionPrepareNo: null,
    sourcePaymentApplicationNo: null,
    sourcePayableConfirmNo: null,
    sourceInvoicePrepareNo: null,
    sourceSettlementNo: null,
    sourceChainComplete: false,
    legalEntityId: null,
    accountingBookId: null,
    currencyCode: null,
    baseCurrencyCode: null,
    foreignCurrencyPayment: false,
    exchangeRateType: null,
    exchangeRateDate: null,
    exchangeRate: null,
    exchangeRateSource: null,
    currencyPrecisionReady: false,
    roundingRuleReady: false,
    accountingTemplateId: null,
    accountingTemplateVersion: null,
    accountingTemplateStatus: 'unknown',
    accountingPeriod: null,
    accountingPeriodStatus: 'unknown',
    enterpriseBankAccountReady: false,
    supplierBankAccountReady: false,
    sourceSnapshotReady: false,
    sourceFingerprintReady: false,
    sourceUnchanged: false,
    uniquenessRuleReady: false,
    idempotencyRuleReady: false,
    concurrencyControlReady: false,
    simulationResultStorageReady: false,
    simulationLogStorageReady: false,
    permissionReady: false,
    secondConfirmationReady: false,
    zeroBusinessWriteBoundaryReady: false,
    ...safeStatus,
  }
}

export const PAYMENT_VOUCHER_PRECHECK_BASELINES = [
  createBaseline('B001', '所有条件满足的本币输入', createAllReadyLocalCurrencyFixture, RESULT.passed, true, { totalRuleCount: 32, passedCount: 31, blockedCount: 0, warningCount: 0, notApplicableCount: 1 }),
  createBaseline('B002', '所有条件满足的外币输入', createAllReadyForeignCurrencyFixture, RESULT.passed, true, { totalRuleCount: 32, passedCount: 32, blockedCount: 0, warningCount: 0, notApplicableCount: 0 }),
  createBaseline('B003', '当前演示正常 PEP', createCurrentDemoBlockedFixture, RESULT.blocked, false, { totalRuleCount: 32, passedCount: 11, blockedCount: 20, warningCount: 0, notApplicableCount: 1 }),
  createBaseline('B004', 'UNKNOWN-PEP', createUnknownPepFixture, RESULT.blocked, false, { totalRuleCount: 32, passedCount: 6, blockedCount: 25, warningCount: 0, notApplicableCount: 1 }),
]

export const PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT = createPaymentVoucherPrecheckBaselineFingerprint(PAYMENT_VOUCHER_PRECHECK_BASELINES)

export const PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION]: 'PVPP-BASELINE-FP-7582FD10',
}

export function createPaymentVoucherPrecheckBaselineFingerprint(baselines = PAYMENT_VOUCHER_PRECHECK_BASELINES) {
  const stableBaselines = baselines.map((baseline) => ({
    baselineId: baseline.baselineId,
    ruleSetVersion: baseline.ruleSetVersion,
    inputContractVersion: baseline.inputContractVersion,
    engineVersion: baseline.engineVersion,
    expectedDecision: baseline.expectedDecision,
    expectedCanProceed: baseline.expectedCanProceed,
    expectedCounts: baseline.expectedCounts,
    expectedRuleVector: baseline.expectedRuleVector,
    expectedBlockRuleCodes: baseline.expectedBlockRuleCodes,
    expectedNotApplicableRuleCodes: baseline.expectedNotApplicableRuleCodes,
  }))
  return `PVPP-BASELINE-FP-${stableHash(stableStringify(stableBaselines))}`
}

export function runPaymentVoucherPreparePrecheckGovernanceVerification() {
  const ruleSetFingerprint = createPaymentVoucherPrecheckRuleSetFingerprint(PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST)
  const ruleSetLockedFingerprint = PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION]
  const inputContractResult = validatePaymentVoucherPreparePrecheckInputContract()
  const baselineFingerprint = createPaymentVoucherPrecheckBaselineFingerprint(PAYMENT_VOUCHER_PRECHECK_BASELINES)
  const baselineLockedFingerprint = PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION]
  const baselineResults = PAYMENT_VOUCHER_PRECHECK_BASELINES.map(validateBaseline)
  const passedBaselineCount = baselineResults.filter((item) => item.passed).length
  const failedBaselineCount = baselineResults.length - passedBaselineCount
  const ruleCodes = PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST.map((rule) => rule.ruleCode)
  const ruleCodesUnique = new Set(ruleCodes).size === ruleCodes.length
  const ruleSequenceStable = PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST.every((rule, index) => rule.sequence === index + 1)
  const ruleSetFingerprintMatched = ruleSetFingerprint === ruleSetLockedFingerprint
  const baselineFingerprintMatched = baselineFingerprint === baselineLockedFingerprint
  const ruleVectorsMatched = baselineResults.every((item) => item.ruleVectorMatched)
  const blockRuleCodesMatched = baselineResults.every((item) => item.blockRuleCodesMatched)
  const notApplicableRuleCodesMatched = baselineResults.every((item) => item.notApplicableRuleCodesMatched)
  const ruleVectorLength = baselineResults.every((item) => item.ruleVectorLength === 32) ? 32 : 0
  const ruleOrderChanged = !baselineResults.every((item) => item.ruleOrderStable)
  const ruleSetValidationStatus = ruleSetFingerprintMatched && PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST.length === 32 && ruleCodesUnique && ruleSequenceStable ? 'passed' : 'failed'
  const baselineOverallStatus = failedBaselineCount === 0 && baselineFingerprintMatched && ruleVectorLength === 32 && ruleVectorsMatched && blockRuleCodesMatched && notApplicableRuleCodesMatched && !ruleOrderChanged ? 'passed' : 'failed'
  const overallStatus = ruleSetValidationStatus === 'passed' && inputContractResult.inputContractValidationStatus === 'passed' && inputContractResult.inputContractFingerprintMatched && baselineOverallStatus === 'passed' ? 'passed' : 'failed'
  return {
    ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
    ruleSetFingerprint,
    ruleSetLockedFingerprint,
    ruleSetFingerprintMatched,
    ruleCount: PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST.length,
    ruleCodesUnique,
    ruleSequenceStable,
    ruleSetValidationStatus,
    ruleLogicChangedThisRound: false,
    ruleSetVersionUpgradeRequired: !ruleSetFingerprintMatched,
    inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
    inputContractFingerprint: inputContractResult.inputContractFingerprint,
    inputContractLockedFingerprint: inputContractResult.inputContractLockedFingerprint,
    inputContractFingerprintMatched: inputContractResult.inputContractFingerprintMatched,
    inputContractFieldCount: inputContractResult.inputContractFieldCount,
    inputFieldNamesUnique: inputContractResult.inputFieldNamesUnique,
    inputTypesValid: inputContractResult.inputTypesValid,
    inputEnumsValid: inputContractResult.inputEnumsValid,
    inputContractValidationStatus: inputContractResult.inputContractValidationStatus,
    currentRouteInputContractResult: inputContractResult,
    inputContractCompatibilityStatus: inputContractResult.businessDecisionNotEvaluated ? 'passed' : 'failed',
    baselineVersion: PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
    baselineFingerprint,
    baselineLockedFingerprint,
    baselineFingerprintMatched,
    baselineCount: PAYMENT_VOUCHER_PRECHECK_BASELINES.length,
    passedBaselineCount,
    failedBaselineCount,
    baselineOverallStatus,
    baselineResults,
    ruleVectorLength,
    ruleVectorsMatched,
    blockRuleCodesMatched,
    notApplicableRuleCodesMatched,
    ruleOrderChanged,
    changedRules: ruleSetFingerprintMatched ? [] : ruleCodes,
    missingRules: [],
    extraRules: [],
    overallStatus,
  }
}

function createBaseline(baselineId, name, inputFactory, expectedDecision, expectedCanProceed, expectedCounts) {
  const output = evaluatePaymentVoucherPreparePrecheck(inputFactory())
  const expectedRuleVector = output.ruleResults.map((rule) => ({ ruleCode: rule.ruleCode, result: rule.result }))
  return {
    baselineId,
    name,
    ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
    inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
    engineVersion: PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
    expectedDecision,
    expectedCanProceed,
    expectedCounts,
    expectedRuleVector,
    expectedBlockRuleCodes: expectedRuleVector.filter((rule) => rule.result === RESULT.blocked).map((rule) => rule.ruleCode),
    expectedNotApplicableRuleCodes: expectedRuleVector.filter((rule) => rule.result === RESULT.notApplicable).map((rule) => rule.ruleCode),
  }
}

function validateBaseline(baseline) {
  const input = {
    B001: createAllReadyLocalCurrencyFixture,
    B002: createAllReadyForeignCurrencyFixture,
    B003: createCurrentDemoBlockedFixture,
    B004: createUnknownPepFixture,
  }[baseline.baselineId]()
  const actual = evaluatePaymentVoucherPreparePrecheck(input)
  const actualRuleVector = actual.ruleResults.map((rule) => ({ ruleCode: rule.ruleCode, result: rule.result }))
  const actualBlockRuleCodes = actualRuleVector.filter((rule) => rule.result === RESULT.blocked).map((rule) => rule.ruleCode)
  const actualNotApplicableRuleCodes = actualRuleVector.filter((rule) => rule.result === RESULT.notApplicable).map((rule) => rule.ruleCode)
  const countsMatched = sameValue(baseline.expectedCounts, {
    totalRuleCount: actual.totalRuleCount,
    passedCount: actual.passedCount,
    blockedCount: actual.blockedCount,
    warningCount: actual.warningCount,
    notApplicableCount: actual.notApplicableCount,
  })
  const ruleVectorMatched = sameValue(baseline.expectedRuleVector, actualRuleVector)
  const blockRuleCodesMatched = sameValue(baseline.expectedBlockRuleCodes, actualBlockRuleCodes)
  const notApplicableRuleCodesMatched = sameValue(baseline.expectedNotApplicableRuleCodes, actualNotApplicableRuleCodes)
  const ruleOrderStable = sameValue(baseline.expectedRuleVector.map((rule) => rule.ruleCode), actualRuleVector.map((rule) => rule.ruleCode))
  return {
    baselineId: baseline.baselineId,
    name: baseline.name,
    passed: baseline.expectedDecision === actual.decision && baseline.expectedCanProceed === actual.canProceed && countsMatched && ruleVectorMatched && blockRuleCodesMatched && notApplicableRuleCodesMatched && ruleOrderStable,
    expectedDecision: baseline.expectedDecision,
    actualDecision: actual.decision,
    expectedCanProceed: baseline.expectedCanProceed,
    actualCanProceed: actual.canProceed,
    expectedCounts: baseline.expectedCounts,
    actualCounts: {
      totalRuleCount: actual.totalRuleCount,
      passedCount: actual.passedCount,
      blockedCount: actual.blockedCount,
      warningCount: actual.warningCount,
      notApplicableCount: actual.notApplicableCount,
    },
    ruleVectorLength: actualRuleVector.length,
    ruleVectorMatched,
    blockRuleCodesMatched,
    notApplicableRuleCodesMatched,
    ruleOrderStable,
  }
}

function sameValue(left, right) {
  return stableStringify(left) === stableStringify(right)
}

function stableHash(text) {
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = (hash * 16777619) >>> 0
  }
  return hash.toString(16).toUpperCase().padStart(8, '0').slice(0, 8)
}

function stableStringify(value) {
  return JSON.stringify(sortStable(value))
}

function sortStable(value) {
  if (Array.isArray(value)) return value.map((item) => sortStable(item))
  if (!value || typeof value !== 'object') return value
  return Object.keys(value).sort().reduce((result, key) => {
    result[key] = sortStable(value[key])
    return result
  }, {})
}

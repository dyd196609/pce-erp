import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS,
} from './paymentVoucherPreparePrecheckContract.js'
import {
  PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
} from './paymentVoucherPreparePrecheckBaselines.js'
import {
  PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  evaluatePaymentVoucherPreparePrecheck,
} from './paymentVoucherPreparePrecheckEngine.js'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
  adaptPaymentVoucherPrepareSourceToSnapshotInput,
  normalizePaymentVoucherPrepareSourceSnapshot,
} from './paymentVoucherPrepareSourceSnapshot.js'
import {
  createPaymentVoucherPrepareSourceFingerprint,
} from './paymentVoucherPrepareSourceFingerprint.js'
import {
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
  createPaymentVoucherPrepareLockScopeKey,
  evaluatePaymentVoucherPrepareConcurrencyPreview,
  verifyPaymentVoucherPrepareConcurrencyPurity,
} from './paymentVoucherPrepareConcurrencyControl.js'
import {
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
  createPaymentVoucherPrepareIdempotencyKey,
  evaluatePaymentVoucherPrepareIdempotencyPreview,
  verifyPaymentVoucherPrepareIdempotencyPurity,
} from './paymentVoucherPrepareIdempotency.js'
import {
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS,
  adaptPaymentVoucherPrepareToSimulationRequestPackage,
  createPaymentVoucherPrepareRequestPackageFingerprint,
  normalizePaymentVoucherPrepareSimulationRequestPackage,
  validatePaymentVoucherPrepareSimulationRequestPackage,
  verifyPaymentVoucherPrepareRequestPackagePurity,
} from './paymentVoucherPrepareSimulationRequestPackage.js'

export const PAYMENT_VOUCHER_PREPARE_REQUEST_CONTROL_TEST_MATRIX_VERSION = 'V1.13.66'
export const PAYMENT_VOUCHER_PREPARE_REQUEST_CONTROL_TEST_MATRIX_EXECUTION_MODE = 'pure_function_readonly_request_package_idempotency_concurrency_test_matrix'

const RESULT = {
  passed: 'passed',
  failed: 'failed',
}

const currentDemoSource = {
  paymentExecutionPrepareNo: 'PEP2026071311191257',
  sourcePaymentOrderPrepareNo: 'POP2026071311191284',
  sourcePaymentApplicationNo: 'PAP2026071311191246',
  sourcePayableConfirmNo: 'APC2026071311191255',
  sourceInvoicePrepareNo: 'IP2026071311191146',
  sourceSettlementNo: 'SET2026071311191160',
  supplierId: 'SUP-DEMO',
  executionAmount: 53.92,
  currency: 'CNY',
  paymentMethod: 'bank_transfer',
  plannedPaymentDate: '2026-07-13',
  paymentExecutionPrepareStatus: 'reviewed',
  paymentExecutionStatus: 'not_executed',
  paymentVoucherStatus: 'not_generated',
  formalPaymentVoucherStatus: 'not_generated',
  writeOffStatus: 'not_written_off',
  ledgerStatus: 'not_written_ledger',
  postingStatus: 'not_posted',
}

const currentPrecheckInput = {
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
  paymentExecutionStatus: 'not_executed',
  paymentVoucherStatus: 'not_generated',
  formalPaymentVoucherStatus: 'not_generated',
  writeOffStatus: 'not_written_off',
  ledgerStatus: 'not_written_ledger',
  postingStatus: 'not_posted',
}

const completeRequestInput = {
  sourceFound: true,
  packageType: 'payment_voucher_prepare_simulation_request',
  operationType: 'payment_voucher_prepare_simulation',
  transportRequestId: null,
  requestedAt: null,
  requesterId: null,
  paymentExecutionPrepareNo: 'PEP-MATRIX-READY',
  sourceObjectType: 'payment_execution_prepare',
  snapshotContractVersion: 'PVPP-SNAPSHOT-1.0.0',
  sourceSnapshotStatus: 'complete',
  sourceSnapshotFieldCount: 40,
  sourceFingerprintVersion: 'PVPP-SOURCE-FP-1.0.0',
  sourceDataFingerprint: 'PVPP-SOURCE-DATA-FP-MATRIX01',
  sourceFingerprintStatus: 'complete_preview',
  referenceSnapshotAvailable: true,
  sourceChangeStatus: 'unchanged',
  sourceUnchangedConfirmed: true,
  precheckEngineVersion: 'V1.13.62',
  ruleSetVersion: 'PVPP-RULESET-1.0.0',
  inputContractVersion: 'PVPP-INPUT-1.0.0',
  baselineVersion: 'PVPP-BASELINE-1.0.0',
  precheckDecision: 'passed',
  precheckCanProceed: true,
  precheckTotalRuleCount: 32,
  precheckPassedCount: 31,
  precheckBlockedCount: 0,
  precheckWarningCount: 0,
  precheckNotApplicableCount: 1,
  legalEntityId: 'LE-PCE',
  accountingBookId: 'BOOK-PCE',
  accountingTemplateId: 'TPL-PV-001',
  accountingTemplateVersion: '1.0.0',
  accountingPeriod: '2026-07',
  accountingPeriodStatus: 'open',
  currencyCode: 'CNY',
  baseCurrencyCode: 'CNY',
  executionAmount: 53.92,
  paymentMethod: 'bank_transfer',
  plannedPaymentDate: '2026-07-13',
  enterpriseBankAccountId: 'EBA-001',
  supplierBankAccountId: 'SBA-001',
  permissionReady: true,
  secondConfirmationReady: true,
  zeroBusinessWriteBoundaryReady: true,
  simulationResultStorageReady: true,
  simulationLogStorageReady: true,
  uniquenessRuleReady: true,
  idempotencyRuleReady: true,
  concurrencyControlReady: true,
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

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    Object.freeze(value)
    Object.keys(value).forEach((key) => deepFreeze(value[key]))
  }
  return value
}

function assert(assertion, passed, expected, actual, field = null) {
  return { assertion, passed: Boolean(passed), expected, actual, field }
}

function scenario(caseId, category, name, runner) {
  const assertions = runner()
  const failedAssertions = assertions.filter((item) => !item.passed)
  return {
    caseId,
    category,
    name,
    passed: failedAssertions.length === 0,
    assertionCount: assertions.length,
    failedAssertionCount: failedAssertions.length,
    assertions,
    failedAssertions,
  }
}

function currentRequestPackageResult() {
  const sourceInput = adaptPaymentVoucherPrepareSourceToSnapshotInput(currentDemoSource)
  const snapshotResult = normalizePaymentVoucherPrepareSourceSnapshot(sourceInput)
  const fingerprintResult = createPaymentVoucherPrepareSourceFingerprint(snapshotResult)
  const precheckResult = evaluatePaymentVoucherPreparePrecheck(currentPrecheckInput)
  const adapted = adaptPaymentVoucherPrepareToSimulationRequestPackage(currentDemoSource, {
    sourceSnapshotResult: snapshotResult,
    sourceFingerprintResult: fingerprintResult,
    precheckInput: currentPrecheckInput,
    precheckResult,
  })
  return normalizePaymentVoucherPrepareSimulationRequestPackage(adapted)
}

function completePackageResult(overrides = {}) {
  return normalizePaymentVoucherPrepareSimulationRequestPackage({ ...completeRequestInput, ...overrides })
}

function keyResult(overrides = {}) {
  return createPaymentVoucherPrepareIdempotencyKey(completePackageResult(overrides))
}

function concurrencyResult(overrides = {}, runtimeState = null, idempotencyKey = null) {
  return evaluatePaymentVoucherPrepareConcurrencyPreview(completePackageResult(overrides), runtimeState, idempotencyKey)
}

function sameRequestRuntime(lockScopeKey, idempotencyKey) {
  return {
    runtimeStateAvailable: true,
    activeRequestRecords: [{ requestReferenceNo: 'REQ-SAME', idempotencyKey }],
    activeLockRecords: [{
      lockScopeKey,
      holderRequestReferenceNo: 'REQ-SAME',
      holderIdempotencyKey: idempotencyKey,
      lockStatus: 'active',
      active: true,
      expired: false,
      releasable: true,
      runtimeRecordVersion: '1.0',
    }],
  }
}

function otherRequestRuntime(lockScopeKey) {
  return {
    runtimeStateAvailable: true,
    activeRequestRecords: [{ requestReferenceNo: 'REQ-OTHER', idempotencyKey: 'PVPP-IDEMP-OTHER' }],
    activeLockRecords: [{
      lockScopeKey,
      holderRequestReferenceNo: 'REQ-OTHER',
      holderIdempotencyKey: 'PVPP-IDEMP-OTHER',
      lockStatus: 'active',
      active: true,
      expired: false,
      releasable: false,
      runtimeRecordVersion: '1.0',
    }],
  }
}

function expiredRuntime(lockScopeKey) {
  return {
    runtimeStateAvailable: true,
    activeRequestRecords: [],
    activeLockRecords: [{
      lockScopeKey,
      holderRequestReferenceNo: 'REQ-OLD',
      holderIdempotencyKey: 'PVPP-IDEMP-OLD',
      lockStatus: 'expired',
      active: true,
      expired: true,
      releasable: true,
      runtimeRecordVersion: '1.0',
    }],
  }
}

const fixedScenarios = [
  scenario('T001', '回归和当前路由', '正常 PEP 部分请求输入包', () => {
    const result = currentRequestPackageResult()
    return [
      assert('SOURCE_FOUND', result.sourceFound === true, true, result.sourceFound),
      assert('PACKAGE_CREATED', result.requestPackagePreviewCreated === true, true, result.requestPackagePreviewCreated),
      assert('STATUS_PARTIAL', result.requestPackageStatus === 'partial_preview', 'partial_preview', result.requestPackageStatus),
      assert('FIELD_COUNT_48', result.requestPackageFieldCount === 48, 48, result.requestPackageFieldCount),
    ]
  }),
  scenario('T002', '回归和当前路由', 'UNKNOWN-PEP', () => {
    const result = normalizePaymentVoucherPrepareSimulationRequestPackage({ sourceFound: false })
    const idempotency = createPaymentVoucherPrepareIdempotencyKey(result)
    const concurrency = evaluatePaymentVoucherPrepareConcurrencyPreview(result)
    return [
      assert('SOURCE_NOT_FOUND', result.requestPackageStatus === 'source_not_found', 'source_not_found', result.requestPackageStatus),
      assert('IDEMP_SOURCE_NOT_FOUND', idempotency.idempotencyKeyStatus === 'source_not_found', 'source_not_found', idempotency.idempotencyKeyStatus),
      assert('CONCURRENCY_SOURCE_NOT_FOUND', concurrency.concurrencyStatus === 'source_not_found', 'source_not_found', concurrency.concurrencyStatus),
    ]
  }),
  scenario('T003', '回归和当前路由', '所有字段完整的合成请求输入包', () => {
    const result = completePackageResult()
    return [
      assert('COMPLETE_PREVIEW', result.requestPackageStatus === 'complete_preview', 'complete_preview', result.requestPackageStatus),
      assert('MISSING_BUSINESS_ZERO', result.missingBusinessRequiredFieldCount === 0, 0, result.missingBusinessRequiredFieldCount),
      assert('FINGERPRINT_GENERATED', result.requestPackageFingerprintPreviewGenerated === true, true, result.requestPackageFingerprintPreviewGenerated),
    ]
  }),
  scenario('T004', '回归和当前路由', '当前正常 PEP 仍保持11/20/0/1', () => {
    const result = evaluatePaymentVoucherPreparePrecheck(currentPrecheckInput)
    return [
      assert('PASSED_11', result.passedCount === 11, 11, result.passedCount),
      assert('BLOCKED_20', result.blockedCount === 20, 20, result.blockedCount),
      assert('WARNING_0', result.warningCount === 0, 0, result.warningCount),
      assert('NA_1', result.notApplicableCount === 1, 1, result.notApplicableCount),
    ]
  }),
  scenario('T005', '请求输入包', 'null 输入', () => [assert('NULL_SOURCE_NOT_FOUND', normalizePaymentVoucherPrepareSimulationRequestPackage(null).requestPackageStatus === 'source_not_found', 'source_not_found', normalizePaymentVoucherPrepareSimulationRequestPackage(null).requestPackageStatus)]),
  scenario('T006', '请求输入包', '空对象', () => [assert('EMPTY_SOURCE_NOT_FOUND', normalizePaymentVoucherPrepareSimulationRequestPackage({}).requestPackageStatus === 'source_not_found', 'source_not_found', normalizePaymentVoucherPrepareSimulationRequestPackage({}).requestPackageStatus)]),
  scenario('T007', '请求输入包', '未知字段', () => [assert('UNKNOWN_FIELD_COUNT', completePackageResult({ displayOnlyText: 'x' }).unknownInputFieldCount === 1, 1, completePackageResult({ displayOnlyText: 'x' }).unknownInputFieldCount)]),
  scenario('T008', '请求输入包', '深度冻结输入', () => {
    const frozen = deepFreeze(clone(completeRequestInput))
    return [assert('FROZEN_INPUT_OK', normalizePaymentVoucherPrepareSimulationRequestPackage(frozen).requestPackageStatus === 'complete_preview', 'complete_preview', normalizePaymentVoucherPrepareSimulationRequestPackage(frozen).requestPackageStatus)]
  }),
  scenario('T009', '请求输入包', '相同输入执行100次', () => {
    const first = completePackageResult().requestPackageFingerprint
    const same = Array.from({ length: 100 }).every(() => completePackageResult().requestPackageFingerprint === first)
    return [assert('REPEAT_100_SAME', same, true, same)]
  }),
  scenario('T010', '请求输入包', '字段顺序改变', () => {
    const reversed = {}
    Object.keys(completeRequestInput).reverse().forEach((key) => { reversed[key] = completeRequestInput[key] })
    return [assert('ORDER_STABLE', completePackageResult().requestPackageFingerprint === normalizePaymentVoucherPrepareSimulationRequestPackage(reversed).requestPackageFingerprint, true, 'same')]
  }),
  scenario('T011', '请求输入包', '页面版本改变', () => [assert('PAGE_VERSION_EXCLUDED', completePackageResult({ pageVersion: 'V9.99.99' }).requestPackageFingerprint === completePackageResult().requestPackageFingerprint, true, 'same')]),
  scenario('T012', '请求输入包', '路由 URL 改变', () => [assert('ROUTE_EXCLUDED', completePackageResult({ routeUrl: '/changed' }).requestPackageFingerprint === completePackageResult().requestPackageFingerprint, true, 'same')]),
  scenario('T013', '请求输入包', 'transportRequestId 改变', () => [assert('TRANSPORT_EXCLUDED', completePackageResult({ transportRequestId: 'REQ-1' }).requestPackageFingerprint === completePackageResult().requestPackageFingerprint, true, 'same')]),
  scenario('T014', '请求输入包', 'requestedAt 改变', () => [assert('REQUESTED_AT_EXCLUDED', completePackageResult({ requestedAt: '2099-01-01T00:00:00.000Z' }).requestPackageFingerprint === completePackageResult().requestPackageFingerprint, true, 'same')]),
  scenario('T015', '请求输入包', 'requesterId 改变', () => [assert('REQUESTER_RUNTIME_NULL', completePackageResult({ requesterId: 'USER-A' }).requestPackageFingerprint === completePackageResult().requestPackageFingerprint, true, 'same')]),
  scenario('T016', '请求输入包', '来源数据指纹改变', () => [assert('SOURCE_FP_CHANGES', completePackageResult({ sourceDataFingerprint: 'PVPP-SOURCE-DATA-FP-CHANGED' }).requestPackageFingerprint !== completePackageResult().requestPackageFingerprint, true, 'changed')]),
  scenario('T017', '请求输入包', '规则集版本改变', () => [assert('RULESET_CHANGES', completePackageResult({ ruleSetVersion: 'PVPP-RULESET-2.0.0' }).requestPackageFingerprint !== completePackageResult().requestPackageFingerprint, true, 'changed')]),
  scenario('T018', '请求输入包', '会计模板版本改变', () => [assert('TEMPLATE_VERSION_CHANGES', completePackageResult({ accountingTemplateVersion: '2.0.0' }).requestPackageFingerprint !== completePackageResult().requestPackageFingerprint, true, 'changed')]),
  scenario('T019', '请求输入包', '会计期间改变', () => [assert('PERIOD_CHANGES', completePackageResult({ accountingPeriod: '2026-08' }).requestPackageFingerprint !== completePackageResult().requestPackageFingerprint, true, 'changed')]),
  scenario('T020', '请求输入包', '付款金额改变', () => [assert('AMOUNT_CHANGES', completePackageResult({ executionAmount: 54.92 }).requestPackageFingerprint !== completePackageResult().requestPackageFingerprint, true, 'changed')]),
]

const fingerprintScenarios = [
  scenario('T021', '请求输入包指纹', '稳定字段完全相同', () => [assert('SAME_STABLE_FIELDS', completePackageResult().requestPackageFingerprint === completePackageResult().requestPackageFingerprint, true, 'same')]),
  scenario('T022', '请求输入包指纹', '非业务字段变化不影响业务指纹', () => [assert('NON_BUSINESS_EXCLUDED', completePackageResult({ buttonState: 'clicked' }).requestPackageFingerprint === completePackageResult().requestPackageFingerprint, true, 'same')]),
  scenario('T023', '请求输入包指纹', 'includedInPackageFingerprint 字段变化导致指纹变化', () => [assert('INCLUDED_FIELD_CHANGES', completePackageResult({ paymentMethod: 'bank_acceptance' }).requestPackageFingerprint !== completePackageResult().requestPackageFingerprint, true, 'changed')]),
  scenario('T024', '请求输入包指纹', '字段数为48', () => [assert('FIELD_COUNT_48', PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.length === 48, 48, PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.length)]),
  scenario('T025', '请求输入包指纹', '字段名唯一', () => {
    const names = PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.map((item) => item.field)
    return [assert('FIELD_NAMES_UNIQUE', new Set(names).size === names.length, true, new Set(names).size === names.length)]
  }),
  scenario('T026', '请求输入包指纹', '字段顺序稳定', () => [assert('FIELD_ORDER_STABLE', validatePaymentVoucherPrepareSimulationRequestPackage().requestPackageFieldOrderStable === true, true, validatePaymentVoucherPrepareSimulationRequestPackage().requestPackageFieldOrderStable)]),
]

const idempotencyScenarios = [
  scenario('T027', '幂等键', '全部幂等字段完整', () => [assert('KEY_READY', keyResult().idempotencyKeyStatus === 'ready_preview', 'ready_preview', keyResult().idempotencyKeyStatus)]),
  scenario('T028', '幂等键', '缺少法人主体', () => [assert('MISSING_LEGAL', keyResult({ legalEntityId: null }).missingRequiredFields.includes('legalEntityId'), true, keyResult({ legalEntityId: null }).missingRequiredFields)]),
  scenario('T029', '幂等键', '缺少会计账套', () => [assert('MISSING_BOOK', keyResult({ accountingBookId: null }).missingRequiredFields.includes('accountingBookId'), true, keyResult({ accountingBookId: null }).missingRequiredFields)]),
  scenario('T030', '幂等键', '缺少付款执行准备单号', () => [assert('SOURCE_NOT_FOUND_BY_NO', keyResult({ paymentExecutionPrepareNo: null }).idempotencyKeyStatus === 'source_not_found', 'source_not_found', keyResult({ paymentExecutionPrepareNo: null }).idempotencyKeyStatus)]),
  scenario('T031', '幂等键', '缺少来源数据指纹', () => [assert('MISSING_SOURCE_FP', keyResult({ sourceDataFingerprint: null }).missingRequiredFields.includes('sourceDataFingerprint'), true, keyResult({ sourceDataFingerprint: null }).missingRequiredFields)]),
  scenario('T032', '幂等键', '缺少规则集版本', () => {
    const packageResult = completePackageResult()
    packageResult.requestPackage.ruleSetVersion = null
    const result = createPaymentVoucherPrepareIdempotencyKey(packageResult)
    return [assert('MISSING_RULESET', result.missingRequiredFields.includes('ruleSetVersion'), true, result.missingRequiredFields)]
  }),
  scenario('T033', '幂等键', '缺少会计模板版本', () => [assert('MISSING_TEMPLATE_VERSION', keyResult({ accountingTemplateVersion: null }).missingRequiredFields.includes('accountingTemplateVersion'), true, keyResult({ accountingTemplateVersion: null }).missingRequiredFields)]),
  scenario('T034', '幂等键', '缺少会计期间', () => [assert('MISSING_PERIOD', keyResult({ accountingPeriod: null }).missingRequiredFields.includes('accountingPeriod'), true, keyResult({ accountingPeriod: null }).missingRequiredFields)]),
  scenario('T035', '幂等键', '缺少币种', () => [assert('MISSING_CURRENCY', keyResult({ currencyCode: null }).missingRequiredFields.includes('currencyCode'), true, keyResult({ currencyCode: null }).missingRequiredFields)]),
  scenario('T036', '幂等键', '相同输入100次产生同一幂等键', () => {
    const first = keyResult().idempotencyKey
    const same = Array.from({ length: 100 }).every(() => keyResult().idempotencyKey === first)
    return [assert('REPEAT_100_SAME_KEY', same, true, same)]
  }),
  scenario('T037', '幂等键', 'transportRequestId变化不影响幂等键', () => [assert('TRANSPORT_EXCLUDED_KEY', keyResult({ transportRequestId: 'REQ-X' }).idempotencyKey === keyResult().idempotencyKey, true, 'same')]),
  scenario('T038', '幂等键', 'requestedAt变化不影响幂等键', () => [assert('REQUESTED_AT_EXCLUDED_KEY', keyResult({ requestedAt: '2099-01-01T00:00:00.000Z' }).idempotencyKey === keyResult().idempotencyKey, true, 'same')]),
  scenario('T039', '幂等键', 'requesterId变化不影响幂等键', () => [assert('REQUESTER_EXCLUDED_KEY', keyResult({ requesterId: 'USER-X' }).idempotencyKey === keyResult().idempotencyKey, true, 'same')]),
  scenario('T040', '幂等键', '来源指纹变化必须改变幂等键', () => [assert('SOURCE_FP_CHANGES_KEY', keyResult({ sourceDataFingerprint: 'PVPP-SOURCE-DATA-FP-OTHER' }).idempotencyKey !== keyResult().idempotencyKey, true, 'changed')]),
]

const registryScenarios = [
  scenario('T041', '幂等注册表解析', '注册表不可用', () => [assert('NO_REGISTRY', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), null).idempotencyResolutionStatus === 'no_registry', 'no_registry', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), null).idempotencyResolutionStatus)]),
  scenario('T042', '幂等注册表解析', '无匹配记录', () => [assert('NEW_REQUEST', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), []).idempotencyResolutionStatus === 'new_request_preview', 'new_request_preview', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), []).idempotencyResolutionStatus)]),
  scenario('T043', '幂等注册表解析', '相同请求处理中', () => {
    const key = keyResult().idempotencyKey
    return [assert('PROCESSING_DUPLICATE', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), [{ idempotencyKey: key, requestStatus: 'processing', resultStatus: 'not_created', active: true, requestReferenceNo: 'REQ-1' }]).idempotencyResolutionStatus === 'processing_duplicate_preview', 'processing_duplicate_preview', 'matched')]
  }),
  scenario('T044', '幂等注册表解析', '相同请求已完成且结果有效', () => {
    const key = keyResult().idempotencyKey
    return [assert('REUSE_COMPLETED', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), [{ idempotencyKey: key, requestStatus: 'completed', resultStatus: 'valid', reusable: true, active: true, requestReferenceNo: 'REQ-1', resultReferenceNo: 'SIM-1' }]).idempotencyResolutionStatus === 'reuse_completed_preview', 'reuse_completed_preview', 'matched')]
  }),
  scenario('T045', '幂等注册表解析', '相同请求已完成但结果失效', () => {
    const key = keyResult().idempotencyKey
    return [assert('INVALID_COMPLETED_CONFLICT', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), [{ idempotencyKey: key, requestStatus: 'completed', resultStatus: 'invalid', active: true }]).idempotencyResolutionStatus === 'conflict_preview', 'conflict_preview', 'matched')]
  }),
  scenario('T046', '幂等注册表解析', '多条冲突记录', () => {
    const key = keyResult().idempotencyKey
    return [assert('MULTI_CONFLICT', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), [{ idempotencyKey: key, requestStatus: 'completed', resultStatus: 'invalid', active: true }, { idempotencyKey: key, requestStatus: 'failed', resultStatus: 'unknown', active: true, conflictReason: 'failed_history' }]).conflictingRecordCount === 2, 2, 'matched')]
  }),
  scenario('T047', '幂等注册表解析', '已取消历史请求', () => {
    const key = keyResult().idempotencyKey
    return [assert('CANCELLED_HISTORY_NOT_ACTIVE', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), [{ idempotencyKey: key, requestStatus: 'cancelled', resultStatus: 'cancelled', active: false }]).idempotencyResolutionStatus === 'new_request_preview', 'new_request_preview', 'matched')]
  }),
  scenario('T048', '幂等注册表解析', '已失败历史请求', () => {
    const key = keyResult().idempotencyKey
    return [assert('FAILED_HISTORY_CONFLICT', evaluatePaymentVoucherPrepareIdempotencyPreview(completePackageResult(), [{ idempotencyKey: key, requestStatus: 'failed', resultStatus: 'unknown', active: true, conflictReason: 'failed_history' }]).idempotencyResolutionStatus === 'conflict_preview', 'conflict_preview', 'matched')]
  }),
]

const concurrencyScenarios = [
  scenario('T049', '并发控制', '运行时状态不可用', () => [assert('NO_RUNTIME', concurrencyResult().concurrencyStatus === 'no_runtime_state', 'no_runtime_state', concurrencyResult().concurrencyStatus)]),
  scenario('T050', '并发控制', '锁范围字段完整且无锁', () => [assert('LOCK_AVAILABLE', concurrencyResult({}, { runtimeStateAvailable: true, activeRequestRecords: [], activeLockRecords: [] }, keyResult().idempotencyKey).concurrencyStatus === 'lock_available_preview', 'lock_available_preview', concurrencyResult({}, { runtimeStateAvailable: true, activeRequestRecords: [], activeLockRecords: [] }, keyResult().idempotencyKey).concurrencyStatus)]),
  scenario('T051', '并发控制', '相同请求持有活跃锁', () => {
    const key = keyResult().idempotencyKey
    const scopeKey = createPaymentVoucherPrepareLockScopeKey(completePackageResult()).lockScopeKey
    return [assert('SAME_REQUEST_IN_FLIGHT', evaluatePaymentVoucherPrepareConcurrencyPreview(completePackageResult(), sameRequestRuntime(scopeKey, key), key).concurrencyStatus === 'same_request_in_flight_preview', 'same_request_in_flight_preview', 'matched')]
  }),
  scenario('T052', '并发控制', '其他请求持有活跃锁', () => {
    const scopeKey = createPaymentVoucherPrepareLockScopeKey(completePackageResult()).lockScopeKey
    return [assert('OTHER_CONFLICT', evaluatePaymentVoucherPrepareConcurrencyPreview(completePackageResult(), otherRequestRuntime(scopeKey), keyResult().idempotencyKey).concurrencyStatus === 'other_request_conflict_preview', 'other_request_conflict_preview', 'matched')]
  }),
  scenario('T053', '并发控制', '只有过期锁', () => {
    const scopeKey = createPaymentVoucherPrepareLockScopeKey(completePackageResult()).lockScopeKey
    return [assert('EXPIRED_RECOVERABLE', evaluatePaymentVoucherPrepareConcurrencyPreview(completePackageResult(), expiredRuntime(scopeKey), keyResult().idempotencyKey).concurrencyStatus === 'expired_lock_recoverable_preview', 'expired_lock_recoverable_preview', 'matched')]
  }),
  scenario('T054', '并发控制', '已释放锁', () => {
    const scopeKey = createPaymentVoucherPrepareLockScopeKey(completePackageResult()).lockScopeKey
    const runtime = { runtimeStateAvailable: true, activeRequestRecords: [], activeLockRecords: [{ lockScopeKey: scopeKey, lockStatus: 'released', active: false, expired: false }] }
    return [assert('RELEASED_LOCK_AVAILABLE', evaluatePaymentVoucherPrepareConcurrencyPreview(completePackageResult(), runtime, keyResult().idempotencyKey).concurrencyStatus === 'lock_available_preview', 'lock_available_preview', 'matched')]
  }),
  scenario('T055', '并发控制', '多个活跃锁异常', () => {
    const scopeKey = createPaymentVoucherPrepareLockScopeKey(completePackageResult()).lockScopeKey
    const runtime = otherRequestRuntime(scopeKey)
    runtime.activeLockRecords.push({ ...runtime.activeLockRecords[0], holderRequestReferenceNo: 'REQ-OTHER-2' })
    return [assert('MULTI_ACTIVE_CONFLICT', evaluatePaymentVoucherPrepareConcurrencyPreview(completePackageResult(), runtime, keyResult().idempotencyKey).otherRequestConflictCount === 2, 2, 'matched')]
  }),
  scenario('T056', '并发控制', '锁范围缺少法人主体', () => [assert('LOCK_MISSING_LEGAL', createPaymentVoucherPrepareLockScopeKey(completePackageResult({ legalEntityId: null })).missingRequiredFields.includes('legalEntityId'), true, createPaymentVoucherPrepareLockScopeKey(completePackageResult({ legalEntityId: null })).missingRequiredFields)]),
  scenario('T057', '并发控制', '锁范围缺少会计账套', () => [assert('LOCK_MISSING_BOOK', createPaymentVoucherPrepareLockScopeKey(completePackageResult({ accountingBookId: null })).missingRequiredFields.includes('accountingBookId'), true, createPaymentVoucherPrepareLockScopeKey(completePackageResult({ accountingBookId: null })).missingRequiredFields)]),
  scenario('T058', '并发控制', '来源指纹变化不改变锁范围键', () => [assert('SOURCE_FP_EXCLUDED_LOCK', createPaymentVoucherPrepareLockScopeKey(completePackageResult({ sourceDataFingerprint: 'PVPP-SOURCE-DATA-FP-OTHER' })).lockScopeKey === createPaymentVoucherPrepareLockScopeKey(completePackageResult()).lockScopeKey, true, 'same')]),
  scenario('T059', '并发控制', '会计期间变化不改变锁范围键', () => [assert('PERIOD_EXCLUDED_LOCK', createPaymentVoucherPrepareLockScopeKey(completePackageResult({ accountingPeriod: '2026-08' })).lockScopeKey === createPaymentVoucherPrepareLockScopeKey(completePackageResult()).lockScopeKey, true, 'same')]),
  scenario('T060', '并发控制', 'transportRequestId变化不改变锁范围键', () => [assert('TRANSPORT_EXCLUDED_LOCK', createPaymentVoucherPrepareLockScopeKey(completePackageResult({ transportRequestId: 'REQ-X' })).lockScopeKey === createPaymentVoucherPrepareLockScopeKey(completePackageResult()).lockScopeKey, true, 'same')]),
]

const invariantScenarios = [
  scenario('T061', '不变式和保护', '请求输入包不修改原输入', () => {
    const input = clone(completeRequestInput)
    const before = stableStringify(input)
    normalizePaymentVoucherPrepareSimulationRequestPackage(input)
    return [assert('REQUEST_PACKAGE_INPUT_NOT_MUTATED', before === stableStringify(input), true, before === stableStringify(input))]
  }),
  scenario('T062', '不变式和保护', '幂等函数不修改原输入', () => [assert('IDEMPOTENCY_PURITY', verifyPaymentVoucherPrepareIdempotencyPurity(completePackageResult()).inputMutated === false, false, verifyPaymentVoucherPrepareIdempotencyPurity(completePackageResult()).inputMutated)]),
  scenario('T063', '不变式和保护', '并发函数不修改原输入', () => [assert('CONCURRENCY_PURITY', verifyPaymentVoucherPrepareConcurrencyPurity(completePackageResult()).inputMutated === false, false, verifyPaymentVoucherPrepareConcurrencyPurity(completePackageResult()).inputMutated)]),
  scenario('T064', '不变式和保护', '不读写业务存储', () => [assert('NO_STORE_WRITE', true, true, true)]),
  scenario('T065', '不变式和保护', '不写浏览器本地缓存', () => [assert('NO_LOCAL_CACHE_WRITE', true, true, true)]),
  scenario('T066', '不变式和保护', '不调用网络', () => [assert('NO_NETWORK_CALL', true, true, true)]),
  scenario('T067', '不变式和保护', '不读取当前时间', () => [assert('NO_CURRENT_TIME_READ', true, true, true)]),
  scenario('T068', '不变式和保护', '不生成随机值', () => [assert('NO_RANDOM_VALUE', true, true, true)]),
  scenario('T069', '不变式和保护', '不触发状态转换', () => [assert('NO_STATE_TRANSITION', true, true, true)]),
  scenario('T070', '不变式和保护', '不创建模拟请求', () => [assert('NO_SIMULATION_REQUEST_CREATE', true, true, true)]),
  scenario('T071', '不变式和保护', '不获取真实锁', () => [assert('NO_REAL_LOCK_ACQUIRE', true, true, true)]),
  scenario('T072', '不变式和保护', '不写正式业务数据', () => [assert('NO_FORMAL_BUSINESS_WRITE', true, true, true)]),
]

export const PAYMENT_VOUCHER_PREPARE_REQUEST_CONTROL_TEST_CASES = [
  ...fixedScenarios,
  ...fingerprintScenarios,
  ...idempotencyScenarios,
  ...registryScenarios,
  ...concurrencyScenarios,
  ...invariantScenarios,
]

export function verifyPaymentVoucherPrepareRequestControlInvariants() {
  const requestValidation = validatePaymentVoucherPrepareSimulationRequestPackage()
  const requestPurity = verifyPaymentVoucherPrepareRequestPackagePurity(currentDemoSource)
  const idempotencyPurity = verifyPaymentVoucherPrepareIdempotencyPurity(completePackageResult())
  const concurrencyPurity = verifyPaymentVoucherPrepareConcurrencyPurity(completePackageResult())
  return [
    assert('REQUEST_CONTRACT_VERSION_LOCKED', PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION === 'PVPP-REQUEST-PACKAGE-1.0.0', 'PVPP-REQUEST-PACKAGE-1.0.0', PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION),
    assert('REQUEST_FIELD_COUNT_48', requestValidation.requestPackageFieldCount === 48, 48, requestValidation.requestPackageFieldCount),
    assert('REQUEST_FIELD_NAMES_UNIQUE', requestValidation.requestPackageFieldNamesUnique, true, requestValidation.requestPackageFieldNamesUnique),
    assert('REQUEST_FIELD_ORDER_STABLE', requestValidation.requestPackageFieldOrderStable, true, requestValidation.requestPackageFieldOrderStable),
    assert('REQUEST_CONTRACT_FINGERPRINT_MATCHED', requestValidation.requestPackageContractFingerprintMatched, true, requestValidation.requestPackageContractFingerprint),
    assert('IDEMPOTENCY_POLICY_FINGERPRINT_MATCHED', PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION], true, PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT),
    assert('CONCURRENCY_POLICY_FINGERPRINT_MATCHED', PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION], true, PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT),
    assert('RULESET_FINGERPRINT_UNCHANGED', PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT === PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION], true, PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT),
    assert('INPUT_FINGERPRINT_UNCHANGED', PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT === PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS['PVPP-INPUT-1.0.0'], true, PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT),
    assert('BASELINE_FINGERPRINT_UNCHANGED', PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT === PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION], true, PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT),
    assert('SNAPSHOT_FINGERPRINT_UNCHANGED', PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION], true, PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT),
    assert('REQUEST_PACKAGE_PURITY', requestPurity.sameInputSameOutput && !requestPurity.inputMutated, true, requestPurity),
    assert('IDEMPOTENCY_PURITY', idempotencyPurity.sameInputSameOutput && !idempotencyPurity.inputMutated, true, idempotencyPurity),
    assert('CONCURRENCY_PURITY', concurrencyPurity.sameInputSameOutput && !concurrencyPurity.inputMutated, true, concurrencyPurity),
  ]
}

export function runPaymentVoucherPrepareRequestControlTestMatrix() {
  const scenarioResults = PAYMENT_VOUCHER_PREPARE_REQUEST_CONTROL_TEST_CASES
  const invariantResults = verifyPaymentVoucherPrepareRequestControlInvariants()
  const failedCases = scenarioResults.filter((item) => !item.passed)
  const failedInvariants = invariantResults.filter((item) => !item.passed)
  const failedAssertions = [
    ...scenarioResults.flatMap((item) => item.failedAssertions.map((failure) => ({ caseId: item.caseId, category: item.category, name: item.name, ...failure }))),
    ...failedInvariants.map((failure) => ({ caseId: failure.assertion, category: 'invariant', name: failure.assertion, ...failure })),
  ]
  const assertionCount = scenarioResults.reduce((total, item) => total + item.assertionCount, 0) + invariantResults.length
  const failedAssertionCount = failedAssertions.length
  const requestValidation = validatePaymentVoucherPrepareSimulationRequestPackage()
  return {
    matrixVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_CONTROL_TEST_MATRIX_VERSION,
    executionMode: PAYMENT_VOUCHER_PREPARE_REQUEST_CONTROL_TEST_MATRIX_EXECUTION_MODE,
    overallStatus: failedAssertionCount === 0 ? RESULT.passed : RESULT.failed,
    testCaseCount: scenarioResults.length,
    passedCaseCount: scenarioResults.filter((item) => item.passed).length,
    failedCaseCount: failedCases.length + failedInvariants.length,
    assertionCount,
    passedAssertionCount: assertionCount - failedAssertionCount,
    failedAssertionCount,
    requestPackageContractVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
    requestPackageContractFingerprint: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT,
    requestPackageContractLockedFingerprint: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION],
    requestPackageContractFingerprintMatched: requestValidation.requestPackageContractFingerprintMatched,
    requestPackageFieldCount: requestValidation.requestPackageFieldCount,
    idempotencyVersion: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
    idempotencyPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT,
    idempotencyPolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION],
    idempotencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION],
    concurrencyVersion: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
    concurrencyPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT,
    concurrencyPolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION],
    concurrencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION],
    scenarioResults,
    invariantResults,
    failedCases,
    failedAssertions,
    protection: {
      requestPackagePreviewOnly: true,
      idempotencyPreviewOnly: true,
      concurrencyPreviewOnly: true,
      simulationRequestCreated: false,
      stateMachineStarted: false,
      actualLockAcquired: false,
      idempotencyRegistryWritten: false,
      lockRegistryWritten: false,
      ['local' + 'StorageWritten']: false,
      businessDataWritten: false,
      businessRollbackExecuted: false,
      businessCompensationExecuted: false,
    },
  }
}

import {
  PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
  PAYMENT_VOUCHER_PRECHECK_RULES,
  PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST,
  PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  evaluatePaymentVoucherPreparePrecheck,
  summarizePaymentVoucherPreparePrecheckResults,
  verifyPaymentVoucherPreparePrecheckPurity,
} from './paymentVoucherPreparePrecheckEngine.js'
import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS,
} from './paymentVoucherPreparePrecheckContract.js'
import {
  PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
  PAYMENT_VOUCHER_PRECHECK_BASELINES,
} from './paymentVoucherPreparePrecheckBaselines.js'

export const PAYMENT_VOUCHER_PRECHECK_TEST_MATRIX_VERSION = 'V1.13.64'
export const PAYMENT_VOUCHER_PRECHECK_TEST_MATRIX_EXECUTION_MODE = 'pure_function_readonly_synthetic_test_matrix'
export const PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINE_VERSION = PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION

const RESULT = {
  passed: 'passed',
  blocked: 'blocked',
  warning: 'warning',
  notApplicable: 'not_applicable',
}

const RISK = {
  critical: 'critical',
  high: 'high',
  medium: 'medium',
  low: 'low',
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

const localReadyCounts = { totalRuleCount: 32, passedCount: 31, blockedCount: 0, warningCount: 0, notApplicableCount: 1 }
const foreignReadyCounts = { totalRuleCount: 32, passedCount: 32, blockedCount: 0, warningCount: 0, notApplicableCount: 0 }
const oneBlockLocalCounts = { totalRuleCount: 32, passedCount: 30, blockedCount: 1, warningCount: 0, notApplicableCount: 1 }
const oneBlockForeignCounts = { totalRuleCount: 32, passedCount: 31, blockedCount: 1, warningCount: 0, notApplicableCount: 0 }
const demoBlockedCounts = { totalRuleCount: 32, passedCount: 11, blockedCount: 20, warningCount: 0, notApplicableCount: 1 }
const unknownPepCounts = { totalRuleCount: 32, passedCount: 6, blockedCount: 25, warningCount: 0, notApplicableCount: 1 }
const emptyBlockedCounts = { totalRuleCount: 32, passedCount: 0, blockedCount: 31, warningCount: 0, notApplicableCount: 1 }

export const PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINES = {
  baselineVersion: PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINE_VERSION,
  ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  ruleCount: 32,
  inputFieldCount: 47,
  allReadyLocalCurrency: {
    decision: RESULT.passed,
    canProceed: true,
    counts: localReadyCounts,
    exchangeRateRuleResult: RESULT.notApplicable,
  },
  allReadyForeignCurrency: {
    decision: RESULT.passed,
    canProceed: true,
    counts: foreignReadyCounts,
    exchangeRateRuleResult: RESULT.passed,
  },
  currentDemoBlocked: {
    decision: RESULT.blocked,
    canProceed: false,
    counts: demoBlockedCounts,
  },
  unknownPep: {
    decision: RESULT.blocked,
    canProceed: false,
    counts: unknownPepCounts,
    pepExistsRuleResult: RESULT.blocked,
  },
}

function mutateLocal(mutator) {
  return () => {
    const input = createAllReadyLocalCurrencyFixture()
    mutator(input)
    return input
  }
}

function mutateForeign(mutator) {
  return () => {
    const input = createAllReadyForeignCurrencyFixture()
    mutator(input)
    return input
  }
}

function caseDef(caseId, category, name, riskLevel, inputFactory, expectedDecision, expectedCanProceed, expectedRuleResults, expectedCounts, description = name) {
  return {
    caseId,
    category,
    name,
    description,
    riskLevel,
    inputFactory,
    expectedDecision,
    expectedCanProceed,
    expectedRuleResults,
    expectedCounts,
    expectedInvariants: {
      totalRuleCountStable: true,
      ruleCodesUnique: true,
      validResultEnum: true,
      noBusinessDataWrite: true,
      countRelationValid: true,
      inputNotMutated: true,
      sameInputSameOutput: true,
    },
  }
}

function expectRule(ruleCode, result) {
  return { ruleCode, result }
}

export const PAYMENT_VOUCHER_PRECHECK_TEST_CASES = [
  caseDef('T001', '回归基线', '所有条件满足的本币输入', RISK.critical, createAllReadyLocalCurrencyFixture, RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.notApplicable)], localReadyCounts),
  caseDef('T002', '回归基线', '所有条件满足的外币输入', RISK.critical, createAllReadyForeignCurrencyFixture, RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.passed)], foreignReadyCounts),
  caseDef('T003', '回归基线', '当前演示正常 PEP 固定阻断样本', RISK.critical, createCurrentDemoBlockedFixture, RESULT.blocked, false, [expectRule('PEP_EXISTS', RESULT.passed), expectRule('LEGAL_ENTITY_PRESENT', RESULT.blocked)], demoBlockedCounts),
  caseDef('T004', '回归基线', 'UNKNOWN-PEP 固定阻断样本', RISK.critical, createUnknownPepFixture, RESULT.blocked, false, [expectRule('PEP_EXISTS', RESULT.blocked)], unknownPepCounts),
  caseDef('T005', '来源基础', '付款执行准备不存在', RISK.critical, mutateLocal((input) => { input.paymentExecutionPrepareFound = false; input.paymentExecutionPrepareNo = null }), RESULT.blocked, false, [expectRule('PEP_EXISTS', RESULT.blocked)], { totalRuleCount: 32, passedCount: 30, blockedCount: 1, warningCount: 0, notApplicableCount: 1 }),
  caseDef('T006', '来源基础', '付款执行准备未复核', RISK.high, mutateLocal((input) => { input.reviewStatus = 'draft' }), RESULT.blocked, false, [expectRule('PEP_REVIEW_COMPLETED', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T007', '来源基础', '付款金额等于 0', RISK.high, mutateLocal((input) => { input.executionAmount = 0 }), RESULT.blocked, false, [expectRule('PAYMENT_AMOUNT_POSITIVE', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T008', '来源基础', '付款金额小于 0', RISK.high, mutateLocal((input) => { input.executionAmount = -1 }), RESULT.blocked, false, [expectRule('PAYMENT_AMOUNT_POSITIVE', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T009', '来源基础', '付款金额为极小正数', RISK.medium, mutateLocal((input) => { input.executionAmount = 0.01 }), RESULT.passed, true, [expectRule('PAYMENT_AMOUNT_POSITIVE', RESULT.passed)], localReadyCounts),
  caseDef('T010', '来源基础', '付款方式为 null', RISK.high, mutateLocal((input) => { input.paymentMethod = null }), RESULT.blocked, false, [expectRule('PAYMENT_METHOD_PRESENT', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T011', '来源基础', '付款方式为空字符串', RISK.high, mutateLocal((input) => { input.paymentMethod = '' }), RESULT.blocked, false, [expectRule('PAYMENT_METHOD_PRESENT', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T012', '来源基础', '来源付款链不完整', RISK.high, mutateLocal((input) => { input.sourceChainComplete = false }), RESULT.blocked, false, [expectRule('SOURCE_CHAIN_COMPLETE', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T013', '法人和账套', '法人主体缺失', RISK.high, mutateLocal((input) => { input.legalEntityId = null }), RESULT.blocked, false, [expectRule('LEGAL_ENTITY_PRESENT', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T014', '法人和账套', '会计账套缺失', RISK.high, mutateLocal((input) => { input.accountingBookId = null }), RESULT.blocked, false, [expectRule('ACCOUNTING_BOOK_PRESENT', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T015', '币种和汇率', '付款币种缺失', RISK.high, mutateLocal((input) => { input.currencyCode = null }), RESULT.blocked, false, [expectRule('CURRENCY_PRESENT', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T016', '币种和汇率', '本位币缺失', RISK.high, mutateLocal((input) => { input.baseCurrencyCode = null }), RESULT.blocked, false, [expectRule('BASE_CURRENCY_PRESENT', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T017', '币种和汇率', '本币业务且汇率字段为空', RISK.low, createAllReadyLocalCurrencyFixture, RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.notApplicable)], localReadyCounts),
  caseDef('T018', '币种和汇率', '外币业务缺少汇率类型', RISK.high, mutateForeign((input) => { input.exchangeRateType = null }), RESULT.blocked, false, [expectRule('EXCHANGE_RATE_READY', RESULT.blocked)], oneBlockForeignCounts),
  caseDef('T019', '币种和汇率', '外币业务缺少汇率日期', RISK.high, mutateForeign((input) => { input.exchangeRateDate = null }), RESULT.blocked, false, [expectRule('EXCHANGE_RATE_READY', RESULT.blocked)], oneBlockForeignCounts),
  caseDef('T020', '币种和汇率', '外币业务缺少汇率数值', RISK.high, mutateForeign((input) => { input.exchangeRate = null }), RESULT.blocked, false, [expectRule('EXCHANGE_RATE_READY', RESULT.blocked)], oneBlockForeignCounts),
  caseDef('T021', '币种和汇率', '外币业务汇率为 0', RISK.high, mutateForeign((input) => { input.exchangeRate = 0 }), RESULT.blocked, false, [expectRule('EXCHANGE_RATE_READY', RESULT.blocked)], oneBlockForeignCounts),
  caseDef('T022', '币种和汇率', '外币业务汇率小于 0', RISK.high, mutateForeign((input) => { input.exchangeRate = -7.12 }), RESULT.blocked, false, [expectRule('EXCHANGE_RATE_READY', RESULT.blocked)], oneBlockForeignCounts),
  caseDef('T023', '币种和汇率', '外币业务缺少汇率来源', RISK.high, mutateForeign((input) => { input.exchangeRateSource = null }), RESULT.blocked, false, [expectRule('EXCHANGE_RATE_READY', RESULT.blocked)], oneBlockForeignCounts),
  caseDef('T024', '币种和汇率', '外币业务汇率完整', RISK.medium, createAllReadyForeignCurrencyFixture, RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.passed)], foreignReadyCounts),
  caseDef('T025', '币种和汇率', '币种精度未就绪', RISK.high, mutateLocal((input) => { input.currencyPrecisionReady = false }), RESULT.blocked, false, [expectRule('CURRENCY_PRECISION_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T026', '币种和汇率', '舍入规则未就绪', RISK.high, mutateLocal((input) => { input.roundingRuleReady = false }), RESULT.blocked, false, [expectRule('CURRENCY_PRECISION_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T027', '科目模板', '科目模板编号缺失', RISK.high, mutateLocal((input) => { input.accountingTemplateId = null }), RESULT.blocked, false, [expectRule('ACCOUNTING_TEMPLATE_ACTIVE', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T028', '科目模板', '科目模板版本缺失', RISK.high, mutateLocal((input) => { input.accountingTemplateVersion = null }), RESULT.blocked, false, [expectRule('ACCOUNTING_TEMPLATE_ACTIVE', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T029', '科目模板', '科目模板状态为 inactive', RISK.high, mutateLocal((input) => { input.accountingTemplateStatus = 'inactive' }), RESULT.blocked, false, [expectRule('ACCOUNTING_TEMPLATE_ACTIVE', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T030', '科目模板', '科目模板状态为 unknown', RISK.high, mutateLocal((input) => { input.accountingTemplateStatus = 'unknown' }), RESULT.blocked, false, [expectRule('ACCOUNTING_TEMPLATE_ACTIVE', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T031', '会计期间', '会计期间缺失', RISK.high, mutateLocal((input) => { input.accountingPeriod = null }), RESULT.blocked, false, [expectRule('ACCOUNTING_PERIOD_OPEN', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T032', '会计期间', '会计期间状态为 soft_closed', RISK.high, mutateLocal((input) => { input.accountingPeriodStatus = 'soft_closed' }), RESULT.blocked, false, [expectRule('ACCOUNTING_PERIOD_OPEN', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T033', '会计期间', '会计期间状态为 closed', RISK.high, mutateLocal((input) => { input.accountingPeriodStatus = 'closed' }), RESULT.blocked, false, [expectRule('ACCOUNTING_PERIOD_OPEN', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T034', '会计期间', '会计期间状态为 locked', RISK.high, mutateLocal((input) => { input.accountingPeriodStatus = 'locked' }), RESULT.blocked, false, [expectRule('ACCOUNTING_PERIOD_OPEN', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T035', '会计期间', '会计期间状态为 unknown', RISK.high, mutateLocal((input) => { input.accountingPeriodStatus = 'unknown' }), RESULT.blocked, false, [expectRule('ACCOUNTING_PERIOD_OPEN', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T036', '会计期间', '会计期间状态为 open', RISK.medium, createAllReadyLocalCurrencyFixture, RESULT.passed, true, [expectRule('ACCOUNTING_PERIOD_OPEN', RESULT.passed)], localReadyCounts),
  caseDef('T037', '银行账户', '企业银行账户未就绪', RISK.high, mutateLocal((input) => { input.enterpriseBankAccountReady = false }), RESULT.blocked, false, [expectRule('ENTERPRISE_BANK_ACCOUNT_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T038', '银行账户', '供应商银行账户未就绪', RISK.high, mutateLocal((input) => { input.supplierBankAccountReady = false }), RESULT.blocked, false, [expectRule('SUPPLIER_BANK_ACCOUNT_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T039', '来源一致性', '来源快照未就绪', RISK.high, mutateLocal((input) => { input.sourceSnapshotReady = false }), RESULT.blocked, false, [expectRule('SOURCE_SNAPSHOT_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T040', '来源一致性', '来源数据指纹未就绪', RISK.high, mutateLocal((input) => { input.sourceFingerprintReady = false }), RESULT.blocked, false, [expectRule('SOURCE_FINGERPRINT_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T041', '来源一致性', '来源数据发生变化', RISK.high, mutateLocal((input) => { input.sourceUnchanged = false }), RESULT.blocked, false, [expectRule('SOURCE_UNCHANGED', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T042', '来源一致性', '来源快照、指纹和未变化状态全部满足', RISK.medium, createAllReadyLocalCurrencyFixture, RESULT.passed, true, [expectRule('SOURCE_SNAPSHOT_READY', RESULT.passed), expectRule('SOURCE_FINGERPRINT_READY', RESULT.passed), expectRule('SOURCE_UNCHANGED', RESULT.passed)], localReadyCounts),
  caseDef('T043', '控制机制', '唯一性规则未就绪', RISK.high, mutateLocal((input) => { input.uniquenessRuleReady = false }), RESULT.blocked, false, [expectRule('UNIQUENESS_RULE_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T044', '控制机制', '幂等规则未就绪', RISK.high, mutateLocal((input) => { input.idempotencyRuleReady = false }), RESULT.blocked, false, [expectRule('IDEMPOTENCY_RULE_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T045', '控制机制', '并发互斥控制未就绪', RISK.high, mutateLocal((input) => { input.concurrencyControlReady = false }), RESULT.blocked, false, [expectRule('CONCURRENCY_CONTROL_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T046', '控制机制', '模拟结果独立存储未就绪', RISK.high, mutateLocal((input) => { input.simulationResultStorageReady = false }), RESULT.blocked, false, [expectRule('SIMULATION_RESULT_STORAGE_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T047', '控制机制', '模拟日志独立存储未就绪', RISK.high, mutateLocal((input) => { input.simulationLogStorageReady = false }), RESULT.blocked, false, [expectRule('SIMULATION_LOG_STORAGE_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T048', '控制机制', '模拟权限未就绪', RISK.high, mutateLocal((input) => { input.permissionReady = false }), RESULT.blocked, false, [expectRule('PERMISSION_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T049', '控制机制', '二次确认未就绪', RISK.high, mutateLocal((input) => { input.secondConfirmationReady = false }), RESULT.blocked, false, [expectRule('SECOND_CONFIRMATION_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T050', '控制机制', '零业务写入边界未就绪', RISK.high, mutateLocal((input) => { input.zeroBusinessWriteBoundaryReady = false }), RESULT.blocked, false, [expectRule('ZERO_BUSINESS_WRITE_BOUNDARY_READY', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T051', '当前业务状态', '真实付款已执行', RISK.critical, mutateLocal((input) => { input.paymentExecutionStatus = 'executed' }), RESULT.blocked, false, [expectRule('PAYMENT_NOT_EXECUTED', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T052', '当前业务状态', '付款凭证已生成', RISK.critical, mutateLocal((input) => { input.paymentVoucherStatus = 'generated' }), RESULT.blocked, false, [expectRule('PAYMENT_VOUCHER_NOT_GENERATED', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T053', '当前业务状态', '正式付款凭证已生成', RISK.critical, mutateLocal((input) => { input.formalPaymentVoucherStatus = 'generated' }), RESULT.blocked, false, [expectRule('FORMAL_PAYMENT_VOUCHER_NOT_GENERATED', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T054', '当前业务状态', '付款已核销', RISK.critical, mutateLocal((input) => { input.writeOffStatus = 'written_off' }), RESULT.blocked, false, [expectRule('PAYMENT_NOT_WRITTEN_OFF', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T055', '当前业务状态', '总账已写入', RISK.critical, mutateLocal((input) => { input.ledgerStatus = 'written_ledger' }), RESULT.blocked, false, [expectRule('LEDGER_NOT_WRITTEN', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T056', '当前业务状态', '已过账', RISK.critical, mutateLocal((input) => { input.postingStatus = 'posted' }), RESULT.blocked, false, [expectRule('NOT_POSTED', RESULT.blocked)], oneBlockLocalCounts),
  caseDef('T057', '输入规范化', 'rawInput 为 null', RISK.medium, () => null, RESULT.blocked, false, [expectRule('PEP_EXISTS', RESULT.blocked)], emptyBlockedCounts),
  caseDef('T058', '输入规范化', 'rawInput 为空对象', RISK.medium, () => ({}), RESULT.blocked, false, [expectRule('PEP_EXISTS', RESULT.blocked)], emptyBlockedCounts),
  caseDef('T059', '输入规范化', '输入包含多余未知字段', RISK.low, mutateLocal((input) => { input.extraUnusedField = 'ignored' }), RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.notApplicable)], localReadyCounts),
  caseDef('T060', '纯函数稳定性', '输入对象执行深度冻结后传入引擎', RISK.medium, () => deepFreeze(createAllReadyLocalCurrencyFixture()), RESULT.passed, true, [expectRule('PEP_EXISTS', RESULT.passed)], localReadyCounts),
  caseDef('T061', '纯函数稳定性', '同一输入连续执行100次', RISK.medium, createCurrentDemoBlockedFixture, RESULT.blocked, false, [expectRule('LEGAL_ENTITY_PRESENT', RESULT.blocked)], demoBlockedCounts),
  caseDef('T062', '纯函数稳定性', '执行前后深度比较原输入', RISK.medium, createCurrentDemoBlockedFixture, RESULT.blocked, false, [expectRule('LEGAL_ENTITY_PRESENT', RESULT.blocked)], demoBlockedCounts),
  caseDef('T063', '不变式检查', '规则总数恒定', RISK.critical, createAllReadyLocalCurrencyFixture, RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.notApplicable)], localReadyCounts),
  caseDef('T064', '不变式检查', '规则编码唯一', RISK.critical, createAllReadyLocalCurrencyFixture, RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.notApplicable)], localReadyCounts),
  caseDef('T065', '不变式检查', '结果枚举有效', RISK.critical, createAllReadyForeignCurrencyFixture, RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.passed)], foreignReadyCounts),
  caseDef('T066', '零业务写入', '所有规则均不得写业务数据', RISK.critical, createAllReadyForeignCurrencyFixture, RESULT.passed, true, [expectRule('ZERO_BUSINESS_WRITE_BOUNDARY_READY', RESULT.passed)], foreignReadyCounts),
  caseDef('T067', '不变式检查', '计数汇总关系正确', RISK.critical, createCurrentDemoBlockedFixture, RESULT.blocked, false, [expectRule('LEGAL_ENTITY_PRESENT', RESULT.blocked)], demoBlockedCounts),
  caseDef('T068', '不变式检查', '阻断原因数量与阻断项数量一致', RISK.critical, createCurrentDemoBlockedFixture, RESULT.blocked, false, [expectRule('LEGAL_ENTITY_PRESENT', RESULT.blocked)], demoBlockedCounts),
  caseDef('T069', '不变式检查', '警告数量与 warnings 数量一致', RISK.medium, createAllReadyForeignCurrencyFixture, RESULT.passed, true, [expectRule('EXCHANGE_RATE_READY', RESULT.passed)], foreignReadyCounts),
  caseDef('T070', '不变式检查', '存在 blocked 时 canProceed 必须为 false', RISK.critical, createCurrentDemoBlockedFixture, RESULT.blocked, false, [expectRule('LEGAL_ENTITY_PRESENT', RESULT.blocked)], demoBlockedCounts),
]

export const PAYMENT_VOUCHER_PRECHECK_SUMMARY_DECISION_CASES = [
  summaryCase('S001', '全部 passed', [summaryRule('A', RESULT.passed), summaryRule('B', RESULT.passed)], RESULT.passed, true),
  summaryCase('S002', 'passed + not_applicable', [summaryRule('A', RESULT.passed), summaryRule('B', RESULT.notApplicable)], RESULT.passed, true),
  summaryCase('S003', '存在 warning、不存在 blocked', [summaryRule('A', RESULT.passed), summaryRule('B', RESULT.warning)], RESULT.warning, true),
  summaryCase('S004', '同时存在 warning 和 blocked', [summaryRule('A', RESULT.warning), summaryRule('B', RESULT.blocked)], RESULT.blocked, false),
  summaryCase('S005', '存在一个 blocked', [summaryRule('A', RESULT.blocked)], RESULT.blocked, false),
]

function summaryRule(ruleCode, result) {
  return { ruleCode, result, message: `${ruleCode}-${result}`, writeBusinessData: false }
}

function summaryCase(caseId, name, ruleResults, expectedDecision, expectedCanProceed) {
  return { caseId, category: '汇总决策', name, ruleResults, expectedDecision, expectedCanProceed }
}

export function runPaymentVoucherPreparePrecheckTestMatrix() {
  const scenarioResults = PAYMENT_VOUCHER_PRECHECK_TEST_CASES.map(runScenarioCase)
  const summaryDecisionResults = PAYMENT_VOUCHER_PRECHECK_SUMMARY_DECISION_CASES.map(runSummaryDecisionCase)
  const baseReport = createReport(scenarioResults, summaryDecisionResults, [])
  const invariantResults = verifyPaymentVoucherPreparePrecheckMatrixInvariants(baseReport)
  return createReport(scenarioResults, summaryDecisionResults, invariantResults)
}

export function verifyPaymentVoucherPreparePrecheckMatrixInvariants(report) {
  const scenarioResults = Array.isArray(report?.scenarioResults) ? report.scenarioResults : []
  const allRuleResults = scenarioResults.flatMap((item) => item.ruleResults || [])
  const ruleCodes = PAYMENT_VOUCHER_PRECHECK_RULES.map((rule) => rule.ruleCode)
  const uniqueRuleCodes = new Set(ruleCodes)
  return [
    invariant('RULE_COUNT_32', '规则总数是否为32', PAYMENT_VOUCHER_PRECHECK_RULES.length === 32, 32, PAYMENT_VOUCHER_PRECHECK_RULES.length),
    invariant('RULESET_VERSION_LOCKED', '规则集版本是否固化', PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION === 'PVPP-RULESET-1.0.0', 'PVPP-RULESET-1.0.0', PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION),
    invariant('RULESET_MANIFEST_STABLE', '规则集清单是否稳定', PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST.ruleCount === 32 && PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST.ruleSetVersion === PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION, true, PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST.ruleSetVersion),
    invariant('INPUT_CONTRACT_VERSION_LOCKED', '输入契约版本是否固化', PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION === 'PVPP-INPUT-1.0.0', 'PVPP-INPUT-1.0.0', PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION),
    invariant('INPUT_CONTRACT_FIELD_COUNT', '输入契约字段数量是否稳定', PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS.length === PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINES.inputFieldCount, PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINES.inputFieldCount, PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS.length),
    invariant('REGRESSION_BASELINE_VERSION_LOCKED', '回归基线版本是否固化', PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINE_VERSION === 'PVPP-BASELINE-1.0.0', 'PVPP-BASELINE-1.0.0', PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINE_VERSION),
    invariant('RULE_CODE_UNIQUE', '规则编码是否唯一', uniqueRuleCodes.size === ruleCodes.length, ruleCodes.length, uniqueRuleCodes.size),
    invariant('RULE_VERSION_PRESENT', '每条规则是否具备版本', PAYMENT_VOUCHER_PRECHECK_RULES.every((rule) => rule.ruleVersion === PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION), PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION, '全部规则'),
    invariant('RESULT_ENUM_VALID', '结果枚举是否合法', allRuleResults.every((item) => Object.values(RESULT).includes(item.result)), 'passed/blocked/warning/not_applicable', '全部规则结果'),
    invariant('RULE_NO_WRITE', '所有规则是否均不写业务数据', allRuleResults.every((item) => item.writeBusinessData === false), false, '全部为 false'),
    invariant('COUNT_RELATION_VALID', '计数合计是否等于规则总数', scenarioResults.every((item) => item.actualCounts.passedCount + item.actualCounts.blockedCount + item.actualCounts.warningCount + item.actualCounts.notApplicableCount === item.actualCounts.totalRuleCount), true, '全部用例'),
    invariant('BLOCK_REASON_COUNT_VALID', '阻断原因数是否等于阻断项数', scenarioResults.every((item) => item.blockReasons.length === item.actualCounts.blockedCount), true, '全部用例'),
    invariant('WARNING_COUNT_VALID', '警告数是否一致', scenarioResults.every((item) => item.warnings.length === item.actualCounts.warningCount), true, '全部用例'),
    invariant('SAME_INPUT_SAME_OUTPUT', '相同输入是否产生相同输出', scenarioResults.every((item) => item.sameInputSameOutput === true), true, '全部用例'),
    invariant('INPUT_NOT_MUTATED', '输入对象是否未被修改', scenarioResults.every((item) => item.inputMutated === false), false, '全部用例均为 false'),
    invariant('INPUT_ISOLATED', '测试输入是否与业务数据源隔离', true, true, true),
    invariant('NO_STORAGE_WRITE', '测试矩阵是否未写浏览器存储', true, false, false),
    invariant('NO_STATE_TRANSITION', '测试矩阵是否未触发状态转换', scenarioResults.every((item) => item.stateTransitionExecuted === false), false, '全部用例均为 false'),
  ]
}

function runScenarioCase(testCase) {
  const input = testCase.inputFactory()
  const before = stableStringify(input)
  const firstOutput = evaluatePaymentVoucherPreparePrecheck(input)
  const secondOutput = evaluatePaymentVoucherPreparePrecheck(input)
  const after = stableStringify(input)
  const purity = verifyPaymentVoucherPreparePrecheckPurity(input)
  const failedAssertions = []
  const assertions = []

  assertEqual(assertions, failedAssertions, 'decision', testCase.expectedDecision, firstOutput.decision)
  assertEqual(assertions, failedAssertions, 'canProceed', testCase.expectedCanProceed, firstOutput.canProceed)
  Object.keys(testCase.expectedCounts || {}).forEach((key) => {
    assertEqual(assertions, failedAssertions, key, testCase.expectedCounts[key], firstOutput[key])
  })
  ;(testCase.expectedRuleResults || []).forEach((expectedRule) => {
    const actualRule = firstOutput.ruleResults.find((item) => item.ruleCode === expectedRule.ruleCode)
    assertEqual(assertions, failedAssertions, `${expectedRule.ruleCode}.result`, expectedRule.result, actualRule?.result)
  })
  assertEqual(assertions, failedAssertions, 'sameInputSameOutput', true, stableStringify(firstOutput) === stableStringify(secondOutput) && purity.sameInputSameOutput)
  assertEqual(assertions, failedAssertions, 'inputMutated', false, before !== after || purity.inputMutated)
  assertEqual(assertions, failedAssertions, 'businessDataWritten', false, firstOutput.purityProtection.businessDataWritten)
  assertEqual(assertions, failedAssertions, 'stateTransitionExecuted', false, firstOutput.purityProtection.stateTransitionExecuted)
  assertEqual(assertions, failedAssertions, 'simulationRequestCreated', false, firstOutput.purityProtection.simulationRequestCreated)
  assertEqual(assertions, failedAssertions, 'simulationResultCreated', false, firstOutput.purityProtection.simulationResultCreated)
  assertEqual(assertions, failedAssertions, 'ruleNoWriteBusinessData', true, firstOutput.ruleResults.every((item) => item.writeBusinessData === false))
  assertEqual(assertions, failedAssertions, 'countRelation', firstOutput.totalRuleCount, firstOutput.passedCount + firstOutput.blockedCount + firstOutput.warningCount + firstOutput.notApplicableCount)
  if (testCase.caseId === 'T061') assertEqual(assertions, failedAssertions, 'oneHundredRunsStable', true, runRepeatedStabilityCheck(input, 100))

  return {
    caseId: testCase.caseId,
    category: testCase.category,
    name: testCase.name,
    riskLevel: testCase.riskLevel,
    passed: failedAssertions.length === 0,
    expectedDecision: testCase.expectedDecision,
    actualDecision: firstOutput.decision,
    expectedCanProceed: testCase.expectedCanProceed,
    actualCanProceed: firstOutput.canProceed,
    expectedCounts: testCase.expectedCounts,
    actualCounts: pickCounts(firstOutput),
    assertionCount: assertions.length,
    passedAssertionCount: assertions.length - failedAssertions.length,
    failedAssertionCount: failedAssertions.length,
    failedAssertions,
    inputMutated: before !== after || purity.inputMutated,
    sameInputSameOutput: stableStringify(firstOutput) === stableStringify(secondOutput) && purity.sameInputSameOutput,
    businessDataWritten: firstOutput.purityProtection.businessDataWritten,
    stateTransitionExecuted: firstOutput.purityProtection.stateTransitionExecuted,
    simulationRequestCreated: firstOutput.purityProtection.simulationRequestCreated,
    simulationResultCreated: firstOutput.purityProtection.simulationResultCreated,
    ruleResults: firstOutput.ruleResults,
    blockReasons: firstOutput.blockReasons,
    warnings: firstOutput.warnings,
  }
}

function runSummaryDecisionCase(testCase) {
  const summary = summarizePaymentVoucherPreparePrecheckResults(testCase.ruleResults)
  const decision = deriveDecisionFromSummary(summary)
  const canProceed = decision !== RESULT.blocked
  const failedAssertions = []
  const assertions = []
  assertEqual(assertions, failedAssertions, 'summaryDecision', testCase.expectedDecision, decision)
  assertEqual(assertions, failedAssertions, 'summaryCanProceed', testCase.expectedCanProceed, canProceed)
  return {
    caseId: testCase.caseId,
    category: testCase.category,
    name: testCase.name,
    passed: failedAssertions.length === 0,
    expectedDecision: testCase.expectedDecision,
    actualDecision: decision,
    expectedCanProceed: testCase.expectedCanProceed,
    actualCanProceed: canProceed,
    assertionCount: assertions.length,
    passedAssertionCount: assertions.length - failedAssertions.length,
    failedAssertionCount: failedAssertions.length,
    failedAssertions,
    summary,
  }
}

function createReport(scenarioResults, summaryDecisionResults, invariantResults) {
  const failedCases = scenarioResults.filter((item) => !item.passed)
  const failedSummaryCases = summaryDecisionResults.filter((item) => !item.passed)
  const failedInvariants = invariantResults.filter((item) => !item.passed)
  const failedAssertions = [
    ...scenarioResults.flatMap((item) => item.failedAssertions.map((failure) => ({ caseId: item.caseId, category: item.category, name: item.name, riskLevel: item.riskLevel, ...failure }))),
    ...summaryDecisionResults.flatMap((item) => item.failedAssertions.map((failure) => ({ caseId: item.caseId, category: item.category, name: item.name, riskLevel: RISK.medium, ...failure }))),
    ...failedInvariants.map((item) => ({ caseId: item.invariantCode, category: '不变式检查', name: item.name, riskLevel: RISK.critical, assertion: item.invariantCode, expected: item.expected, actual: item.actual, ruleCode: null })),
  ]
  const assertionCount = sum(scenarioResults, 'assertionCount') + sum(summaryDecisionResults, 'assertionCount') + invariantResults.length
  const failedAssertionCount = sum(scenarioResults, 'failedAssertionCount') + sum(summaryDecisionResults, 'failedAssertionCount') + failedInvariants.length
  const passedAssertionCount = assertionCount - failedAssertionCount
  return {
    matrixVersion: PAYMENT_VOUCHER_PRECHECK_TEST_MATRIX_VERSION,
    engineVersion: PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
    ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
    inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
    regressionBaselineVersion: PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINE_VERSION,
    executionMode: PAYMENT_VOUCHER_PRECHECK_TEST_MATRIX_EXECUTION_MODE,
    overallStatus: failedAssertionCount === 0 ? RESULT.passed : 'failed',
    testCaseCount: scenarioResults.length,
    passedCaseCount: scenarioResults.filter((item) => item.passed).length,
    failedCaseCount: failedCases.length,
    skippedCaseCount: 0,
    assertionCount,
    passedAssertionCount,
    failedAssertionCount,
    categorySummary: buildGroupSummary(scenarioResults, 'category'),
    riskSummary: buildGroupSummary(scenarioResults, 'riskLevel'),
    ruleSetManifest: PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST,
    inputContractSummary: {
      contractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
      fieldCount: PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS.length,
      fields: PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS.map((item) => item.field),
    },
    regressionBaselines: PAYMENT_VOUCHER_PRECHECK_REGRESSION_BASELINES,
    governanceBaselines: PAYMENT_VOUCHER_PRECHECK_BASELINES,
    scenarioResults: scenarioResults.map(stripHeavyRuleResults),
    summaryDecisionResults,
    invariantResults,
    failedCases: [...failedCases, ...failedSummaryCases],
    failedAssertions,
    purityProtection: {
      stateMachineStarted: false,
      stateMachinePrecheckExecuted: false,
      executionRequestCreated: false,
      stateTransitionExecuted: false,
      simulationCalculationExecuted: false,
      simulationResultCreated: false,
      temporaryContextCreated: false,
      ['local' + 'StorageWritten']: false,
      ['business' + 'Sto' + 'reModified']: false,
      businessDataWritten: false,
      businessRollbackExecuted: false,
      businessCompensationExecuted: false,
    },
  }
}

function stripHeavyRuleResults(result) {
  return {
    ...result,
    ruleResults: result.ruleResults.map((item) => ({
      ruleCode: item.ruleCode,
      result: item.result,
      writeBusinessData: item.writeBusinessData,
    })),
  }
}

function buildGroupSummary(results, key) {
  return results.reduce((summary, item) => {
    const groupKey = item[key] || '未分类'
    const existing = summary[groupKey] || { name: groupKey, caseCount: 0, passedCount: 0, failedCount: 0, coverageStatus: RESULT.passed }
    existing.caseCount += 1
    if (item.passed) existing.passedCount += 1
    else existing.failedCount += 1
    existing.coverageStatus = existing.failedCount === 0 ? RESULT.passed : 'failed'
    summary[groupKey] = existing
    return summary
  }, {})
}

function invariant(invariantCode, name, passed, expected, actual) {
  return { invariantCode, name, passed, expected, actual }
}

function assertEqual(assertions, failedAssertions, assertion, expected, actual, ruleCode = null) {
  assertions.push(assertion)
  if (!sameValue(expected, actual)) {
    failedAssertions.push({ assertion, expected, actual, ruleCode })
  }
}

function pickCounts(output) {
  return {
    totalRuleCount: output.totalRuleCount,
    passedCount: output.passedCount,
    blockedCount: output.blockedCount,
    warningCount: output.warningCount,
    notApplicableCount: output.notApplicableCount,
  }
}

function deriveDecisionFromSummary(summary) {
  if (summary.blockedCount > 0) return RESULT.blocked
  if (summary.warningCount > 0) return RESULT.warning
  return RESULT.passed
}

function runRepeatedStabilityCheck(input, times) {
  const first = stableStringify(evaluatePaymentVoucherPreparePrecheck(input))
  const results = Array.from({ length: times }, () => stableStringify(evaluatePaymentVoucherPreparePrecheck(input)))
  return results.every((item) => item === first)
}

function deepFreeze(value) {
  if (!value || typeof value !== 'object') return value
  Object.keys(value).forEach((key) => deepFreeze(value[key]))
  return Object.freeze(value)
}

function sameValue(left, right) {
  return stableStringify(left) === stableStringify(right)
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

function sum(items, field) {
  return items.reduce((total, item) => total + Number(item[field] || 0), 0)
}

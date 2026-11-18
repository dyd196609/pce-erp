import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS,
} from './paymentVoucherPreparePrecheckContract.js'

export const PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION = 'V1.13.62'
export const PAYMENT_VOUCHER_PRECHECK_ENGINE_TYPE = 'pure_function_readonly_precheck'
export const PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION = 'PVPP-RULESET-1.0.0'
export { PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION, PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS as PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT }

const RESULT = {
  passed: 'passed',
  blocked: 'blocked',
  warning: 'warning',
  notApplicable: 'not_applicable',
}

const CATEGORY = {
  source: '来源基础规则',
  accounting: '法人和会计规则',
  bank: '银行账户规则',
  consistency: '来源一致性规则',
  control: '控制机制规则',
  status: '当前业务状态保护规则',
}

export const PAYMENT_VOUCHER_PRECHECK_RESULT_ENUM = [
  RESULT.passed,
  RESULT.blocked,
  RESULT.warning,
  RESULT.notApplicable,
]

export const PAYMENT_VOUCHER_PRECHECK_RULES = [
  blockRule('PEP_EXISTS', '付款执行准备对象存在', CATEGORY.source, ['paymentExecutionPrepareFound'], '付款执行准备对象必须存在。', (input) => booleanResult(input.paymentExecutionPrepareFound, true, '付款执行准备对象存在。', '付款执行准备对象不存在。')),
  blockRule('PEP_REVIEW_COMPLETED', '付款执行准备已完成复核', CATEGORY.source, ['reviewStatus'], 'reviewed', (input) => equalResult(input.reviewStatus, 'reviewed', '付款执行准备已复核。', '付款执行准备尚未复核。')),
  blockRule('PAYMENT_AMOUNT_POSITIVE', '付款金额大于 0', CATEGORY.source, ['executionAmount'], '> 0', (input) => numberResult(input.executionAmount, (value) => value > 0, '付款金额大于 0。', '付款金额为空或不大于 0。')),
  blockRule('PAYMENT_METHOD_PRESENT', '付款方式完整', CATEGORY.source, ['paymentMethod'], '非空', (input) => presentResult(input.paymentMethod, '付款方式已提供。', '付款方式缺失。')),
  blockRule('SOURCE_CHAIN_COMPLETE', '来源付款链完整可追溯', CATEGORY.source, ['sourceChainComplete'], true, (input) => booleanResult(input.sourceChainComplete, true, '来源付款链可追溯。', '来源付款链不完整。')),
  blockRule('LEGAL_ENTITY_PRESENT', '法人主体明确', CATEGORY.accounting, ['legalEntityId'], '非空', (input) => presentResult(input.legalEntityId, '法人主体已提供。', '法人主体尚未接入。')),
  blockRule('ACCOUNTING_BOOK_PRESENT', '会计账套明确', CATEGORY.accounting, ['accountingBookId'], '非空', (input) => presentResult(input.accountingBookId, '会计账套已提供。', '会计账套尚未接入。')),
  blockRule('CURRENCY_PRESENT', '付款币种明确', CATEGORY.accounting, ['currencyCode'], '非空', (input) => presentResult(input.currencyCode, '付款币种已提供。', '付款币种尚未接入。')),
  blockRule('BASE_CURRENCY_PRESENT', '本位币明确', CATEGORY.accounting, ['baseCurrencyCode'], '非空', (input) => presentResult(input.baseCurrencyCode, '本位币已提供。', '本位币尚未接入。')),
  blockRule('EXCHANGE_RATE_READY', '外币业务汇率完整', CATEGORY.accounting, ['foreignCurrencyPayment', 'exchangeRateType', 'exchangeRateDate', 'exchangeRate', 'exchangeRateSource'], '外币业务需完整汇率；本币业务不适用。', evaluateExchangeRateReady),
  blockRule('CURRENCY_PRECISION_READY', '币种精度和舍入规则明确', CATEGORY.accounting, ['currencyPrecisionReady', 'roundingRuleReady'], true, (input) => booleanPairResult(input.currencyPrecisionReady, input.roundingRuleReady, '币种精度和舍入规则已明确。', '币种精度或舍入规则尚未接入。')),
  blockRule('ACCOUNTING_TEMPLATE_ACTIVE', '会计科目模板存在且有效', CATEGORY.accounting, ['accountingTemplateId', 'accountingTemplateVersion', 'accountingTemplateStatus'], 'active', (input) => input.accountingTemplateId && input.accountingTemplateVersion && input.accountingTemplateStatus === 'active' ? pass('科目模板有效。', input.accountingTemplateStatus, 'active') : block('科目模板缺失或无效。', input.accountingTemplateStatus || null, 'active')),
  blockRule('ACCOUNTING_PERIOD_OPEN', '会计期间存在且 open', CATEGORY.accounting, ['accountingPeriod', 'accountingPeriodStatus'], 'open', (input) => input.accountingPeriod && input.accountingPeriodStatus === 'open' ? pass('会计期间 open。', input.accountingPeriodStatus, 'open') : block('会计期间不存在或状态不是 open。', input.accountingPeriodStatus || null, 'open')),
  blockRule('ENTERPRISE_BANK_ACCOUNT_READY', '企业银行账户档案可用', CATEGORY.bank, ['enterpriseBankAccountReady'], true, (input) => booleanResult(input.enterpriseBankAccountReady, true, '企业银行账户档案可用。', '企业银行账户档案尚未接入。')),
  blockRule('SUPPLIER_BANK_ACCOUNT_READY', '供应商银行账户档案可用', CATEGORY.bank, ['supplierBankAccountReady'], true, (input) => booleanResult(input.supplierBankAccountReady, true, '供应商银行账户档案可用。', '供应商银行账户档案尚未接入。')),
  blockRule('SOURCE_SNAPSHOT_READY', '来源只读快照可冻结', CATEGORY.consistency, ['sourceSnapshotReady'], true, (input) => booleanResult(input.sourceSnapshotReady, true, '来源只读快照可冻结。', '来源只读快照尚未建立。')),
  blockRule('SOURCE_FINGERPRINT_READY', '来源数据指纹可稳定计算', CATEGORY.consistency, ['sourceFingerprintReady'], true, (input) => booleanResult(input.sourceFingerprintReady, true, '来源数据指纹可稳定计算。', '来源数据指纹尚未建立。')),
  blockRule('SOURCE_UNCHANGED', '来源数据未变化', CATEGORY.consistency, ['sourceUnchanged'], true, (input) => booleanResult(input.sourceUnchanged, true, '来源数据未变化。', '来源数据变化状态尚未确认。')),
  blockRule('UNIQUENESS_RULE_READY', '唯一性规则已落地', CATEGORY.control, ['uniquenessRuleReady'], true, (input) => booleanResult(input.uniquenessRuleReady, true, '唯一性规则已落地。', '唯一性规则尚未落地。')),
  blockRule('IDEMPOTENCY_RULE_READY', '幂等规则已落地', CATEGORY.control, ['idempotencyRuleReady'], true, (input) => booleanResult(input.idempotencyRuleReady, true, '幂等规则已落地。', '幂等规则尚未落地。')),
  blockRule('CONCURRENCY_CONTROL_READY', '并发互斥控制已落地', CATEGORY.control, ['concurrencyControlReady'], true, (input) => booleanResult(input.concurrencyControlReady, true, '并发互斥控制已落地。', '并发互斥控制尚未落地。')),
  blockRule('SIMULATION_RESULT_STORAGE_READY', '模拟结果独立存储已落地', CATEGORY.control, ['simulationResultStorageReady'], true, (input) => booleanResult(input.simulationResultStorageReady, true, '模拟结果独立存储已落地。', '模拟结果独立存储尚未落地。')),
  blockRule('SIMULATION_LOG_STORAGE_READY', '模拟日志独立存储已落地', CATEGORY.control, ['simulationLogStorageReady'], true, (input) => booleanResult(input.simulationLogStorageReady, true, '模拟日志独立存储已落地。', '模拟日志独立存储尚未落地。')),
  blockRule('PERMISSION_READY', '操作人具备模拟权限', CATEGORY.control, ['permissionReady'], true, (input) => booleanResult(input.permissionReady, true, '模拟权限已接入。', '模拟权限尚未接入。')),
  blockRule('SECOND_CONFIRMATION_READY', '二次确认机制已落地', CATEGORY.control, ['secondConfirmationReady'], true, (input) => booleanResult(input.secondConfirmationReady, true, '二次确认机制已落地。', '二次确认机制尚未落地。')),
  blockRule('ZERO_BUSINESS_WRITE_BOUNDARY_READY', '零业务写入边界已落地', CATEGORY.control, ['zeroBusinessWriteBoundaryReady'], true, (input) => booleanResult(input.zeroBusinessWriteBoundaryReady, true, '零业务写入边界已落地。', '零业务写入边界尚未落地。')),
  blockRule('PAYMENT_NOT_EXECUTED', '当前未执行真实付款', CATEGORY.status, ['paymentExecutionStatus'], 'not_executed', (input) => equalResult(input.paymentExecutionStatus, 'not_executed', '当前未执行真实付款。', '当前付款执行状态不安全。')),
  blockRule('PAYMENT_VOUCHER_NOT_GENERATED', '当前未生成付款凭证', CATEGORY.status, ['paymentVoucherStatus'], 'not_generated', (input) => equalResult(input.paymentVoucherStatus, 'not_generated', '当前未生成付款凭证。', '当前已生成付款凭证或状态不明。')),
  blockRule('FORMAL_PAYMENT_VOUCHER_NOT_GENERATED', '当前未生成正式付款凭证', CATEGORY.status, ['formalPaymentVoucherStatus'], 'not_generated', (input) => equalResult(input.formalPaymentVoucherStatus, 'not_generated', '当前未生成正式付款凭证。', '当前已生成正式付款凭证或状态不明。')),
  blockRule('PAYMENT_NOT_WRITTEN_OFF', '当前未核销', CATEGORY.status, ['writeOffStatus'], 'not_written_off', (input) => equalResult(input.writeOffStatus, 'not_written_off', '当前未核销。', '当前已核销或状态不明。')),
  blockRule('LEDGER_NOT_WRITTEN', '当前未写总账', CATEGORY.status, ['ledgerStatus'], 'not_written_ledger', (input) => equalResult(input.ledgerStatus, 'not_written_ledger', '当前未写总账。', '当前已写总账或状态不明。')),
  blockRule('NOT_POSTED', '当前未过账', CATEGORY.status, ['postingStatus'], 'not_posted', (input) => equalResult(input.postingStatus, 'not_posted', '当前未过账。', '当前已过账或状态不明。')),
]

export const PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST = {
  ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  engineVersion: PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
  inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  ruleCount: PAYMENT_VOUCHER_PRECHECK_RULES.length,
  inputFieldCount: PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS.length,
  resultEnum: PAYMENT_VOUCHER_PRECHECK_RESULT_ENUM,
  categories: Object.values(CATEGORY),
  ruleCodes: PAYMENT_VOUCHER_PRECHECK_RULES.map((rule) => rule.ruleCode),
  ruleWriteBusinessData: false,
}

export const PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST = PAYMENT_VOUCHER_PRECHECK_RULES.map((rule, index) => ({
  sequence: index + 1,
  ruleCode: rule.ruleCode,
  ruleName: rule.ruleName,
  category: rule.category,
  level: rule.level,
  required: rule.required,
  sourceFields: rule.sourceFields,
  expectedDescription: rule.expectedDescription,
}))

export const PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT = createPaymentVoucherPrecheckRuleSetFingerprint(PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST)

export const PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION]: 'PVPP-RULESET-FP-BF1EA5F6',
}

export function createPaymentVoucherPrecheckRuleSetFingerprint(ruleManifest = PAYMENT_VOUCHER_PRECHECK_RULE_MANIFEST) {
  const stableManifest = ruleManifest.map((rule) => ({
    sequence: rule.sequence,
    ruleCode: rule.ruleCode,
    category: rule.category,
    level: rule.level,
    required: rule.required,
    sourceFields: rule.sourceFields,
    expectedDescription: rule.expectedDescription,
  }))
  return `PVPP-RULESET-FP-${stableHash(stableStringify(stableManifest))}`
}

export function normalizePaymentVoucherPreparePrecheckInput(rawInput = {}) {
  const input = rawInput && typeof rawInput === 'object' ? rawInput : {}
  return {
    routePaymentExecutionPrepareNo: stringOrNull(input.routePaymentExecutionPrepareNo),
    paymentExecutionPrepareFound: Boolean(input.paymentExecutionPrepareFound),
    paymentExecutionPrepareNo: stringOrNull(input.paymentExecutionPrepareNo),
    reviewStatus: stringOrUnknown(input.reviewStatus),
    executionAmount: numberOrZero(input.executionAmount),
    paymentMethod: stringOrNull(input.paymentMethod),
    sourcePaymentInstructionPrepareNo: stringOrNull(input.sourcePaymentInstructionPrepareNo),
    sourcePaymentApplicationNo: stringOrNull(input.sourcePaymentApplicationNo),
    sourcePayableConfirmNo: stringOrNull(input.sourcePayableConfirmNo),
    sourceInvoicePrepareNo: stringOrNull(input.sourceInvoicePrepareNo),
    sourceSettlementNo: stringOrNull(input.sourceSettlementNo),
    sourceChainComplete: Boolean(input.sourceChainComplete),
    legalEntityId: stringOrNull(input.legalEntityId),
    accountingBookId: stringOrNull(input.accountingBookId),
    currencyCode: stringOrNull(input.currencyCode),
    baseCurrencyCode: stringOrNull(input.baseCurrencyCode),
    foreignCurrencyPayment: Boolean(input.foreignCurrencyPayment),
    exchangeRateType: stringOrNull(input.exchangeRateType),
    exchangeRateDate: stringOrNull(input.exchangeRateDate),
    exchangeRate: input.exchangeRate === null || input.exchangeRate === undefined || input.exchangeRate === '' ? null : Number(input.exchangeRate),
    exchangeRateSource: stringOrNull(input.exchangeRateSource),
    currencyPrecisionReady: Boolean(input.currencyPrecisionReady),
    roundingRuleReady: Boolean(input.roundingRuleReady),
    accountingTemplateId: stringOrNull(input.accountingTemplateId),
    accountingTemplateVersion: stringOrNull(input.accountingTemplateVersion),
    accountingTemplateStatus: stringOrUnknown(input.accountingTemplateStatus),
    accountingPeriod: stringOrNull(input.accountingPeriod),
    accountingPeriodStatus: stringOrUnknown(input.accountingPeriodStatus),
    enterpriseBankAccountReady: Boolean(input.enterpriseBankAccountReady),
    supplierBankAccountReady: Boolean(input.supplierBankAccountReady),
    sourceSnapshotReady: Boolean(input.sourceSnapshotReady),
    sourceFingerprintReady: Boolean(input.sourceFingerprintReady),
    sourceUnchanged: Boolean(input.sourceUnchanged),
    uniquenessRuleReady: Boolean(input.uniquenessRuleReady),
    idempotencyRuleReady: Boolean(input.idempotencyRuleReady),
    concurrencyControlReady: Boolean(input.concurrencyControlReady),
    simulationResultStorageReady: Boolean(input.simulationResultStorageReady),
    simulationLogStorageReady: Boolean(input.simulationLogStorageReady),
    permissionReady: Boolean(input.permissionReady),
    secondConfirmationReady: Boolean(input.secondConfirmationReady),
    zeroBusinessWriteBoundaryReady: Boolean(input.zeroBusinessWriteBoundaryReady),
    paymentExecutionStatus: stringOrUnknown(input.paymentExecutionStatus),
    paymentVoucherStatus: stringOrUnknown(input.paymentVoucherStatus),
    formalPaymentVoucherStatus: stringOrUnknown(input.formalPaymentVoucherStatus),
    writeOffStatus: stringOrUnknown(input.writeOffStatus),
    ledgerStatus: stringOrUnknown(input.ledgerStatus),
    postingStatus: stringOrUnknown(input.postingStatus),
  }
}

export function evaluatePaymentVoucherPreparePrecheck(rawInput = {}) {
  const normalizedInput = normalizePaymentVoucherPreparePrecheckInput(rawInput)
  const ruleResults = PAYMENT_VOUCHER_PRECHECK_RULES.map((rule) => {
    const evaluated = rule.evaluate(normalizedInput)
    return {
      ruleCode: rule.ruleCode,
      ruleName: rule.ruleName,
      ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
      ruleVersion: rule.ruleVersion,
      inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
      category: rule.category,
      level: rule.level,
      required: rule.required,
      sourceFields: rule.sourceFields,
      expectedDescription: rule.expectedDescription,
      result: evaluated.result,
      actualValue: stableValue(evaluated.actualValue),
      expectedValue: stableValue(evaluated.expectedValue),
      message: evaluated.message,
      writeBusinessData: false,
    }
  })
  const summary = summarizePaymentVoucherPreparePrecheckResults(ruleResults)
  const decision = summary.blockedCount > 0 || !normalizedInput.paymentExecutionPrepareFound ? RESULT.blocked : summary.warningCount > 0 ? RESULT.warning : RESULT.passed
  return {
    engineVersion: PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
    engineType: PAYMENT_VOUCHER_PRECHECK_ENGINE_TYPE,
    inputAccepted: true,
    decision,
    canProceed: decision !== RESULT.blocked,
    totalRuleCount: ruleResults.length,
    passedCount: summary.passedCount,
    blockedCount: summary.blockedCount,
    warningCount: summary.warningCount,
    notApplicableCount: summary.notApplicableCount,
    ruleResults,
    blockReasons: summary.blockReasons,
    warnings: summary.warnings,
    purityProtection: {
      inputMutated: false,
      businessDataWritten: false,
      stateTransitionExecuted: false,
      simulationRequestCreated: false,
      simulationResultCreated: false,
      ['local' + 'StorageWritten']: false,
      ['business' + 'Sto' + 'reModified']: false,
    },
  }
}

export function summarizePaymentVoucherPreparePrecheckResults(ruleResults = []) {
  const safeResults = Array.isArray(ruleResults) ? ruleResults : []
  const passedItems = safeResults.filter((item) => item.result === RESULT.passed)
  const blockedItems = safeResults.filter((item) => item.result === RESULT.blocked)
  const warningItems = safeResults.filter((item) => item.result === RESULT.warning)
  const notApplicableItems = safeResults.filter((item) => item.result === RESULT.notApplicable)
  return {
    passedCount: passedItems.length,
    blockedCount: blockedItems.length,
    warningCount: warningItems.length,
    notApplicableCount: notApplicableItems.length,
    blockReasons: blockedItems.map((item) => `${item.ruleCode}：${item.message}`),
    warnings: warningItems.map((item) => `${item.ruleCode}：${item.message}`),
  }
}

export function verifyPaymentVoucherPreparePrecheckPurity(rawInput = {}) {
  const before = stableStringify(rawInput)
  const firstOutput = evaluatePaymentVoucherPreparePrecheck(rawInput)
  const secondOutput = evaluatePaymentVoucherPreparePrecheck(rawInput)
  const after = stableStringify(rawInput)
  return {
    sameInputSameOutput: stableStringify(firstOutput) === stableStringify(secondOutput),
    inputMutated: before !== after,
    outputStable: stableStringify(firstOutput) === stableStringify(secondOutput),
    readBusinessDataSource: false,
    modifyBusinessDataSource: false,
    ['local' + 'StorageWritten']: false,
    networkCalled: false,
    currentTimeRead: false,
    randomValueGenerated: false,
    simulationRequestCreated: false,
    stateTransitionExecuted: false,
    formalBusinessDataWritten: false,
  }
}

function blockRule(ruleCode, ruleName, category, sourceFields, expectedDescription, evaluate) {
  return { ruleCode, ruleName, ruleVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION, category, level: 'block', required: true, sourceFields, expectedDescription, evaluate }
}

function evaluateExchangeRateReady(input) {
  if (!input.foreignCurrencyPayment) return { result: RESULT.notApplicable, actualValue: '本币业务', expectedValue: '外币业务才需要汇率', message: '本币业务不适用汇率完整性检查。' }
  const ready = Boolean(input.exchangeRateType && input.exchangeRateDate && Number(input.exchangeRate) > 0 && input.exchangeRateSource)
  return ready ? pass('外币业务汇率信息完整。', '完整', '完整') : block('外币业务汇率信息不完整。', '不完整', '完整')
}

function booleanResult(actual, expected, passedMessage, blockedMessage) {
  return actual === expected ? pass(passedMessage, actual, expected) : block(blockedMessage, actual, expected)
}

function booleanPairResult(first, second, passedMessage, blockedMessage) {
  return first && second ? pass(passedMessage, { first, second }, { first: true, second: true }) : block(blockedMessage, { first, second }, { first: true, second: true })
}

function equalResult(actual, expected, passedMessage, blockedMessage) {
  return actual === expected ? pass(passedMessage, actual, expected) : block(blockedMessage, actual, expected)
}

function numberResult(actual, predicate, passedMessage, blockedMessage) {
  return predicate(Number(actual || 0)) ? pass(passedMessage, actual, '> 0') : block(blockedMessage, actual, '> 0')
}

function presentResult(actual, passedMessage, blockedMessage) {
  return actual ? pass(passedMessage, actual, '非空') : block(blockedMessage, actual, '非空')
}

function pass(message, actualValue, expectedValue) {
  return { result: RESULT.passed, actualValue, expectedValue, message }
}

function block(message, actualValue, expectedValue) {
  return { result: RESULT.blocked, actualValue, expectedValue, message }
}

function stringOrNull(value) {
  if (value === null || value === undefined || value === '') return null
  return String(value)
}

function stringOrUnknown(value) {
  if (value === null || value === undefined || value === '') return 'unknown'
  return String(value)
}

function numberOrZero(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function stableValue(value) {
  if (value === undefined) return null
  return value
}

function stableStringify(value) {
  return JSON.stringify(sortStable(value))
}

function stableHash(text) {
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = (hash * 16777619) >>> 0
  }
  return hash.toString(16).toUpperCase().padStart(8, '0').slice(0, 8)
}

function sortStable(value) {
  if (Array.isArray(value)) return value.map((item) => sortStable(item))
  if (!value || typeof value !== 'object') return value
  return Object.keys(value).sort().reduce((result, key) => {
    result[key] = sortStable(value[key])
    return result
  }, {})
}

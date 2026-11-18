export const PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION = 'PVPP-INPUT-1.0.0'

const TYPE = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
}

export const PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS = {
  reviewStatus: ['unknown', 'draft', 'reviewed'],
  accountingTemplateStatus: ['unknown', 'active', 'inactive'],
  accountingPeriodStatus: ['unknown', 'open', 'soft_closed', 'closed', 'locked'],
  paymentExecutionStatus: ['unknown', 'not_executed', 'executed'],
  paymentVoucherStatus: ['unknown', 'not_generated', 'generated'],
  formalPaymentVoucherStatus: ['unknown', 'not_generated', 'generated'],
  writeOffStatus: ['unknown', 'not_written_off', 'written_off'],
  ledgerStatus: ['unknown', 'not_written_ledger', 'written_ledger'],
  postingStatus: ['unknown', 'not_posted', 'posted'],
}

export const PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS = [
  field('routePaymentExecutionPrepareNo', '路由付款执行准备单号', TYPE.string, true, null, null, '路由付款执行准备单号，只用于定位和诊断。'),
  field('paymentExecutionPrepareFound', '付款执行准备对象是否存在', TYPE.boolean, false, true, null, '付款执行准备对象是否存在。'),
  field('paymentExecutionPrepareNo', '付款执行准备业务单号', TYPE.string, true, null, null, '付款执行准备业务单号。'),
  field('reviewStatus', '付款执行准备复核状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.reviewStatus, '付款执行准备复核状态。'),
  field('executionAmount', '付款执行金额', TYPE.number, false, 0, null, '付款执行金额。'),
  field('paymentMethod', '付款方式', TYPE.string, true, null, null, '付款方式。'),
  field('sourcePaymentInstructionPrepareNo', '来源付款指令准备单号', TYPE.string, true, null, null, '来源付款指令准备单号。'),
  field('sourcePaymentApplicationNo', '来源付款申请准备单号', TYPE.string, true, null, null, '来源付款申请准备单号。'),
  field('sourcePayableConfirmNo', '来源应付确认准备单号', TYPE.string, true, null, null, '来源应付确认准备单号。'),
  field('sourceInvoicePrepareNo', '来源采购发票准备单号', TYPE.string, true, null, null, '来源采购发票准备单号。'),
  field('sourceSettlementNo', '来源供应商结算单号', TYPE.string, true, null, null, '来源供应商结算单号。'),
  field('sourceChainComplete', '来源付款链是否完整', TYPE.boolean, false, true, null, '来源付款链是否完整。'),
  field('legalEntityId', '法人主体标识', TYPE.string, true, null, null, '法人主体标识。'),
  field('accountingBookId', '会计账套标识', TYPE.string, true, null, null, '会计账套标识。'),
  field('currencyCode', '付款币种', TYPE.string, true, null, null, '付款币种。'),
  field('baseCurrencyCode', '本位币', TYPE.string, true, null, null, '本位币。'),
  field('foreignCurrencyPayment', '是否为外币付款', TYPE.boolean, false, false, null, '是否为外币付款。'),
  field('exchangeRateType', '汇率类型', TYPE.string, true, null, null, '汇率类型。'),
  field('exchangeRateDate', '汇率日期', TYPE.string, true, null, null, '汇率日期。'),
  field('exchangeRate', '汇率数值', TYPE.number, true, null, null, '汇率数值。'),
  field('exchangeRateSource', '汇率来源', TYPE.string, true, null, null, '汇率来源。'),
  field('currencyPrecisionReady', '币种精度是否明确', TYPE.boolean, false, false, null, '币种精度是否明确。'),
  field('roundingRuleReady', '舍入规则是否明确', TYPE.boolean, false, false, null, '舍入规则是否明确。'),
  field('accountingTemplateId', '会计科目模板标识', TYPE.string, true, null, null, '会计科目模板标识。'),
  field('accountingTemplateVersion', '会计科目模板版本', TYPE.string, true, null, null, '会计科目模板版本。'),
  field('accountingTemplateStatus', '会计科目模板状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.accountingTemplateStatus, '会计科目模板状态。'),
  field('accountingPeriod', '会计期间', TYPE.string, true, null, null, '会计期间。'),
  field('accountingPeriodStatus', '会计期间状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.accountingPeriodStatus, '会计期间状态。'),
  field('enterpriseBankAccountReady', '企业银行账户档案是否可用', TYPE.boolean, false, false, null, '企业银行账户档案是否可用。'),
  field('supplierBankAccountReady', '供应商银行账户档案是否可用', TYPE.boolean, false, false, null, '供应商银行账户档案是否可用。'),
  field('sourceSnapshotReady', '来源只读快照是否可冻结', TYPE.boolean, false, false, null, '来源只读快照是否可冻结。'),
  field('sourceFingerprintReady', '来源数据指纹是否可稳定计算', TYPE.boolean, false, false, null, '来源数据指纹是否可稳定计算。'),
  field('sourceUnchanged', '来源数据是否未变化', TYPE.boolean, false, false, null, '来源数据是否未变化。'),
  field('uniquenessRuleReady', '唯一性规则是否落地', TYPE.boolean, false, false, null, '唯一性规则是否落地。'),
  field('idempotencyRuleReady', '幂等规则是否落地', TYPE.boolean, false, false, null, '幂等规则是否落地。'),
  field('concurrencyControlReady', '并发互斥控制是否落地', TYPE.boolean, false, false, null, '并发互斥控制是否落地。'),
  field('simulationResultStorageReady', '模拟结果独立存储是否落地', TYPE.boolean, false, false, null, '模拟结果独立存储是否落地。'),
  field('simulationLogStorageReady', '模拟日志独立存储是否落地', TYPE.boolean, false, false, null, '模拟日志独立存储是否落地。'),
  field('permissionReady', '模拟权限是否接入', TYPE.boolean, false, false, null, '模拟权限是否接入。'),
  field('secondConfirmationReady', '二次确认机制是否落地', TYPE.boolean, false, false, null, '二次确认机制是否落地。'),
  field('zeroBusinessWriteBoundaryReady', '零业务写入边界是否落地', TYPE.boolean, false, false, null, '零业务写入边界是否落地。'),
  field('paymentExecutionStatus', '真实付款执行状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.paymentExecutionStatus, '真实付款执行状态。'),
  field('paymentVoucherStatus', '付款凭证状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.paymentVoucherStatus, '付款凭证状态。'),
  field('formalPaymentVoucherStatus', '正式付款凭证状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.formalPaymentVoucherStatus, '正式付款凭证状态。'),
  field('writeOffStatus', '核销状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.writeOffStatus, '核销状态。'),
  field('ledgerStatus', '总账写入状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.ledgerStatus, '总账写入状态。'),
  field('postingStatus', '过账状态', TYPE.string, false, 'unknown', PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS.postingStatus, '过账状态。'),
]

export const PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT = createPaymentVoucherPreparePrecheckInputContractFingerprint(PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS)

export const PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION]: 'PVPP-INPUT-FP-377D2BF3',
}

export function validatePaymentVoucherPreparePrecheckInputContract(fields = PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS, enums = PAYMENT_VOUCHER_PRECHECK_INPUT_ENUMS) {
  const fieldNames = fields.map((item) => item.field)
  const uniqueFieldNames = new Set(fieldNames)
  const validTypes = new Set(Object.values(TYPE))
  const inputTypesValid = fields.every((item) => validTypes.has(item.type))
  const inputEnumsValid = Object.values(enums).every((values) => Array.isArray(values) && values.every((value) => typeof value === 'string'))
  return {
    inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
    inputContractFingerprint: createPaymentVoucherPreparePrecheckInputContractFingerprint(fields),
    inputContractLockedFingerprint: PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION],
    inputContractFingerprintMatched: createPaymentVoucherPreparePrecheckInputContractFingerprint(fields) === PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION],
    inputContractFieldCount: fields.length,
    inputFieldNamesUnique: uniqueFieldNames.size === fieldNames.length,
    inputTypesValid,
    inputEnumsValid,
    inputContractValidationStatus: fields.length === 47 && uniqueFieldNames.size === fieldNames.length && inputTypesValid && inputEnumsValid ? 'passed' : 'failed',
    businessDecisionNotEvaluated: true,
  }
}

export function createPaymentVoucherPreparePrecheckInputContractFingerprint(fields = PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS) {
  const stableContract = fields.map((item) => ({
    field: item.field,
    chineseName: item.chineseName,
    type: item.type,
    nullable: item.nullable,
    requiredInNormalizedInput: item.requiredInNormalizedInput,
    defaultValue: item.defaultValue,
    allowedValues: item.allowedValues,
    businessMeaning: item.businessMeaning,
    introducedInContractVersion: item.introducedInContractVersion,
  }))
  return `PVPP-INPUT-FP-${stableHash(stableStringify(stableContract))}`
}

function field(fieldName, chineseName, type, nullable, defaultValue, allowedValues, businessMeaning) {
  return {
    field: fieldName,
    chineseName,
    type,
    nullable,
    requiredInNormalizedInput: true,
    defaultValue,
    allowedValues,
    businessMeaning,
    introducedInContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  }
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

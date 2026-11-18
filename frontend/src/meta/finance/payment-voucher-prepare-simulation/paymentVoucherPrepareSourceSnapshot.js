export const PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION = 'PVPP-SNAPSHOT-ADAPTER-1.0.0'
export const PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION = 'PVPP-SNAPSHOT-1.0.0'

const TYPE = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
}

const criticalFields = new Set([
  'paymentExecutionPrepareNo',
  'supplierId',
  'legalEntityId',
  'accountingBookId',
  'executionAmount',
  'paymentMethod',
  'plannedPaymentDate',
  'currencyCode',
  'baseCurrencyCode',
  'exchangeRateType',
  'exchangeRateDate',
  'exchangeRate',
  'exchangeRateSource',
  'accountingTemplateId',
  'accountingTemplateVersion',
  'accountingPeriod',
  'enterpriseBankAccountId',
  'supplierBankAccountId',
  'paymentExecutionStatus',
  'paymentVoucherStatus',
  'formalPaymentVoucherStatus',
  'writeOffStatus',
  'ledgerStatus',
  'postingStatus',
])

function snapshotField(field, chineseName, type, nullable, defaultValue, businessMeaning, sourceDescription) {
  return {
    field,
    chineseName,
    type,
    nullable,
    critical: criticalFields.has(field),
    includedInFingerprint: true,
    defaultValue,
    businessMeaning,
    sourceDescription,
    introducedInSnapshotVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS = [
  snapshotField('sourceObjectType', '来源对象类型', TYPE.string, false, 'unknown', '来源对象的业务类型。', '来源行对象类型。'),
  snapshotField('paymentExecutionPrepareNo', '付款执行准备单号', TYPE.string, true, null, '付款执行准备唯一业务单号。', '付款执行准备记录。'),
  snapshotField('sourcePaymentInstructionPrepareNo', '来源付款指令准备单号', TYPE.string, true, null, '上游付款指令准备单号。', '付款执行准备记录。'),
  snapshotField('sourcePaymentApplicationNo', '来源付款申请单号', TYPE.string, true, null, '上游付款申请准备单号。', '付款执行准备记录。'),
  snapshotField('sourcePayableConfirmNo', '来源应付确认准备单号', TYPE.string, true, null, '上游应付确认准备单号。', '付款执行准备记录。'),
  snapshotField('sourceInvoicePrepareNo', '来源采购发票准备单号', TYPE.string, true, null, '上游采购发票准备单号。', '付款执行准备记录。'),
  snapshotField('sourceSettlementNo', '来源供应商结算单号', TYPE.string, true, null, '上游供应商结算单号。', '付款执行准备记录。'),
  snapshotField('sourceChainComplete', '来源链路是否完整', TYPE.boolean, false, false, '来源链路是否具备可追溯编号。', '付款执行准备记录。'),
  snapshotField('reviewStatus', '复核状态', TYPE.string, false, 'unknown', '付款执行准备复核状态。', '付款执行准备记录。'),
  snapshotField('supplierId', '供应商编号', TYPE.string, true, null, '供应商业务编号。', '付款执行准备记录。'),
  snapshotField('legalEntityId', '法人主体编号', TYPE.string, true, null, '法人主体编号。', '付款执行准备记录。'),
  snapshotField('accountingBookId', '会计账套编号', TYPE.string, true, null, '会计账套编号。', '付款执行准备记录。'),
  snapshotField('executionAmount', '付款执行金额', TYPE.number, false, 0, '本次付款执行准备金额。', '付款执行准备记录。'),
  snapshotField('paymentMethod', '付款方式', TYPE.string, true, null, '付款执行方式。', '付款执行准备记录。'),
  snapshotField('plannedPaymentDate', '计划付款日期', TYPE.string, true, null, '计划付款日期。', '付款执行准备记录。'),
  snapshotField('currencyCode', '付款币种', TYPE.string, true, null, '付款币种编码。', '付款执行准备记录。'),
  snapshotField('baseCurrencyCode', '本位币币种', TYPE.string, true, null, '本位币币种编码。', '付款执行准备记录。'),
  snapshotField('foreignCurrencyPayment', '是否外币付款', TYPE.boolean, false, false, '是否属于外币付款。', '付款执行准备记录。'),
  snapshotField('exchangeRateType', '汇率类型', TYPE.string, true, null, '外币付款汇率类型。', '付款执行准备记录。'),
  snapshotField('exchangeRateDate', '汇率日期', TYPE.string, true, null, '外币付款汇率日期。', '付款执行准备记录。'),
  snapshotField('exchangeRate', '汇率', TYPE.number, true, null, '外币付款汇率数值。', '付款执行准备记录。'),
  snapshotField('exchangeRateSource', '汇率来源', TYPE.string, true, null, '外币付款汇率来源。', '付款执行准备记录。'),
  snapshotField('currencyPrecision', '币种精度', TYPE.number, true, null, '付款币种金额精度。', '付款执行准备记录。'),
  snapshotField('roundingMode', '舍入规则', TYPE.string, true, null, '金额舍入规则。', '付款执行准备记录。'),
  snapshotField('accountingTemplateId', '科目模板编号', TYPE.string, true, null, '付款凭证准备科目模板编号。', '付款执行准备记录。'),
  snapshotField('accountingTemplateVersion', '科目模板版本', TYPE.string, true, null, '付款凭证准备科目模板版本。', '付款执行准备记录。'),
  snapshotField('accountingTemplateStatus', '科目模板状态', TYPE.string, false, 'unknown', '付款凭证准备科目模板状态。', '付款执行准备记录。'),
  snapshotField('accountingPeriod', '会计期间', TYPE.string, true, null, '付款凭证准备会计期间。', '付款执行准备记录。'),
  snapshotField('accountingPeriodStatus', '会计期间状态', TYPE.string, false, 'unknown', '付款凭证准备会计期间状态。', '付款执行准备记录。'),
  snapshotField('enterpriseBankAccountId', '企业银行账户编号', TYPE.string, true, null, '付款方企业银行账户编号。', '付款执行准备记录。'),
  snapshotField('supplierBankAccountId', '供应商银行账户编号', TYPE.string, true, null, '收款方供应商银行账户编号。', '付款执行准备记录。'),
  snapshotField('paymentExecutionStatus', '付款执行状态', TYPE.string, false, 'unknown', '真实付款执行状态。', '付款执行准备记录。'),
  snapshotField('paymentVoucherStatus', '付款凭证状态', TYPE.string, false, 'unknown', '付款凭证生成状态。', '付款执行准备记录。'),
  snapshotField('formalPaymentVoucherStatus', '正式付款凭证状态', TYPE.string, false, 'unknown', '正式付款凭证生成状态。', '付款执行准备记录。'),
  snapshotField('writeOffStatus', '核销状态', TYPE.string, false, 'unknown', '付款核销状态。', '付款执行准备记录。'),
  snapshotField('ledgerStatus', '总账状态', TYPE.string, false, 'unknown', '总账写入状态。', '付款执行准备记录。'),
  snapshotField('postingStatus', '过账状态', TYPE.string, false, 'unknown', '凭证过账状态。', '付款执行准备记录。'),
  snapshotField('sourceRevision', '来源修订号', TYPE.string, true, null, '来源业务对象修订号。', '付款执行准备记录。'),
  snapshotField('sourceUpdatedAt', '来源更新时间', TYPE.string, true, null, '来源业务对象最后更新时间。', '付款执行准备记录。'),
  snapshotField('sourceDataVersion', '来源数据版本', TYPE.string, true, null, '来源业务对象数据版本。', '付款执行准备记录。'),
]

const snapshotFieldNames = PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.map((item) => item.field)
const snapshotFieldSet = new Set(snapshotFieldNames)

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

function isBlank(value) {
  return value === null || typeof value === 'undefined' || value === ''
}

function toStringValue(value, defaultValue) {
  if (isBlank(value)) return defaultValue
  return String(value).trim()
}

function toNumberValue(value, defaultValue) {
  if (isBlank(value)) return defaultValue
  const next = Number(value)
  if (!Number.isFinite(next)) return defaultValue
  return Number(next.toFixed(6))
}

function toBooleanValue(value, defaultValue) {
  if (isBlank(value)) return defaultValue
  if (value === true || value === false) return value
  if (String(value).toLowerCase() === 'true') return true
  if (String(value).toLowerCase() === 'false') return false
  return defaultValue
}

function normalizeValue(field, value) {
  if (field.type === TYPE.number) return toNumberValue(value, field.defaultValue)
  if (field.type === TYPE.boolean) return toBooleanValue(value, field.defaultValue)
  return toStringValue(value, field.defaultValue)
}

function hasPresentValue(input, field) {
  if (!Object.prototype.hasOwnProperty.call(input, field.field)) return false
  const value = input[field.field]
  if (field.type === TYPE.boolean) return value === true || value === false || String(value).trim() !== ''
  return !isBlank(value) && value !== 'unknown'
}

export function adaptPaymentVoucherPrepareSourceToSnapshotInput(source = {}) {
  const row = source && typeof source === 'object' ? source : {}
  const paymentExecutionPrepareNo = row.paymentExecutionPrepareNo || null
  const sourcePaymentInstructionPrepareNo = row.sourcePaymentInstructionPrepareNo || row.sourcePaymentOrderPrepareNo || null
  const sourceChainComplete = Boolean(paymentExecutionPrepareNo && (sourcePaymentInstructionPrepareNo || row.sourcePaymentApplicationNo || row.sourcePayableConfirmNo || row.sourceInvoicePrepareNo || row.sourceSettlementNo))
  return {
    sourceFound: Boolean(paymentExecutionPrepareNo),
    sourceObjectType: paymentExecutionPrepareNo ? 'payment_execution_prepare' : null,
    paymentExecutionPrepareNo,
    sourcePaymentInstructionPrepareNo,
    sourcePaymentApplicationNo: row.sourcePaymentApplicationNo || null,
    sourcePayableConfirmNo: row.sourcePayableConfirmNo || null,
    sourceInvoicePrepareNo: row.sourceInvoicePrepareNo || null,
    sourceSettlementNo: row.sourceSettlementNo || null,
    sourceChainComplete,
    reviewStatus: row.paymentExecutionPrepareStatus || row.reviewStatus || 'unknown',
    supplierId: row.supplierId || null,
    legalEntityId: row.legalEntityId || null,
    accountingBookId: row.accountingBookId || null,
    executionAmount: row.executionAmount ?? row.orderAmount ?? 0,
    paymentMethod: row.paymentMethod || null,
    plannedPaymentDate: row.plannedPaymentDate || null,
    currencyCode: row.currencyCode || row.currency || null,
    baseCurrencyCode: row.baseCurrencyCode || null,
    foreignCurrencyPayment: Boolean(row.foreignCurrencyPayment),
    exchangeRateType: row.exchangeRateType || null,
    exchangeRateDate: row.exchangeRateDate || null,
    exchangeRate: row.exchangeRate ?? null,
    exchangeRateSource: row.exchangeRateSource || null,
    currencyPrecision: row.currencyPrecision ?? null,
    roundingMode: row.roundingMode || null,
    accountingTemplateId: row.accountingTemplateId || null,
    accountingTemplateVersion: row.accountingTemplateVersion || null,
    accountingTemplateStatus: row.accountingTemplateStatus || 'unknown',
    accountingPeriod: row.accountingPeriod || null,
    accountingPeriodStatus: row.accountingPeriodStatus || 'unknown',
    enterpriseBankAccountId: row.enterpriseBankAccountId || null,
    supplierBankAccountId: row.supplierBankAccountId || null,
    paymentExecutionStatus: row.paymentExecutionStatus || 'unknown',
    paymentVoucherStatus: row.paymentVoucherStatus || 'unknown',
    formalPaymentVoucherStatus: row.formalPaymentVoucherStatus || 'unknown',
    writeOffStatus: row.writeOffStatus || 'unknown',
    ledgerStatus: row.ledgerStatus || 'unknown',
    postingStatus: row.postingStatus || 'unknown',
    sourceRevision: row.sourceRevision || null,
    sourceUpdatedAt: row.sourceUpdatedAt || null,
    sourceDataVersion: row.sourceDataVersion || null,
  }
}

export function normalizePaymentVoucherPrepareSourceSnapshot(input = {}) {
  const before = stableStringify(input)
  const sourceFound = Boolean(input && input.sourceFound !== false && input.paymentExecutionPrepareNo)
  const unknownFields = Object.keys(input || {}).filter((key) => key !== 'sourceFound' && !snapshotFieldSet.has(key))
  const criticalFieldCount = PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.filter((field) => field.critical).length
  if (!sourceFound) {
    return {
      adapterVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION,
      snapshotContractVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
      sourceFound: false,
      snapshotPreviewCreated: false,
      snapshotStructureStatus: 'source_not_found',
      snapshot: null,
      snapshotFieldCount: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.length,
      presentFieldCount: 0,
      missingFieldCount: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.length,
      criticalFieldCount,
      missingCriticalFieldCount: criticalFieldCount,
      missingCriticalFields: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.filter((field) => field.critical).map((field) => field.field),
      unknownInputFieldCount: unknownFields.length,
      ignoredUnknownFields: unknownFields,
      inputMutated: before !== stableStringify(input),
      businessSnapshotMechanismReady: false,
    }
  }

  const snapshot = {}
  const missingFields = []
  const missingCriticalFields = []
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.forEach((field) => {
    snapshot[field.field] = normalizeValue(field, input[field.field])
    if (!hasPresentValue(input, field)) {
      missingFields.push(field.field)
      if (field.critical) missingCriticalFields.push(field.field)
    }
  })

  return {
    adapterVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION,
    snapshotContractVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
    sourceFound: true,
    snapshotPreviewCreated: true,
    snapshotStructureStatus: missingCriticalFields.length ? 'partial' : 'complete',
    snapshot,
    snapshotFieldCount: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.length,
    presentFieldCount: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.length - missingFields.length,
    missingFieldCount: missingFields.length,
    criticalFieldCount,
    missingCriticalFieldCount: missingCriticalFields.length,
    missingCriticalFields,
    unknownInputFieldCount: unknownFields.length,
    ignoredUnknownFields: unknownFields,
    inputMutated: before !== stableStringify(input),
    businessSnapshotMechanismReady: false,
  }
}

export function createPaymentVoucherPrepareSourceSnapshotContractFingerprint(fields = PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS) {
  const payload = fields.map((field) => ({
    field: field.field,
    type: field.type,
    nullable: field.nullable,
    critical: field.critical,
    includedInFingerprint: field.includedInFingerprint,
    defaultValue: field.defaultValue,
    businessMeaning: field.businessMeaning,
  }))
  return `PVPP-SNAPSHOT-CONTRACT-FP-${stableHash(payload)}`
}

export const PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT = createPaymentVoucherPrepareSourceSnapshotContractFingerprint()

export const PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION]: 'PVPP-SNAPSHOT-CONTRACT-FP-C9AC3D91',
}

export function validatePaymentVoucherPrepareSourceSnapshot(fields = PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS) {
  const fieldNames = fields.map((field) => field.field)
  const allowedTypes = new Set(Object.values(TYPE))
  const fingerprint = createPaymentVoucherPrepareSourceSnapshotContractFingerprint(fields)
  const locked = PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION]
  return {
    snapshotContractVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
    snapshotContractFingerprint: fingerprint,
    snapshotContractLockedFingerprint: locked,
    snapshotContractFingerprintMatched: fingerprint === locked,
    snapshotFieldCount: fields.length,
    snapshotFieldNamesUnique: new Set(fieldNames).size === fieldNames.length,
    snapshotFieldOrderStable: fieldNames.join('|') === snapshotFieldNames.join('|'),
    snapshotFieldTypesValid: fields.every((field) => allowedTypes.has(field.type)),
    snapshotDefaultValuesValid: fields.every((field) => Object.prototype.hasOwnProperty.call(field, 'defaultValue') && typeof field.defaultValue !== 'undefined'),
  }
}

export function verifyPaymentVoucherPrepareSourceSnapshotPurity(input = {}) {
  const frozen = clone(input)
  const before = stableStringify(input)
  const first = normalizePaymentVoucherPrepareSourceSnapshot(input)
  const second = normalizePaymentVoucherPrepareSourceSnapshot(clone(frozen))
  const after = stableStringify(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: before !== after,
    businessSnapshotMechanismReady: false,
  }
}

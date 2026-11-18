export const PCE_ADVANCED_FILTER_CONTRACT_VERSION = 'V1.14.2.8.4.7.53.2'

export const PCE_FILTER_DISPLAY_MAP = Object.freeze({
  draft: '草稿',
  prepared: '已准备',
  submitted: '已提交',
  cancelled: '已取消',
  reviewed: '已复核',
  passed: '已通过',
  blocked: '已阻断',
  approved: '已批准',
  pending: '待处理',
  rejected: '已驳回',
  checked: '已核对',
  matched: '已匹配',
  difference_found: '发现差异',
  difference: '存在差异',
  source_missing: '来源缺失',
  not_created: '未创建',
  not_started: '未开始',
  not_collected: '未采集',
  not_validated: '未校验',
  complete: '完整',
  committed: '已提交',
  existing_result: '已有结果',
  consumed: '已使用',
  validated: '已校验',
  ready: '可进入下一步',
  created: '已创建',
  written: '已回写',
  failed: '失败',
  reconciling: '对账中',
  reconciled: '已对账',
  difference_pending: '差异待处理',
  closed: '已关闭',
  amount_difference: '金额存在差异',
  low: '低',
  medium: '中',
  high: '高',
  true: '是',
  false: '否',
  ready_for_invoice_prepare: '可进入采购发票准备',
  ready_for_accounts_payable_draft: '可进入采购应付账款草稿',
  ready_for_payment_request_prepare: '可进入付款申请准备',
  ready_for_payment_request: '可进入付款申请',
  ready_for_payment_instruction_prepare: '可进入付款指令准备',
  ready_for_payment_order_prepare: '可进入正式付款单预备',
  ready_for_payment_order_draft: '可进入正式付款单草稿',
  ready_for_payment_risk_review: '可进入真实付款风险评审',
  ready_for_formal_payment_order: '可进入正式付款单',
})

const FILTER_LABELS = Object.freeze({
  objectNo: '当前编号',
  sourceObjectNo: '来源编号',
  sourceInventoryTransactionNo: '来源库存流水编号',
  payablePrepareNo: '应付预备单号',
  sourcePurchaseOrderNo: '来源采购订单号',
  payableStatus: '应付状态',
  flowWritebackStatus: '来源回写状态',
  payableCheckNo: '应付核对单号',
  sourcePayablePrepareNo: '来源应付预备编号',
  checkStatus: '核对状态',
  downstreamStatus: '下游对象状态',
  checkedDateFrom: '核对日期起',
  checkedDateTo: '核对日期止',
  settlementNo: '供应商结算单号',
  sourcePayableCheckNo: '来源应付核对单号',
  purchaseOrderNo: '采购订单号',
  reconciliationStatus: '采购对账状态',
  settlementStatus: '结算状态',
  nextStepReadiness: '下一步资格',
  reconciliationNo: '采购对账编号',
  sourceSettlementNo: '来源供应商结算单号',
  prepareNo: '准备编号',
  sourcePurchaseReconciliationNo: '来源采购对账编号',
  sourceReconciliationNo: '来源采购对账编号',
  invoiceDataStatus: '发票资料状态',
  transactionId: '事务标识',
  draftNo: '草稿编号',
  sourcePurchaseInvoicePrepareNo: '来源采购发票准备编号',
  sourceDraftNo: '来源采购应付账款草稿',
  sourcePayableConfirmationPrepareNo: '来源应付确认准备编号',
  sourceApDraftNo: '来源AP草稿',
  sourcePaymentRequestPrepareNo: '来源付款申请准备编号',
  sourcePaymentRequestNo: '来源付款申请编号',
  sourcePaymentInstructionPrepareNo: '来源付款指令准备编号',
  sourcePaymentOrderPrepareNo: '来源正式付款单预备编号',
  sourcePaymentOrderDraftNo: '来源正式付款单草稿编号',
  reviewNo: '风险评审编号',
  orderNo: '正式付款单编号',
  sourceRiskReviewNo: '来源风险评审编号',
  sourceNo: '来源编号',
  supplierName: '供应商',
  legalEntity: '法人',
  ledgerBook: '账簿',
  legalEntityName: '法人',
  ledgerBookId: '账簿',
  currency: '币种',
  bankInterfaceProfileId: '银行接口',
  paymentRouteId: '支付路线',
  signingPolicyId: '签署策略',
  authorizationRouteId: '授权路线',
  scenarioType: '场景类型',
  scenarioCode: '场景编码',
  status: '业务状态',
  sourceStatus: '来源状态',
  validationStatus: '校验状态',
  sourceValidationStatus: '来源校验状态',
  approvalStatus: '审批状态',
  reviewStatus: '复核状态',
  reviewResultCode: '复核结果编码',
  riskLevel: '风险等级',
  paymentDataStatus: '付款资料状态',
  sourceNextStepReadiness: '来源下游资格',
  accountingPeriod: '会计期间',
  paymentTermsCode: '付款条件',
  amountMin: '金额下限',
  amountMax: '金额上限',
  executionDateFrom: '执行日期起',
  executionDateTo: '执行日期止',
  dateRange: '业务日期',
  plannedDateRange: '计划日期',
  payerBankAccountMasked: '付款方银行账户',
  payeeBankAccountMasked: '收款方银行账户',
  fundsSufficient: '资金是否充足',
  segregationValid: '职责分离是否通过',
  signingCapabilityStatus: '签署能力状态',
  credentialStatus: '凭据状态',
})

const DICTIONARY_FIELD_PATTERN = /supplier|legalEntity|ledgerBook|currency|bankInterface|paymentRoute|signingPolicy|authorizationRoute|scenarioType/i
const ENUM_FIELD_PATTERN = /status|state|readiness|result|riskLevel|sufficient|valid$/i
const AMOUNT_FIELD_PATTERN = /amount|quantity/i
const DATE_FIELD_PATTERN = /date|time/i
const DOCUMENT_NUMBER_FIELD_PATTERN = /(?:No|Number)$/i
const SOURCE_DOCUMENT_NUMBER_FIELD_PATTERN = /^(?:source|root).*(?:No|Number)$/i
const SCENARIO_CODE_FIELD_PATTERN = /^scenarioCode$/i

export function isPceDocumentNumberField(field = '') {
  return DOCUMENT_NUMBER_FIELD_PATTERN.test(String(field))
}

export function isPceSourceDocumentNumberField(field = '') {
  return SOURCE_DOCUMENT_NUMBER_FIELD_PATTERN.test(String(field))
}

export function isPceScenarioCodeField(field = '') {
  return SCENARIO_CODE_FIELD_PATTERN.test(String(field))
}

export function isPceSelectOnlyBusinessIdentifier(field = '') {
  return isPceDocumentNumberField(field)
    || isPceSourceDocumentNumberField(field)
    || isPceScenarioCodeField(field)
}

function fallbackLabel(field) {
  if (/No$/i.test(field)) return '业务编号'
  if (DATE_FIELD_PATTERN.test(field)) return '业务日期'
  if (AMOUNT_FIELD_PATTERN.test(field)) return '金额'
  if (ENUM_FIELD_PATTERN.test(field)) return '业务状态'
  return '业务条件'
}

function canonicalType(field, source = {}) {
  const legacyType = source.filterType || source.queryType || source.filterControlType || source.controlType || source.type || ''
  if (isPceSelectOnlyBusinessIdentifier(field)) return 'select'
  if (['decimal-min', 'decimal-max', 'number_range', 'numberRange'].includes(legacyType)) return 'numberRange'
  if (legacyType === 'date') return 'date'
  if (['date-min', 'date-max', 'date_range', 'dateRange', 'daterange'].includes(legacyType)) return 'daterange'
  if (legacyType === 'boolean') return 'boolean'
  if (['select', 'boolean_select', 'searchable_select'].includes(legacyType)) return 'select'
  if (AMOUNT_FIELD_PATTERN.test(field) && /(Min|Max|Range)$/i.test(field)) return 'numberRange'
  if (DATE_FIELD_PATTERN.test(field)) return 'daterange'
  if (DICTIONARY_FIELD_PATTERN.test(field) || ENUM_FIELD_PATTERN.test(field)) return 'select'
  return legacyType === 'text' || legacyType === 'input' ? 'text' : 'select'
}

function queryType(field, source, type) {
  const value = source.queryType || source.filterControlType || source.controlType || source.type || ''
  if (['decimal-min', 'decimal-max', 'date-min', 'date-max', 'boolean'].includes(value)) return value
  if (type === 'numberRange') return /Max$/i.test(field) ? 'decimal-max' : 'decimal-min'
  if (type === 'daterange') return 'date-range'
  if (type === 'date') return 'date'
  if (type === 'boolean') return 'boolean'
  return type === 'select' ? 'select' : 'text'
}

function displayMapFor(field, source, type) {
  if (source.displayMap && typeof source.displayMap === 'object') return { ...source.displayMap }
  if (type !== 'select') return {}
  if (ENUM_FIELD_PATTERN.test(field)) return { ...PCE_FILTER_DISPLAY_MAP }
  return {}
}

export function createPceAdvancedFilterField(fieldOrConfig) {
  const source = typeof fieldOrConfig === 'string' ? { field: fieldOrConfig } : { ...fieldOrConfig }
  const field = source.field || source.key
  const filterType = canonicalType(field, source)
  const semanticType = filterType === 'daterange' ? 'dateRange' : filterType
  const displayMap = displayMapFor(field, source, filterType)
  const staticOptions = Array.isArray(source.options)
    ? source.options.map(option => (
      typeof option === 'object'
        ? { value: option.value, label: option.label || displayMap[String(option.value)] || String(option.value) }
        : { value: option, label: displayMap[String(option)] || String(option) }
    ))
    : []
  return Object.freeze({
    ...source,
    field,
    key: field,
    label: FILTER_LABELS[field] || (
      /[\u4e00-\u9fff]/.test(String(source.label || '')) ? source.label : fallbackLabel(field)
    ),
    filterType,
    type: semanticType,
    displayMap,
    optionsProvider: source.optionsProvider || source.optionSource || (
      staticOptions.length ? 'staticOptions' : filterType === 'select' ? 'currentResultDistinctValues' : 'none'
    ),
    options: Object.freeze(staticOptions),
    queryType: queryType(field, source, filterType),
    sourceKey: source.sourceKey || field,
    clearable: source.clearable !== false,
    searchable: filterType === 'select',
  })
}

export function createPceAdvancedFilterSchema(fields = []) {
  return Object.freeze(fields.map(createPceAdvancedFilterField))
}

export function displayPceFilterValue(value) {
  const normalized = String(value ?? '').trim()
  return PCE_FILTER_DISPLAY_MAP[normalized] || normalized
}

export function resolvePceFilterOptions(field, rows = []) {
  const values = field.options?.length
    ? field.options
    : [...new Set(rows.map(row => row?.[field.sourceKey || field.field]).filter(value => value !== '' && value != null))]
      .map(value => ({ value, label: field.displayMap?.[String(value)] || displayPceFilterValue(value) }))
  return values.map(option => ({
    value: option.value,
    label: field.displayMap?.[String(option.value)] || displayPceFilterValue(option.label || option.value),
  }))
}

export function isPceBusinessDictionaryField(field = '') {
  return DICTIONARY_FIELD_PATTERN.test(String(field))
}

export function isPceEnumField(field = '') {
  return ENUM_FIELD_PATTERN.test(String(field))
}

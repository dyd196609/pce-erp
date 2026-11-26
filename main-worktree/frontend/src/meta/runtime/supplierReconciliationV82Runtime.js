import { SCM_7_GATE_LIST_CONTRACTS } from '../schema/scm/scm7GateListContracts.js'

export const SUPPLIER_RECONCILIATION_V82_VERSION = 'V1.14.2.8.4.8.2'

const differenceTypeOptions = [
  { value: 'quantity_difference', label: '数量差异' },
  { value: 'quality_difference', label: '质量差异' },
  { value: 'price_difference', label: '价格差异' },
  { value: 'amount_difference', label: '金额差异' },
  { value: 'delivery_difference', label: '交付差异' },
  { value: 'other_difference', label: '其他差异' },
]
const responsibilityOptions = [
  { value: 'supplier', label: '供应商责任' },
  { value: 'buyer', label: '采购责任' },
  { value: 'warehouse', label: '仓库责任' },
  { value: 'quality', label: '质量责任' },
  { value: 'unknown', label: '待确认' },
]

export const v82PageDefinitions = Object.freeze({
  difference: {
    title: '供应商对账差异分析',
    pageCode: 'supplier-reconciliation-differences',
    moduleCode: 'SCM_SUPPLIER_RECONCILIATION_DIFFERENCE',
    apiKey: 'differences',
    factKey: 'differenceFacts',
    factType: 'SupplierReconciliationDifferenceFacts',
    primaryField: 'differenceNo',
    primaryLabel: '差异编号',
    listTitle: '供应商对账差异列表',
    filterSchema: [
      { field: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'differenceType', label: '差异类型', filterType: 'select', options: differenceTypeOptions },
      { field: 'responsibilityType', label: '责任类型', filterType: 'select', options: responsibilityOptions },
      { field: 'statusCode', label: '状态', filterType: 'select', options: [
        { value: 'draft', label: '草稿' }, { value: 'analyzing', label: '分析中' },
        { value: 'responsibility_confirmed', label: '责任已确认' },
        { value: 'supplier_communicating', label: '供应商沟通中' },
        { value: 'closed', label: '已关闭' },
      ] },
      { field: 'occurredAt', label: '差异日期', filterType: 'daterange', apiFrom: 'occurredAtFrom', apiTo: 'occurredAtTo' },
    ],
  },
  confirmation: {
    title: '供应商协同确认',
    pageCode: 'supplier-reconciliation-confirmations',
    moduleCode: 'SCM_SUPPLIER_RECONCILIATION_CONFIRMATION',
    apiKey: 'confirmations',
    factKey: 'confirmationFacts',
    factType: 'SupplierReconciliationConfirmationFacts',
    primaryField: 'confirmationNo',
    primaryLabel: '确认编号',
    listTitle: '协同确认列表',
    filterSchema: [
      { field: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'supplierResponse', label: '处理结果', filterType: 'select', options: [
        { value: 'accepted', label: '认可' }, { value: 'disputed', label: '有异议' }, { value: 'pending', label: '待回复' },
      ] },
      { field: 'statusCode', label: '确认状态', filterType: 'select', options: [
        { value: 'waiting_supplier', label: '等待供应商确认' },
        { value: 'supplier_confirmed', label: '供应商已确认' },
        { value: 'internal_verified', label: '内部已复核' },
        { value: 'completed', label: '协同确认完成' },
      ] },
      { field: 'confirmedAt', label: '确认日期', filterType: 'daterange', apiFrom: 'confirmedAtFrom', apiTo: 'confirmedAtTo' },
    ],
  },
  buyerException: {
    title: '采购异常责任分析',
    pageCode: 'buyer-exception-analysis',
    moduleCode: 'SCM_BUYER_EXCEPTION_ANALYSIS',
    apiKey: 'buyerExceptions',
    factKey: 'exceptionFacts',
    factType: 'BuyerExceptionAnalysisFacts',
    primaryField: 'buyerName',
    primaryLabel: '采购员',
    listTitle: '采购责任分析区域',
    filterSchema: SCM_7_GATE_LIST_CONTRACTS['buyer-exception-analysis'].filterSchema,
  },
})

export function normalizeV82Facts(payload, kind) {
  const data = payload?.success === true ? payload.data : payload?.data?.data || payload?.data || payload
  const definition = v82PageDefinitions[kind]
  const facts = data?.[definition.factKey]
  const rows = Array.isArray(data?.results) ? data.results : []
  if (!facts || facts.factSource !== 'server' || facts.factLoadStatus !== 'success') {
    throw new Error(`${definition.factType} missing`)
  }
  const counts = [
    rows.length,
    facts.recordCount,
    data.diagnosticFacts?.recordCount,
    data.strictFacts?.recordCount,
    data.acceptanceFacts?.recordCount,
  ]
  if (new Set(counts).size !== 1) throw new Error(`${definition.factType} five-surface mismatch`)
  return {
    rows,
    facts,
    diagnosticFacts: data.diagnosticFacts,
    strictFacts: data.strictFacts,
    acceptanceFacts: data.acceptanceFacts,
  }
}

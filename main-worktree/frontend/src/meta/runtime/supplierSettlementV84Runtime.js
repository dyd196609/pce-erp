export const SUPPLIER_SETTLEMENT_V84_VERSION = 'V1.14.2.8.4.8.4'

export const supplierSettlementV84Definitions = Object.freeze({
  paymentStatus: {
    title: '供应商付款状态记录',
    pageCode: 'supplier-payment-status',
    moduleCode: 'SCM_SUPPLIER_PAYMENT_STATUS',
    apiKey: 'paymentStatus',
    factKey: 'paymentStatusFacts',
    primaryField: 'paymentRequestNo',
    primaryLabel: '付款申请编号',
    listTitle: '供应商付款状态列表',
    filterSchema: [
      { field: 'paymentRequestNo', label: '付款申请编号', filterType: 'text' },
      { field: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'paymentStatus', label: '业务状态', filterType: 'select', options: [
        { value: 'draft', label: '待提交' },
        { value: 'submitted', label: '审核中' },
        { value: 'approved', label: '已批准' },
        { value: 'payment_scheduled', label: '付款安排中' },
        { value: 'payment_completed', label: '付款完成' },
        { value: 'settlement_completed', label: '结算完成' },
      ] },
    ],
  },
  completion: {
    title: '供应商结算完成确认',
    pageCode: 'supplier-settlement-completion',
    moduleCode: 'SCM_SUPPLIER_SETTLEMENT_COMPLETION',
    apiKey: 'settlementCompletions',
    factKey: 'settlementCompletionFacts',
    primaryField: 'settlementNo',
    primaryLabel: '结算编号',
    listTitle: '供应商结算完成状态',
    filterSchema: [
      { field: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'reconciliationNo', label: '对账编号', filterType: 'text' },
      { field: 'paymentRequestNo', label: '付款申请编号', filterType: 'text' },
      { field: 'completionStatus', label: '结算状态', filterType: 'select', options: [
        { value: 'pending', label: '待确认' },
        { value: 'completed', label: '结算完成' },
      ] },
    ],
  },
})

export function normalizeSupplierSettlementV84Facts(payload, kind) {
  const data = payload?.success === true ? payload.data : payload?.data?.data || payload?.data || payload
  const definition = supplierSettlementV84Definitions[kind]
  const rows = Array.isArray(data?.results) ? data.results : []
  const facts = data?.[definition.factKey]
  if (!facts || facts.factSource !== 'server' || facts.factLoadStatus !== 'success') {
    throw new Error(`${definition.factKey} missing`)
  }
  const counts = [
    rows.length,
    facts.recordCount,
    data.diagnosticFacts?.recordCount,
    data.strictFacts?.recordCount,
    data.acceptanceFacts?.recordCount,
  ]
  if (new Set(counts).size !== 1) throw new Error(`${definition.factKey} facts mismatch`)
  return {
    rows,
    facts,
    diagnosticFacts: data.diagnosticFacts,
    strictFacts: data.strictFacts,
    acceptanceFacts: data.acceptanceFacts,
  }
}


export const SUPPLIER_PAYABLE_V83_VERSION = 'V1.14.2.8.4.8.3.1.1'

export const v83PageDefinitions = Object.freeze({
  payable: {
    title: '供应商应付确认',
    pageCode: 'supplier-payable-confirmation',
    moduleCode: 'SCM_SUPPLIER_PAYABLE_CONFIRMATION',
    apiKey: 'payableConfirmations',
    factKey: 'payableConfirmationFacts',
    factType: 'SupplierPayableConfirmationFacts',
    primaryField: 'payableConfirmationNo',
    primaryLabel: '应付确认编号',
    listTitle: '供应商应付确认列表',
    filterSchema: [
      { field: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'statusCode', label: '确认状态', filterType: 'select', options: [
        { value: 'draft', label: '草稿' },
        { value: 'internal_review', label: '内部审核中' },
        { value: 'confirmed', label: '应付已确认' },
        { value: 'ready_for_payment_request', label: '可申请付款' },
      ] },
      { field: 'period', label: '对账期间', filterType: 'daterange', apiFrom: 'periodFrom', apiTo: 'periodTo' },
    ],
  },
  request: {
    title: '供应商付款申请',
    pageCode: 'supplier-payment-request',
    moduleCode: 'SCM_SUPPLIER_PAYMENT_REQUEST',
    apiKey: 'paymentRequests',
    factKey: 'paymentRequestFacts',
    factType: 'SupplierPaymentRequestFacts',
    primaryField: 'paymentRequestNo',
    primaryLabel: '付款申请编号',
    listTitle: '供应商付款申请列表',
    filterSchema: [
      { field: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'statusCode', label: '申请状态', filterType: 'select', options: [
        { value: 'draft', label: '草稿' },
        { value: 'submitted', label: '已提交' },
        { value: 'approved', label: '申请已批准' },
        { value: 'payment_pending', label: '待后续付款处理' },
      ] },
      { field: 'period', label: '申请期间', filterType: 'daterange', apiFrom: 'periodFrom', apiTo: 'periodTo' },
    ],
  },
})

export function normalizeV83Facts(payload, kind) {
  const data = payload?.success === true ? payload.data : payload?.data?.data || payload?.data || payload
  const definition = v83PageDefinitions[kind]
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
  const fields = [
    'workflowActionCount',
    'availableActionCount',
    'executedActionCount',
    'auditRecordCount',
    'detailViewMode',
  ]
  for (const field of fields) {
    const values = [
      facts[field],
      data.diagnosticFacts?.[field],
      data.strictFacts?.[field],
      data.acceptanceFacts?.[field],
    ]
    if (new Set(values).size !== 1) {
      throw new Error(`${definition.factType} ${field} five-surface mismatch`)
    }
  }
  if (facts.detailViewMode !== 'business_card') {
    throw new Error(`${definition.factType} detail view contract mismatch`)
  }
  return {
    rows, facts,
    diagnosticFacts: data.diagnosticFacts,
    strictFacts: data.strictFacts,
    acceptanceFacts: data.acceptanceFacts,
  }
}

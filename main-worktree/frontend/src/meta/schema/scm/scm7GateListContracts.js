const freezeFields = fields => Object.freeze(fields.map(field => Object.freeze({ ...field })))

export const SCM_7_GATE_LIST_CONTRACT_VERSION = 'SCM-7-GATE-LIST-CONTRACT-V1.0'

export const SCM_7_GATE_LIST_CONTRACTS = Object.freeze({
  'purchase-inquiry': Object.freeze({
    searchFields: Object.freeze(['inquiryNo', 'sourceRequestNo', 'buyerName', 'statusLabel']),
    filterSchema: freezeFields([
      { field: 'inquiryNo', label: '询价编号', filterType: 'text' },
      { field: 'inquiryDate', label: '询价日期', filterType: 'daterange' },
      { field: 'buyerName', label: '采购员', filterType: 'select', optionsProvider: 'UserProvider' },
      { field: 'statusCode', label: '业务状态', filterType: 'select', optionsProvider: 'PurchaseInquiryStateContract' },
    ]),
  }),
  'purchase-inquiry-acceptance': Object.freeze({
    searchFields: Object.freeze(['inquiryNo', 'sourceRequestNo', 'materialCode', 'materialName', 'supplierCode', 'supplierName', 'preparationStatus', 'supplierStatus']),
    filterSchema: freezeFields([
      { field: 'inquiryNo', label: '询价编号', filterType: 'text' },
      { field: 'sourceRequestNo', label: '来源采购申请', filterType: 'text' },
      { field: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'preparationStatus', label: '准备状态', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
    ]),
  }),
  'supplier-performance': Object.freeze({
    searchFields: Object.freeze(['supplierId', 'supplierName', 'period']),
    filterSchema: freezeFields([
      { field: 'supplierId', label: '供应商编号', filterType: 'text' },
      { field: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'period', label: '周期', filterType: 'daterange', apiFrom: 'periodFrom', apiTo: 'periodTo' },
    ]),
  }),
  'buyer-performance': Object.freeze({
    searchFields: Object.freeze(['buyerId', 'buyerName', 'period']),
    filterSchema: freezeFields([
      { field: 'buyerId', label: '采购员编号', filterType: 'text' },
      { field: 'buyerName', label: '采购员', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'period', label: '周期', filterType: 'daterange', apiFrom: 'periodFrom', apiTo: 'periodTo' },
    ]),
  }),
  'buyer-exception-analysis': Object.freeze({
    searchFields: Object.freeze(['buyerId', 'buyerName', 'period']),
    filterSchema: freezeFields([
      { field: 'buyerId', label: '采购员编号', filterType: 'text' },
      { field: 'buyerName', label: '采购员', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'period', label: '周期', filterType: 'daterange', apiFrom: 'periodFrom', apiTo: 'periodTo' },
    ]),
  }),
})

export function resolveScm7GateListContract(pageCode) {
  return SCM_7_GATE_LIST_CONTRACTS[pageCode] || null
}

export function createPurchaseInquiryFilterSchema({ buyerOptions = [], stateOptions = [] } = {}) {
  return SCM_7_GATE_LIST_CONTRACTS['purchase-inquiry'].filterSchema.map(field => ({
    ...field,
    ...(field.field === 'buyerName' ? { options: buyerOptions } : {}),
    ...(field.field === 'statusCode' ? { options: stateOptions } : {}),
  }))
}

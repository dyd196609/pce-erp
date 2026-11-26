export const SUPPLIER_QUOTE_PAGE_CONTRACT_VERSION = 'V1.14.2.8.18.9'

export const SUPPLIER_QUOTE_PAGE_CONTRACT = Object.freeze({
  pageCode: 'supplier-quote-workbench',
  pageName: '供应商报价',
  route: '/scm/supplier-quotation',
  moduleCode: 'SCM',
  businessObject: 'SupplierQuotation',
  providerCode: 'SCM_SUPPLIER_QUOTE_PROVIDER',
  previousModule: 'price-approval-preparation',
  currentModule: 'supplier-quote',
  nextModule: 'quote-comparison-preparation',
  regions: Object.freeze(['business-context', 'quote-detail', 'business-actions', 'next-action']),
  buttons: Object.freeze([
    Object.freeze({ label: '进入供应商报价', actionCode: 'CREATE_SUPPLIER_QUOTE_CONTEXT' }),
    Object.freeze({ label: '保存报价', actionCode: 'SAVE_SUPPLIER_QUOTE' }),
    Object.freeze({ label: '完成报价收集', actionCode: 'COMPLETE_SUPPLIER_QUOTE' }),
  ]),
  forbiddenButtons: Object.freeze(['发送供应商', '生成订单']),
})

export function validateSupplierQuotePageContract() {
  const page = SUPPLIER_QUOTE_PAGE_CONTRACT
  const valid = ['pageCode', 'pageName', 'route', 'moduleCode', 'businessObject', 'providerCode']
    .every(field => Boolean(page[field])) && page.regions.length === 4 && page.buttons.length === 3
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL' })
}

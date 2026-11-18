export const SUPPLIER_QUOTATION_RUNTIME_GUARD_VERSION = 'V1.14.2.8.6.1'

export const SUPPLIER_QUOTATION_FORBIDDEN_ACTIONS = Object.freeze([
  'autoCreateQuotation',
  'writeProductionDatabase',
  'advancePriceApproval',
  'createPurchaseOrder',
  'modifyPurchaseFlow',
  'sendSupplier',
])

export function evaluateSupplierQuotationRuntimeGuard(action = '') {
  const forbidden = SUPPLIER_QUOTATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: forbidden ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: forbidden ? 'quotation_runtime_boundary_forbidden' : 'read_only_default_deny',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

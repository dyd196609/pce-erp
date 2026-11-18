export const PURCHASE_INQUIRY_ACTIVATION_GUARD_VERSION = 'V1.14.2.8.7.11'
export const PURCHASE_INQUIRY_ACTIVATION_FORBIDDEN_ACTIONS = Object.freeze([
  'createSupplierQuote', 'sendSupplier', 'callQuotationApi', 'createQuoteComparison',
  'createPriceApproval', 'createPurchaseOrder', 'createFinanceObject', 'createInventoryAction',
])

export function evaluatePurchaseInquiryActivationGuard(action = '') {
  if (action === 'activatePurchaseInquiry') return Object.freeze({ result: 'PASS', decision: 'allow_manual_activation',
    allowed: true, targetStatus: 'draft', automaticIssue: false })
  const forbidden = PURCHASE_INQUIRY_ACTIVATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: forbidden ? 'PASS' : 'FAIL', decision: 'deny', allowed: false,
    reason: forbidden ? 'activation_downstream_boundary' : 'default_deny', quotationCreated: false,
    supplierSent: false, priceApprovalCreated: false, purchaseOrderCreated: false })
}

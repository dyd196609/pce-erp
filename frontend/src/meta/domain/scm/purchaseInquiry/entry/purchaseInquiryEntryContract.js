export const PURCHASE_INQUIRY_ENTRY_CONTRACT_VERSION = 'V1.14.2.8.7.12'

export const PURCHASE_INQUIRY_ENTRY_CONTRACT = Object.freeze({
  contractCode: 'SCM_PURCHASE_INQUIRY_BUSINESS_ENTRY_CONTRACT',
  version: PURCHASE_INQUIRY_ENTRY_CONTRACT_VERSION,
  canonicalRoute: '/scm/purchase-inquiry',
  canonicalPageCode: 'purchase-inquiry',
  allowedEntryTypes: Object.freeze(['purchase_request_preparation', 'existing_purchase_inquiry', 'business_process_center_browse']),
  creationSourceChain: Object.freeze(['PurchaseRequest', 'InquiryPreparationObject', 'PurchaseInquiry']),
  creationRequiresPreparationContext: true,
  emptyEntryMode: 'browse_only',
  emptyEntryAutoCreation: false,
  legacyRoutes: Object.freeze(['/scm/purchase-inquiries', '/scm/purchase-inquiry/create', '/scm/purchase-inquiry/:id']),
  allowedActions: Object.freeze(['startInquiry', 'viewInquiry']),
  forbiddenActions: Object.freeze(['createWithoutContext', 'sendSupplier', 'createSupplierQuote', 'createPurchaseOrder', 'payment']),
})

export function validatePurchaseInquiryEntryContract(contract = PURCHASE_INQUIRY_ENTRY_CONTRACT) {
  const valid = contract.canonicalRoute === '/scm/purchase-inquiry'
    && contract.creationSourceChain.join('>') === 'PurchaseRequest>InquiryPreparationObject>PurchaseInquiry'
    && contract.creationRequiresPreparationContext === true && contract.emptyEntryMode === 'browse_only'
    && contract.emptyEntryAutoCreation === false && contract.allowedActions.length === 2
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

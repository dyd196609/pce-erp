import { PURCHASE_INQUIRY_ENTRY_CONTRACT, validatePurchaseInquiryEntryContract } from '../../domain/scm/purchaseInquiry/entry/purchaseInquiryEntryContract.js'
import { resolvePurchaseInquiryBusinessContext, validatePurchaseInquiryBusinessContext } from '../../domain/scm/purchaseInquiry/entry/purchaseInquiryBusinessContext.js'
import { evaluatePurchaseInquiryEntryGuard } from '../../domain/scm/purchaseInquiry/entry/purchaseInquiryEntryGuard.js'

export const PURCHASE_INQUIRY_ENTRY_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_ENTRY_GOVERNANCE', version: 'V1.14.2.8.7.12',
  status: 'SCM_PURCHASE_INQUIRY_ENTRY_GOVERNANCE_READY', canonicalRoute: '/scm/purchase-inquiry',
  uniquePage: true, emptyEntryMode: 'browse_only', emptyEntryAutoCreation: false,
  allowedActions: Object.freeze(['startInquiry', 'viewInquiry']),
  forbiddenObjects: Object.freeze(['SupplierQuote', 'PurchaseOrder', 'FinanceObject']),
})

export function validatePurchaseInquiryEntryAcceptance() {
  const preparation = { inquiryPreparationNo: 'IPR-PR202608020008', sourceRequestNo: 'PR202608020008', statusLabel: '询价准备完成' }
  const preparationContext = resolvePurchaseInquiryBusinessContext({ query: { inquiryPreparationNo: preparation.inquiryPreparationNo }, preparations: [preparation] })
  const emptyContext = resolvePurchaseInquiryBusinessContext()
  const valid = validatePurchaseInquiryEntryContract().valid && validatePurchaseInquiryBusinessContext(preparationContext).valid
    && validatePurchaseInquiryBusinessContext(emptyContext).valid
    && evaluatePurchaseInquiryEntryGuard({ context: preparationContext, action: 'startInquiry' }).allowed
    && !evaluatePurchaseInquiryEntryGuard({ context: emptyContext, action: 'startInquiry' }).allowed
    && PURCHASE_INQUIRY_ENTRY_CONTRACT.canonicalRoute === PURCHASE_INQUIRY_ENTRY_ACCEPTANCE_PROFILE.canonicalRoute
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

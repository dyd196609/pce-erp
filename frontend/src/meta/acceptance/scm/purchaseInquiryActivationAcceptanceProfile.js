import { assessPurchaseInquiryActivation } from '../../domain/scm/inquiryPreparation/purchaseInquiryActivationRule.js'
import { PURCHASE_INQUIRY_ACTIVATION_FORBIDDEN_ACTIONS, evaluatePurchaseInquiryActivationGuard } from '../../domain/scm/inquiryPreparation/purchaseInquiryActivationGuard.js'

export const PURCHASE_INQUIRY_ACTIVATION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_ACTIVATION', version: 'V1.14.2.8.7.11',
  status: 'SCM_PURCHASE_INQUIRY_ACTIVATION_READY', route: '/scm/purchase-inquiry',
  sourceObject: 'InquiryPreparationObject', targetObject: 'PurchaseInquiry', targetStatus: 'draft',
  triggerMode: 'manual_only', quotationCount: 0, supplierSent: false, purchaseOrderCreated: false,
  forbiddenActions: PURCHASE_INQUIRY_ACTIVATION_FORBIDDEN_ACTIONS,
})

export function validatePurchaseInquiryActivationAcceptance() {
  const preparation = { inquiryPreparationNo: 'IPR-PR202608020008', sourceRequestNo: 'PR202608020008',
    status: 'prepared', inquiryLines: [{ materialCode: 'MT068' }] }
  const assessment = assessPurchaseInquiryActivation(preparation)
  const valid = assessment.eligible && assessment.decision === 'allow_create_draft'
    && evaluatePurchaseInquiryActivationGuard('activatePurchaseInquiry').allowed
    && PURCHASE_INQUIRY_ACTIVATION_FORBIDDEN_ACTIONS.every(action => !evaluatePurchaseInquiryActivationGuard(action).allowed)
    && PURCHASE_INQUIRY_ACTIVATION_ACCEPTANCE_PROFILE.quotationCount === 0
    && PURCHASE_INQUIRY_ACTIVATION_ACCEPTANCE_PROFILE.supplierSent === false
    && PURCHASE_INQUIRY_ACTIVATION_ACCEPTANCE_PROFILE.purchaseOrderCreated === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

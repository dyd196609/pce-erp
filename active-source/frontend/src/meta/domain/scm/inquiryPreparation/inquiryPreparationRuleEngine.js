import { evaluatePurchaseRequestActionGuard } from '../../../process/scm/purchaseRequest/state/purchaseRequestStateContract.js'

export const INQUIRY_PREPARATION_RULE_VERSION = 'V1.14.2.8.7.9'

export function assessInquiryPreparationCreation(request = {}) {
  const stateGuard = evaluatePurchaseRequestActionGuard(request, 'CREATE_INQUIRY_PREPARATION')
  const checks = Object.freeze({
    approvalApproved: stateGuard.state.approvalStatus === 'approved',
    businessLifecycleAllowsPreparation: stateGuard.allowed,
    inquiryEligible: request.inquiryEligibility?.eligible === true,
    sourceLinesComplete: Array.isArray(request.items || request.inquiryEligibility?.items)
      && (request.items || request.inquiryEligibility?.items).length > 0,
  })
  const eligible = Object.values(checks).every(Boolean)
  const reasons = Object.freeze(Object.entries(checks).filter(([, passed]) => !passed).map(([code]) => code))
  return Object.freeze({ result: eligible ? 'PASS' : 'FAIL', eligible, checks, reasons, stateGuard,
    createsFormalInquiry: false, createsQuotationTask: false, sendsSupplier: false, createsQuotation: false })
}

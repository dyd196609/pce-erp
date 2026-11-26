export const QUOTATION_REVIEW_RUNTIME_GUARD_VERSION = 'V1.14.2.8.6.2'

export const QUOTATION_REVIEW_FORBIDDEN_ACTIONS = Object.freeze([
  'autoCreatePriceReview',
  'autoApproveQuotation',
  'autoSelectSupplier',
  'createPurchaseOrder',
  'autoCloseInquiry',
  'advancePriceApproval',
  'writeProductionDatabase',
])

export function evaluateQuotationReviewRuntimeGuard(action = '') {
  const protectedAction = QUOTATION_REVIEW_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'quotation_review_boundary_forbidden' : 'read_only_default_deny',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export const PRICE_REVIEW_PREPARATION_ACCEPTANCE_VERSION = 'V1.14.2.8.6.2'

export const PRICE_REVIEW_PREPARATION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_PRICE_REVIEW_PREPARATION_ACCEPTANCE',
  version: PRICE_REVIEW_PREPARATION_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_PRICE_REVIEW_PREPARATION_READY',
  route: '/scm/purchase-inquiry',
  objects: Object.freeze(['SCM_QUOTATION_COMPARISON_RUNTIME', 'SCM_PRICE_REVIEW_PREPARATION']),
  requiredRegions: Object.freeze(['quotation-comparison-runtime-status', 'price-review-preparation-status']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  activationMode: 'read_only',
  autoSupplierSelection: false,
  autoPriceApproval: false,
  autoPurchaseOrderCreation: false,
  autoCloseInquiry: false,
  existingPurchaseFlowModified: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validatePriceReviewPreparationAcceptance(profile = PRICE_REVIEW_PREPARATION_ACCEPTANCE_PROFILE) {
  const requiredGates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = requiredGates.every((gate) => profile.gates.includes(gate))
    && profile.objects.length === 2
    && profile.activationMode === 'read_only'
    && profile.autoSupplierSelection === false
    && profile.autoPriceApproval === false
    && profile.autoPurchaseOrderCreation === false
    && profile.autoCloseInquiry === false
    && profile.existingPurchaseFlowModified === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

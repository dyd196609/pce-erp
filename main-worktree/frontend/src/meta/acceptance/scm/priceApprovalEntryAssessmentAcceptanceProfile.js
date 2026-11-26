export const PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_VERSION = 'V1.14.2.8.6.3'

export const PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_PRICE_APPROVAL_ENTRY_ACCEPTANCE',
  version: PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_PRICE_APPROVAL_ENTRY_READY',
  route: '/scm/purchase-inquiry',
  objectCode: 'SCM_PRICE_APPROVAL_ENTRY_ASSESSMENT',
  requiredRegions: Object.freeze(['price-approval-entry-assessment']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  activationMode: 'read_only',
  formalPriceApprovalObjectCreated: false,
  approvalSubmitted: false,
  priceApproved: false,
  autoSupplierSelection: false,
  autoPurchaseOrderCreation: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validatePriceApprovalEntryAssessmentAcceptance(profile = PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.activationMode === 'read_only'
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalSubmitted === false
    && profile.priceApproved === false
    && profile.autoSupplierSelection === false
    && profile.autoPurchaseOrderCreation === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

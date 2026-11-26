export const FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_VERSION = 'V1.14.2.8.6.5'

export const FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_PROJECTION_READY',
  route: '/scm/purchase-inquiry',
  objects: Object.freeze(['SCM_FORMAL_PRICE_APPROVAL_PROJECTION', 'SCM_PRICE_APPROVAL_EVIDENCE_PACKAGE']),
  requiredRegions: Object.freeze(['formal-price-approval-projection', 'price-approval-evidence-package']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  activationMode: 'read_only',
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  approvalTaskCreated: false,
  approvalSubmitted: false,
  priceApproved: false,
  autoPurchaseOrderCreation: false,
  evidenceArchiveWritten: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalProjectionAcceptance(profile = FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.objects.length === 2
    && profile.activationMode === 'read_only'
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.approvalTaskCreated === false
    && profile.approvalSubmitted === false
    && profile.priceApproved === false
    && profile.autoPurchaseOrderCreation === false
    && profile.evidenceArchiveWritten === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

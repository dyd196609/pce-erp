export const FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_VERSION = 'V1.14.2.8.6.6'

export const FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_OBJECT_MODEL_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_OBJECT_MODEL_READY',
  route: '/scm/purchase-inquiry',
  objectCode: 'SCM_FORMAL_PRICE_APPROVAL_OBJECT',
  requiredRegions: Object.freeze(['formal-price-approval-object-model']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  activationMode: 'definition_only',
  currentAllowedStates: Object.freeze(['definition_only', 'ready_for_creation']),
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  approvalTaskCreated: false,
  approvalSubmitted: false,
  priceApproved: false,
  autoPurchaseOrderCreation: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalObjectAcceptance(profile = FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.activationMode === 'definition_only'
    && profile.currentAllowedStates.join(',') === 'definition_only,ready_for_creation'
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.approvalTaskCreated === false
    && profile.approvalSubmitted === false
    && profile.priceApproved === false
    && profile.autoPurchaseOrderCreation === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

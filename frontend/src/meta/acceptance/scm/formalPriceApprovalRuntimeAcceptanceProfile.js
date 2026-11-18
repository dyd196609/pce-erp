export const FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_VERSION = 'V1.14.2.8.6.7'

export const FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_RUNTIME_DESIGN_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_RUNTIME_DESIGN_READY',
  route: '/scm/purchase-inquiry',
  runtimeCode: 'SCM_FORMAL_PRICE_APPROVAL_RUNTIME',
  requiredRegions: Object.freeze(['formal-price-approval-runtime-design']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  executionMode: 'design_only',
  enabledTransition: Object.freeze({ from: 'definition_only', to: 'ready_for_creation' }),
  stateMutationAllowed: false,
  automaticProgression: false,
  workflowEngineConnected: false,
  approvalInstanceCreated: false,
  approvalWorkflowStarted: false,
  approvalTaskCreated: false,
  priceApproved: false,
  autoPurchaseOrderCreation: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalRuntimeAcceptance(profile = FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.executionMode === 'design_only'
    && profile.enabledTransition.from === 'definition_only'
    && profile.enabledTransition.to === 'ready_for_creation'
    && profile.stateMutationAllowed === false
    && profile.automaticProgression === false
    && profile.workflowEngineConnected === false
    && profile.approvalInstanceCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.approvalTaskCreated === false
    && profile.priceApproved === false
    && profile.autoPurchaseOrderCreation === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

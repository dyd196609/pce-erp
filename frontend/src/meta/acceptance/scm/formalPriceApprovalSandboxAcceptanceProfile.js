export const FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_VERSION = 'V1.14.2.8.6.12'

export const FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_SANDBOX_READY',
  route: '/scm/purchase-inquiry',
  sandboxCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SANDBOX',
  confirmationCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION',
  requiredRegions: Object.freeze(['formal-price-approval-creation-sandbox-confirmation']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  sandboxIsProduction: false,
  confirmationIsExecution: false,
  simulationIsCreation: false,
  productionEndpointConnected: false,
  executionPermissionGranted: false,
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalSandboxAcceptance(profile = FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.sandboxIsProduction === false
    && profile.confirmationIsExecution === false
    && profile.simulationIsCreation === false
    && profile.productionEndpointConnected === false
    && profile.executionPermissionGranted === false
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

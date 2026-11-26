export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_VERSION = 'V1.14.2.8.6.9'

export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_CREATE_FORMAL_PRICE_APPROVAL_COMMAND_DESIGN_ACCEPTANCE',
  version: CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_CREATION_COMMAND_DESIGN_READY',
  route: '/scm/purchase-inquiry',
  commandCode: 'SCM_CREATE_FORMAL_PRICE_APPROVAL_COMMAND',
  requiredRegions: Object.freeze(['create-formal-price-approval-command-design']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  triggerMode: 'manual_only',
  automaticExecution: false,
  closedStates: Object.freeze(['approved_for_execution', 'executed']),
  commandInstanceCreated: false,
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  approvalTaskCreated: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateCreateFormalPriceApprovalCommandAcceptance(profile = CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.triggerMode === 'manual_only'
    && profile.automaticExecution === false
    && profile.closedStates.join(',') === 'approved_for_execution,executed'
    && profile.commandInstanceCreated === false
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.approvalTaskCreated === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

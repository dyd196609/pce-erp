export const FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_VERSION = 'V1.14.2.8.6.18'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-workflow-handoff']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  lifecycleIsWorkflow: false,
  ownershipMeansExecution: false,
  pendingApprovalMeansWorkflowStarted: false,
  workflowStarted: false,
  workflowInstanceCount: 0,
  approvalTaskCount: 0,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalWorkflowHandoffAcceptance(profile = FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.lifecycleIsWorkflow === false
    && profile.ownershipMeansExecution === false
    && profile.pendingApprovalMeansWorkflowStarted === false
    && profile.workflowStarted === false
    && profile.workflowInstanceCount === 0
    && profile.approvalTaskCount === 0
    && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

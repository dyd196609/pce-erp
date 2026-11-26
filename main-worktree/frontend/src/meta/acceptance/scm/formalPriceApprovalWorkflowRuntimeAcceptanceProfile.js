export const FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_VERSION = 'V1.14.2.8.6.21'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-workflow-runtime']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  workflowRunningMeansApproved: false,
  workflowCompletedMeansResultCreated: false,
  runtimeStateMeansBusinessState: false,
  workflowStarted: false,
  approvalResultCount: 0,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalWorkflowRuntimeAcceptance(profile = FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.workflowRunningMeansApproved === false
    && profile.workflowCompletedMeansResultCreated === false
    && profile.runtimeStateMeansBusinessState === false
    && profile.workflowStarted === false
    && profile.approvalResultCount === 0
    && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

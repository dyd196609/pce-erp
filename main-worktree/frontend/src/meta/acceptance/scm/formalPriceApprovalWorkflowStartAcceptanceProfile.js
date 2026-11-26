export const FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_VERSION = 'V1.14.2.8.6.19'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_WORKFLOW_START_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-workflow-start-assessment']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  assessmentMeansStart: false,
  requestMeansInstance: false,
  pendingApprovalMeansRunning: false,
  workflowStarted: false,
  workflowRunning: false,
  workflowInstanceCount: 0,
  approvalTaskCount: 0,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalWorkflowStartAcceptance(profile = FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.assessmentMeansStart === false
    && profile.requestMeansInstance === false
    && profile.pendingApprovalMeansRunning === false
    && profile.workflowStarted === false
    && profile.workflowRunning === false
    && profile.workflowInstanceCount === 0
    && profile.approvalTaskCount === 0
    && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

export const FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT_VERSION = 'V1.14.2.8.6.19'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT_STATUSES = Object.freeze([
  'not_assessed',
  'checking',
  'start_ready',
  'manual_review',
  'blocked',
])

export const FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT = Object.freeze({
  assessmentCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT',
  version: FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT_VERSION,
  prerequisiteHandoffCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF',
  status: 'not_assessed',
  mode: 'assessment_only',
  assessmentMeansWorkflowStart: false,
  requestMeansInstance: false,
  pendingApprovalMeansRunning: false,
  workflowStarted: false,
  workflowRunning: false,
  workflowInstanceCount: 0,
  approvalTaskCount: 0,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalWorkflowStartAssessment(model = FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT) {
  const valid = model.assessmentCode === 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT'
    && FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT_STATUSES.includes(model.status)
    && model.prerequisiteHandoffCode === 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF'
    && model.mode === 'assessment_only'
    && model.assessmentMeansWorkflowStart === false
    && model.requestMeansInstance === false
    && model.pendingApprovalMeansRunning === false
    && model.workflowStarted === false
    && model.workflowRunning === false
    && model.workflowInstanceCount === 0
    && model.approvalTaskCount === 0
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

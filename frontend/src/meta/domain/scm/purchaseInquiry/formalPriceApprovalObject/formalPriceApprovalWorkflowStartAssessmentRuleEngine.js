export const FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT_RULE_VERSION = 'V1.14.2.8.6.19'

export function evaluateFormalPriceApprovalWorkflowStartAssessment(input = {}) {
  if (input.assessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', assessmentStatus: 'not_assessed', workflowStarted: false, workflowRunning: false, workflowInstanceCreated: false, approvalTaskCreated: false, stateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const evidenceComplete = input.handoffStatus === 'handoff_ready'
    && input.lifecycleState === 'pending_approval'
    && input.startAssessmentRequestPresent === true
    && input.requestValidated === true
    && input.humanConfirmationPresent === true
  const manualReview = input.specialProcurement === true && input.specialProcurementReviewed !== true
  const forbiddenRequest = input.automaticStart === true
    || input.workflowStartExecutionRequested === true
    || input.workflowInstanceCreationRequested === true
    || input.approvalTaskCreationRequested === true
    || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  const assessmentStatus = forbiddenRequest || !evidenceComplete ? 'blocked' : manualReview ? 'manual_review' : 'start_ready'
  return Object.freeze({
    result: assessmentStatus === 'start_ready' || assessmentStatus === 'manual_review' ? 'PASS' : 'FAIL',
    decision: assessmentStatus,
    assessmentStatus,
    requestEvidencePresent: input.startAssessmentRequestPresent === true,
    requestSeparatedFromInstance: true,
    workflowStarted: false,
    workflowRunning: false,
    workflowInstanceCreated: false,
    approvalTaskCreated: false,
    stateChanged: false,
    persistencePerformed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

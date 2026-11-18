export const FORMAL_PRICE_APPROVAL_FEEDBACK_RULE_VERSION = 'V1.14.2.8.6.23'

export function evaluateFormalPriceApprovalFeedback(input = {}) {
  if (input.assessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', feedbackStatus: 'not_assessed', commentCreated: false, feedbackExecuted: false, taskCreated: false, taskExecuted: false, approvalResultCreated: false, businessChangeApplied: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const definitionComplete = input.nodeDecisionStatus === 'node_decision_definition_ready'
    && input.commentDefinitionComplete === true
    && input.evidenceFeedbackDefinitionComplete === true
    && input.feedbackBoundaryIsolated === true
  const forbiddenRequest = input.commentCreationRequested === true
    || input.feedbackExecutionRequested === true
    || input.taskCreationRequested === true
    || input.taskExecutionRequested === true
    || input.approvalResultCreationRequested === true
    || input.businessChangeRequested === true
    || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  const feedbackStatus = definitionComplete && !forbiddenRequest ? 'feedback_definition_ready' : 'blocked'
  return Object.freeze({
    result: feedbackStatus === 'feedback_definition_ready' ? 'PASS' : 'FAIL', decision: feedbackStatus, feedbackStatus,
    commentCreated: false, feedbackExecuted: false, taskCreated: false, taskExecuted: false,
    approvalResultCreated: false, businessChangeApplied: false, businessStateChanged: false,
    persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false,
  })
}

export const FORMAL_PRICE_APPROVAL_FEEDBACK_GUARD_VERSION = 'V1.14.2.8.6.23'

export const FORMAL_PRICE_APPROVAL_FEEDBACK_FORBIDDEN_ACTIONS = Object.freeze([
  'createApprovalComment', 'executeEvidenceFeedback', 'createApprovalTask', 'executeApprovalTask',
  'runApprovalNode', 'createApprovalResult', 'applyBusinessChange', 'changeBusinessState',
  'persistCommentOrFeedback', 'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalFeedbackGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectFeedbackDefinition') {
    const definitionOnly = mode === 'feedback_definition_only'
    return Object.freeze({ result: definitionOnly ? 'PASS' : 'FAIL', decision: definitionOnly ? 'allow_definition_inspection_only' : 'deny', commentCreated: false, feedbackExecuted: false, taskCreated: false, taskExecuted: false, approvalResultCreated: false, businessChangeApplied: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_FEEDBACK_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny', reason: protectedAction ? 'feedback_chain_frozen' : 'feedback_default_deny', commentCreated: false, feedbackExecuted: false, taskCreated: false, taskExecuted: false, approvalResultCreated: false, businessChangeApplied: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}

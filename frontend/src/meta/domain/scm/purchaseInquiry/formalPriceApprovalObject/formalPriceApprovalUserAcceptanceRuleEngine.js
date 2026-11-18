export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_RULE_VERSION = 'V1.14.2.8.7.5'

const zeroEffect = Object.freeze({ viewSwitchExecuted: false, businessActionTriggered: false, userFeedbackPersisted: false,
  businessStateChanged: false, priceChanged: false, approvalObjectCreated: false, workflowStarted: false,
  approvalTaskCreated: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalUserAcceptance(input = {}) {
  if (input.action === 'resolveDefaultView') {
    const acceptanceRoles = ['developer', 'implementation', 'tester']
    const viewMode = acceptanceRoles.includes(input.userRole) ? 'acceptance_view' : 'business_view'
    return Object.freeze({ result: 'PASS', decision: viewMode, viewMode, ...zeroEffect })
  }
  if (input.action === 'switchView') {
    const allowed = ['business_view', 'acceptance_view'].includes(input.targetMode)
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'view_switched' : 'blocked',
      viewMode: allowed ? input.targetMode : 'business_view', ...zeroEffect, viewSwitchExecuted: allowed })
  }
  if (input.action === 'recordFeedback') {
    const validFeedback = input.feedbackIsBusinessData === false && input.persistRequested !== true
      && input.businessStateChangeRequested !== true && input.approvalActionRequested !== true
    return Object.freeze({ result: validFeedback ? 'PASS' : 'FAIL', decision: validFeedback ? 'session_feedback_recorded' : 'blocked',
      viewMode: input.viewMode || 'business_view', ...zeroEffect })
  }
  return Object.freeze({ result: 'FAIL', decision: 'blocked', viewMode: 'business_view', ...zeroEffect })
}

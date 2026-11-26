export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_RULE_VERSION = 'V1.14.2.8.7.6'

const zeroEffect = Object.freeze({ businessExecutionTriggered: false, feedbackPersisted: false,
  feedbackIsErpData: false, businessObjectCreated: false, approvalObjectCreated: false,
  workflowStarted: false, approvalTaskCreated: false, businessStateChanged: false,
  priceChanged: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalHumanAcceptance(input = {}) {
  if (input.action === 'runCanaryAcceptance') {
    const valid = input.environment === 'canary' && input.productionConnected === false
      && ['purchase_buyer', 'purchase_manager', 'acceptance_observer'].includes(input.userRole)
    return Object.freeze({ result: valid ? 'PASS' : 'FAIL', decision: valid ? 'session_acceptance_completed' : 'blocked',
      acceptanceStatus: valid ? 'accepted' : 'not_started', ...zeroEffect })
  }
  if (input.action === 'advanceFeedbackLoop') {
    const transitions = Object.freeze({ not_recorded: 'session_recorded', session_recorded: 'human_reviewed',
      human_reviewed: 'improvement_proposed', improvement_proposed: 'session_closed' })
    const nextState = transitions[input.currentState]
    const valid = Boolean(nextState) && input.persistRequested !== true && input.businessEffectRequested !== true
    return Object.freeze({ result: valid ? 'PASS' : 'FAIL', decision: valid ? 'feedback_loop_advanced' : 'blocked',
      feedbackState: valid ? nextState : input.currentState || 'not_recorded', ...zeroEffect })
  }
  return Object.freeze({ result: 'FAIL', decision: 'blocked', acceptanceStatus: 'not_started', ...zeroEffect })
}

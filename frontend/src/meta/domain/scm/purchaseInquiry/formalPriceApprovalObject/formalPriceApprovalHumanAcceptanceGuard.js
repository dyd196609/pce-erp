export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_GUARD_VERSION = 'V1.14.2.8.7.6'

export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FORBIDDEN_ACTIONS = Object.freeze([
  'connectCanaryToProduction', 'createBusinessObjectFromAcceptance', 'createApprovalObjectFromAcceptance',
  'startWorkflowFromAcceptance', 'createApprovalTaskFromAcceptance', 'persistHumanAcceptance',
  'persistFeedbackLoop', 'treatFeedbackAsErpData', 'changePriceFromFeedback',
  'changeBusinessStateFromFeedback', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ businessExecutionTriggered: false, feedbackPersisted: false,
  feedbackIsErpData: false, businessObjectCreated: false, approvalObjectCreated: false,
  workflowStarted: false, approvalTaskCreated: false, businessStateChanged: false,
  priceChanged: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalHumanAcceptanceGuard({ action = '', environment = '' } = {}) {
  if (action === 'runSessionHumanAcceptance') {
    const allowed = environment === 'canary'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_session_only' : 'deny', ...zeroEffect })
  }
  const forbidden = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: forbidden ? 'PASS' : 'FAIL', decision: 'deny',
    reason: forbidden ? 'human_acceptance_business_effect_frozen' : 'human_acceptance_default_deny', ...zeroEffect })
}

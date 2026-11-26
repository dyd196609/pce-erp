export const FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_GUARD_VERSION = 'V1.14.2.8.7.6.2'

export const FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_FORBIDDEN_ACTIONS = Object.freeze([
  'createPurchaseObjectFromHumanAcceptance', 'createApprovalObjectFromHumanAcceptance',
  'startWorkflowFromHumanAcceptance', 'createApprovalTaskFromHumanAcceptance',
  'persistHumanFeedbackAsErpData', 'changePriceFromHumanAcceptance',
  'changeBusinessStateFromHumanAcceptance', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ businessExecutionTriggered: false, feedbackPersisted: false,
  businessObjectCreated: false, approvalObjectCreated: false, workflowStarted: false,
  approvalTaskCreated: false, priceChanged: false, businessStateChanged: false,
  businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalHumanBusinessAcceptanceGuard({ action = '', viewMode = '' } = {}) {
  if (action === 'executeSessionHumanAcceptance') {
    const allowed = viewMode === 'business_view'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_acceptance_only' : 'deny', ...zeroEffect })
  }
  if (action === 'inspectAcceptanceView') {
    const allowed = viewMode === 'acceptance_view'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_read_only' : 'deny', ...zeroEffect })
  }
  const forbidden = FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: forbidden ? 'PASS' : 'FAIL', decision: 'deny',
    reason: forbidden ? 'human_business_acceptance_effect_frozen' : 'human_business_acceptance_default_deny', ...zeroEffect })
}

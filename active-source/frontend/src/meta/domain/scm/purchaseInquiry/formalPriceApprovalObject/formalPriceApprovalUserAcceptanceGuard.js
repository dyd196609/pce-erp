export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_GUARD_VERSION = 'V1.14.2.8.7.5'

export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FORBIDDEN_ACTIONS = Object.freeze([
  'createObjectFromViewSwitch', 'startApprovalFromFeedback', 'changePriceFromFeedback',
  'changeBusinessStateFromFeedback', 'writeBusinessDatabaseFromFeedback', 'createApprovalTaskFromFeedback',
])

const zeroEffect = Object.freeze({ businessActionTriggered: false, userFeedbackPersisted: false, priceChanged: false,
  businessStateChanged: false, approvalObjectCreated: false, workflowStarted: false,
  approvalTaskCreated: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalUserAcceptanceGuard({ action = '', mode = '' } = {}) {
  if (action === 'recordSessionFeedback') {
    const allowed = mode === 'session_only'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_session_only' : 'deny', ...zeroEffect })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny',
    reason: protectedAction ? 'user_acceptance_business_effect_frozen' : 'user_acceptance_default_deny', ...zeroEffect })
}

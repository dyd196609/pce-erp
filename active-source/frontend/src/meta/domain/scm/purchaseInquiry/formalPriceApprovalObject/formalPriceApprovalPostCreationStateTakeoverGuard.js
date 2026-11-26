export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_GUARD_VERSION = 'V1.14.2.8.6.16'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_FORBIDDEN_ACTIONS = Object.freeze([
  'autoTakeoverState',
  'mutateCreatedState',
  'transitionToPendingApproval',
  'claimWorkflowOwnership',
  'startApprovalWorkflow',
  'createApprovalInstance',
  'createApprovalTask',
  'approvePrice',
  'persistTakeoverAssessment',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalPostCreationStateTakeoverGuard({ action = '', takeoverMode = '' } = {}) {
  if (action === 'evaluateStateTakeover') {
    const isolated = takeoverMode === 'manual_isolated'
    return Object.freeze({ result: isolated ? 'PASS' : 'FAIL', decision: isolated ? 'allow_takeover_assessment_only' : 'deny', stateChanged: false, stateMutationAllowed: false, workflowEngineConnected: false, approvalWorkflowStarted: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'post_creation_takeover_isolated' : 'post_creation_takeover_default_deny',
    stateChanged: false,
    stateMutationAllowed: false,
    workflowEngineConnected: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

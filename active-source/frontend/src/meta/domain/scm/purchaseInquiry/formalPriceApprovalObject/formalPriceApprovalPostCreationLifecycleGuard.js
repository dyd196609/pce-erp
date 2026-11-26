export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_GUARD_VERSION = 'V1.14.2.8.6.17'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_FORBIDDEN_ACTIONS = Object.freeze([
  'autoTransitionFromCreated',
  'transitionToPendingApproval',
  'transitionToApproved',
  'transitionToRejected',
  'transitionToCancelled',
  'executeLifecycle',
  'startApprovalWorkflow',
  'createApprovalTask',
  'persistLifecycleState',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalPostCreationLifecycleGuard({ action = '', executionMode = '' } = {}) {
  if (action === 'inspectLifecycleTransition') {
    const frozenDesign = executionMode === 'frozen_design_only'
    return Object.freeze({ result: frozenDesign ? 'PASS' : 'FAIL', decision: frozenDesign ? 'allow_transition_inspection_only' : 'deny', lifecycleExecuted: false, stateChanged: false, workflowEngineConnected: false, statePersisted: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'post_creation_lifecycle_frozen' : 'post_creation_lifecycle_default_deny',
    lifecycleExecuted: false,
    stateChanged: false,
    workflowEngineConnected: false,
    statePersisted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

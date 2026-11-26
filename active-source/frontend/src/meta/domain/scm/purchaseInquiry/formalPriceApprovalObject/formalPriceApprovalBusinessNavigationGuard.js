export const FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_GUARD_VERSION = 'V1.14.2.8.7.2'

export const FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_FORBIDDEN_ACTIONS = Object.freeze([
  'executeNavigationStep', 'startWorkflowRuntimeFromPath', 'autoRunNextStep', 'createApprovalObject',
  'createApprovalTask', 'persistNavigationState', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ routeActionPerformed: false, workflowRuntimeStarted: false, autoActionPerformed: false,
  approvalObjectCreated: false, approvalTaskCreated: false, persistencePerformed: false,
  businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalBusinessNavigationGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectBusinessNavigation') {
    const allowed = mode === 'read_only_guidance'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_read_only' : 'deny', ...zeroEffect })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny',
    reason: protectedAction ? 'navigation_execution_boundary_frozen' : 'navigation_default_deny', ...zeroEffect })
}

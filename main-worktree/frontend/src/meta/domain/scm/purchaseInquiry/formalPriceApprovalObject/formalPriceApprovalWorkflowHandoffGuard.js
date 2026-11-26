export const FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_GUARD_VERSION = 'V1.14.2.8.6.18'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_FORBIDDEN_ACTIONS = Object.freeze([
  'startWorkflow',
  'createWorkflowInstance',
  'createApprovalTask',
  'executeHandoff',
  'advanceLifecycleState',
  'persistHandoff',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalWorkflowHandoffGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectHandoffBoundary') {
    const designOnly = mode === 'boundary_design_only'
    return Object.freeze({ result: designOnly ? 'PASS' : 'FAIL', decision: designOnly ? 'allow_inspection_only' : 'deny', workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false, stateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny', reason: protectedAction ? 'workflow_handoff_isolated' : 'workflow_handoff_default_deny', workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false, stateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}

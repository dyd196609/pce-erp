export const FORMAL_PRICE_APPROVAL_INSTANCE_TASK_GUARD_VERSION = 'V1.14.2.8.6.20'

export const FORMAL_PRICE_APPROVAL_INSTANCE_TASK_FORBIDDEN_ACTIONS = Object.freeze([
  'createApprovalInstance',
  'createApprovalTask',
  'startWorkflow',
  'markWorkflowRunning',
  'createApprovalResult',
  'advanceInstanceLifecycle',
  'advanceTaskLifecycle',
  'persistInstanceOrTask',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalInstanceTaskGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectInstanceTaskLifecycle') {
    const definitionOnly = mode === 'definition_only'
    return Object.freeze({ result: definitionOnly ? 'PASS' : 'FAIL', decision: definitionOnly ? 'allow_definition_inspection_only' : 'deny', instanceCreated: false, taskCreated: false, workflowStarted: false, workflowRunning: false, approvalResultCreated: false, stateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_INSTANCE_TASK_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny', reason: protectedAction ? 'instance_task_lifecycle_frozen' : 'instance_task_default_deny', instanceCreated: false, taskCreated: false, workflowStarted: false, workflowRunning: false, approvalResultCreated: false, stateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}

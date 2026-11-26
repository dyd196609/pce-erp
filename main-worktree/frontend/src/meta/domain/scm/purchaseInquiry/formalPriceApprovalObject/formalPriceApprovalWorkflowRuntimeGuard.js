export const FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_GUARD_VERSION = 'V1.14.2.8.6.21'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_FORBIDDEN_ACTIONS = Object.freeze([
  'initializeWorkflowRuntime',
  'startWorkflow',
  'markWorkflowRunning',
  'completeWorkflow',
  'createApprovalInstance',
  'createApprovalTask',
  'createApprovalResult',
  'approvePrice',
  'changeBusinessState',
  'persistRuntimeOrResult',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalWorkflowRuntimeGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectWorkflowRuntimeDefinition') {
    const definitionOnly = mode === 'definition_only'
    return Object.freeze({ result: definitionOnly ? 'PASS' : 'FAIL', decision: definitionOnly ? 'allow_definition_inspection_only' : 'deny', workflowInitialized: false, workflowStarted: false, workflowRunning: false, workflowCompleted: false, approvalResultCreated: false, approved: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny', reason: protectedAction ? 'workflow_runtime_frozen' : 'workflow_runtime_default_deny', workflowInitialized: false, workflowStarted: false, workflowRunning: false, workflowCompleted: false, approvalResultCreated: false, approved: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}

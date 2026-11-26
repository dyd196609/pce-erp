export const FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_GUARD_VERSION = 'V1.14.2.8.6.25'

export const FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_FORBIDDEN_ACTIONS = Object.freeze([
  'createApprovalObject', 'startWorkflow', 'createWorkflowInstance', 'createApprovalTask',
  'executeOperation', 'autoRunAfterPass', 'changeBusinessState', 'persistGovernanceSummary', 'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalGovernanceSummaryGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectGovernanceSummary') {
    const validationOnly = mode === 'validation_only'
    return Object.freeze({ result: validationOnly ? 'PASS' : 'FAIL', decision: validationOnly ? 'allow_validation_only' : 'deny', approvalObjectCreated: false, workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false, operationExecuted: false, autoRunPerformed: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny', reason: protectedAction ? 'governance_summary_execution_frozen' : 'governance_summary_default_deny', approvalObjectCreated: false, workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false, operationExecuted: false, autoRunPerformed: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}

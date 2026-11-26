export const FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT_GUARD_VERSION = 'V1.14.2.8.6.19'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_START_FORBIDDEN_ACTIONS = Object.freeze([
  'startWorkflow',
  'autoStartWorkflow',
  'createWorkflowInstance',
  'createApprovalTask',
  'markWorkflowRunning',
  'advancePendingApprovalState',
  'persistStartAssessment',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalWorkflowStartAssessmentGuard({ action = '', mode = '' } = {}) {
  if (action === 'assessWorkflowStartConditions') {
    const assessmentOnly = mode === 'assessment_only'
    return Object.freeze({ result: assessmentOnly ? 'PASS' : 'FAIL', decision: assessmentOnly ? 'allow_assessment_only' : 'deny', workflowStarted: false, workflowRunning: false, workflowInstanceCreated: false, approvalTaskCreated: false, stateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_WORKFLOW_START_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny', reason: protectedAction ? 'workflow_start_frozen' : 'workflow_start_default_deny', workflowStarted: false, workflowRunning: false, workflowInstanceCreated: false, approvalTaskCreated: false, stateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}

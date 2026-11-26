export const FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_RULE_VERSION = 'V1.14.2.8.6.21'

export function evaluateFormalPriceApprovalWorkflowRuntime(input = {}) {
  if (input.assessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', runtimeStatus: 'not_assessed', workflowInitialized: false, workflowStarted: false, workflowRunning: false, workflowCompleted: false, approvalResultCreated: false, approved: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const definitionComplete = input.instanceTaskLifecycleStatus === 'lifecycle_definition_ready'
    && input.runtimeDefinitionComplete === true
    && input.resultBoundaryIsolated === true
  const forbiddenRequest = input.workflowInitializationRequested === true
    || input.workflowStartRequested === true
    || input.workflowRunningRequested === true
    || input.workflowCompletionRequested === true
    || input.approvalResultCreationRequested === true
    || input.approvalDecisionRequested === true
    || input.businessStateChangeRequested === true
    || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  const runtimeStatus = definitionComplete && !forbiddenRequest ? 'runtime_definition_ready' : 'blocked'
  return Object.freeze({
    result: runtimeStatus === 'runtime_definition_ready' ? 'PASS' : 'FAIL',
    decision: runtimeStatus,
    runtimeStatus,
    workflowInitialized: false,
    workflowStarted: false,
    workflowRunning: false,
    workflowCompleted: false,
    approvalResultCreated: false,
    approved: false,
    businessStateChanged: false,
    persistencePerformed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

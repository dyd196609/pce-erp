export const FORMAL_PRICE_APPROVAL_INSTANCE_TASK_RULE_VERSION = 'V1.14.2.8.6.20'

export function evaluateFormalPriceApprovalInstanceTaskLifecycle(input = {}) {
  if (input.assessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', lifecycleStatus: 'not_assessed', instanceCreated: false, taskCreated: false, workflowStarted: false, workflowRunning: false, approvalResultCreated: false, stateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const definitionComplete = input.workflowStartAssessmentStatus === 'start_ready'
    && input.instanceDefinitionComplete === true
    && input.taskDefinitionComplete === true
    && input.instanceBoundaryIsolated === true
  const forbiddenRequest = input.instanceCreationRequested === true
    || input.taskCreationRequested === true
    || input.workflowStartRequested === true
    || input.workflowRunningRequested === true
    || input.approvalResultRequested === true
    || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  const lifecycleStatus = definitionComplete && !forbiddenRequest ? 'lifecycle_definition_ready' : 'blocked'
  return Object.freeze({
    result: lifecycleStatus === 'lifecycle_definition_ready' ? 'PASS' : 'FAIL',
    decision: lifecycleStatus,
    lifecycleStatus,
    instanceDefinitionReady: definitionComplete,
    taskDefinitionReady: definitionComplete,
    instanceCreated: false,
    taskCreated: false,
    workflowStarted: false,
    workflowRunning: false,
    approvalResultCreated: false,
    stateChanged: false,
    persistencePerformed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

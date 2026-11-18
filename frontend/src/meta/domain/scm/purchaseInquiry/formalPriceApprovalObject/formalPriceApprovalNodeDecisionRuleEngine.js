export const FORMAL_PRICE_APPROVAL_NODE_DECISION_RULE_ENGINE_VERSION = 'V1.14.2.8.6.22'

export function evaluateFormalPriceApprovalNodeDecisionRules(input = {}) {
  if (input.assessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', definitionStatus: 'not_assessed', taskCreated: false, nodeExecuted: false, decisionExecuted: false, approvalResultCreated: false, businessEffectApplied: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const definitionComplete = input.workflowRuntimeStatus === 'runtime_definition_ready'
    && input.nodeDefinitionsComplete === true
    && input.decisionRulesComplete === true
    && input.nodeDecisionBoundaryIsolated === true
  const forbiddenRequest = input.taskCreationRequested === true
    || input.nodeExecutionRequested === true
    || input.decisionExecutionRequested === true
    || input.approvalResultCreationRequested === true
    || input.businessEffectRequested === true
    || input.businessStateChangeRequested === true
    || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  const definitionStatus = definitionComplete && !forbiddenRequest ? 'node_decision_definition_ready' : 'blocked'
  return Object.freeze({
    result: definitionStatus === 'node_decision_definition_ready' ? 'PASS' : 'FAIL',
    decision: definitionStatus,
    definitionStatus,
    taskCreated: false,
    nodeExecuted: false,
    decisionExecuted: false,
    approvalResultCreated: false,
    businessEffectApplied: false,
    businessStateChanged: false,
    persistencePerformed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

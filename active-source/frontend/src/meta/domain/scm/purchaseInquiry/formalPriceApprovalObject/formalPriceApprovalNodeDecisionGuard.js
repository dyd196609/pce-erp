export const FORMAL_PRICE_APPROVAL_NODE_DECISION_GUARD_VERSION = 'V1.14.2.8.6.22'

export const FORMAL_PRICE_APPROVAL_NODE_DECISION_FORBIDDEN_ACTIONS = Object.freeze([
  'createApprovalTask',
  'runApprovalNode',
  'executeDecisionRule',
  'makeApprovalDecision',
  'createApprovalResult',
  'applyBusinessEffect',
  'changeBusinessState',
  'persistNodeDecision',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalNodeDecisionGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectNodeDecisionDefinition') {
    const inspectionOnly = mode === 'definition_inspection_only'
    return Object.freeze({ result: inspectionOnly ? 'PASS' : 'FAIL', decision: inspectionOnly ? 'allow_definition_inspection_only' : 'deny', taskCreated: false, nodeExecuted: false, decisionExecuted: false, approvalResultCreated: false, businessEffectApplied: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_NODE_DECISION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny', reason: protectedAction ? 'node_decision_frozen' : 'node_decision_default_deny', taskCreated: false, nodeExecuted: false, decisionExecuted: false, approvalResultCreated: false, businessEffectApplied: false, businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}

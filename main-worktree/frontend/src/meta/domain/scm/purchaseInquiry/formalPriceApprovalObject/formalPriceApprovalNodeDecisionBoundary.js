export const FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY_VERSION = 'V1.14.2.8.6.22'

export const FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY = Object.freeze({
  boundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY',
  version: FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY_VERSION,
  mode: 'definition_inspection_only',
  nodeDefinitionMeansTaskCreated: false,
  decisionRuleMeansResult: false,
  approvalDecisionMeansBusinessEffect: false,
  nodeExecutorConnected: false,
  taskFactoryConnected: false,
  resultFactoryConnected: false,
  businessEffectExecutorConnected: false,
  persistenceAdapterConnected: false,
  productionExecution: false,
})

export function validateFormalPriceApprovalNodeDecisionBoundary(model = FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY) {
  const valid = model.boundaryCode === 'SCM_FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY'
    && model.mode === 'definition_inspection_only'
    && model.nodeDefinitionMeansTaskCreated === false
    && model.decisionRuleMeansResult === false
    && model.approvalDecisionMeansBusinessEffect === false
    && model.nodeExecutorConnected === false
    && model.taskFactoryConnected === false
    && model.resultFactoryConnected === false
    && model.businessEffectExecutorConnected === false
    && model.persistenceAdapterConnected === false
    && model.productionExecution === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

export const FORMAL_PRICE_APPROVAL_NODE_DEFINITION_VERSION = 'V1.14.2.8.6.22'

export const FORMAL_PRICE_APPROVAL_NODE_DEFINITIONS = Object.freeze([
  Object.freeze({ nodeCode: 'evidence_review', sequence: 1, roleCode: 'price_evidence_reviewer', mode: 'definition_only', executionEnabled: false }),
  Object.freeze({ nodeCode: 'price_review', sequence: 2, roleCode: 'price_reviewer', mode: 'definition_only', executionEnabled: false }),
  Object.freeze({ nodeCode: 'final_confirmation', sequence: 3, roleCode: 'price_confirmation_reviewer', mode: 'definition_only', executionEnabled: false }),
])

export const FORMAL_PRICE_APPROVAL_NODE_DEFINITION = Object.freeze({
  definitionCode: 'SCM_FORMAL_PRICE_APPROVAL_NODE_DEFINITION',
  version: FORMAL_PRICE_APPROVAL_NODE_DEFINITION_VERSION,
  nodes: FORMAL_PRICE_APPROVAL_NODE_DEFINITIONS,
  nodeDefinitionMeansTaskCreated: false,
  nodeExecutionEnabled: false,
  taskFactoryConnected: false,
  nodeRuntimeCount: 0,
  taskCount: 0,
  persistenceConnected: false,
})

export function validateFormalPriceApprovalNodeDefinition(model = FORMAL_PRICE_APPROVAL_NODE_DEFINITION) {
  const valid = model.definitionCode === 'SCM_FORMAL_PRICE_APPROVAL_NODE_DEFINITION'
    && model.nodes.length === 3
    && model.nodes.every((node, index) => node.sequence === index + 1 && node.mode === 'definition_only' && node.executionEnabled === false)
    && new Set(model.nodes.map((node) => node.roleCode)).size === model.nodes.length
    && model.nodeDefinitionMeansTaskCreated === false
    && model.nodeExecutionEnabled === false
    && model.taskFactoryConnected === false
    && model.nodeRuntimeCount === 0
    && model.taskCount === 0
    && model.persistenceConnected === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

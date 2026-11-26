export const FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_VERSION = 'V1.14.2.8.6.22'

export const FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_NODE_DECISION_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-node-decision']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  nodeDefinitionMeansTaskCreated: false,
  decisionRuleMeansResult: false,
  approvalDecisionMeansBusinessEffect: false,
  taskCount: 0,
  approvalResultCount: 0,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalNodeDecisionAcceptance(profile = FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.nodeDefinitionMeansTaskCreated === false
    && profile.decisionRuleMeansResult === false
    && profile.approvalDecisionMeansBusinessEffect === false
    && profile.taskCount === 0
    && profile.approvalResultCount === 0
    && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

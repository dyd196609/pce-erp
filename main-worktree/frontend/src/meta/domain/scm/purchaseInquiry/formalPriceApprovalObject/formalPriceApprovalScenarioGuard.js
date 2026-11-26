export const FORMAL_PRICE_APPROVAL_SCENARIO_GUARD_VERSION = 'V1.14.2.8.7.3'

export const FORMAL_PRICE_APPROVAL_SCENARIO_FORBIDDEN_ACTIONS = Object.freeze([
  'useProductionScenarioData', 'applyExpectedResultAsDecision', 'createBusinessObject',
  'createApprovalObject', 'startWorkflow', 'persistScenarioResult', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ productionDataUsed: false, autoDecisionPerformed: false, businessObjectCreated: false,
  approvalObjectCreated: false, workflowStarted: false, persistencePerformed: false,
  businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalScenarioGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectScenarioCase') {
    const allowed = mode === 'synthetic_read_only'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_read_only' : 'deny', ...zeroEffect })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_SCENARIO_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny',
    reason: protectedAction ? 'scenario_production_boundary_frozen' : 'scenario_default_deny', ...zeroEffect })
}

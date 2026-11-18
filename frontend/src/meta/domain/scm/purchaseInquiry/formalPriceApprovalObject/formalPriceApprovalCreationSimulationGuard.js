export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_GUARD_VERSION = 'V1.14.2.8.6.8'

export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_FORBIDDEN_ACTIONS = Object.freeze([
  'createFormalPriceApprovalObject',
  'persistSimulationArtifact',
  'writeProductionDatabase',
  'startApprovalWorkflow',
  'createApprovalInstance',
  'createApprovalTask',
  'submitApproval',
  'approvePrice',
  'createPurchaseOrder',
])

export function evaluateFormalPriceApprovalCreationSimulationGuard(action = '') {
  const protectedAction = FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'creation_simulation_zero_write_boundary' : 'simulation_default_deny',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

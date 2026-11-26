export const FORMAL_PRICE_APPROVAL_RUNTIME_GUARD_VERSION = 'V1.14.2.8.6.7'

export const FORMAL_PRICE_APPROVAL_RUNTIME_FORBIDDEN_ACTIONS = Object.freeze([
  'autoAdvanceState',
  'transitionToCreated',
  'startApprovalWorkflow',
  'createApprovalInstance',
  'createApprovalTask',
  'submitApproval',
  'approvePrice',
  'createPurchaseOrder',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalRuntimeGuard(action = '') {
  const protectedAction = FORMAL_PRICE_APPROVAL_RUNTIME_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'formal_price_approval_runtime_isolated' : 'runtime_design_default_deny',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

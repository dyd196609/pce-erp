export const FORMAL_PRICE_APPROVAL_PROJECTION_GUARD_VERSION = 'V1.14.2.8.6.5'

export const FORMAL_PRICE_APPROVAL_PROJECTION_FORBIDDEN_ACTIONS = Object.freeze([
  'createFormalPriceApproval',
  'startApprovalWorkflow',
  'createApprovalTask',
  'submitApproval',
  'approvePrice',
  'createPurchaseOrder',
  'persistEvidencePackage',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalProjectionRuntimeGuard(action = '') {
  const protectedAction = FORMAL_PRICE_APPROVAL_PROJECTION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'formal_price_approval_projection_read_only' : 'read_only_default_deny',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

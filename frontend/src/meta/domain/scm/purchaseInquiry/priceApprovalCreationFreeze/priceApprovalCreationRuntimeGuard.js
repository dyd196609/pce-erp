export const PRICE_APPROVAL_CREATION_RUNTIME_GUARD_VERSION = 'V1.14.2.8.6.4'

export const PRICE_APPROVAL_CREATION_FORBIDDEN_ACTIONS = Object.freeze([
  'autoCreateFormalPriceApproval',
  'createFormalPriceApproval',
  'autoStartApprovalWorkflow',
  'startApprovalWorkflow',
  'autoSubmitApproval',
  'submitApproval',
  'autoApprovePrice',
  'approvePrice',
  'createPurchaseOrder',
  'writeProductionDatabase',
])

export function evaluatePriceApprovalCreationRuntimeGuard(action = '') {
  const protectedAction = PRICE_APPROVAL_CREATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'formal_price_approval_creation_frozen' : 'read_only_default_deny',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

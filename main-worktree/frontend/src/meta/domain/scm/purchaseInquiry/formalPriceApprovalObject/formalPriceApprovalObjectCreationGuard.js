export const FORMAL_PRICE_APPROVAL_OBJECT_CREATION_GUARD_VERSION = 'V1.14.2.8.6.6'

export const FORMAL_PRICE_APPROVAL_OBJECT_FORBIDDEN_ACTIONS = Object.freeze([
  'autoCreateApprovalObject',
  'createFormalPriceApprovalObject',
  'autoSubmitApproval',
  'submitApproval',
  'autoApprovePrice',
  'approvePrice',
  'startApprovalWorkflow',
  'createApprovalTask',
  'createPurchaseOrder',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalObjectCreationGuard(action = '') {
  const protectedAction = FORMAL_PRICE_APPROVAL_OBJECT_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'formal_price_approval_object_creation_frozen' : 'definition_only_default_deny',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

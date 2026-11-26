export const PRICE_APPROVAL_ENTRY_RUNTIME_GUARD_VERSION = 'V1.14.2.8.6.3'

export const PRICE_APPROVAL_ENTRY_FORBIDDEN_ACTIONS = Object.freeze([
  'autoCreatePriceApproval',
  'createPriceApproval',
  'autoSubmitApproval',
  'submitPriceApproval',
  'autoApprovePrice',
  'approvePrice',
  'autoSelectSupplier',
  'createPurchaseOrder',
  'writeProductionDatabase',
])

export function evaluatePriceApprovalEntryRuntimeGuard(action = '') {
  const protectedAction = PRICE_APPROVAL_ENTRY_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'price_approval_entry_frozen' : 'read_only_default_deny',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

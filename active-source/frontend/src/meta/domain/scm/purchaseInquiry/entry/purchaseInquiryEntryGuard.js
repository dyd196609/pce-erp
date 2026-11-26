import { PURCHASE_INQUIRY_ENTRY_CONTRACT } from './purchaseInquiryEntryContract.js'

export function evaluatePurchaseInquiryEntryGuard({ context = {}, action = '' } = {}) {
  if (PURCHASE_INQUIRY_ENTRY_CONTRACT.forbiddenActions.includes(action)) return Object.freeze({ result: 'PASS', decision: 'deny', allowed: false,
    reason: 'entry_contract_forbidden_action', businessWriteCount: 0 })
  if (action === 'startInquiry') {
    const allowed = context.entryType === 'purchase_request_preparation' && context.creationContextComplete === true
      && !context.currentInquiryNo
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', allowed,
      reason: allowed ? '' : 'inquiry_preparation_context_required', businessWriteCount: 0 })
  }
  if (action === 'viewInquiry') {
    const allowed = Boolean(context.currentInquiryNo)
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow' : 'deny', allowed,
      reason: allowed ? '' : 'existing_inquiry_required', businessWriteCount: 0 })
  }
  return Object.freeze({ result: 'FAIL', decision: 'deny', allowed: false, reason: 'entry_guard_default_deny', businessWriteCount: 0 })
}

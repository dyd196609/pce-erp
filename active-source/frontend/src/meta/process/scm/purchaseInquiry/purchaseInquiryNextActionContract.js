export const PURCHASE_INQUIRY_NEXT_ACTION_CONTRACT = Object.freeze({
  contractCode: 'SCM_PURCHASE_INQUIRY_NEXT_ACTION_CONTRACT',
  objectType: 'PurchaseInquiry', statusCode: 'draft',
  allowedActions: Object.freeze([
    'EDIT_PURCHASE_INQUIRY', 'SAVE_PURCHASE_INQUIRY', 'PREPARE_SUPPLIER_QUOTE',
  ]),
  forbiddenActions: Object.freeze(['CREATE_PURCHASE_ORDER']),
})

export function evaluatePurchaseInquiryNextAction(inquiry = {}, actionCode = '') {
  const allowed = inquiry.statusCode === PURCHASE_INQUIRY_NEXT_ACTION_CONTRACT.statusCode
    && PURCHASE_INQUIRY_NEXT_ACTION_CONTRACT.allowedActions.includes(actionCode)
    && !PURCHASE_INQUIRY_NEXT_ACTION_CONTRACT.forbiddenActions.includes(actionCode)
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', allowed, actionCode,
    nextState: allowed ? 'draft' : inquiry.statusCode || 'unknown', purchaseOrderCreated: false })
}

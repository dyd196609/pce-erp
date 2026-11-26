export const PURCHASE_INQUIRY_PAGE_ACTION_CONTRACT_VERSION = 'V1.14.2.8.18.4'

export const PURCHASE_INQUIRY_PAGE_ACTION_CODES = Object.freeze({
  view: 'VIEW_PURCHASE_INQUIRY', edit: 'EDIT_PURCHASE_INQUIRY', save: 'SAVE_PURCHASE_INQUIRY',
})

export const PURCHASE_INQUIRY_PAGE_ACTION_CONTRACT = Object.freeze({
  contractCode: 'SCM_PURCHASE_INQUIRY_PAGE_ACTION_CONTRACT', objectType: 'PurchaseInquiry',
  allowedStatus: 'draft',
  actions: Object.freeze([
    Object.freeze({ actionCode: 'VIEW_PURCHASE_INQUIRY', buttonCode: 'view-purchase-inquiry', writeMode: 'none' }),
    Object.freeze({ actionCode: 'VIEW_INQUIRY', buttonCode: 'view-purchase-inquiry', writeMode: 'none' }),
    Object.freeze({ actionCode: 'EDIT_PURCHASE_INQUIRY', buttonCode: 'edit-purchase-inquiry', writeMode: 'session_draft' }),
    Object.freeze({ actionCode: 'SAVE_PURCHASE_INQUIRY', buttonCode: 'save-purchase-inquiry', writeMode: 'session_draft' }),
  ]),
  forbiddenActions: Object.freeze(['SEND_SUPPLIER', 'CREATE_PURCHASE_ORDER']),
})

export function evaluatePurchaseInquiryPageAction(inquiry = {}, actionCode = '') {
  const declared = PURCHASE_INQUIRY_PAGE_ACTION_CONTRACT.actions.find(item => item.actionCode === actionCode)
  const forbidden = PURCHASE_INQUIRY_PAGE_ACTION_CONTRACT.forbiddenActions.includes(actionCode)
  const runtimeState = inquiry.runtimeState || (inquiry.statusCode === 'draft' ? 'inquiry_draft' : '')
  const runtimeAllowed = actionCode === 'VIEW_PURCHASE_INQUIRY' || actionCode === 'VIEW_INQUIRY'
    ? ['inquiry_draft', 'quote_preparation_ready'].includes(runtimeState)
    : runtimeState === 'inquiry_draft'
  const allowed = Boolean(declared) && inquiry.statusCode === 'draft' && runtimeAllowed && !forbidden
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', allowed, actionCode,
    reason: forbidden ? 'PURCHASE_INQUIRY_PAGE_ACTION_FORBIDDEN'
      : allowed ? 'PURCHASE_INQUIRY_DRAFT_ACTION_ALLOWED' : 'PURCHASE_INQUIRY_DRAFT_REQUIRED', contract: declared || null })
}

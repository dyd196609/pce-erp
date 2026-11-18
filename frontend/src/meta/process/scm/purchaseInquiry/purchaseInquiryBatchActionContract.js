import { evaluatePurchaseInquiryPageAction } from './purchaseInquiryPageActionContract.js'

export const PURCHASE_INQUIRY_BATCH_ACTION_CONTRACT = Object.freeze({
  contractCode: 'SCM_PURCHASE_INQUIRY_BATCH_ACTION_CONTRACT',
  actions: Object.freeze([
    Object.freeze({ actionCode: 'BATCH_VIEW_PURCHASE_INQUIRIES', itemActionCode: 'VIEW_PURCHASE_INQUIRY', writeMode: 'none' }),
    Object.freeze({ actionCode: 'BATCH_EDIT_PURCHASE_INQUIRIES', itemActionCode: 'EDIT_PURCHASE_INQUIRY', writeMode: 'session_draft_queue' }),
  ]),
  forbiddenActions: Object.freeze(['BATCH_SEND_SUPPLIER', 'BATCH_CREATE_PURCHASE_ORDER']),
})

export function executePurchaseInquiryBatchAction(rows = [], actionCode = '') {
  const selected = Array.isArray(rows) ? rows : []
  const contract = PURCHASE_INQUIRY_BATCH_ACTION_CONTRACT.actions.find(item => item.actionCode === actionCode)
  const forbidden = PURCHASE_INQUIRY_BATCH_ACTION_CONTRACT.forbiddenActions.includes(actionCode)
  const itemResults = Object.freeze(selected.map(row => Object.freeze({ inquiryNo: row.inquiryNo,
    ...evaluatePurchaseInquiryPageAction(row, contract?.itemActionCode || actionCode) })))
  const valid = !forbidden && Boolean(contract) && selected.length > 0 && itemResults.every(item => item.allowed)
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, actionCode,
    selectedCount: selected.length, itemResults, inquiries: Object.freeze([...selected]),
    supplierSent: false, purchaseOrderCreated: false, productionDataWritten: false })
}

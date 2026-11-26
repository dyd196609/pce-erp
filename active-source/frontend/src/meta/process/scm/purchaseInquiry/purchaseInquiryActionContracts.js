import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { PURCHASE_INQUIRY_NODE_CODE } from './purchaseInquiryNodeRuntimeContract.js'

const base = {
  nodeCode: PURCHASE_INQUIRY_NODE_CODE,
  objectType: 'PurchaseInquiry',
  stateModel: 'PURCHASE_INQUIRY_RUNTIME_STATE',
}

export const PURCHASE_INQUIRY_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'START_PURCHASE_INQUIRY',
    actionName: '启动询价',
    buttonCode: 'start-purchase-inquiry',
    allowedFromStates: ['preparation_ready'],
    resultState: 'inquiry_draft',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'EDIT_PURCHASE_INQUIRY',
    actionName: '编辑询价',
    buttonCode: 'edit-purchase-inquiry',
    allowedFromStates: ['inquiry_draft'],
    resultState: 'inquiry_editing',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'SAVE_PURCHASE_INQUIRY',
    actionName: '保存询价',
    buttonCode: 'save-purchase-inquiry',
    allowedFromStates: ['inquiry_editing'],
    resultState: 'inquiry_draft',
  }),
])

export const PURCHASE_INQUIRY_ACTION_BY_CODE = Object.freeze(Object.fromEntries(
  PURCHASE_INQUIRY_ACTION_CONTRACTS.map(contract => [contract.actionCode, contract]),
))

export const PURCHASE_INQUIRY_UI_ACTION_CODES = Object.freeze({
  startInquiry: 'START_PURCHASE_INQUIRY',
  editInquiry: 'EDIT_PURCHASE_INQUIRY',
  saveInquiry: 'SAVE_PURCHASE_INQUIRY',
})

export function resolvePurchaseInquiryActionContract(uiAction) {
  const actionCode = PURCHASE_INQUIRY_UI_ACTION_CODES[uiAction]
  return actionCode ? PURCHASE_INQUIRY_ACTION_BY_CODE[actionCode] : null
}


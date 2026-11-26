import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { PURCHASE_REQUEST_NODE_CODE } from './purchaseRequestNodeRuntimeContract.js'

const base = {
  nodeCode: PURCHASE_REQUEST_NODE_CODE,
  objectType: 'PurchaseRequest',
  stateModel: 'PURCHASE_REQUEST_RUNTIME_STATE',
}

export const PURCHASE_REQUEST_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'SAVE_PURCHASE_REQUEST',
    actionName: '保存',
    buttonCode: 'save-purchase-request',
    allowedFromStates: ['new'],
    resultState: 'draft',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'SUBMIT_PURCHASE_REQUEST',
    actionName: '提交审批',
    buttonCode: 'submit-purchase-request',
    allowedFromStates: ['draft'],
    resultState: 'pending_approval',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'APPROVE_PURCHASE_REQUEST',
    actionName: '审批通过',
    buttonCode: 'approve-purchase-request',
    allowedFromStates: ['pending_approval'],
    resultState: 'approved',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'GENERATE_INQUIRY_PREPARATION',
    actionName: '生成询价准备',
    buttonCode: 'generate-inquiry-preparation',
    allowedFromStates: ['approved'],
    resultState: 'inquiry_prepared',
    handoffCode: 'PURCHASE_REQUEST_TO_INQUIRY_PREPARATION',
  }),
])

export const PURCHASE_REQUEST_ACTION_BY_CODE = Object.freeze(Object.fromEntries(
  PURCHASE_REQUEST_ACTION_CONTRACTS.map(contract => [contract.actionCode, contract]),
))

export const PURCHASE_REQUEST_UI_ACTION_CODES = Object.freeze({
  save: 'SAVE_PURCHASE_REQUEST',
  submit: 'SUBMIT_PURCHASE_REQUEST',
  approve: 'APPROVE_PURCHASE_REQUEST',
  convert: 'GENERATE_INQUIRY_PREPARATION',
})

// Business-facing codes remain stable while the V1.14.2.8.9 runtime codes are preserved for regression.
export const PURCHASE_REQUEST_GOVERNED_ACTION_CODES = Object.freeze({
  SUBMIT_APPROVAL: 'SUBMIT_PURCHASE_REQUEST',
  APPROVE: 'APPROVE_PURCHASE_REQUEST',
  CREATE_INQUIRY_PREPARATION: 'GENERATE_INQUIRY_PREPARATION',
})
export const PURCHASE_REQUEST_BUTTON_ACTION_CODES = Object.freeze({
  submit: 'SUBMIT_APPROVAL',
  approve: 'APPROVE',
  convert: 'CREATE_INQUIRY_PREPARATION',
})

export function resolvePurchaseRequestGovernedActionContract(businessActionCode) {
  return PURCHASE_REQUEST_ACTION_BY_CODE[PURCHASE_REQUEST_GOVERNED_ACTION_CODES[businessActionCode]] || null
}

export function resolvePurchaseRequestActionContract(uiAction) {
  const actionCode = PURCHASE_REQUEST_UI_ACTION_CODES[uiAction]
  return actionCode ? PURCHASE_REQUEST_ACTION_BY_CODE[actionCode] : null
}

import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { PURCHASE_ORDER_TRANSACTION_NODE_CODE } from './purchaseOrderTransactionNodeRuntimeContract.js'

const base = {
  nodeCode: PURCHASE_ORDER_TRANSACTION_NODE_CODE,
  objectType: 'PurchaseOrderTransaction',
  stateModel: 'PURCHASE_ORDER_TRANSACTION_STATE',
}

export const PURCHASE_ORDER_TRANSACTION_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'CREATE_PURCHASE_ORDER_TRANSACTION_CONTEXT', actionName: 'Create Purchase Order Transaction Context',
    buttonCode: 'create-purchase-order-transaction-context', allowedFromStates: ['purchase_order_gate_eligible'],
    resultState: 'transaction_context_created' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'CREATE_PURCHASE_ORDER_TRANSACTION', actionName: 'Create Purchase Order Transaction Draft',
    buttonCode: 'create-purchase-order-transaction', allowedFromStates: ['transaction_context_created'],
    resultState: 'draft' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'SAVE_PURCHASE_ORDER_TRANSACTION', actionName: 'Save Purchase Order Transaction',
    buttonCode: 'save-purchase-order-transaction', allowedFromStates: ['draft'],
    resultState: 'pending_issue' }),
])

export const PURCHASE_ORDER_TRANSACTION_UI_ACTION_CODES = Object.freeze({
  createContext: 'CREATE_PURCHASE_ORDER_TRANSACTION_CONTEXT',
  createTransaction: 'CREATE_PURCHASE_ORDER_TRANSACTION',
  saveTransaction: 'SAVE_PURCHASE_ORDER_TRANSACTION',
})

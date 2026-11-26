import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { SUPPLIER_QUOTE_NODE_CODE } from './supplierQuoteNodeRuntimeContract.js'

const base = { nodeCode: SUPPLIER_QUOTE_NODE_CODE, objectType: 'SupplierQuote', stateModel: 'SUPPLIER_QUOTE_RUNTIME_STATE' }

export const SUPPLIER_QUOTE_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({ ...base, actionCode: 'CREATE_SUPPLIER_QUOTE_CONTEXT', actionName: '创建报价上下文',
    buttonCode: 'create-supplier-quote-context', allowedFromStates: ['purchase_inquiry_ready'], resultState: 'quote_context_created' }),
  createProcessActionRuntimeContract({ ...base, actionCode: 'RECEIVE_SUPPLIER_QUOTE', actionName: '接收供应商报价',
    buttonCode: 'receive-supplier-quote', allowedFromStates: ['waiting_supplier_quote'], resultState: 'quotation_received' }),
  createProcessActionRuntimeContract({ ...base, actionCode: 'SAVE_SUPPLIER_QUOTE', actionName: '保存供应商报价',
    buttonCode: 'save-supplier-quote', allowedFromStates: ['quotation_received'], resultState: 'quotation_completed' }),
])

export const SUPPLIER_QUOTE_UI_ACTION_CODES = Object.freeze({
  createContext: 'CREATE_SUPPLIER_QUOTE_CONTEXT',
  receiveQuote: 'RECEIVE_SUPPLIER_QUOTE',
  saveQuote: 'SAVE_SUPPLIER_QUOTE',
})


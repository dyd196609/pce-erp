import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const SUPPLIER_QUOTE_NODE_CODE = 'SCM_SUPPLIER_QUOTE'
export const PURCHASE_INQUIRY_HANDOFF_SOURCE_NODE_CODE = 'SCM_PURCHASE_INQUIRY_HANDOFF'

export const SUPPLIER_QUOTE_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: SUPPLIER_QUOTE_NODE_CODE,
  nodeName: '供应商报价',
  inputObject: 'SupplierQuoteContext',
  outputObject: 'SupplierQuote',
  actions: ['CREATE_SUPPLIER_QUOTE_CONTEXT', 'RECEIVE_SUPPLIER_QUOTE', 'SAVE_SUPPLIER_QUOTE'],
  stateModel: 'SUPPLIER_QUOTE_RUNTIME_STATE',
  nextNode: null,
})

export const PURCHASE_INQUIRY_HANDOFF_SOURCE = Object.freeze({
  nodeCode: PURCHASE_INQUIRY_HANDOFF_SOURCE_NODE_CODE,
  nodeName: '采购询价交付',
  inputObject: 'InquiryPreparationBatch',
  outputObject: 'PurchaseInquiry',
  nextNode: SUPPLIER_QUOTE_NODE_CODE,
  handoffActionOwner: 'target',
})


import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const PURCHASE_ORDER_TRANSACTION_NODE_CODE = 'SCM_PURCHASE_ORDER_TRANSACTION'
export const PURCHASE_ORDER_GATE_HANDOFF_SOURCE_NODE_CODE = 'SCM_PURCHASE_ORDER_GATE_HANDOFF'

export const PURCHASE_ORDER_TRANSACTION_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: PURCHASE_ORDER_TRANSACTION_NODE_CODE,
  nodeName: 'Purchase Order Transaction',
  inputObject: 'PurchaseOrderTransactionContext',
  outputObject: 'PurchaseOrderTransaction',
  actions: [
    'CREATE_PURCHASE_ORDER_TRANSACTION_CONTEXT',
    'CREATE_PURCHASE_ORDER_TRANSACTION',
    'SAVE_PURCHASE_ORDER_TRANSACTION',
  ],
  stateModel: 'PURCHASE_ORDER_TRANSACTION_STATE',
  nextNode: null,
})

export const PURCHASE_ORDER_GATE_HANDOFF_SOURCE = Object.freeze({
  nodeCode: PURCHASE_ORDER_GATE_HANDOFF_SOURCE_NODE_CODE,
  nodeName: 'Purchase Order Creation Gate Handoff',
  inputObject: 'PurchaseOrderCreationGateContext',
  outputObject: 'PurchaseOrderCreationGateDecision',
  nextNode: PURCHASE_ORDER_TRANSACTION_NODE_CODE,
  handoffActionOwner: 'target',
})

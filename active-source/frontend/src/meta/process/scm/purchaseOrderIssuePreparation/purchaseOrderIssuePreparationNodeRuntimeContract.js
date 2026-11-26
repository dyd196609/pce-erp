import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE = 'SCM_PURCHASE_ORDER_ISSUE_PREPARATION'
export const PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE_NODE_CODE = 'SCM_PURCHASE_ORDER_TRANSACTION_HANDOFF'

export const PURCHASE_ORDER_ISSUE_PREPARATION_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
  nodeName: 'Purchase Order Issue Preparation',
  inputObject: 'PurchaseOrderIssuePreparationContext',
  outputObject: 'PurchaseOrderIssuePreparation',
  actions: ['CREATE_ISSUE_PREPARATION_CONTEXT', 'CHECK_ISSUE_REQUIREMENTS', 'SAVE_ISSUE_PREPARATION'],
  stateModel: 'PURCHASE_ORDER_ISSUE_PREPARATION_STATE',
  nextNode: null,
})

export const PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE = Object.freeze({
  nodeCode: PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE_NODE_CODE,
  nodeName: 'Purchase Order Transaction Handoff',
  inputObject: 'PurchaseOrderTransactionContext',
  outputObject: 'PurchaseOrderTransaction',
  nextNode: PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
  handoffActionOwner: 'target',
})

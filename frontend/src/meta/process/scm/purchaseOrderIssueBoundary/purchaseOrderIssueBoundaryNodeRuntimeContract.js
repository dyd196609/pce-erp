import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE = 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY'
export const ISSUE_PREPARATION_HANDOFF_SOURCE_NODE_CODE = 'SCM_PURCHASE_ORDER_ISSUE_PREPARATION_HANDOFF'

export const PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
  nodeName: 'Purchase Order Issue Boundary',
  inputObject: 'PurchaseOrderIssueBoundaryContext',
  outputObject: 'PurchaseOrderIssueDecision',
  actions: ['CREATE_ISSUE_BOUNDARY_CONTEXT', 'EVALUATE_ISSUE_PERMISSION', 'SAVE_ISSUE_DECISION'],
  stateModel: 'PURCHASE_ORDER_ISSUE_BOUNDARY_STATE',
  nextNode: null,
})

export const ISSUE_PREPARATION_HANDOFF_SOURCE = Object.freeze({
  nodeCode: ISSUE_PREPARATION_HANDOFF_SOURCE_NODE_CODE,
  nodeName: 'Purchase Order Issue Preparation Handoff',
  inputObject: 'PurchaseOrderIssuePreparationContext',
  outputObject: 'PurchaseOrderIssuePreparation',
  nextNode: PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
  handoffActionOwner: 'target',
})

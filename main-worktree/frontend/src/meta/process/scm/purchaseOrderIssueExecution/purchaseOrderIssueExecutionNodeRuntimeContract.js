import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE = 'SCM_PURCHASE_ORDER_ISSUE_EXECUTION'
export const ISSUE_BOUNDARY_HANDOFF_SOURCE_NODE_CODE = 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_HANDOFF'

export const PURCHASE_ORDER_ISSUE_EXECUTION_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
  nodeName: 'Purchase Order Issue Execution Authorization',
  inputObject: 'PurchaseOrderIssueExecutionContext',
  outputObject: 'PurchaseOrderIssueAuthorization',
  actions: ['CREATE_ISSUE_EXECUTION_CONTEXT', 'CHECK_EXECUTION_AUTHORIZATION', 'SAVE_EXECUTION_PREPARATION'],
  stateModel: 'PURCHASE_ORDER_ISSUE_EXECUTION_STATE',
  nextNode: null,
})

export const ISSUE_BOUNDARY_HANDOFF_SOURCE = Object.freeze({
  nodeCode: ISSUE_BOUNDARY_HANDOFF_SOURCE_NODE_CODE,
  nodeName: 'Purchase Order Issue Boundary Handoff',
  inputObject: 'PurchaseOrderIssueBoundaryContext',
  outputObject: 'PurchaseOrderIssueDecision',
  nextNode: PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
  handoffActionOwner: 'target',
})

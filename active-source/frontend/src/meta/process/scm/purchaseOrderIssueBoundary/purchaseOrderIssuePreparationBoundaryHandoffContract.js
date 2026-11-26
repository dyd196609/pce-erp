import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  ISSUE_PREPARATION_HANDOFF_SOURCE_NODE_CODE,
  PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
} from './purchaseOrderIssueBoundaryNodeRuntimeContract.js'

export const ISSUE_PREPARATION_BOUNDARY_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'PURCHASE_ORDER_ISSUE_PREPARATION_TO_ISSUE_BOUNDARY_CONTEXT',
  fromNode: ISSUE_PREPARATION_HANDOFF_SOURCE_NODE_CODE,
  toNode: PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
  outputObject: 'PurchaseOrderIssuePreparation', inputObject: 'PurchaseOrderIssueBoundaryContext',
  mappingCode: 'MAP_ISSUE_PREPARATION_TO_ISSUE_BOUNDARY_CONTEXT',
  actionCode: 'CREATE_ISSUE_BOUNDARY_CONTEXT',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validateIssuePreparationBoundaryHandoff(preparation = {}, context = {}) {
  const valid = preparation.objectType === 'PurchaseOrderIssuePreparation'
    && ['ready_for_issue', 'blocked'].includes(preparation.status)
    && context.objectType === 'PurchaseOrderIssueBoundaryContext'
    && context.preparationNo === preparation.preparationNo
    && context.supplier?.supplierId === preparation.supplier?.supplierId
    && context.orderInformation?.transactionNo === preparation.transactionNo
    && context.preparationResult?.status === preparation.status
    && context.sourceChain?.transactionNo === preparation.transactionNo
    && context.evidence?.checks?.length === preparation.checks?.length
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL', valid,
    transferredFields: Object.freeze(['supplier', 'orderInformation', 'preparationResult', 'sourceChain', 'evidence']),
    mappingCode: ISSUE_PREPARATION_BOUNDARY_HANDOFF_CONTRACT.mappingCode,
  })
}

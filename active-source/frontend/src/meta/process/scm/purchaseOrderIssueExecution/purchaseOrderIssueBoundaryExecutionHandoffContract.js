import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  ISSUE_BOUNDARY_HANDOFF_SOURCE_NODE_CODE,
  PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
} from './purchaseOrderIssueExecutionNodeRuntimeContract.js'

export const ISSUE_BOUNDARY_EXECUTION_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'PURCHASE_ORDER_ISSUE_BOUNDARY_TO_EXECUTION_CONTEXT',
  fromNode: ISSUE_BOUNDARY_HANDOFF_SOURCE_NODE_CODE,
  toNode: PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
  outputObject: 'PurchaseOrderIssueDecision', inputObject: 'PurchaseOrderIssueExecutionContext',
  mappingCode: 'MAP_ISSUE_BOUNDARY_TO_EXECUTION_CONTEXT',
  actionCode: 'CREATE_ISSUE_EXECUTION_CONTEXT',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validateIssueBoundaryExecutionHandoff(issueDecision = {}, context = {}) {
  const valid = issueDecision.objectType === 'PurchaseOrderIssueDecision'
    && ['allowed', 'blocked'].includes(issueDecision.status)
    && context.objectType === 'PurchaseOrderIssueExecutionContext'
    && context.issueDecisionNo === issueDecision.issueDecisionNo
    && context.orderInformation?.transactionNo === issueDecision.orderInformation?.transactionNo
    && context.supplierInformation?.supplierId === issueDecision.supplier?.supplierId
    && context.authorizationEvidence?.checks?.length === issueDecision.checks?.length
    && context.sourceChain?.transactionNo === issueDecision.sourceChain?.transactionNo
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL', valid,
    transferredFields: Object.freeze(['orderInformation', 'supplierInformation', 'authorizationEvidence', 'sourceChain']),
    mappingCode: ISSUE_BOUNDARY_EXECUTION_HANDOFF_CONTRACT.mappingCode,
  })
}

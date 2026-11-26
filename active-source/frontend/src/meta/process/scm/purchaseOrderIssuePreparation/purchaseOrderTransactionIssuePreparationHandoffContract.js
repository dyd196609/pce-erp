import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
  PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE_NODE_CODE,
} from './purchaseOrderIssuePreparationNodeRuntimeContract.js'

export const PURCHASE_ORDER_TRANSACTION_ISSUE_PREPARATION_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'PURCHASE_ORDER_TRANSACTION_TO_ISSUE_PREPARATION_CONTEXT',
  fromNode: PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE_NODE_CODE,
  toNode: PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
  outputObject: 'PurchaseOrderTransaction', inputObject: 'PurchaseOrderIssuePreparationContext',
  mappingCode: 'MAP_PURCHASE_ORDER_TRANSACTION_TO_ISSUE_PREPARATION_CONTEXT',
  actionCode: 'CREATE_ISSUE_PREPARATION_CONTEXT',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validatePurchaseOrderTransactionIssuePreparationHandoff(transaction = {}, context = {}) {
  const valid = transaction.objectType === 'PurchaseOrderTransaction' && transaction.status === 'draft'
    && context.objectType === 'PurchaseOrderIssuePreparationContext'
    && context.transactionNo === transaction.transactionNo
    && context.supplier?.supplierId === transaction.supplier?.supplierId
    && context.orderDetails.length === transaction.purchaseDetails?.length
    && context.orderDetails.every(item => item.materialCode && item.quantity > 0)
    && context.totalQuantity === transaction.totalQuantity
    && context.amountReference?.totalAmount === transaction.amountReference?.totalAmount
    && context.deliveryRequirements.length === transaction.purchaseDetails?.length
    && context.deliveryRequirements.every(item => item.deliveryDate && item.validUntil)
    && context.sourceChain?.transactionNo === transaction.transactionNo
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL', valid,
    transferredFields: Object.freeze([
      'supplier', 'orderDetails', 'quantity', 'amountReference', 'deliveryRequirements', 'sourceChain',
    ]),
    mappingCode: PURCHASE_ORDER_TRANSACTION_ISSUE_PREPARATION_HANDOFF_CONTRACT.mappingCode,
  })
}

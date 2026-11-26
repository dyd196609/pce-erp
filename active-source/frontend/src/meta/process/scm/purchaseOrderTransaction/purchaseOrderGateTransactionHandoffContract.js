import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  PURCHASE_ORDER_GATE_HANDOFF_SOURCE_NODE_CODE,
  PURCHASE_ORDER_TRANSACTION_NODE_CODE,
} from './purchaseOrderTransactionNodeRuntimeContract.js'

export const PURCHASE_ORDER_GATE_TRANSACTION_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'PURCHASE_ORDER_GATE_TO_PURCHASE_ORDER_TRANSACTION_CONTEXT',
  fromNode: PURCHASE_ORDER_GATE_HANDOFF_SOURCE_NODE_CODE,
  toNode: PURCHASE_ORDER_TRANSACTION_NODE_CODE,
  outputObject: 'PurchaseOrderCreationGateDecision',
  inputObject: 'PurchaseOrderTransactionContext',
  mappingCode: 'MAP_PURCHASE_ORDER_GATE_TO_TRANSACTION_CONTEXT',
  actionCode: 'CREATE_PURCHASE_ORDER_TRANSACTION_CONTEXT',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validatePurchaseOrderGateTransactionHandoff(gateDecision = {}, context = {}) {
  const valid = gateDecision.objectType === 'PurchaseOrderCreationGateDecision'
    && gateDecision.status === 'eligible' && gateDecision.eligible === true
    && context.objectType === 'PurchaseOrderTransactionContext'
    && context.gateDecisionNo === gateDecision.gateDecisionNo
    && context.supplier?.supplierId === gateDecision.recommendedSupplier?.supplierId
    && context.purchaseDetails.length === gateDecision.purchaseDetails?.length
    && context.purchaseDetails.every(item => item.materialCode && item.quantity > 0)
    && context.totalQuantity === gateDecision.totalQuantity
    && context.amountReference?.totalAmount === gateDecision.costReference?.totalCost
    && context.sourceChain?.gateDecisionNo === gateDecision.gateDecisionNo
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL', valid,
    transferredFields: Object.freeze(['supplier', 'purchaseDetails', 'quantity', 'amountReference', 'sourceChain']),
    mappingCode: PURCHASE_ORDER_GATE_TRANSACTION_HANDOFF_CONTRACT.mappingCode,
  })
}

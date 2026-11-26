export const SCM_TRACE_DIAGNOSTIC_VERSION = 'V1.14.2.8.4.11'

export const SCM_TRACE_DIAGNOSTIC_FIELDS = Object.freeze([
  'nodeCode',
  'nodeName',
  'sourceNode',
  'targetNode',
  'sourceObjectType',
  'sourceObjectId',
  'targetObjectType',
  'targetObjectId',
  'sourceStatus',
  'targetStatus',
  'quantity',
  'amount',
  'diagnosticResult',
  'blockingReason',
])

export const SCM_TRACE_OBJECT_TYPES = Object.freeze([
  'PurchaseRequest',
  'PurchaseInquiry',
  'PriceApproval',
  'PurchaseOrder',
  'Receipt',
  'IncomingInspection',
  'WarehouseReceipt',
  'SupplierReconciliation',
  'SupplierReconciliationDifference',
  'SupplierReconciliationConfirmation',
  'SupplierPayableConfirmation',
  'SupplierPaymentRequest',
  'SupplierPaymentStatus',
  'SupplierSettlementCompletion',
  'SupplierPerformance',
  'BuyerPerformance',
])

export const SCM_TRACE_RELATIONSHIP_FIELDS = Object.freeze([
  ['PurchaseRequest', 'PurchaseInquiry', 'id', 'requestId'],
  ['PurchaseInquiry', 'PriceApproval', 'id', 'inquiryId'],
  ['PriceApproval', 'PurchaseOrder', 'id', 'sourceId'],
  ['PurchaseOrder', 'Receipt', 'id', 'sourcePurchaseOrderId'],
  ['Receipt', 'IncomingInspection', 'id', 'sourceReceiveId'],
  ['IncomingInspection', 'WarehouseReceipt', 'id', 'sourceInspectionId'],
  ['WarehouseReceipt', 'SupplierReconciliation', 'id', 'warehouseReceiptIds'],
  ['SupplierReconciliation', 'SupplierReconciliationDifference', 'reconciliationNo', 'reconciliationNo'],
  ['SupplierReconciliationDifference', 'SupplierReconciliationConfirmation', 'differenceNo', 'differenceNo'],
  ['SupplierReconciliationConfirmation', 'SupplierPayableConfirmation', 'reconciliationNo', 'reconciliationNo'],
  ['SupplierPayableConfirmation', 'SupplierPaymentRequest', 'payableConfirmationNo', 'payableConfirmationNo'],
  ['SupplierPaymentRequest', 'SupplierPaymentStatus', 'paymentRequestNo', 'paymentRequestNo'],
  ['SupplierPaymentStatus', 'SupplierSettlementCompletion', 'paymentRequestNo', 'paymentRequestNo'],
  ['SupplierSettlementCompletion', 'SupplierPerformance', 'settlementNo', 'sourceSettlementCompletionNos'],
  ['SupplierSettlementCompletion', 'BuyerPerformance', 'settlementNo', 'sourceSettlementCompletionNos'],
].map((item) => Object.freeze(item)))

export const SCM_TRACE_STATE_MATRIX = Object.freeze({
  'purchase-request->request-for-quotation': Object.freeze({ source: ['approved', 'converted'], target: ['draft', 'submitted', 'approved', 'sent', 'quoted', 'converted'] }),
  'request-for-quotation->price-verification': Object.freeze({ source: ['approved', 'sent', 'quoted', 'converted'], target: ['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'converted'] }),
  'price-verification->purchase-order': Object.freeze({ source: ['approved', 'converted'], target: ['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'issued', 'released', 'ordered'] }),
  'purchase-order->goods-receipt': Object.freeze({ source: ['approved', 'issued', 'released', 'ordered', 'partiallyReceived', 'receiving', 'received', 'fullyReceived'], target: ['pending', 'receiving', 'received'] }),
  'goods-receipt->quality-inspection': Object.freeze({ source: ['received', 'completed'], target: ['pending', 'inspecting', 'inspected', 'inboundPrepared', 'rejected'] }),
  'quality-inspection->warehouse-receipt': Object.freeze({ source: ['inboundPrepared'], target: ['pending', 'done'] }),
  'warehouse-receipt->supplier-reconciliation': Object.freeze({ source: ['done'], target: ['draft', 'internal_review', 'supplier_confirming', 'completed'] }),
  'supplier-reconciliation->reconciliation-difference': Object.freeze({ source: ['internal_review', 'supplier_confirming', 'completed'], target: ['open', 'analyzing', 'resolved'] }),
  'reconciliation-difference->supplier-confirmation': Object.freeze({ source: ['analyzing', 'resolved'], target: ['pending', 'supplier_confirming', 'confirmed', 'rejected'] }),
  'supplier-confirmation->supplier-payable-confirmation': Object.freeze({ source: ['confirmed'], target: ['draft', 'confirmed'] }),
  'supplier-payable-confirmation->supplier-payment-request': Object.freeze({ source: ['confirmed'], target: ['draft', 'submitted', 'approved', 'returned'] }),
  'supplier-payment-request->payment-status-record': Object.freeze({ source: ['approved'], target: ['recorded', 'completed'] }),
  'payment-status-record->supplier-settlement-completion': Object.freeze({ source: ['recorded', 'completed'], target: ['completed'] }),
  'supplier-settlement-completion->supplier-performance': Object.freeze({ source: ['completed'], target: ['calculated', 'published'] }),
  'supplier-performance->buyer-performance': Object.freeze({ source: ['calculated', 'published'], target: ['calculated', 'published'] }),
})

export function createScmTraceDiagnostic(input = {}) {
  const diagnostic = {}
  SCM_TRACE_DIAGNOSTIC_FIELDS.forEach((field) => {
    diagnostic[field] = input[field] ?? (field === 'quantity' || field === 'amount' ? null : '')
  })
  return Object.freeze(diagnostic)
}

export function createScmTraceRelationshipDiagnostics(nodes = []) {
  return nodes.slice(0, -1).map((node, index) => {
    const target = nodes[index + 1]
    const relationship = SCM_TRACE_RELATIONSHIP_FIELDS[index] || []
    return createScmTraceDiagnostic({
      nodeCode: node.nodeCode,
      nodeName: node.nodeName,
      sourceNode: node.nodeCode,
      targetNode: target.nodeCode,
      sourceObjectType: relationship[0] || '',
      sourceObjectId: relationship[2] || '',
      targetObjectType: relationship[1] || '',
      targetObjectId: relationship[3] || '',
      diagnosticResult: relationship.length ? 'ANALYZABLE' : 'FAIL',
      blockingReason: relationship.length ? '' : '节点对象关系字段未登记。',
    })
  })
}

export function getScmTraceStateRule(sourceNode, targetNode) {
  return SCM_TRACE_STATE_MATRIX[`${sourceNode}->${targetNode}`] || null
}

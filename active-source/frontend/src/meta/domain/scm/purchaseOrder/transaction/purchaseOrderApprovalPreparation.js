export const PURCHASE_ORDER_APPROVAL_PREPARATION_VERSION = 'V1.14.2.8.5.7'
export const PURCHASE_ORDER_APPROVAL_PREPARATION_CODE = 'SCM_PURCHASE_ORDER_APPROVAL_PREPARATION'

export const PURCHASE_ORDER_APPROVAL_PREPARATION = Object.freeze({
  objectCode: PURCHASE_ORDER_APPROVAL_PREPARATION_CODE,
  objectName: '采购订单审批准备',
  businessObject: 'PurchaseOrderApprovalPreparation',
  fields: Object.freeze([
    Object.freeze({ name: 'creationRequestId', type: 'object_reference', required: true }),
    Object.freeze({ name: 'transactionBoundaryId', type: 'object_reference', required: true }),
    Object.freeze({ name: 'preparationStatus', type: 'status', required: true }),
    Object.freeze({ name: 'evidenceReferences', type: 'array_reference', required: true }),
    Object.freeze({ name: 'blockingReasons', type: 'array', required: true }),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  submitsApproval: false,
  approvalExecutionAllowed: false,
  createsPurchaseOrder: false,
})

export function buildPurchaseOrderApprovalPreparation(input = {}) {
  const ready = input.transactionAllowed === true && input.requestStatus === 'ready_for_approval' && Array.isArray(input.evidenceReferences) && input.evidenceReferences.length > 0
  return Object.freeze({
    preparationCode: PURCHASE_ORDER_APPROVAL_PREPARATION_CODE,
    preparationStatus: ready ? 'READY' : 'BLOCKED',
    evidenceReferences: Object.freeze(Array.isArray(input.evidenceReferences) ? [...input.evidenceReferences] : []),
    blockingReasons: Object.freeze([
      ...(input.transactionAllowed === true ? [] : ['transaction_not_allowed']),
      ...(input.requestStatus === 'ready_for_approval' ? [] : ['creation_request_not_ready']),
      ...(Array.isArray(input.evidenceReferences) && input.evidenceReferences.length > 0 ? [] : ['approval_evidence_missing']),
    ]),
    submitsApproval: false,
    createsPurchaseOrder: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

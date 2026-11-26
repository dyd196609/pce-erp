export const PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY_VERSION = 'V1.14.2.8.5.8'
export const PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY_CODE = 'SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY'

export const PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY = Object.freeze({
  objectCode: PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY_CODE,
  objectName: 'Purchase Order Approval Interface Boundary',
  businessObject: 'PurchaseOrderApprovalInterfaceBoundary',
  inputObjects: Object.freeze(['PurchaseOrderApprovalPreparation', 'PurchaseOrderApprovalContext']),
  outputMode: 'read_only_contract',
  workflowIntegrationAllowed: false,
  createsApprovalInstance: false,
  createsWorkflowInstance: false,
  submitsApproval: false,
  approvalDecisionAllowed: false,
  persistenceMode: 'definition_only',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function evaluatePurchaseOrderApprovalInterfaceBoundary({ preparation, context } = {}) {
  const blockingReasons = Object.freeze([
    ...(preparation?.approvalPreparationReady === true ? [] : ['approval_preparation_not_ready']),
    ...(context?.contextStatus === 'ready' ? [] : ['approval_context_not_ready']),
  ])
  return Object.freeze({
    boundaryStatus: blockingReasons.length ? 'blocked' : 'ready',
    interfaceReady: blockingReasons.length === 0,
    blockingReasons,
    outputMode: 'read_only_contract',
    createsApprovalInstance: false,
    createsWorkflowInstance: false,
    submitsApproval: false,
    approvalDecisionAllowed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

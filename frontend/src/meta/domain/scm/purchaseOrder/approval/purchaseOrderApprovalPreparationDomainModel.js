export const PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_VERSION = 'V1.14.2.8.5.8'
export const PURCHASE_ORDER_APPROVAL_PREPARATION_OBJECT_CODE = 'SCM_PURCHASE_ORDER_APPROVAL_PREPARATION'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL = Object.freeze({
  objectCode: PURCHASE_ORDER_APPROVAL_PREPARATION_OBJECT_CODE,
  objectName: 'Purchase Order Approval Preparation',
  businessObject: 'PurchaseOrderApprovalPreparation',
  fields: Object.freeze([
    field('purchaseOrderDomainId', 'object_reference'),
    field('creationRequestId', 'object_reference'),
    field('transactionBoundaryId', 'object_reference'),
    field('supplierReference', 'object_reference'),
    field('amountReference', 'fact_reference'),
    field('deliveryRequirement', 'fact_reference'),
    field('evidenceReferences', 'array_reference'),
    field('riskSummary', 'fact_snapshot'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  submitsApproval: false,
  createsWorkflowInstance: false,
  createsPurchaseOrder: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validatePurchaseOrderApprovalPreparationDomainModel(model = PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL) {
  const requiredFields = ['purchaseOrderDomainId', 'creationRequestId', 'transactionBoundaryId', 'supplierReference', 'amountReference', 'deliveryRequirement', 'evidenceReferences', 'riskSummary']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  for (const flag of ['createdAutomatically', 'submitsApproval', 'createsWorkflowInstance']) {
    if (model?.[flag] !== false) missing.push(flag)
  }
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}

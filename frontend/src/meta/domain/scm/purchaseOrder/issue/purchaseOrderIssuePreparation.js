export const PURCHASE_ORDER_ISSUE_PREPARATION_VERSION = 'V1.14.2.8.5.10'
export const PURCHASE_ORDER_ISSUE_PREPARATION_CODE = 'SCM_PURCHASE_ORDER_ISSUE_PREPARATION'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const PURCHASE_ORDER_ISSUE_PREPARATION = Object.freeze({
  objectCode: PURCHASE_ORDER_ISSUE_PREPARATION_CODE,
  objectName: 'Purchase Order Issue Preparation',
  businessObject: 'PurchaseOrderIssuePreparation',
  fields: Object.freeze([
    field('purchaseOrderTransactionId', 'object_reference'),
    field('supplierReleaseContextId', 'object_reference'),
    field('approvalReference', 'object_reference'),
    field('evidenceReferences', 'array_reference'),
    field('preparationStatus', 'status'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  executesIssue: false,
  sendsSupplier: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function buildPurchaseOrderIssuePreparation(input = {}) {
  const requiredFields = ['purchaseOrderTransactionId', 'supplierReleaseContextId', 'approvalReference', 'evidenceReferences']
  const missingFields = Object.freeze(requiredFields.filter(name => {
    const value = input[name]
    return name === 'evidenceReferences' ? !Array.isArray(value) || value.length === 0 : value === undefined || value === null || value === ''
  }))
  return Object.freeze({
    preparationStatus: missingFields.length ? 'blocked' : 'ready',
    purchaseOrderTransactionId: input.purchaseOrderTransactionId || null,
    supplierReleaseContextId: input.supplierReleaseContextId || null,
    approvalReference: input.approvalReference || null,
    evidenceReferences: Object.freeze(Array.isArray(input.evidenceReferences) ? [...input.evidenceReferences] : []),
    missingFields,
    createdAutomatically: false,
    executesIssue: false,
    sendsSupplier: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export const PURCHASE_ORDER_ISSUE_BOUNDARY_VERSION = 'V1.14.2.8.5.10'
export const PURCHASE_ORDER_ISSUE_BOUNDARY_CODE = 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const PURCHASE_ORDER_ISSUE_BOUNDARY = Object.freeze({
  objectCode: PURCHASE_ORDER_ISSUE_BOUNDARY_CODE,
  objectName: 'Purchase Order Issue Boundary',
  businessObject: 'PurchaseOrderIssueBoundary',
  fields: Object.freeze([
    field('purchaseOrderTransactionId', 'object_reference'),
    field('approvalReference', 'object_reference'),
    field('supplierReference', 'object_reference'),
    field('issueStatus', 'status'),
    field('issueAllowed', 'boolean'),
    field('blockingReasons', 'array'),
    field('evidenceReferences', 'array_reference'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  executesIssue: false,
  sendsSupplier: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validatePurchaseOrderIssueBoundary(model = PURCHASE_ORDER_ISSUE_BOUNDARY) {
  const requiredFields = ['purchaseOrderTransactionId', 'approvalReference', 'supplierReference', 'issueStatus', 'issueAllowed', 'blockingReasons', 'evidenceReferences']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  for (const flag of ['createdAutomatically', 'executesIssue', 'sendsSupplier']) {
    if (model?.[flag] !== false) missing.push(flag)
  }
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}

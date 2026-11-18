export const PURCHASE_ORDER_APPROVAL_CONTEXT_VERSION = 'V1.14.2.8.5.8'
export const PURCHASE_ORDER_APPROVAL_CONTEXT_CODE = 'SCM_PURCHASE_ORDER_APPROVAL_CONTEXT'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const PURCHASE_ORDER_APPROVAL_CONTEXT = Object.freeze({
  objectCode: PURCHASE_ORDER_APPROVAL_CONTEXT_CODE,
  objectName: 'Purchase Order Approval Context',
  businessObject: 'PurchaseOrderApprovalContext',
  fields: Object.freeze([
    field('approvalPreparationId', 'object_reference'),
    field('approvalSubject', 'subject_snapshot'),
    field('sourceReference', 'object_reference'),
    field('businessEvidence', 'evidence_snapshot'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  createsApprovalInstance: false,
  createsWorkflowInstance: false,
  submitsApproval: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function buildPurchaseOrderApprovalContext(input = {}) {
  const requiredFields = PURCHASE_ORDER_APPROVAL_CONTEXT.fields.map(item => item.name)
  const missingFields = Object.freeze(requiredFields.filter(name => input[name] === undefined || input[name] === null || input[name] === ''))
  return Object.freeze({
    contextStatus: missingFields.length ? 'blocked' : 'ready',
    approvalPreparationId: input.approvalPreparationId || null,
    approvalSubject: input.approvalSubject ?? null,
    sourceReference: input.sourceReference ?? null,
    businessEvidence: input.businessEvidence ?? null,
    missingFields,
    createsApprovalInstance: false,
    createsWorkflowInstance: false,
    submitsApproval: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function validatePurchaseOrderApprovalContext(model = PURCHASE_ORDER_APPROVAL_CONTEXT) {
  const requiredFields = ['approvalPreparationId', 'approvalSubject', 'sourceReference', 'businessEvidence']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.createsApprovalInstance !== false) missing.push('createsApprovalInstance')
  if (model?.createsWorkflowInstance !== false) missing.push('createsWorkflowInstance')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}

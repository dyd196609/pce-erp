export const PURCHASE_ORDER_DOMAIN_MODEL_VERSION = 'V1.14.2.8.4.27.1'

const field = (name, type, required = true) => Object.freeze({ name, type, required })

export const PURCHASE_ORDER_DOMAIN_MODEL = Object.freeze({
  objectCode: 'SCM_PURCHASE_ORDER',
  objectName: '采购订单',
  businessObject: 'PurchaseOrder',
  fields: Object.freeze([
    field('sourceGateId', 'object_reference'),
    field('sourceRecommendationId', 'object_reference'),
    field('sourceInquiryId', 'object_reference'),
    field('sourcePriceApprovalId', 'object_reference'),
    field('supplierId', 'object_reference'),
    field('supplierName', 'string'),
    field('confirmedBy', 'string'),
    field('confirmedAt', 'datetime'),
    field('confirmationSource', 'string'),
    field('quoteEvidence', 'array'),
    field('priceEvidence', 'array'),
    field('qualificationEvidence', 'array'),
    field('status', 'status'),
    field('orderLines', 'array_relation'),
  ]),
  relationships: Object.freeze([
    'PURCHASE_ORDER_SOURCE_GATE_TO_DOMAIN',
    'PURCHASE_ORDER_SOURCE_RECOMMENDATION_TO_DOMAIN',
    'PURCHASE_ORDER_TO_LINE',
  ]),
  traceFields: Object.freeze([
    'sourceGateId', 'sourceRecommendationId', 'sourceInquiryId',
    'sourcePriceApprovalId', 'confirmationSource',
  ]),
  lifecycleDefinitionCode: 'SCM_PURCHASE_ORDER_LIFECYCLE_STATE',
  statusField: 'status',
  initialStatus: 'draft',
  creationActionCode: 'CREATE_PURCHASE_ORDER',
  actionRules: Object.freeze({
    ruleCode: 'SCM_PURCHASE_ORDER_GATE_CREATION_GUARD',
    mode: 'explicit_human_action_default_deny',
  }),
  persistenceMode: 'governed_runtime_business_fact',
  createdAutomatically: false,
  automaticCreation: false,
  createsBusinessTransaction: true,
  createsPurchaseOrder: true,
  automaticSubmit: false,
  automaticApprove: false,
  automaticIssue: false,
})

export function validatePurchaseOrderDomainModel(model = PURCHASE_ORDER_DOMAIN_MODEL) {
  const requiredFields = [
    'sourceGateId', 'sourceRecommendationId', 'sourceInquiryId',
    'sourcePriceApprovalId', 'supplierId', 'supplierName', 'confirmedBy',
    'confirmedAt', 'confirmationSource', 'quoteEvidence', 'priceEvidence',
    'qualificationEvidence', 'status', 'orderLines',
  ]
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.businessObject !== 'PurchaseOrder') missing.push('businessObject')
  if (model?.initialStatus !== 'draft') missing.push('initialStatus')
  if (model?.creationActionCode !== 'CREATE_PURCHASE_ORDER') missing.push('creationActionCode')
  if (model?.createdAutomatically !== false) missing.push('createdAutomatically')
  if (model?.automaticSubmit !== false) missing.push('automaticSubmit')
  if (model?.automaticApprove !== false) missing.push('automaticApprove')
  if (model?.automaticIssue !== false) missing.push('automaticIssue')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}

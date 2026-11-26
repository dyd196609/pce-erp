export const SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL_VERSION = 'V1.14.2.8.5.4'

const field = (name, type, required = true) => Object.freeze({ name, type, required })

export const SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL = Object.freeze({
  objectCode: 'SCM_SUPPLIER_RECOMMENDATION_DECISION',
  objectName: '供应商推荐决策',
  businessObject: 'SupplierRecommendationDecision',
  fields: Object.freeze([
    field('inquiryId', 'object_reference'),
    field('quoteComparisonId', 'object_reference'),
    field('recommendedSupplierId', 'object_reference'),
    field('recommendationStatus', 'status'),
    field('recommendationReason', 'string'),
    field('evidenceReferences', 'array_reference'),
    field('riskWarnings', 'array'),
    field('approvalRequired', 'boolean'),
  ]),
  relationships: Object.freeze([
    Object.freeze({ relationshipCode: 'QUOTE_COMPARISON_TO_RECOMMENDATION_DECISION', sourceObject: 'SCM_QUOTE_COMPARISON', targetObject: 'SCM_SUPPLIER_RECOMMENDATION_DECISION', relationshipType: 'business_reference', direction: 'forward' }),
    Object.freeze({ relationshipCode: 'RECOMMENDATION_DECISION_TO_PURCHASE_APPROVAL', sourceObject: 'SCM_SUPPLIER_RECOMMENDATION_DECISION', targetBoundary: 'PURCHASE_APPROVAL_PRECONDITION', relationshipType: 'evidence_reference', direction: 'forward' }),
  ]),
  traceFields: Object.freeze(['inquiryId', 'quoteComparisonId', 'recommendedSupplierId', 'evidenceReferences']),
  statusField: 'recommendationStatus',
  actionRules: Object.freeze({ ruleCode: 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ACTION_GUARD', mode: 'explicit_whitelist_default_deny' }),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  createsPurchaseOrder: false,
  triggersApproval: false,
})

export function validateSupplierRecommendationDecisionDomainModel(model = SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL) {
  const requiredFields = ['inquiryId', 'quoteComparisonId', 'recommendedSupplierId', 'recommendationStatus', 'recommendationReason', 'evidenceReferences', 'riskWarnings', 'approvalRequired']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.createdAutomatically !== false) missing.push('createdAutomatically')
  if (model?.createsPurchaseOrder !== false) missing.push('createsPurchaseOrder')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}

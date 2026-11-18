export const QUOTE_COMPARISON_DOMAIN_MODEL_VERSION = 'V1.14.2.8.5.3'

const field = (name, type, required = true) => Object.freeze({ name, type, required })

export const QUOTE_COMPARISON_DOMAIN_MODEL = Object.freeze({
  objectCode: 'SCM_QUOTE_COMPARISON',
  objectName: '报价比较',
  businessObject: 'QuoteComparison',
  purpose: 'quote_comparison_fact',
  fields: Object.freeze([
    field('comparisonNo', 'string'),
    field('inquiryNo', 'string'),
    field('quoteList', 'array_reference'),
    field('evaluationCriteria', 'array'),
    field('recommendedSupplier', 'object_reference'),
    field('comparisonReason', 'string'),
    field('status', 'status'),
    field('traceId', 'string'),
  ]),
  relationships: Object.freeze([
    'SUPPLIER_QUOTE_TO_COMPARISON',
    'COMPARISON_TO_PRICE_APPROVAL',
  ]),
  traceFields: Object.freeze(['sourceObject', 'targetObject', 'relationshipType', 'traceId', 'direction']),
  statusField: 'status',
  actionRules: Object.freeze({ ruleCode: 'SCM_QUOTE_COMPARISON_ACTION_GUARD', mode: 'explicit_whitelist_default_deny' }),
  persistenceMode: 'definition_only',
  automaticCreation: false,
  createsPurchaseOrder: false,
})

export function validateQuoteComparisonDomainModel(model = QUOTE_COMPARISON_DOMAIN_MODEL) {
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const requiredFields = ['comparisonNo', 'inquiryNo', 'quoteList', 'evaluationCriteria', 'recommendedSupplier', 'comparisonReason', 'status']
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.createsPurchaseOrder !== false) missing.push('createsPurchaseOrder')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}

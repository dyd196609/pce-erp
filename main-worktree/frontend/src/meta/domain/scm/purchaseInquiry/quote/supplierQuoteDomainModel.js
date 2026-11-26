export const SUPPLIER_QUOTE_DOMAIN_MODEL_VERSION = 'V1.14.2.8.5.3'

const field = (name, type, required = true) => Object.freeze({ name, type, required })

export const SUPPLIER_QUOTE_DOMAIN_MODEL = Object.freeze({
  objectCode: 'SCM_SUPPLIER_QUOTE',
  objectName: '供应商报价',
  businessObject: 'SupplierQuote',
  fields: Object.freeze([
    field('quoteNo', 'string'),
    field('inquiryNo', 'string'),
    field('supplierCode', 'string'),
    field('quoteDate', 'date'),
    field('currency', 'currency'),
    field('validUntil', 'date'),
    field('deliveryDays', 'number'),
    field('paymentTerms', 'string'),
    field('status', 'status'),
    field('lines', 'array_relation'),
    field('traceId', 'string'),
  ]),
  relationships: Object.freeze([
    'INQUIRY_TO_SUPPLIER_QUOTE',
    'SUPPLIER_QUOTE_TO_LINE',
    'SUPPLIER_QUOTE_TO_COMPARISON',
  ]),
  traceFields: Object.freeze(['sourceObject', 'targetObject', 'relationshipType', 'traceId', 'direction']),
  statusField: 'status',
  actionRules: Object.freeze({ ruleCode: 'SCM_SUPPLIER_QUOTE_ACTION_GUARD', mode: 'explicit_whitelist_default_deny' }),
  persistenceMode: 'definition_only',
  automaticCreation: false,
  createsPurchaseOrder: false,
})

export function validateSupplierQuoteDomainModel(model = SUPPLIER_QUOTE_DOMAIN_MODEL) {
  const required = ['objectCode', 'fields', 'relationships', 'traceFields', 'statusField', 'actionRules']
  const missing = required.filter(key => model?.[key] == null || (Array.isArray(model[key]) && model[key].length === 0))
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}

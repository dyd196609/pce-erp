export const SUPPLIER_QUOTE_LINE_DOMAIN_MODEL_VERSION = 'V1.14.2.8.5.3'

const field = (name, type, required = true) => Object.freeze({ name, type, required })

export const SUPPLIER_QUOTE_LINE_DOMAIN_MODEL = Object.freeze({
  objectCode: 'SCM_SUPPLIER_QUOTE_LINE',
  objectName: '供应商报价明细',
  businessObject: 'SupplierQuoteLine',
  fields: Object.freeze([
    field('quoteNo', 'string'),
    field('inquiryLineNo', 'string'),
    field('materialCode', 'string'),
    field('quantity', 'quantity'),
    field('unitPrice', 'money'),
    field('taxRate', 'percentage'),
    field('totalAmount', 'money'),
    field('deliveryDate', 'date'),
    field('status', 'status'),
    field('traceId', 'string'),
  ]),
  relationships: Object.freeze([
    Object.freeze({ relationshipCode: 'SUPPLIER_QUOTE_TO_LINE', parentObject: 'SCM_SUPPLIER_QUOTE', relationshipType: 'composition', cardinality: '1:N' }),
    Object.freeze({ relationshipCode: 'QUOTE_LINE_TO_INQUIRY_LINE', targetObject: 'SCM_PURCHASE_INQUIRY_LINE', relationshipType: 'business_reference', cardinality: 'N:1' }),
  ]),
  traceFields: Object.freeze(['sourceObject', 'targetObject', 'relationshipType', 'traceId', 'direction']),
  statusField: 'status',
  actionRules: Object.freeze({ ruleCode: 'SCM_SUPPLIER_QUOTE_LINE_ACTION_GUARD', mode: 'parent_controlled' }),
  parentObject: 'SCM_SUPPLIER_QUOTE',
  independentCreationAllowed: false,
  persistenceMode: 'definition_only',
  automaticCreation: false,
})

export function validateSupplierQuoteLineDomainModel(model = SUPPLIER_QUOTE_LINE_DOMAIN_MODEL) {
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const requiredFields = ['quoteNo', 'inquiryLineNo', 'materialCode', 'quantity', 'unitPrice', 'taxRate', 'totalAmount', 'deliveryDate']
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.parentObject !== 'SCM_SUPPLIER_QUOTE') missing.push('parentObject')
  if (model?.independentCreationAllowed !== false) missing.push('independentCreationAllowed')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}

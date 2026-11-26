export const PURCHASE_INQUIRY_DOMAIN_MODEL_VERSION = 'V1.14.2.8.5.1'

const field = (name, type, required = true) => Object.freeze({ name, type, required })

const defineObject = definition => Object.freeze({
  ...definition,
  fields: Object.freeze(definition.fields),
  relationships: Object.freeze(definition.relationships),
  traceFields: Object.freeze(definition.traceFields),
  actionRules: Object.freeze(definition.actionRules),
  persistenceMode: 'definition_only',
  automaticCreation: false,
})

const TRACE_FIELDS = Object.freeze(['sourceObject', 'targetObject', 'relationshipType', 'traceId', 'direction'])

export const PURCHASE_INQUIRY_DOMAIN_OBJECTS = Object.freeze([
  defineObject({
    objectCode: 'SCM_PURCHASE_INQUIRY',
    objectName: '采购询价单',
    businessObject: 'PurchaseInquiry',
    fields: [
      field('inquiryNo', 'string'),
      field('sourcePurchaseRequest', 'object_reference'),
      field('sourceRequestNo', 'string'),
      field('supplierScope', 'array'),
      field('inquiryDate', 'date'),
      field('buyer', 'object_reference'),
      field('status', 'status'),
      field('supplierCount', 'number'),
      field('currency', 'currency'),
      field('totalAmount', 'money'),
      field('inquiryLines', 'array_relation'),
      field('quotes', 'array_relation'),
      field('comparisonResult', 'object_relation', false),
      field('traceId', 'string'),
    ],
    relationships: ['PURCHASE_REQUEST_TO_INQUIRY', 'INQUIRY_TO_LINE', 'INQUIRY_TO_SUPPLIER_QUOTE'],
    traceFields: TRACE_FIELDS,
    statusField: 'status',
    actionRules: { ruleCode: 'SCM_PURCHASE_INQUIRY_ACTION_RULE', mode: 'whitelist', defaultDecision: 'deny' },
  }),
  defineObject({
    objectCode: 'SCM_PURCHASE_INQUIRY_LINE',
    objectName: '采购询价明细',
    businessObject: 'PurchaseInquiryLine',
    fields: [
      field('lineNo', 'string'),
      field('inquiryNo', 'string'),
      field('sourceRequestLineNo', 'string'),
      field('materialCode', 'string'),
      field('specification', 'string'),
      field('quantity', 'quantity'),
      field('unit', 'string'),
      field('requiredDate', 'date'),
      field('referencePrice', 'money', false),
      field('status', 'status'),
      field('traceId', 'string'),
    ],
    relationships: ['PURCHASE_REQUEST_LINE_TO_INQUIRY_LINE', 'INQUIRY_TO_LINE', 'QUOTE_LINE_TO_INQUIRY_LINE'],
    traceFields: TRACE_FIELDS,
    statusField: 'status',
    actionRules: { ruleCode: 'SCM_PURCHASE_INQUIRY_LINE_ACTION_RULE', mode: 'parent_controlled', defaultDecision: 'deny' },
  }),
  defineObject({
    objectCode: 'SCM_SUPPLIER_QUOTE',
    objectName: '供应商报价',
    businessObject: 'SupplierQuote',
    fields: [
      field('quoteNo', 'string'),
      field('inquiryNo', 'string'),
      field('supplierCode', 'string'),
      field('quoteDate', 'date'),
      field('currency', 'currency'),
      field('paymentTerms', 'string'),
      field('deliveryDays', 'number'),
      field('status', 'status'),
      field('lines', 'array_relation'),
      field('totalQuoteAmount', 'money'),
      field('traceId', 'string'),
    ],
    relationships: ['INQUIRY_TO_SUPPLIER_QUOTE', 'SUPPLIER_QUOTE_TO_LINE', 'SUPPLIER_QUOTE_TO_COMPARISON'],
    traceFields: TRACE_FIELDS,
    statusField: 'status',
    actionRules: { ruleCode: 'SCM_SUPPLIER_QUOTE_ACTION_RULE', mode: 'inquiry_controlled', defaultDecision: 'deny' },
  }),
  defineObject({
    objectCode: 'SCM_SUPPLIER_QUOTE_LINE',
    objectName: '供应商报价明细',
    businessObject: 'SupplierQuoteLine',
    fields: [
      field('lineNo', 'string'),
      field('quoteNo', 'string'),
      field('inquiryLineNo', 'string'),
      field('materialCode', 'string'),
      field('quotePrice', 'money'),
      field('taxRate', 'percentage'),
      field('deliveryDate', 'date'),
      field('remark', 'string', false),
      field('status', 'status'),
      field('traceId', 'string'),
    ],
    relationships: ['SUPPLIER_QUOTE_TO_LINE', 'QUOTE_LINE_TO_INQUIRY_LINE'],
    traceFields: TRACE_FIELDS,
    statusField: 'status',
    actionRules: { ruleCode: 'SCM_SUPPLIER_QUOTE_LINE_ACTION_RULE', mode: 'parent_controlled', defaultDecision: 'deny' },
  }),
  defineObject({
    objectCode: 'SCM_QUOTE_COMPARISON',
    objectName: '报价比较',
    businessObject: 'QuoteComparison',
    fields: [
      field('comparisonNo', 'string'),
      field('inquiryNo', 'string'),
      field('suppliers', 'array'),
      field('comparisonItems', 'array_relation'),
      field('recommendedSupplier', 'object_reference', false),
      field('reason', 'string'),
      field('status', 'status'),
      field('traceId', 'string'),
    ],
    relationships: ['SUPPLIER_QUOTE_TO_COMPARISON', 'COMPARISON_TO_PRICE_APPROVAL'],
    traceFields: TRACE_FIELDS,
    statusField: 'status',
    actionRules: { ruleCode: 'SCM_QUOTE_COMPARISON_ACTION_RULE', mode: 'inquiry_controlled', defaultDecision: 'deny' },
  }),
])

const OBJECT_BY_IDENTITY = new Map(PURCHASE_INQUIRY_DOMAIN_OBJECTS.flatMap(object => [[object.objectCode, object], [object.businessObject, object]]))

export function listPurchaseInquiryDomainObjects() {
  return PURCHASE_INQUIRY_DOMAIN_OBJECTS
}

export function resolvePurchaseInquiryDomainObject(identity = '') {
  return OBJECT_BY_IDENTITY.get(identity) || null
}

export function validatePurchaseInquiryDomainObjectDefinition(object) {
  if (!object) return Object.freeze({ result: 'FAIL', missing: Object.freeze(['object']) })
  const required = ['objectCode', 'fields', 'relationships', 'traceFields', 'statusField', 'actionRules']
  const missing = required.filter(key => object[key] == null || (Array.isArray(object[key]) && object[key].length === 0))
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}


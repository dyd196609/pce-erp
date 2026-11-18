export const PURCHASE_INQUIRY_RELATIONSHIP_MODEL_VERSION = 'V1.14.2.8.5.1'

export const PURCHASE_INQUIRY_TRACE_CHAIN = Object.freeze([
  'SCM_PURCHASE_REQUEST',
  'SCM_PURCHASE_INQUIRY',
  'SCM_SUPPLIER_QUOTE',
  'SCM_QUOTE_COMPARISON',
  'SCM_PRICE_APPROVAL',
  'SCM_PURCHASE_ORDER',
])

const relationship = (relationshipCode, sourceObject, targetObject, cardinality, relationshipType = 'business_reference') => Object.freeze({
  relationshipCode,
  sourceObject,
  targetObject,
  relationshipType,
  cardinality,
  traceIdField: 'traceId',
  direction: 'forward',
  reverseGenerationForbidden: true,
  automaticCreation: false,
})

export const PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS = Object.freeze([
  relationship('PURCHASE_REQUEST_TO_INQUIRY', 'SCM_PURCHASE_REQUEST', 'SCM_PURCHASE_INQUIRY', '1:N'),
  relationship('INQUIRY_TO_SUPPLIER_QUOTE', 'SCM_PURCHASE_INQUIRY', 'SCM_SUPPLIER_QUOTE', '1:N'),
  relationship('SUPPLIER_QUOTE_TO_COMPARISON', 'SCM_SUPPLIER_QUOTE', 'SCM_QUOTE_COMPARISON', 'N:1'),
  relationship('COMPARISON_TO_PRICE_APPROVAL', 'SCM_QUOTE_COMPARISON', 'SCM_PRICE_APPROVAL', '1:1'),
  relationship('PRICE_APPROVAL_TO_PURCHASE_ORDER', 'SCM_PRICE_APPROVAL', 'SCM_PURCHASE_ORDER', '1:N'),
])

export const PURCHASE_INQUIRY_INTERNAL_RELATIONSHIPS = Object.freeze([
  relationship('PURCHASE_REQUEST_LINE_TO_INQUIRY_LINE', 'SCM_PURCHASE_REQUEST_LINE', 'SCM_PURCHASE_INQUIRY_LINE', '1:N'),
  relationship('INQUIRY_TO_LINE', 'SCM_PURCHASE_INQUIRY', 'SCM_PURCHASE_INQUIRY_LINE', '1:N', 'composition'),
  relationship('SUPPLIER_QUOTE_TO_LINE', 'SCM_SUPPLIER_QUOTE', 'SCM_SUPPLIER_QUOTE_LINE', '1:N', 'composition'),
  relationship('QUOTE_LINE_TO_INQUIRY_LINE', 'SCM_SUPPLIER_QUOTE_LINE', 'SCM_PURCHASE_INQUIRY_LINE', 'N:1'),
])

export const PURCHASE_INQUIRY_RELATIONSHIPS = Object.freeze([...PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS, ...PURCHASE_INQUIRY_INTERNAL_RELATIONSHIPS])

const present = value => String(value ?? '').trim().length > 0

export function evaluatePurchaseInquiryTrace(input = {}) {
  if (!['sourceObject', 'targetObject', 'relationshipType', 'traceId', 'direction'].every(field => present(input[field]))) {
    return Object.freeze({ result: 'UNKNOWN', reason: 'TRACE_REQUIRED_FACT_MISSING' })
  }
  const rule = PURCHASE_INQUIRY_RELATIONSHIPS.find(item => item.sourceObject === input.sourceObject && item.targetObject === input.targetObject)
  if (!rule) return Object.freeze({ result: 'FAIL', reason: 'RELATIONSHIP_NOT_REGISTERED' })
  const pass = input.relationshipType === rule.relationshipType
    && input.direction === 'forward'
    && (!input.sourceTraceId || input.sourceTraceId === input.traceId)
    && (!input.targetTraceId || input.targetTraceId === input.traceId)
  return Object.freeze({ result: pass ? 'PASS' : 'FAIL', reason: pass ? '' : 'TRACE_FACT_MISMATCH', relationshipCode: rule.relationshipCode })
}

export function isPurchaseInquiryReverseGeneration(sourceObject, targetObject) {
  const sourceIndex = PURCHASE_INQUIRY_TRACE_CHAIN.indexOf(sourceObject)
  const targetIndex = PURCHASE_INQUIRY_TRACE_CHAIN.indexOf(targetObject)
  return sourceIndex >= 0 && targetIndex >= 0 && sourceIndex > targetIndex
}


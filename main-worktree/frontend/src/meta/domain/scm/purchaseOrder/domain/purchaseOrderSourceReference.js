export const PURCHASE_ORDER_SOURCE_REFERENCE_VERSION = 'V1.14.2.8.5.6'
export const PURCHASE_ORDER_SOURCE_REFERENCE_CODE = 'SCM_PURCHASE_ORDER_SOURCE_REFERENCE'

export const PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS = Object.freeze([
  'SCM_SUPPLIER_RECOMMENDATION_DECISION',
  'SCM_PURCHASE_ORDER_CREATION_GATE',
])

export const PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS = Object.freeze([
  'SCM_SUPPLIER_QUOTE',
  'SCM_QUOTE_COMPARISON',
])

export const PURCHASE_ORDER_SOURCE_REFERENCE = Object.freeze({
  referenceCode: PURCHASE_ORDER_SOURCE_REFERENCE_CODE,
  allowedSourceObjects: PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS,
  forbiddenDirectSourceObjects: PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS,
  relationshipType: 'business_reference',
  direction: 'forward',
  automaticGenerationAllowed: false,
  executionMode: 'read_only',
})

export function evaluatePurchaseOrderSourceReference({ sourceObject, sourceReferenceId } = {}) {
  if (!sourceObject || !sourceReferenceId) return Object.freeze({ result: 'UNKNOWN', reason: 'source_reference_fact_missing' })
  if (PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS.includes(sourceObject)) return Object.freeze({ result: 'FAIL', reason: 'direct_quote_source_forbidden' })
  if (!PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS.includes(sourceObject)) return Object.freeze({ result: 'FAIL', reason: 'source_object_not_allowed' })
  return Object.freeze({ result: 'PASS', reason: '', createsPurchaseOrder: false, businessWriteCount: 0, productionUserDataWritten: false })
}

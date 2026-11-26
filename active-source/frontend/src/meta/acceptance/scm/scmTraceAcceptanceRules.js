export const SCM_TRACE_ACCEPTANCE_VERSION = 'V1.14.2.8.4.23'

export const SCM_TRACE_CHAIN = Object.freeze([
  'SCM_PURCHASE_REQUEST',
  'SCM_PURCHASE_INQUIRY',
  'SCM_PRICE_APPROVAL',
  'SCM_PURCHASE_ORDER',
  'SCM_WAREHOUSE_RECEIPT',
  'SCM_QUALITY_INSPECTION',
  'SCM_AP_PREPARE',
])

export const SCM_TRACE_ACCEPTANCE_RULES = Object.freeze(SCM_TRACE_CHAIN.slice(0, -1).map((sourceObject, index) => Object.freeze({
  ruleCode: `SCM-TRACE-${String(index + 1).padStart(3, '0')}`,
  sourceObject,
  targetObject: SCM_TRACE_CHAIN[index + 1],
  relationshipType: 'upstream_to_downstream',
  traceIdField: 'traceId',
  direction: 'forward',
  reverseGenerationForbidden: true,
})))

const required = value => String(value ?? '').trim().length > 0

export function evaluateScmTraceRelationship(input = {}) {
  const rule = SCM_TRACE_ACCEPTANCE_RULES.find(item => item.sourceObject === input.sourceObject && item.targetObject === input.targetObject)
  if (!required(input.sourceObject) || !required(input.targetObject) || !required(input.relationshipType) || !required(input.traceId) || !required(input.direction)) {
    return Object.freeze({ result: 'UNKNOWN', reason: 'TRACE_REQUIRED_FACT_MISSING' })
  }
  if (!rule) return Object.freeze({ result: 'FAIL', reason: 'TRACE_RELATIONSHIP_NOT_ALLOWED' })
  const pass = input.relationshipType === rule.relationshipType
    && input.direction === rule.direction
    && (!input.sourceTraceId || input.sourceTraceId === input.traceId)
    && (!input.targetTraceId || input.targetTraceId === input.traceId)
  return Object.freeze({ result: pass ? 'PASS' : 'FAIL', reason: pass ? '' : 'TRACE_FACT_MISMATCH', ruleCode: rule.ruleCode })
}

export function isReverseScmGeneration(sourceObject, targetObject) {
  const sourceIndex = SCM_TRACE_CHAIN.indexOf(sourceObject)
  const targetIndex = SCM_TRACE_CHAIN.indexOf(targetObject)
  return sourceIndex >= 0 && targetIndex >= 0 && sourceIndex > targetIndex
}


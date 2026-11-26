export const SCM_PURCHASE_LIFECYCLE_RELATION_RULES_VERSION = 'V1.14.2.8.5.11'
export const SCM_PURCHASE_LIFECYCLE_RELATION_RULE_SET_CODE = 'SCM_PURCHASE_LIFECYCLE_RELATION_RULES'

const relation = (sourceNode, targetNode, relationshipType) => Object.freeze({ sourceNode, targetNode, relationshipType, direction: 'forward', automaticGenerationAllowed: false, executionAllowed: false })

export const SCM_PURCHASE_LIFECYCLE_RELATION_RULES = Object.freeze([
  relation('PURCHASE_INQUIRY', 'SUPPLIER_QUOTE', 'business_reference'),
  relation('SUPPLIER_QUOTE', 'QUOTE_COMPARISON', 'evidence_reference'),
  relation('QUOTE_COMPARISON', 'SUPPLIER_RECOMMENDATION_DECISION', 'decision_reference'),
  relation('SUPPLIER_RECOMMENDATION_DECISION', 'PURCHASE_ORDER_CREATION_GATE', 'eligibility_reference'),
  relation('PURCHASE_ORDER_CREATION_GATE', 'PURCHASE_ORDER_DOMAIN', 'domain_reference'),
  relation('PURCHASE_ORDER_DOMAIN', 'PURCHASE_ORDER_TRANSACTION_BOUNDARY', 'boundary_reference'),
  relation('PURCHASE_ORDER_TRANSACTION_BOUNDARY', 'PURCHASE_ORDER_APPROVAL_INTERFACE', 'approval_preparation_reference'),
  relation('PURCHASE_ORDER_APPROVAL_INTERFACE', 'PURCHASE_ORDER_TRANSACTION', 'transaction_definition_reference'),
  relation('PURCHASE_ORDER_TRANSACTION', 'PURCHASE_ORDER_LIFECYCLE', 'lifecycle_definition_reference'),
  relation('PURCHASE_ORDER_LIFECYCLE', 'PURCHASE_ORDER_ISSUE_BOUNDARY', 'issue_eligibility_reference'),
])

export function evaluateScmPurchaseLifecycleRelation({ sourceNode, targetNode } = {}) {
  if (!sourceNode || !targetNode) return Object.freeze({ result: 'UNKNOWN', allowed: false, reason: 'lifecycle_relation_fact_missing', executionAllowed: false })
  const rule = SCM_PURCHASE_LIFECYCLE_RELATION_RULES.find(item => item.sourceNode === sourceNode && item.targetNode === targetNode)
  return Object.freeze({
    result: rule ? 'PASS' : 'FAIL',
    allowed: Boolean(rule),
    reason: rule ? '' : 'non_adjacent_or_reverse_lifecycle_relation_forbidden',
    relationshipType: rule?.relationshipType || null,
    automaticGenerationAllowed: false,
    executionAllowed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

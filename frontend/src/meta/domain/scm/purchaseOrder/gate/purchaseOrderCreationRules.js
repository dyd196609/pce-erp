export const PURCHASE_ORDER_CREATION_RULES_VERSION = 'V1.14.2.8.5.5'

export const PURCHASE_ORDER_CREATION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'PO-GATE-RULE-001', conditionCode: 'recommendation_decision_exists', description: 'SupplierRecommendationDecision存在' }),
  Object.freeze({ ruleCode: 'PO-GATE-RULE-002', conditionCode: 'supplier_quote_valid', description: 'SupplierQuote有效' }),
  Object.freeze({ ruleCode: 'PO-GATE-RULE-003', conditionCode: 'quote_comparison_completed', description: 'QuoteComparison完成' }),
  Object.freeze({ ruleCode: 'PO-GATE-RULE-004', conditionCode: 'supplier_valid', description: 'Supplier有效' }),
])

export function evaluatePurchaseOrderCreationCondition(ruleCode, facts = {}) {
  let pass = null
  if (ruleCode === 'PO-GATE-RULE-001') pass = facts.recommendationDecisionExists === true || Boolean(facts.recommendationDecision?.recommendationStatus)
  if (ruleCode === 'PO-GATE-RULE-002') pass = facts.supplierQuoteValid === true || ['valid', 'validated'].includes(facts.supplierQuote?.status) || facts.supplierQuote?.validationResult === 'PASS'
  if (ruleCode === 'PO-GATE-RULE-003') pass = facts.quoteComparisonCompleted === true || ['completed', 'approved'].includes(facts.quoteComparison?.status)
  if (ruleCode === 'PO-GATE-RULE-004') pass = facts.supplierValid === true || ['valid', 'active', 'approved'].includes(facts.supplier?.status)
  return Object.freeze({ ruleCode, result: pass === null ? 'UNKNOWN' : pass ? 'PASS' : 'FAIL' })
}

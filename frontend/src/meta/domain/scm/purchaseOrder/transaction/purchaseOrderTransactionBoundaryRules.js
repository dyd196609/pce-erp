export const PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULES_VERSION = 'V1.14.2.8.5.7'
export const PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULE_SET_CODE = 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULES'

export const PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'PO-TXN-RULE-001', conditionCode: 'supplier_recommendation_decision_exists' }),
  Object.freeze({ ruleCode: 'PO-TXN-RULE-002', conditionCode: 'purchase_order_creation_gate_exists' }),
  Object.freeze({ ruleCode: 'PO-TXN-RULE-003', conditionCode: 'creation_gate_eligible' }),
  Object.freeze({ ruleCode: 'PO-TXN-RULE-004', conditionCode: 'purchase_order_domain_valid' }),
])

const conditionPass = (ruleCode, facts) => {
  if (ruleCode === 'PO-TXN-RULE-001') return facts.supplierRecommendationDecisionExists === true
  if (ruleCode === 'PO-TXN-RULE-002') return facts.purchaseOrderCreationGateExists === true
  if (ruleCode === 'PO-TXN-RULE-003') return facts.gateEligibilityResult === 'ELIGIBLE'
  if (ruleCode === 'PO-TXN-RULE-004') return facts.purchaseOrderDomainValid === true
  return null
}

export function evaluatePurchaseOrderTransactionBoundary(facts = {}) {
  const evaluatedConditions = Object.freeze(PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULES.map(rule => {
    const pass = conditionPass(rule.ruleCode, facts)
    return Object.freeze({ ...rule, result: pass === null ? 'UNKNOWN' : pass ? 'PASS' : 'FAIL' })
  }))
  const blockingReasons = Object.freeze(evaluatedConditions.filter(item => item.result !== 'PASS').map(item => item.conditionCode))
  const transactionAllowed = blockingReasons.length === 0
  return Object.freeze({
    boundaryStatus: 'evaluated',
    transactionAllowed,
    boundaryResult: transactionAllowed ? 'READY_FOR_FUTURE_TRANSACTION' : 'BLOCKED',
    blockingReasons,
    evaluatedConditions,
    decisionOnly: true,
    createsPurchaseOrder: false,
    executesTransaction: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

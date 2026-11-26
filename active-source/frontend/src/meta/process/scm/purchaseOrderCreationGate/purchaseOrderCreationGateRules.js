export const PURCHASE_ORDER_CREATION_GATE_RULES_VERSION = 'V1.14.2.8.14'

export const PURCHASE_ORDER_CREATION_GATE_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'PO-GATE-RECOMMENDATION-READY', field: 'recommendationStatus' }),
  Object.freeze({ ruleCode: 'PO-GATE-SUPPLIER-IDENTIFIED', field: 'recommendedSupplier' }),
  Object.freeze({ ruleCode: 'PO-GATE-COST-REFERENCED', field: 'costReference' }),
  Object.freeze({ ruleCode: 'PO-GATE-NO-BLOCKING-RISK', field: 'recommendationEvidence.risks' }),
  Object.freeze({ ruleCode: 'PO-GATE-SOURCE-CHAIN-COMPLETE', field: 'sourceChain' }),
])

export function evaluatePurchaseOrderCreationEligibility(context = {}) {
  if (context.objectType !== 'PurchaseOrderCreationGateContext' || context.status !== 'gate_context_created') {
    throw new Error('PURCHASE_ORDER_GATE_CONTEXT_NOT_READY')
  }
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'PO-GATE-RECOMMENDATION-READY', passed: context.recommendationStatus === 'approval_ready' }),
    Object.freeze({ ruleCode: 'PO-GATE-SUPPLIER-IDENTIFIED', passed: Boolean(context.recommendedSupplier?.supplierId) }),
    Object.freeze({ ruleCode: 'PO-GATE-COST-REFERENCED', passed: context.costReference?.totalCost > 0 && Boolean(context.costReference?.currency) }),
    Object.freeze({ ruleCode: 'PO-GATE-NO-BLOCKING-RISK', passed: !context.recommendationEvidence.some(item => item.risks?.some(risk => risk.severity === 'high')) }),
    Object.freeze({ ruleCode: 'PO-GATE-SOURCE-CHAIN-COMPLETE', passed: Boolean(context.sourceChain?.inquiryNo && context.sourceChain?.comparisonNo && context.sourceChain?.decisionNo) }),
  ])
  const blockedReasons = Object.freeze(checks.filter(item => !item.passed).map(item => item.ruleCode))
  return Object.freeze({ eligible: blockedReasons.length === 0, checks, blockedReasons })
}

export const PURCHASE_ORDER_TRANSACTION_RULES_VERSION = 'V1.14.2.8.15'

export const PURCHASE_ORDER_TRANSACTION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'POT-GATE-ELIGIBLE', field: 'gateStatus' }),
  Object.freeze({ ruleCode: 'POT-SUPPLIER-REQUIRED', field: 'supplier' }),
  Object.freeze({ ruleCode: 'POT-PURCHASE-LINES-REQUIRED', field: 'purchaseDetails' }),
  Object.freeze({ ruleCode: 'POT-AMOUNT-REFERENCE-REQUIRED', field: 'amountReference' }),
  Object.freeze({ ruleCode: 'POT-SOURCE-CHAIN-REQUIRED', field: 'sourceChain' }),
])

export function validatePurchaseOrderTransactionContextFacts(context = {}) {
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'POT-GATE-ELIGIBLE', passed: context.gateStatus === 'eligible' }),
    Object.freeze({ ruleCode: 'POT-SUPPLIER-REQUIRED', passed: Boolean(context.supplier?.supplierId) }),
    Object.freeze({ ruleCode: 'POT-PURCHASE-LINES-REQUIRED', passed: context.purchaseDetails?.length > 0
      && context.purchaseDetails.every(item => item.materialCode && item.quantity > 0 && item.unitPrice > 0) }),
    Object.freeze({ ruleCode: 'POT-AMOUNT-REFERENCE-REQUIRED', passed: context.amountReference?.totalAmount > 0
      && Boolean(context.amountReference?.currency) }),
    Object.freeze({ ruleCode: 'POT-SOURCE-CHAIN-REQUIRED', passed: Boolean(context.sourceChain?.gateDecisionNo
      && context.sourceChain?.recommendationDecisionNo && context.sourceChain?.comparisonNo && context.sourceChain?.inquiryNo) }),
  ])
  return Object.freeze({ valid: checks.every(item => item.passed), checks,
    errors: Object.freeze(checks.filter(item => !item.passed).map(item => item.ruleCode)) })
}

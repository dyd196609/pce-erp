export const PURCHASE_ORDER_ISSUE_PREPARATION_RULES_VERSION = 'V1.14.2.8.16'

export const PURCHASE_ORDER_ISSUE_PREPARATION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'POIP-TRANSACTION-DRAFT', field: 'transactionStatus' }),
  Object.freeze({ ruleCode: 'POIP-SUPPLIER-READY', field: 'supplier' }),
  Object.freeze({ ruleCode: 'POIP-LINES-COMPLETE', field: 'orderDetails' }),
  Object.freeze({ ruleCode: 'POIP-AMOUNT-REFERENCED', field: 'amountReference' }),
  Object.freeze({ ruleCode: 'POIP-DELIVERY-REQUIREMENTS', field: 'deliveryRequirements' }),
  Object.freeze({ ruleCode: 'POIP-SOURCE-CHAIN', field: 'sourceChain' }),
])

export function checkPurchaseOrderIssueRequirements(context = {}) {
  if (context.objectType !== 'PurchaseOrderIssuePreparationContext' || context.status !== 'issue_context_created') {
    throw new Error('PURCHASE_ORDER_ISSUE_PREPARATION_CONTEXT_NOT_READY')
  }
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'POIP-TRANSACTION-DRAFT', passed: context.transactionStatus === 'draft' }),
    Object.freeze({ ruleCode: 'POIP-SUPPLIER-READY', passed: Boolean(context.supplier?.supplierId) }),
    Object.freeze({ ruleCode: 'POIP-LINES-COMPLETE', passed: context.orderDetails?.length > 0
      && context.orderDetails.every(item => item.materialCode && item.quantity > 0 && item.unitPrice > 0) }),
    Object.freeze({ ruleCode: 'POIP-AMOUNT-REFERENCED', passed: context.amountReference?.totalAmount > 0
      && Boolean(context.amountReference?.currency) }),
    Object.freeze({ ruleCode: 'POIP-DELIVERY-REQUIREMENTS', passed: context.deliveryRequirements?.length === context.orderDetails?.length
      && context.deliveryRequirements.every(item => item.deliveryDate && item.validUntil) }),
    Object.freeze({ ruleCode: 'POIP-SOURCE-CHAIN', passed: Boolean(context.sourceChain?.transactionNo
      && context.sourceChain?.gateDecisionNo && context.sourceChain?.recommendationDecisionNo) }),
  ])
  const blockedReasons = Object.freeze(checks.filter(item => !item.passed).map(item => item.ruleCode))
  return Object.freeze({ ready: blockedReasons.length === 0, checks, blockedReasons })
}

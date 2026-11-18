export const PURCHASE_ORDER_ISSUE_BOUNDARY_RULES_VERSION = 'V1.14.2.8.17'

export const PURCHASE_ORDER_ISSUE_BOUNDARY_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'POIB-PREPARATION-READY', field: 'preparationResult' }),
  Object.freeze({ ruleCode: 'POIB-SUPPLIER-PRESENT', field: 'supplier' }),
  Object.freeze({ ruleCode: 'POIB-ORDER-INFORMATION-COMPLETE', field: 'orderInformation' }),
  Object.freeze({ ruleCode: 'POIB-EVIDENCE-PASSED', field: 'evidence.checks' }),
  Object.freeze({ ruleCode: 'POIB-SOURCE-CHAIN-COMPLETE', field: 'sourceChain' }),
])

export function evaluatePurchaseOrderIssuePermission(context = {}) {
  if (context.objectType !== 'PurchaseOrderIssueBoundaryContext'
    || context.status !== 'issue_boundary_context_created') {
    throw new Error('PURCHASE_ORDER_ISSUE_BOUNDARY_CONTEXT_NOT_READY')
  }
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'POIB-PREPARATION-READY', passed: context.preparationResult?.status === 'ready_for_issue' }),
    Object.freeze({ ruleCode: 'POIB-SUPPLIER-PRESENT', passed: Boolean(context.supplier?.supplierId) }),
    Object.freeze({ ruleCode: 'POIB-ORDER-INFORMATION-COMPLETE', passed: Boolean(context.orderInformation?.transactionNo)
      && context.orderInformation?.orderDetails?.length > 0 && context.orderInformation?.totalQuantity > 0 }),
    Object.freeze({ ruleCode: 'POIB-EVIDENCE-PASSED', passed: context.evidence?.checks?.length > 0
      && context.evidence.checks.every(item => item.passed) }),
    Object.freeze({ ruleCode: 'POIB-SOURCE-CHAIN-COMPLETE', passed: Boolean(context.sourceChain?.transactionNo
      && context.sourceChain?.gateDecisionNo && context.sourceChain?.recommendationDecisionNo) }),
  ])
  const blockedReasons = Object.freeze(checks.filter(item => !item.passed).map(item => item.ruleCode))
  return Object.freeze({ allowed: blockedReasons.length === 0, checks, blockedReasons })
}

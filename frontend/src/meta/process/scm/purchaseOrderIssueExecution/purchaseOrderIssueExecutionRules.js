export const PURCHASE_ORDER_ISSUE_EXECUTION_RULES_VERSION = 'V1.14.2.8.18'

export const PURCHASE_ORDER_ISSUE_EXECUTION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'POIE-BOUNDARY-ALLOWED', field: 'authorizationEvidence.boundaryStatus' }),
  Object.freeze({ ruleCode: 'POIE-ORDER-INFORMATION-COMPLETE', field: 'orderInformation' }),
  Object.freeze({ ruleCode: 'POIE-SUPPLIER-INFORMATION-COMPLETE', field: 'supplierInformation' }),
  Object.freeze({ ruleCode: 'POIE-AUTHORIZATION-EVIDENCE-PASSED', field: 'authorizationEvidence.checks' }),
  Object.freeze({ ruleCode: 'POIE-SOURCE-CHAIN-COMPLETE', field: 'sourceChain' }),
  Object.freeze({ ruleCode: 'POIE-PRODUCTION-EXECUTION-ISOLATED', field: 'executionIsolation' }),
])

export function checkPurchaseOrderIssueExecutionAuthorization(context = {}) {
  if (context.objectType !== 'PurchaseOrderIssueExecutionContext' || context.status !== 'execution_context_created') {
    throw new Error('PURCHASE_ORDER_ISSUE_EXECUTION_CONTEXT_NOT_READY')
  }
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'POIE-BOUNDARY-ALLOWED', passed: context.authorizationEvidence?.boundaryStatus === 'allowed' }),
    Object.freeze({ ruleCode: 'POIE-ORDER-INFORMATION-COMPLETE', passed: Boolean(context.orderInformation?.transactionNo)
      && context.orderInformation?.orderDetails?.length > 0 }),
    Object.freeze({ ruleCode: 'POIE-SUPPLIER-INFORMATION-COMPLETE', passed: Boolean(context.supplierInformation?.supplierId) }),
    Object.freeze({ ruleCode: 'POIE-AUTHORIZATION-EVIDENCE-PASSED', passed: context.authorizationEvidence?.checks?.length > 0
      && context.authorizationEvidence.checks.every(item => item.passed) }),
    Object.freeze({ ruleCode: 'POIE-SOURCE-CHAIN-COMPLETE', passed: Boolean(context.sourceChain?.transactionNo
      && context.sourceChain?.gateDecisionNo && context.sourceChain?.recommendationDecisionNo) }),
    Object.freeze({ ruleCode: 'POIE-PRODUCTION-EXECUTION-ISOLATED', passed: context.executionIsolation?.supplierApiEnabled === false
      && context.executionIsolation?.purchaseOrderIssueEnabled === false }),
  ])
  const blockedReasons = Object.freeze(checks.filter(item => !item.passed).map(item => item.ruleCode))
  return Object.freeze({ authorized: blockedReasons.length === 0, checks, blockedReasons })
}

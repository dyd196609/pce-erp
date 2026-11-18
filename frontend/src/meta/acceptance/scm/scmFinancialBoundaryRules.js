export const SCM_FINANCIAL_BOUNDARY_VERSION = 'V1.14.2.8.4.23'

export const SCM_FINANCIAL_BOUNDARY = Object.freeze({
  moduleCode: 'SCM',
  boundaryPolicy: 'read_and_judge_only',
  allowedFacts: Object.freeze(['priceReference', 'costEstimate', 'purchaseAmount']),
  forbiddenActions: Object.freeze(['createPayment', 'executePayment', 'bankTransfer', 'postLedger', 'reconcile']),
  forbiddenWriteScopes: Object.freeze(['payment', 'bank_send', 'ledger', 'reconciliation', 'finance_execution']),
  financeImpactAllowed: false,
  productionUserDataWritten: false,
})

export function evaluateScmFinancialBoundary({ action, fact, writeScope, financeImpact } = {}) {
  if (financeImpact === true || SCM_FINANCIAL_BOUNDARY.forbiddenActions.includes(action) || SCM_FINANCIAL_BOUNDARY.forbiddenWriteScopes.includes(writeScope)) {
    return Object.freeze({ result: 'FAIL', reason: 'SCM_FINANCE_BOUNDARY_VIOLATION' })
  }
  if (fact && SCM_FINANCIAL_BOUNDARY.allowedFacts.includes(fact) && (financeImpact === false || financeImpact == null)) {
    return Object.freeze({ result: 'PASS', reason: '' })
  }
  return Object.freeze({ result: 'UNKNOWN', reason: 'FINANCIAL_BOUNDARY_FACT_MISSING' })
}


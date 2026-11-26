export const PURCHASE_INQUIRY_FINANCIAL_BOUNDARY_VERSION = 'V1.14.2.8.5.1'
export const PURCHASE_INQUIRY_FINANCIAL_BOUNDARY_RULE_CODE = 'SCM_PURCHASE_INQUIRY_FINANCIAL_BOUNDARY_RULE'

export const PURCHASE_INQUIRY_FINANCIAL_BOUNDARY = Object.freeze({
  ruleCode: PURCHASE_INQUIRY_FINANCIAL_BOUNDARY_RULE_CODE,
  objectCode: 'SCM_PURCHASE_INQUIRY',
  boundaryPolicy: 'price_fact_only',
  allowedFacts: Object.freeze(['quoteAmount', 'estimatedCost', 'priceReference']),
  forbiddenActions: Object.freeze(['payment', 'createPayment', 'bankTransfer', 'ledgerPost', 'reconcile']),
  forbiddenDomains: Object.freeze(['payment_execution', 'bank_execution', 'general_ledger', 'settlement_reconciliation']),
  createsPurchaseOrder: false,
  financeExecutionAllowed: false,
  productionUserDataWritten: false,
})

export function evaluatePurchaseInquiryFinancialBoundary({ fact, action, targetDomain, financeImpact } = {}) {
  if (financeImpact === true || PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.forbiddenActions.includes(action) || PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.forbiddenDomains.includes(targetDomain)) {
    return Object.freeze({ result: 'FAIL', reason: 'PURCHASE_INQUIRY_FINANCE_BOUNDARY_VIOLATION' })
  }
  if (fact && PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.allowedFacts.includes(fact)) return Object.freeze({ result: 'PASS', reason: '' })
  return Object.freeze({ result: 'UNKNOWN', reason: 'FINANCIAL_BOUNDARY_FACT_MISSING' })
}

export const SUPPLIER_QUOTE_FINANCIAL_BOUNDARY_VERSION = 'V1.14.2.8.5.3'
export const SUPPLIER_QUOTE_FINANCIAL_BOUNDARY_CODE = 'SCM_SUPPLIER_QUOTE_FINANCIAL_BOUNDARY'

export const SUPPLIER_QUOTE_FINANCIAL_BOUNDARY = Object.freeze({
  ruleCode: SUPPLIER_QUOTE_FINANCIAL_BOUNDARY_CODE,
  objectCodes: Object.freeze(['SCM_SUPPLIER_QUOTE', 'SCM_QUOTE_COMPARISON']),
  allowedFacts: Object.freeze(['quoteAmount', 'estimatedPurchaseCost', 'priceReference']),
  forbiddenActions: Object.freeze(['paymentExecution', 'bankTransfer', 'ledgerPosting', 'settlement']),
  financeExecutionAllowed: false,
  createsPurchaseOrder: false,
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export function evaluateSupplierQuoteFinancialBoundary({ fact, action } = {}) {
  if (SUPPLIER_QUOTE_FINANCIAL_BOUNDARY.forbiddenActions.includes(action)) return Object.freeze({ result: 'FAIL', reason: 'finance_action_forbidden' })
  if (SUPPLIER_QUOTE_FINANCIAL_BOUNDARY.allowedFacts.includes(fact)) return Object.freeze({ result: 'PASS', reason: '' })
  return Object.freeze({ result: 'UNKNOWN', reason: 'finance_boundary_fact_missing' })
}

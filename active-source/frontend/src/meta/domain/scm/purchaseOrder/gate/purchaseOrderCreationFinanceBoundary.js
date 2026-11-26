export const PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY_VERSION = 'V1.14.2.8.5.5'
export const PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY_CODE = 'SCM_PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY'

export const PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY = Object.freeze({
  boundaryCode: PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY_CODE,
  allowedFacts: Object.freeze(['estimatedPurchaseCostReference']),
  forbiddenActions: Object.freeze(['financeVoucher', 'payment', 'posting', 'ledger', 'costSettlement']),
  financeExecutionAllowed: false,
  costSettlementAllowed: false,
  createsPurchaseOrder: false,
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export function evaluatePurchaseOrderCreationFinanceBoundary({ fact, action } = {}) {
  if (PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY.forbiddenActions.includes(action)) return Object.freeze({ result: 'FAIL', reason: 'finance_boundary_violation' })
  if (PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY.allowedFacts.includes(fact)) return Object.freeze({ result: 'PASS', reason: '' })
  return Object.freeze({ result: 'UNKNOWN', reason: 'finance_boundary_fact_missing' })
}

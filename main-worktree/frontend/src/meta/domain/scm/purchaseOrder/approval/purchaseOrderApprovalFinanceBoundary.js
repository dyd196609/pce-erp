export const PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY_VERSION = 'V1.14.2.8.5.8'
export const PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY_CODE = 'SCM_PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY'

export const PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY = Object.freeze({
  boundaryCode: PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY_CODE,
  allowedFacts: Object.freeze(['amountReference', 'costReference']),
  forbiddenActions: Object.freeze(['financeVoucher', 'payment', 'posting', 'ledger', 'costSettlement']),
  financeExecutionAllowed: false,
  persistenceMode: 'definition_only',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function evaluatePurchaseOrderApprovalFinanceBoundary({ fact, action } = {}) {
  if (PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY.forbiddenActions.includes(action)) return Object.freeze({ result: 'FAIL', reason: 'approval_finance_boundary_violation' })
  if (PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY.allowedFacts.includes(fact)) return Object.freeze({ result: 'PASS', reason: '' })
  return Object.freeze({ result: 'UNKNOWN', reason: 'approval_finance_boundary_fact_missing' })
}

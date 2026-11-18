export const PURCHASE_APPROVAL_BOUNDARY_VERSION = 'V1.14.2.8.5.4'
export const PURCHASE_APPROVAL_BOUNDARY_CODE = 'SCM_PURCHASE_APPROVAL_PRECONDITION_BOUNDARY'

export const PURCHASE_APPROVAL_BOUNDARY = Object.freeze({
  boundaryCode: PURCHASE_APPROVAL_BOUNDARY_CODE,
  sourceObject: 'SCM_SUPPLIER_RECOMMENDATION_DECISION',
  allowedFacts: Object.freeze(['recommendationEvidenceReference']),
  forbiddenFinanceActions: Object.freeze(['financeVoucher', 'createFinanceVoucher', 'payment', 'posting', 'ledger', 'ledgerPost']),
  forbiddenExecutionActions: Object.freeze(['createPurchaseOrder', 'createContract', 'submitPayment', 'generateFinanceDocument', 'reserveInventory']),
  approvalExecutionAllowed: false,
  purchaseExecutionAllowed: false,
  financeExecutionAllowed: false,
  inventoryReservationAllowed: false,
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export function evaluatePurchaseApprovalBoundary({ fact, action } = {}) {
  if ([...PURCHASE_APPROVAL_BOUNDARY.forbiddenFinanceActions, ...PURCHASE_APPROVAL_BOUNDARY.forbiddenExecutionActions].includes(action)) {
    return Object.freeze({ result: 'FAIL', reason: 'purchase_approval_boundary_violation' })
  }
  if (PURCHASE_APPROVAL_BOUNDARY.allowedFacts.includes(fact)) return Object.freeze({ result: 'PASS', reason: '' })
  return Object.freeze({ result: 'UNKNOWN', reason: 'purchase_approval_boundary_fact_missing' })
}

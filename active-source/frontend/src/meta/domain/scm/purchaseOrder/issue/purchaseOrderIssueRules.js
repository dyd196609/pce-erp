export const PURCHASE_ORDER_ISSUE_RULES_VERSION = 'V1.14.2.8.5.10'
export const PURCHASE_ORDER_ISSUE_RULE_SET_CODE = 'SCM_PURCHASE_ORDER_ISSUE_RULES'

export const PURCHASE_ORDER_ISSUE_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'PO-ISSUE-RULE-001', conditionCode: 'transaction_is_approved' }),
  Object.freeze({ ruleCode: 'PO-ISSUE-RULE-002', conditionCode: 'approval_reference_exists' }),
  Object.freeze({ ruleCode: 'PO-ISSUE-RULE-003', conditionCode: 'supplier_release_context_ready' }),
  Object.freeze({ ruleCode: 'PO-ISSUE-RULE-004', conditionCode: 'issue_evidence_exists' }),
])

const conditionPass = (ruleCode, facts) => {
  if (ruleCode === 'PO-ISSUE-RULE-001') return facts.lifecycleStatus === 'approved'
  if (ruleCode === 'PO-ISSUE-RULE-002') return Boolean(facts.approvalReference)
  if (ruleCode === 'PO-ISSUE-RULE-003') return facts.supplierReleaseContextStatus === 'ready'
  if (ruleCode === 'PO-ISSUE-RULE-004') return Array.isArray(facts.evidenceReferences) && facts.evidenceReferences.length > 0
  return false
}

export function evaluatePurchaseOrderIssueBoundary(facts = {}) {
  const evaluatedConditions = Object.freeze(PURCHASE_ORDER_ISSUE_RULES.map(rule => Object.freeze({ ...rule, result: conditionPass(rule.ruleCode, facts) ? 'PASS' : 'FAIL' })))
  const blockingReasons = Object.freeze(evaluatedConditions.filter(item => item.result !== 'PASS').map(item => item.conditionCode))
  const issueAllowed = blockingReasons.length === 0
  return Object.freeze({
    purchaseOrderTransactionId: facts.purchaseOrderTransactionId || null,
    approvalReference: facts.approvalReference || null,
    supplierReference: facts.supplierReference || null,
    issueStatus: issueAllowed ? 'ready_for_future_issue' : 'blocked',
    issueAllowed,
    blockingReasons,
    evidenceReferences: Object.freeze(Array.isArray(facts.evidenceReferences) ? [...facts.evidenceReferences] : []),
    evaluatedConditions,
    decisionOnly: true,
    createdAutomatically: false,
    executesIssue: false,
    sendsSupplier: false,
    supplierApiCalled: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

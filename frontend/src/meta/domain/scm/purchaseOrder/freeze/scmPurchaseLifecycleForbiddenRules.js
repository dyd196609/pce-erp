export const SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES_VERSION = 'V1.14.2.8.5.11'
export const SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULE_SET_CODE = 'SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES'

const forbidden = (ruleCode, sourceObject, action, targetObject, reason) => Object.freeze({ ruleCode, sourceObject, action, targetObject, reason, decision: 'deny' })

export const SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES = Object.freeze([
  forbidden('SCM-PO-FREEZE-FORBID-001', 'SCM_SUPPLIER_QUOTE', 'createPurchaseOrder', 'SCM_PURCHASE_ORDER', 'supplier_quote_cannot_create_purchase_order'),
  forbidden('SCM-PO-FREEZE-FORBID-002', 'SCM_QUOTE_COMPARISON', 'createPurchaseOrder', 'SCM_PURCHASE_ORDER', 'quote_comparison_cannot_create_purchase_order'),
  forbidden('SCM-PO-FREEZE-FORBID-003', 'SCM_SUPPLIER_RECOMMENDATION_DECISION', 'sendSupplier', 'SUPPLIER_INTERFACE', 'recommendation_cannot_issue_supplier'),
  forbidden('SCM-PO-FREEZE-FORBID-004', 'SCM_PURCHASE_ORDER_APPROVAL_PREPARATION', 'submitApproval', 'WORKFLOW', 'approval_preparation_cannot_submit_workflow'),
  forbidden('SCM-PO-FREEZE-FORBID-005', 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY', 'callSupplierApi', 'SUPPLIER_API', 'issue_boundary_cannot_call_supplier_api'),
])

export function evaluateScmPurchaseLifecycleForbiddenPath({ sourceObject, action, targetObject } = {}) {
  if (!sourceObject || !action || !targetObject) return Object.freeze({ result: 'UNKNOWN', decision: 'deny', blocked: true, reason: 'forbidden_path_fact_missing' })
  const rule = SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES.find(item => item.sourceObject === sourceObject && item.action === action && item.targetObject === targetObject)
  return Object.freeze({
    result: rule ? 'PASS' : 'FAIL',
    decision: 'deny',
    blocked: true,
    reason: rule?.reason || 'path_not_registered_and_default_deny',
    ruleCode: rule?.ruleCode || null,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

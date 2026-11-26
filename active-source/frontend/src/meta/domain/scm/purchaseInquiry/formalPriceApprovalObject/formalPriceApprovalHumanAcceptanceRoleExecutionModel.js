export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTION_VERSION = 'V1.14.2.8.7.6.2'

const roleExecution = (userRole, roleLabel, acceptanceTargets) => Object.freeze({
  userRole, roleLabel, acceptanceTargets: Object.freeze(acceptanceTargets),
  viewMode: 'business_view', executionMode: 'human_session_only',
  executionStatus: 'not_started', persisted: false, businessExecutionPermission: false,
})

export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTIONS = Object.freeze([
  roleExecution('purchase_user', '采购员', ['current_inquiry_stage_known', 'supplier_quotation_found', 'next_step_understood']),
  roleExecution('purchase_manager', '采购经理', ['price_comparison_understood', 'approval_preparation_understood', 'risk_understood']),
  roleExecution('acceptance_observer', '验收观察员', ['business_view_concise', 'acceptance_view_complete', 'boundary_clear']),
])

export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTION = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTION',
  version: FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTION_VERSION,
  roles: FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTIONS,
  roleCount: FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTIONS.length,
  persisted: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalHumanAcceptanceRoleExecution(model = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTION) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTION'
    && model.roleCount === 3 && model.roles.length === 3
    && model.roles.map(item => item.userRole).join('|') === 'purchase_user|purchase_manager|acceptance_observer'
    && model.roles.every(item => item.acceptanceTargets.length === 3 && item.viewMode === 'business_view'
      && item.executionMode === 'human_session_only' && item.executionStatus === 'not_started'
      && item.persisted === false && item.businessExecutionPermission === false)
    && model.persisted === false && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

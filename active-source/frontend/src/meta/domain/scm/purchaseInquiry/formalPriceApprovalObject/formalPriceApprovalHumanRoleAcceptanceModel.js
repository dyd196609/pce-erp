export const FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE_VERSION = 'V1.14.2.8.7.6'

const role = (roleCode, roleLabel, validationFocus) => Object.freeze({
  roleCode, roleLabel, validationFocus: Object.freeze(validationFocus),
  acceptanceMode: 'human_session_only', status: 'ready', persisted: false,
  businessExecutionPermission: false, approvalExecutionPermission: false,
})

export const FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE_ROLES = Object.freeze([
  role('purchase_buyer', '采购员', ['business_language', 'evidence_findability', 'next_step_clarity']),
  role('purchase_manager', '采购经理', ['decision_basis', 'risk_warning', 'role_boundary']),
  role('acceptance_observer', '验收观察员', ['view_separation', 'guard_evidence', 'zero_write_evidence']),
])

export const FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE_VERSION,
  states: Object.freeze(['not_started', 'in_review', 'accepted', 'feedback_required']),
  roles: FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE_ROLES,
  roleCount: FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE_ROLES.length,
  executionMode: 'session_validation_only',
  isBusinessExecution: false,
  persisted: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalHumanRoleAcceptance(model = FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE'
    && model.states.join('|') === 'not_started|in_review|accepted|feedback_required'
    && model.roleCount === 3 && model.roles.length === 3
    && model.roles.every((item) => item.acceptanceMode === 'human_session_only'
      && item.status === 'ready' && item.persisted === false
      && item.businessExecutionPermission === false && item.approvalExecutionPermission === false)
    && model.executionMode === 'session_validation_only' && model.isBusinessExecution === false
    && model.persisted === false && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

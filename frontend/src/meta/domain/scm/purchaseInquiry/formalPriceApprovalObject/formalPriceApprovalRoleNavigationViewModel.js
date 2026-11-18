export const FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW_VERSION = 'V1.14.2.8.7.2'

const roleView = (roleCode, roleLabel, focusSteps, responsibility) => Object.freeze({
  roleCode, roleLabel, focusSteps: Object.freeze(focusSteps), responsibility,
  viewMode: 'read_only', workflowPermission: false, executionPermission: false,
})

export const FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW',
  version: FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW_VERSION,
  viewStatus: 'ready_for_user_path_validation',
  roles: Object.freeze([
    roleView('purchase_buyer', '采购员', ['inquiry_overview', 'quotation_evidence', 'comparison_preparation'], '理解询价和报价证据，准备人工评审'),
    roleView('price_reviewer', '价格评审人员', ['comparison_preparation', 'approval_entry', 'user_acceptance'], '核对判断依据和准入边界'),
    roleView('read_only_observer', '只读观察者', ['inquiry_overview', 'user_acceptance'], '查看业务路径和零写入保护结果'),
  ]),
  roleCount: 3,
  roleViewMeansRoleExecution: false,
  approvalObjectCreated: false,
  workflowStarted: false,
  approvalTaskCreated: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalRoleNavigationView(model = FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW'
    && model.viewStatus === 'ready_for_user_path_validation' && model.roleCount === 3 && model.roles.length === 3
    && model.roles.every((role) => role.focusSteps.length > 0 && role.viewMode === 'read_only'
      && role.workflowPermission === false && role.executionPermission === false)
    && model.roleViewMeansRoleExecution === false && model.approvalObjectCreated === false
    && model.workflowStarted === false && model.approvalTaskCreated === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

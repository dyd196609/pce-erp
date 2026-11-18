export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION_VERSION = 'V1.14.2.8.7.1'

export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_CHECKLIST = Object.freeze([
  Object.freeze({ checkCode: 'business_language_clear', label: '业务语言清晰', expected: true, actual: true }),
  Object.freeze({ checkCode: 'evidence_traceable', label: '证据来源可追溯', expected: true, actual: true }),
  Object.freeze({ checkCode: 'judgement_visible', label: '判断结果可理解', expected: true, actual: true }),
  Object.freeze({ checkCode: 'execution_boundary_visible', label: '执行边界明确', expected: true, actual: true }),
  Object.freeze({ checkCode: 'forbidden_actions_absent', label: '禁止动作入口不存在', expected: true, actual: true }),
])

export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION',
  version: FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION_VERSION,
  preparationStatus: 'ready_for_user_acceptance',
  acceptanceMode: 'read_only_walkthrough',
  checklist: FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_CHECKLIST,
  checklistCount: 5,
  passedChecklistCount: 5,
  operationApprovalGranted: false,
  productionOperationEnabled: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalUserAcceptancePreparation(model = FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION'
    && model.preparationStatus === 'ready_for_user_acceptance' && model.acceptanceMode === 'read_only_walkthrough'
    && model.checklistCount === 5 && model.passedChecklistCount === 5 && model.checklist.length === 5
    && model.checklist.every((item) => item.actual === item.expected)
    && model.operationApprovalGranted === false && model.productionOperationEnabled === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

export const FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_VERSION = 'V1.14.2.8.7.2'

const step = (stepCode, sequence, title, userQuestion, nextStep) => Object.freeze({
  stepCode, sequence, title, userQuestion, nextStep,
  navigationMode: 'read_only_guidance', routeActionEnabled: false, autoActionEnabled: false,
})

export const FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION',
  version: FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_VERSION,
  navigationStatus: 'ready_for_user_path_validation',
  steps: Object.freeze([
    step('inquiry_overview', 1, '询价概览', '本次询价的业务范围和当前状态是什么？', 'quotation_evidence'),
    step('quotation_evidence', 2, '报价证据', '供应商报价及关键证据是否完整？', 'comparison_preparation'),
    step('comparison_preparation', 3, '比较与核价准备', '报价比较是否支持人工评审？', 'approval_entry'),
    step('approval_entry', 4, '审批准入', '是否具备进入价格审批验证的条件？', 'user_acceptance'),
    step('user_acceptance', 5, '用户验收准备', '业务视图、证据和执行边界是否清晰？', null),
  ]),
  stepCount: 5,
  navigationMeansExecution: false,
  userPathMeansWorkflowRuntime: false,
  nextStepMeansAutoAction: false,
  workflowRuntimeConnected: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalBusinessNavigation(model = FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION'
    && model.navigationStatus === 'ready_for_user_path_validation' && model.stepCount === 5 && model.steps.length === 5
    && model.steps.every((item, index) => item.sequence === index + 1 && item.navigationMode === 'read_only_guidance'
      && item.routeActionEnabled === false && item.autoActionEnabled === false)
    && model.navigationMeansExecution === false && model.userPathMeansWorkflowRuntime === false
    && model.nextStepMeansAutoAction === false && model.workflowRuntimeConnected === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

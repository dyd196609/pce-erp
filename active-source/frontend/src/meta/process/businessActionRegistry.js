import { listBusinessProcessSteps } from './businessProcessRegistry.js'

export const BUSINESS_ACTION_REGISTRY_VERSION = 'V1.14.0'

function action({
  actionCode,
  actionName,
  pageStepId,
  handlerType = 'navigation',
  requiredStoreMethod = null,
  requiredStatus = [],
  targetStatus = null,
  targetRouteName = null,
  requiresSourceObject = false,
  requiresSelection = false,
  requiresConfirmation = false,
  visibleWhen = 'always',
  enabledWhen = 'route_exists',
  disabledReason = '当前功能尚未接入，不能执行。',
  successMessage = '',
  failureMessage = '操作未完成，请检查来源数据和当前状态。',
  writesBusinessData = false,
  introducedInVersion = BUSINESS_ACTION_REGISTRY_VERSION,
}) {
  return {
    actionCode,
    actionName,
    pageStepId,
    handlerType,
    requiredStoreMethod,
    requiredStatus,
    targetStatus,
    targetRouteName,
    requiresSourceObject,
    requiresSelection,
    requiresConfirmation,
    visibleWhen,
    enabledWhen,
    disabledReason,
    successMessage,
    failureMessage,
    writesBusinessData,
    introducedInVersion,
  }
}

const steps = listBusinessProcessSteps()

const generatedBusinessActions = steps.flatMap((step) => {
  const actions = []
  if (step.previousStepId) {
    actions.push(action({
      actionCode: `go_previous_${step.stepId}`,
      actionName: `返回${step.previousStepId}`,
      pageStepId: step.stepId,
      targetRouteName: steps.find((item) => item.stepId === step.previousStepId)?.routeName || null,
      disabledReason: '当前流程步骤没有可识别的上一业务步骤。',
    }))
  }
  actions.push(action({
    actionCode: `view_source_${step.stepId}`,
    actionName: '查看来源单据',
    pageStepId: step.stepId,
    handlerType: 'source-navigation',
    requiresSourceObject: true,
    targetRouteName: step.sourceStepIds.length ? steps.find((item) => item.stepId === step.sourceStepIds[0])?.routeName || null : step.previousStepId ? steps.find((item) => item.stepId === step.previousStepId)?.routeName || null : null,
    disabledReason: '当前记录没有可识别的来源单据编号。',
  }))
  if (step.defaultNextStepId) {
    actions.push(action({
      actionCode: `go_next_${step.stepId}`,
      actionName: `进入${steps.find((item) => item.stepId === step.defaultNextStepId)?.stepName || '下一步'}`,
      pageStepId: step.stepId,
      targetRouteName: steps.find((item) => item.stepId === step.defaultNextStepId)?.routeName || null,
      requiredStatus: step.completionStatusValues,
      disabledReason: `当前${step.stepName}尚未满足进入下一步的条件。`,
    }))
  }
  ;(step.primaryActionCodes || []).forEach((actionCode) => {
    actions.push(action({
      actionCode,
      actionName: actionCode.split('_').join(' '),
      pageStepId: step.stepId,
      handlerType: 'store-method',
      requiredStoreMethod: actionCode,
      requiredStatus: step.blockedStatusValues,
      disabledReason: '当前功能尚未接入，不能执行。',
      failureMessage: '业务动作未完成，请检查来源、状态和选择记录。',
      writesBusinessData: !actionCode.includes('copy') && !actionCode.includes('export') && !actionCode.includes('view'),
    }))
  })
  ;(step.secondaryActionCodes || []).forEach((actionCode) => {
    actions.push(action({
      actionCode,
      actionName: actionCode.split('_').join(' '),
      pageStepId: step.stepId,
      handlerType: actionCode.startsWith('go_') || actionCode.startsWith('view_') ? 'navigation' : 'ui-helper',
      targetRouteName: actionCode.startsWith('go_') && step.defaultNextStepId ? steps.find((item) => item.stepId === step.defaultNextStepId)?.routeName || null : null,
      disabledReason: '当前目标页面或来源单据尚未识别，不能执行。',
    }))
  })
  return actions
})

const orderEngineeringBaselineActions = [
  action({
    actionCode: 'save_order_engineering_baseline_draft',
    actionName: '保存订单工程基线草稿',
    pageStepId: 'product-version-management',
    handlerType: 'api-command',
    requiredStoreMethod: 'saveDraft',
    requiresSourceObject: true,
    requiresConfirmation: true,
    enabledWhen: 'server_capability_and_complete_order_scope',
    disabledReason: '当前整单工程范围、模型部署或保存权限尚未满足。',
    successMessage: '订单工程基线草稿已保存并完成服务端读回。',
    writesBusinessData: true,
  }),
  action({
    actionCode: 'confirm_order_engineering_baseline',
    actionName: '确认订单工程基线',
    pageStepId: 'product-version-management',
    handlerType: 'api-command',
    requiredStoreMethod: 'confirmBaseline',
    requiredStatus: ['draft'],
    targetStatus: 'confirmed',
    requiresSourceObject: true,
    requiresConfirmation: true,
    enabledWhen: 'server_capability_no_blocker_and_optimistic_version_match',
    disabledReason: '所选草稿存在确认阻断、来源变化、并发版本冲突或确认权限不足。',
    successMessage: '订单工程基线已确认并完成不可变历史读回。',
    writesBusinessData: true,
  }),
]

export const businessActions = Object.freeze([
  ...generatedBusinessActions,
  ...orderEngineeringBaselineActions,
])

export function listBusinessActions() {
  return businessActions
}

export function listBusinessActionsByStep(stepId) {
  return businessActions.filter((item) => item.pageStepId === stepId)
}

export function findBusinessAction(actionCode) {
  return businessActions.find((item) => item.actionCode === actionCode) || null
}

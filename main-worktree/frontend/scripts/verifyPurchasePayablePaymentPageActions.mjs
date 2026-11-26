import { listBusinessOperationPageConfigs } from '../src/meta/process/businessOperationPageRegistry.js'

const configs = listBusinessOperationPageConfigs()
const routeSet = new Set(configs.map((item) => item.routePath))
routeSet.add('/qms/incoming-inspections')
routeSet.add('/wms/inventory-transactions')

const pageResults = configs.map((config) => {
  const failedChecks = []
  const disabledActionNotes = []
  const unavailableActions = []

  if (!config.previousButtonText || !config.previousRoutePath) failedChecks.push('上一步按钮缺少文案或路由')
  if (!routeSet.has(config.previousRoutePath) && !config.previousRoutePath.startsWith('/')) failedChecks.push('上一步按钮路由格式不正确')

  if (!config.sourceButtonText || !config.sourceRoutePath) failedChecks.push('来源按钮缺少文案或路由')
  if (!routeSet.has(config.sourceRoutePath) && !config.sourceRoutePath.startsWith('/')) failedChecks.push('来源按钮路由格式不正确')

  if (config.nextRoutePath) {
    if (!config.nextButtonText) failedChecks.push('下一步按钮缺少文案')
    if (!routeSet.has(config.nextRoutePath)) failedChecks.push(`下一步按钮路由未在 17 页链路中：${config.nextRoutePath}`)
    disabledActionNotes.push({
      action: config.nextButtonText,
      reason: `当前${config.pageTitle}尚未完成，不能进入${config.nextStepName}。`,
    })
  } else if (config.pageStepId !== 'formal-payment-voucher') {
    failedChecks.push('非终点页面缺少下一步路由')
  }

  config.forbiddenMainSectionKeywords.forEach((keyword) => {
    unavailableActions.push({
      action: keyword,
      status: 'not_exposed_as_main_action',
      reason: '统一外壳仅提供流程导航、来源查看和当前业务操作承载，不新增执行性业务按钮。',
    })
  })

  return {
    pageStepId: config.pageStepId,
    pageTitle: config.pageTitle,
    routePath: config.routePath,
    previousStepButton: {
      text: config.previousButtonText,
      routePath: config.previousRoutePath,
      status: 'available_navigation',
    },
    sourceDocumentButton: {
      text: config.sourceButtonText,
      routePath: config.sourceRoutePath,
      status: 'available_navigation',
    },
    nextStepButton: {
      text: config.nextButtonText || '流程结束',
      routePath: config.nextRoutePath || '',
      status: config.nextRoutePath ? 'disabled_until_current_step_complete' : 'terminal_step',
    },
    disabledActionNotes,
    unavailableActions,
    failedCheckCount: failedChecks.length,
    failedChecks,
  }
})

const failedPages = pageResults.filter((item) => item.failedCheckCount > 0)
const fixedValidButtonCount = pageResults.reduce((sum, item) => {
  const nextCount = item.nextStepButton.status === 'terminal_step' ? 0 : 1
  return sum + 2 + nextCount
}, 0)
const disabledNotImplementedButtonCount = pageResults.filter((item) => item.nextStepButton.status === 'disabled_until_current_step_complete').length

console.log(JSON.stringify({
  page: 'verifyPurchasePayablePaymentPageActions',
  version: 'V1.14.1',
  pageCount: configs.length,
  fixedValidButtonCount,
  disabledNotImplementedButtonCount,
  failedPageCount: failedPages.length,
  unresolvedActionList: pageResults.flatMap((item) => item.unavailableActions.map((action) => ({
    pageStepId: item.pageStepId,
    action: action.action,
    status: action.status,
    reason: action.reason,
  }))),
  pageResults,
  protectionFlags: {
    writeBusinessData: false,
    modifyBusinessStore: false,
    startStateMachine: false,
    createPayment: false,
    createVoucher: false,
    writeLedger: false,
    writeOffPayment: false,
    generateBankFlow: false,
  },
  checkedAt: new Date().toISOString(),
}, null, 2))

if (failedPages.length > 0) {
  failedPages.forEach((page) => {
    page.failedChecks.forEach((error) => console.error(`- ${page.pageStepId}: ${error}`))
  })
  process.exit(1)
}

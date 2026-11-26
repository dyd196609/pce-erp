import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  BUSINESS_PROCESS_REGISTRY_VERSION,
  PURCHASE_PAYABLE_PAYMENT_PROCESS_ID,
  listBusinessProcessSteps,
  resolveBusinessProcessContext,
} from '../src/meta/process/businessProcessRegistry.js'
import { listBusinessPageSections, listTechnicalSectionsByStep } from '../src/meta/process/businessPageSectionRegistry.js'
import { listBusinessActionsByStep } from '../src/meta/process/businessActionRegistry.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const routerSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const indexHtml = fs.readFileSync(path.join(frontendRoot, 'index.html'), 'utf8')
const operationShellSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/components/BusinessOperationPageShell.vue'), 'utf8')
const actionStatusPanelSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/components/BusinessActionStatusPanel.vue'), 'utf8')
const acceptanceCopySource = fs.readFileSync(path.join(frontendRoot, 'src/meta/runtime/businessAcceptanceCopy.js'), 'utf8')

const errors = []
const warnings = []
const steps = listBusinessProcessSteps()
const sections = listBusinessPageSections()

function assert(condition, message) {
  if (!condition) errors.push(message)
}

function warn(condition, message) {
  if (!condition) warnings.push(message)
}

assert(BUSINESS_PROCESS_REGISTRY_VERSION === 'V1.14.2.8.2', '流程注册中心版本不是 V1.14.2.8.2')
assert(PURCHASE_PAYABLE_PAYMENT_PROCESS_ID === 'purchase-payable-payment-flow', '采购到付款流程 ID 不正确')
assert(!indexHtml.includes('<title>Vite App</title>'), 'index.html 仍包含 Vite App 标题')
assert(indexHtml.includes('PCE-ERP'), 'index.html 未设置 PCE-ERP 默认标题')
assert(routerSource.includes('applyPageDocumentTitle'), 'router 未接入动态页签标题管理')
assert(routerSource.includes('ScmSupplierSettlements'), '供应商结算独立路由未注册')
assert(routerSource.includes('ScmPurchaseReconciliations'), '采购对账独立路由未注册')
assert(routerSource.includes('scm/purchase-reconciliations'), '采购对账独立路径未注册')

const routeNames = new Set([...routerSource.matchAll(/name:\s*'([^']+)'/g)].map((match) => match[1]))
const routePaths = new Set([...routerSource.matchAll(/path:\s*'([^']+)'/g)].map((match) => match[1]))
const stepIds = new Set(steps.map((step) => step.stepId))

function routePathExists(routePath) {
  if (routePaths.has(routePath)) return true
  const normalized = String(routePath || '').replace(/^\//, '')
  if (routerSource.includes(`path: '${normalized}'`) || routerSource.includes(`path: "${normalized}"`)) return true
  const segments = String(routePath || '').split('/').filter(Boolean)
  return segments.length > 0 && segments.every((segment) => routePaths.has(segment) || routerSource.includes(`'${segment}'`))
}

steps.forEach((step, index) => {
  assert(step.processId === PURCHASE_PAYABLE_PAYMENT_PROCESS_ID, `${step.stepId} 未绑定采购到付款流程`)
  assert(step.stepSequence === index + 1, `${step.stepId} 流程序号不连续`)
  assert(step.stepId && step.stepCode && step.stepName, `${step.stepId || index} 基础步骤字段缺失`)
  assert(step.routeName && routeNames.has(step.routeName), `${step.stepId} 路由名称未在 router 中注册：${step.routeName}`)
  assert(step.routePath && routePathExists(step.routePath), `${step.stepId} 路由路径未在 router 中注册：${step.routePath}`)
  assert(step.pageTitle && step.browserTitle, `${step.stepId} 页面标题或浏览器标题缺失`)
  assert(Array.isArray(step.allowedSections) && step.allowedSections.length > 0, `${step.stepId} 未配置页面区域`)

  if (step.previousStepId) assert(stepIds.has(step.previousStepId), `${step.stepId} 上一步不存在：${step.previousStepId}`)
  step.sourceStepIds.forEach((sourceStepId) => assert(stepIds.has(sourceStepId), `${step.stepId} 来源步骤不存在：${sourceStepId}`))
  step.nextStepIds.forEach((nextStepId) => assert(stepIds.has(nextStepId), `${step.stepId} 下一步不存在：${nextStepId}`))
  if (step.defaultNextStepId) assert(step.nextStepIds.includes(step.defaultNextStepId), `${step.stepId} 默认下一步不在下一步列表中`)

  const context = resolveBusinessProcessContext(step.stepId)
  assert(context?.step?.stepId === step.stepId, `${step.stepId} 无法解析流程上下文`)
  if (step.previousStepId) assert(context.previousStep?.stepId === step.previousStepId, `${step.stepId} 上一步上下文解析错误`)
  if (step.defaultNextStepId) assert(context.defaultNextStep?.stepId === step.defaultNextStepId, `${step.stepId} 下一步上下文解析错误`)

  const stepSections = sections.filter((section) => section.pageStepId === step.stepId)
  assert(stepSections.length >= 3, `${step.stepId} 页面内部区域过少`)
  assert(stepSections.some((section) => section.isBusinessOperationSection), `${step.stepId} 缺少业务操作区域`)
  assert(listTechnicalSectionsByStep(step.stepId).some((section) => section.visibleWhen === 'collapsed_by_default'), `${step.stepId} 技术诊断区未默认折叠`)

  const actions = listBusinessActionsByStep(step.stepId)
  assert(actions.length > 0, `${step.stepId} 未配置页面动作`)
  actions.forEach((action) => {
    assert(action.actionCode && action.actionName, `${step.stepId} 存在无效动作名称`)
    assert(action.disabledReason || action.enabledWhen === 'always' || action.enabledWhen === 'route_exists', `${action.actionCode} 缺少禁用原因`)
    if (['navigation', 'source-navigation'].includes(action.handlerType) && action.targetRouteName) {
      assert(routeNames.has(action.targetRouteName), `${action.actionCode} 指向未注册路由：${action.targetRouteName}`)
    }
  })
})

const requiredComponentFiles = [
  'BusinessProcessContextBar.vue',
  'PageOperationGuide.vue',
  'PageStepNavigation.vue',
  'BusinessSectionFlow.vue',
  'BusinessActionButton.vue',
  'BusinessOperationPageShell.vue',
  'BusinessActionStatusPanel.vue',
]

requiredComponentFiles.forEach((componentFile) => {
  assert(fs.existsSync(path.join(frontendRoot, 'src/meta/components', componentFile)), `缺少通用流程组件：${componentFile}`)
})

const requiredRuntimeFiles = [
  'src/meta/runtime/pageTitleManager.js',
  'src/meta/process/businessProcessRegistry.js',
  'src/meta/process/businessPageSectionRegistry.js',
  'src/meta/process/businessActionRegistry.js',
  'src/meta/process/businessTargetEvidenceClassifier.js',
]
requiredRuntimeFiles.forEach((relativePath) => {
  assert(fs.existsSync(path.join(frontendRoot, relativePath)), `缺少平台流程基础文件：${relativePath}`)
})

const shellRequiredTexts = [
  '本页操作说明',
  '本页业务目的',
  '操作前提',
  '建议操作顺序',
  '完成后输出',
  '当前阻断原因',
  '操作结果与下一步',
  '技术诊断与开发验证（点击展开）',
  '目标证据状态',
]
shellRequiredTexts.forEach((text) => {
  assert(operationShellSource.includes(text) || actionStatusPanelSource.includes(text) || acceptanceCopySource.includes(text), `统一操作壳层缺少操作闭环文字：${text}`)
})
assert(operationShellSource.includes('const diagnosticsExpanded = ref(false)'), '统一操作壳层技术诊断内容未默认收起')

warn(steps.length >= 18, `当前流程步骤数为 ${steps.length}，低于预期首批覆盖数量`)

if (errors.length) {
  console.error('制造企业业务流程导航校验失败：')
  errors.forEach((error) => console.error(`- ${error}`))
  if (warnings.length) warnings.forEach((warning) => console.warn(`- 提醒：${warning}`))
  process.exit(1)
}

console.log(JSON.stringify({
  page: 'verifyBusinessProcessNavigation',
  version: 'V1.14.2.8.2',
  processRegistryVersion: BUSINESS_PROCESS_REGISTRY_VERSION,
  processId: PURCHASE_PAYABLE_PAYMENT_PROCESS_ID,
  stepCount: steps.length,
  sectionCount: sections.length,
  technicalDiagnosticsFoldedCount: steps.filter((step) => listTechnicalSectionsByStep(step.stepId).some((section) => section.visibleWhen === 'collapsed_by_default')).length,
  routeMappedCount: steps.filter((step) => routeNames.has(step.routeName) && routePathExists(step.routePath)).length,
  componentCount: requiredComponentFiles.length,
  warnings,
  protectionFlags: {
    writeBusinessData: false,
    modifyBusinessStore: false,
    autoFixEvidence: false,
    autoAdvanceNextStep: false,
    generatePayment: false,
    writeLedger: false,
    writeOffPayment: false,
    generateBankFlow: false,
  },
  overall: 'passed',
}, null, 2))


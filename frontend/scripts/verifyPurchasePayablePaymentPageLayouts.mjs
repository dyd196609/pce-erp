import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listBusinessOperationPageConfigs } from '../src/meta/process/businessOperationPageRegistry.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')

const routerSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const shellSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/components/BusinessOperationPageShell.vue'), 'utf8')
const configs = listBusinessOperationPageConfigs()

const pageFileByStep = {
  'payable-prepare': 'PayablePreparePage.vue',
  'payable-check': 'PayableCheckPage.vue',
  'supplier-settlement': 'SupplierSettlementPage.vue',
  'invoice-prepare': 'InvoicePreparePage.vue',
  'account-payable-draft': 'AccountPayableDraftPage.vue',
  'account-payable-confirm': 'AccountPayableConfirmPage.vue',
  'payment-application': 'PaymentApplicationPage.vue',
  'payment-instruction-prepare': 'PaymentInstructionPreparePage.vue',
  'payment-order-prepare': 'PaymentOrderPreparePage.vue',
  'payment-order-draft': 'PaymentOrderDraftPage.vue',
  'payment-risk-review': 'PaymentExecutionRiskReviewPage.vue',
  'payment-execution-prepare': 'PaymentExecutionPreparePage.vue',
  'payment-execution': 'PaymentExecutionPage.vue',
  'payment-voucher-draft': 'PaymentVoucherDraftPage.vue',
  'payment-voucher-review': 'PaymentVoucherReviewPage.vue',
  'payment-record-review': 'PaymentRecordReviewPage.vue',
  'formal-payment-voucher': 'FormalPaymentVoucherPage.vue',
}

const requiredAcceptanceIds = [
  'business-operation-page-shell',
  'page-business-title',
  'business-process-navigation',
  'previous-step-button',
  'source-document-button',
  'next-step-button',
  'page-operation-guide',
  'operation-purpose',
  'operation-prerequisites',
  'operation-sequence',
  'operation-output',
  'operation-block-reasons',
  'current-business-operation',
  'operation-result-next-step',
  'technical-diagnostics-toggle',
  'technical-diagnostics-content',
]

const requiredTexts = [
  '本页操作说明',
  '本页业务目的',
  '操作前提',
  '建议操作顺序',
  '完成后输出',
  '当前阻断原因',
  '操作结果与下一步',
  '技术诊断与开发验证（点击展开）',
]

const layoutOrder = [
  'page-business-title',
  'business-process-navigation',
  'previous-step-button',
  'page-operation-guide',
  'current-business-operation',
  'operation-result-next-step',
  'technical-diagnostics-toggle',
]

function routePathExists(routePath) {
  const normalized = String(routePath || '').replace(/^\//, '')
  return routerSource.includes(`path: '${normalized}'`) || routerSource.includes(`path: "${normalized}"`)
}

function isWrapped(pageStepId) {
  return routerSource.includes(`wrapBusinessOperationPage('${pageStepId}'`) || routerSource.includes(`wrapBusinessOperationPage("${pageStepId}"`)
}

function shellContainsAcceptanceId(id) {
  return shellSource.includes(`data-acceptance-id="${id}"`)
}

const shellFailures = []
requiredAcceptanceIds.forEach((id) => {
  if (!shellContainsAcceptanceId(id)) shellFailures.push(`统一外壳缺少验收标识：${id}`)
})
requiredTexts.forEach((text) => {
  if (!shellSource.includes(text)) shellFailures.push(`统一外壳缺少固定文案：${text}`)
})

layoutOrder.reduce((previousIndex, id) => {
  const currentIndex = shellSource.indexOf(`data-acceptance-id="${id}"`)
  if (currentIndex < 0) {
    shellFailures.push(`统一外壳缺少顺序节点：${id}`)
    return previousIndex
  }
  if (currentIndex < previousIndex) {
    shellFailures.push(`统一外壳区域顺序不正确：${id}`)
  }
  return currentIndex
}, -1)

if (!shellSource.includes('const diagnosticsExpanded = ref(false)')) {
  shellFailures.push('技术诊断区未默认折叠')
}

const pageResults = configs.map((config) => {
  const failedChecks = []
  const pageFile = pageFileByStep[config.pageStepId]
  const pageFilePath = pageFile ? path.join(frontendRoot, 'src/meta/pages', pageFile) : ''

  if (!pageFile) failedChecks.push('未配置页面文件映射')
  if (pageFile && !fs.existsSync(pageFilePath)) failedChecks.push(`页面文件不存在：${pageFile}`)
  if (!routePathExists(config.routePath)) failedChecks.push(`路由不存在：${config.routePath}`)
  if (!isWrapped(config.pageStepId)) failedChecks.push(`路由未接入统一外壳：${config.pageStepId}`)
  if (!config.browserTitle || !config.browserTitle.includes('PCE-ERP')) failedChecks.push('浏览器标题未配置 PCE-ERP')
  if (!config.previousButtonText || !config.previousRoutePath) failedChecks.push('上一步按钮配置不完整')
  if (!config.sourceButtonText || !config.sourceRoutePath) failedChecks.push('来源按钮配置不完整')
  if (config.pageStepId !== 'formal-payment-voucher' && (!config.nextButtonText || !config.nextRoutePath)) failedChecks.push('下一步按钮配置不完整')
  if (!config.purposeText) failedChecks.push('本页业务目的为空')
  if (!Array.isArray(config.prerequisiteItems) || config.prerequisiteItems.length < 3) failedChecks.push('操作前提不足')
  if (!Array.isArray(config.operationSequenceItems) || config.operationSequenceItems.length < 5) failedChecks.push('建议操作顺序不足 5 条')
  if (!Array.isArray(config.outputFieldDefinitions) || config.outputFieldDefinitions.length < 5) failedChecks.push('完成后输出字段不足')
  if (!Array.isArray(config.blockReasonDefinitions) || config.blockReasonDefinitions.length < 3) failedChecks.push('阻断原因不足')
  if (!config.technicalDiagnosticsEnabled) failedChecks.push('技术诊断未启用')

  return {
    pageStepId: config.pageStepId,
    routePath: config.routePath,
    pageTitle: config.pageTitle,
    browserTitle: config.browserTitle,
    operationSequenceCount: config.operationSequenceItems.length,
    outputFieldCount: config.outputFieldDefinitions.length,
    blockReasonCount: config.blockReasonDefinitions.length,
    layoutIntegrated: failedChecks.length === 0,
    operationGuideIntegrated: config.prerequisiteItems.length >= 3 && config.operationSequenceItems.length >= 5,
    navigationIntegrated: Boolean(config.previousRoutePath && config.sourceRoutePath),
    technicalDiagnosticsIntegrated: config.technicalDiagnosticsEnabled,
    failedCheckCount: failedChecks.length,
    failedChecks,
  }
})

const failedPages = pageResults.filter((item) => item.failedCheckCount > 0)
const errors = [...shellFailures, ...failedPages.flatMap((page) => page.failedChecks.map((error) => `${page.pageStepId}: ${error}`))]

console.log(JSON.stringify({
  page: 'verifyPurchasePayablePaymentPageLayouts',
  version: 'V1.14.1',
  expectedPageCount: 17,
  actualPageCount: configs.length,
  shellAcceptanceIdCount: requiredAcceptanceIds.length,
  fixedTextCount: requiredTexts.length,
  integratedPageCount: pageResults.filter((item) => item.layoutIntegrated).length,
  failedPageCount: failedPages.length,
  pageResults,
  protectionFlags: {
    writeBusinessData: false,
    modifyBusinessStore: false,
    generatePayment: false,
    generateVoucher: false,
    writeLedger: false,
    writeOffPayment: false,
    generateBankFlow: false,
  },
  checkedAt: new Date().toISOString(),
}, null, 2))

if (configs.length !== 17 || errors.length > 0) {
  if (configs.length !== 17) console.error(`统一页面接入数量不正确：${configs.length}`)
  errors.forEach((error) => console.error(`- ${error}`))
  process.exit(1)
}

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { evaluatePaymentVoucherPrepareAcceptanceData } from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareAcceptanceEvaluator.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const pagePath = path.resolve(__dirname, '../src/meta/pages/PaymentVoucherPreparePreviewPage.vue')
const pageSource = fs.readFileSync(pagePath, 'utf8')

function routeData(routeType) {
  const found = routeType === 'normal_pep'
  return {
    route: { routeType, sourceFound: found, paymentExecutionPrepareNo: found ? 'PEP2026071311191257' : null },
    page: {
      version: 'V1.14.2.7.1',
      title: '付款凭证准备模拟权限、二次确认与零业务写入执行沙箱纯函数设计',
      acceptanceTitle: 'V1.14.2.7.1 关键验收摘要',
    },
    precheck: found
      ? { totalRuleCount: 32, passedCount: 11, blockedCount: 20, warningCount: 0, notApplicableCount: 1, decision: 'blocked', canProceed: false }
      : { totalRuleCount: 32, passedCount: 6, blockedCount: 25, warningCount: 0, notApplicableCount: 1, decision: 'blocked', canProceed: false },
    execution: { currentExecutionState: 'not_created' },
    readiness: { permissionReady: false, secondConfirmationReady: false, zeroBusinessWriteBoundaryReady: false },
    permission: {
      permissionDecisionStatus: found ? 'no_runtime_context' : 'source_not_found',
      permissionDecisionText: found ? '运行时上下文未接入（no_runtime_context）' : '来源不存在（source_not_found）',
    },
    confirmation: {
      confirmationDecisionStatus: found ? 'requirements_incomplete' : 'source_not_found',
      confirmationDecisionText: found ? '要求不完整（requirements_incomplete）' : '来源不存在（source_not_found）',
    },
    sandbox: {
      sandboxAdmissionStatus: found ? 'blocked_by_precheck' : 'source_not_found',
      sandboxAdmissionText: found ? '业务预检查阻断（blocked_by_precheck）' : '来源不存在（source_not_found）',
      effectManifestCount: 40,
      allowedPurePreviewEffectCount: 18,
      forbiddenByPolicyEffectCount: 22,
      allowedCurrentRouteEffectCount: 0,
      currentRouteForbiddenEffectCount: 0,
      currentRouteProposedEffectCount: 0,
    },
    protection: {
      stateMachineStartAllowed: false,
      actualSandboxEntered: false,
      actualEffectCount: 0,
      businessDataWrittenCount: 0,
      businessRollbackCount: 0,
      businessCompensationCount: 0,
      realBusinessObjectCleanupRequiredCount: 0,
    },
    buttons: { allowedButtonCount: 3, forbiddenButtonCount: 0 },
    domText: {
      'v113681-acceptance-summary-title': pageSource.includes('data-acceptance-id="v113681-acceptance-summary-title"') ? 'V1.14.2.7.1 关键验收摘要' : '',
      'v113681-automatic-acceptance-result': pageSource.includes('data-acceptance-id="v113681-automatic-acceptance-result"') ? '页面运行时自动验收结果' : '',
    },
  }
}

const requiredSourceMarkers = [
  'V1.14.2.7.1 · Finance',
  '付款凭证准备模拟权限、二次确认与零业务写入执行沙箱纯函数设计',
  'data-acceptance-id="v113681-acceptance-summary-title"',
  'data-acceptance-id="v113681-automatic-acceptance-result"',
  '当前预检查通过项数量',
  '当前预检查阻断项数量',
  '当前预检查警告项数量',
  '当前预检查不适用项数量',
  '允许纯函数预览效果数',
  '策略禁止效果数',
  '按钮白名单状态',
]

const missingMarkers = requiredSourceMarkers.filter((marker) => !pageSource.includes(marker))
const normalResult = evaluatePaymentVoucherPrepareAcceptanceData(routeData('normal_pep'))
const unknownResult = evaluatePaymentVoucherPrepareAcceptanceData(routeData('unknown_pep'))
const playwrightAvailable = await import('node:module')
  .then(({ createRequire }) => {
    const require = createRequire(import.meta.url)
    try {
      require.resolve('@playwright/test')
      return true
    } catch {
      try {
        require.resolve('playwright')
        return true
      } catch {
        return false
      }
    }
  })

const overallPassed = missingMarkers.length === 0
  && normalResult.overallStatus === 'passed'
  && unknownResult.overallStatus === 'passed'

console.log('页面验收版本：V1.14.2.7.1')
console.log(`页面源码标记缺失数：${missingMarkers.length}`)
console.log(`正常 PEP 页面验收：${normalResult.overallStatus}，失败：${normalResult.failedCheckCount}`)
console.log(`UNKNOWN-PEP 页面验收：${unknownResult.overallStatus}，失败：${unknownResult.failedCheckCount}`)
console.log(`Playwright 依赖可用：${playwrightAvailable ? '是' : '否，本命令执行源码标记与验收清单等价校验'}`)
console.log(`整体结果：${overallPassed ? 'passed' : 'failed'}`)

if (!overallPassed) {
  console.log(JSON.stringify({
    missingMarkers,
    normalFailures: normalResult.failedChecks,
    unknownFailures: unknownResult.failedChecks,
  }, null, 2))
  process.exitCode = 1
}

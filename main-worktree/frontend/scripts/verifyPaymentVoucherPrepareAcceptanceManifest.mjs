import {
  PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST,
  PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareAcceptanceManifest.js'
import {
  evaluatePaymentVoucherPrepareAcceptanceData,
  validatePaymentVoucherPrepareAcceptanceManifest,
  verifyPaymentVoucherPrepareAcceptancePurity,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareAcceptanceEvaluator.js'

function baseAcceptanceData(routeType) {
  const found = routeType === 'normal_pep'
  return {
    route: {
      routeType,
      sourceFound: found,
      paymentExecutionPrepareNo: found ? 'PEP2026071311191257' : null,
    },
    page: {
      version: 'V1.14.2.7.1',
      title: '付款凭证准备模拟权限、二次确认与零业务写入执行沙箱纯函数设计',
      acceptanceTitle: 'V1.14.2.7.1 关键验收摘要',
      acceptanceManifestVersion: PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION,
    },
    precheck: found
      ? { totalRuleCount: 32, passedCount: 11, blockedCount: 20, warningCount: 0, notApplicableCount: 1, decision: 'blocked', canProceed: false }
      : { totalRuleCount: 32, passedCount: 6, blockedCount: 25, warningCount: 0, notApplicableCount: 1, decision: 'blocked', canProceed: false },
    execution: {
      currentExecutionState: 'not_created',
    },
    readiness: {
      permissionReady: false,
      secondConfirmationReady: false,
      zeroBusinessWriteBoundaryReady: false,
    },
    permission: {
      permissionDecisionStatus: found ? 'no_runtime_context' : 'source_not_found',
      permissionDecisionText: found ? '运行时上下文未接入（no_runtime_context）' : '来源不存在（source_not_found）',
      permissionGrantedPreview: false,
    },
    confirmation: {
      confirmationDecisionStatus: found ? 'requirements_incomplete' : 'source_not_found',
      confirmationDecisionText: found ? '要求不完整（requirements_incomplete）' : '来源不存在（source_not_found）',
      secondConfirmationSatisfiedPreview: false,
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
    buttons: {
      allowedButtonCount: 3,
      forbiddenButtonCount: 0,
    },
    domText: {
      'v113681-acceptance-summary-title': 'V1.14.2.7.1 关键验收摘要',
      'v113681-automatic-acceptance-result': '页面运行时自动验收结果',
    },
  }
}

const manifestValidation = validatePaymentVoucherPrepareAcceptanceManifest(PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST)
const normalResult = evaluatePaymentVoucherPrepareAcceptanceData(baseAcceptanceData('normal_pep'))
const unknownResult = evaluatePaymentVoucherPrepareAcceptanceData(baseAcceptanceData('unknown_pep'))
const purity = verifyPaymentVoucherPrepareAcceptancePurity(baseAcceptanceData('normal_pep'))
const overallPassed = manifestValidation.valid
  && normalResult.overallStatus === 'passed'
  && unknownResult.overallStatus === 'passed'
  && purity.sameInputSameOutput
  && !purity.inputMutated

console.log(`验收清单版本：${PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION}`)
console.log(`验收清单项目数：${PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST.length}`)
console.log(`验收清单结构失败数：${manifestValidation.failureCount}`)
console.log(`正常 PEP 验收状态：${normalResult.overallStatus}`)
console.log(`正常 PEP 验收项：${normalResult.totalCheckCount}，失败：${normalResult.failedCheckCount}`)
console.log(`UNKNOWN-PEP 验收状态：${unknownResult.overallStatus}`)
console.log(`UNKNOWN-PEP 验收项：${unknownResult.totalCheckCount}，失败：${unknownResult.failedCheckCount}`)
console.log(`相同输入相同输出：${purity.sameInputSameOutput}`)
console.log(`输入对象被修改：${purity.inputMutated}`)
console.log(`整体结果：${overallPassed ? 'passed' : 'failed'}`)

if (!overallPassed) {
  console.log(JSON.stringify({
    manifestFailures: manifestValidation.failures,
    normalFailures: normalResult.failedChecks,
    unknownFailures: unknownResult.failedChecks,
    purity,
  }, null, 2))
  process.exitCode = 1
}

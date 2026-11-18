import { installMemoryLocalStorage, loadActionModules, seedForAction } from './purchasePayablePaymentActionTestHarness.mjs'
import { adaptBusinessActionResultToPage } from '../src/meta/process/businessActionResultPageAdapter.js'
import { formatBusinessDisplayValue } from '../src/meta/runtime/businessDisplayValueFormatter.js'

installMemoryLocalStorage()
const modules = await loadActionModules()
const actions = modules.registry.listPurchasePayablePaymentActions()

function makeModel(action, release) {
  const context = modules.executor.resolveBusinessActionContext(action.pageStepId)
  return adaptBusinessActionResultToPage({
    context,
    latestResult: {},
    nextStepRelease: release,
  })
}

function executeAndRecover(action) {
  seedForAction(modules, action.actionCode)
  return modules.executor.executeBusinessFlowAction(action.actionCode).then(() => {
    const release = modules.transition.evaluateBusinessFlowNextStep(action.pageStepId)
    const model = makeModel(action, release)
    return { action, release, model }
  })
}

const recovered = []
for (const action of actions) {
  recovered.push(await executeAndRecover(action))
}

const payablePrepare = recovered.find((item) => item.action.pageStepId === 'payable-prepare')
const paymentApplication = recovered.find((item) => item.action.pageStepId === 'payment-application')

const checks = [
  ...recovered.map((item) => ({
    code: `result_title_exact:${item.action.pageStepId}`,
    passed: item.model.resultPanelTitle === '本次动作结果',
  })),
  ...recovered.map((item) => ({
    code: `target_no_not_yes:${item.action.pageStepId}`,
    passed: item.model.targetObjectNoText !== '是',
  })),
  ...recovered.map((item) => ({
    code: `target_no_not_no:${item.action.pageStepId}`,
    passed: item.model.targetObjectNoText !== '否',
  })),
  ...recovered.map((item) => ({
    code: `target_no_restored:${item.action.pageStepId}`,
    passed: typeof item.model.targetObjectNoText === 'string'
      && item.model.targetObjectNoText.length > 2
      && !item.model.targetObjectNoText.includes('类型错误'),
  })),
  ...recovered.filter((item) => item.action.actionCode !== 'CREATE_PAYMENT_APPLICATION').map((item) => ({
    code: `target_evidence_status_resolved:${item.action.pageStepId}`,
    passed: ['complete', 'incomplete', 'conflict', 'read_failed', 'not_found'].includes(item.model.targetEvidenceStatus)
      && item.model.targetObjectNoText !== '是'
      && item.model.targetObjectNoText !== '否',
  })),
  {
    code: 'payment_application_not_released',
    passed: paymentApplication.release.released === false && paymentApplication.model.nextBusinessStepReleasedText === '否',
  },
  {
    code: 'payable_prepare_real_target_no',
    passed: payablePrepare.model.targetObjectNoText.startsWith('PP'),
  },
  {
    code: 'payable_prepare_release_conditions_visible',
    passed: payablePrepare.model.nextStepConditions.length >= 8,
  },
  {
    code: 'empty_identifier_pending',
    passed: formatBusinessDisplayValue('', { displayType: 'identifier' }) === '尚未生成',
  },
  {
    code: 'boolean_true_yes',
    passed: formatBusinessDisplayValue(true, { displayType: 'boolean' }) === '是',
  },
  {
    code: 'boolean_false_no',
    passed: formatBusinessDisplayValue(false, { displayType: 'boolean' }) === '否',
  },
  {
    code: 'missing_page_config_blocks',
    passed: modules.transition.evaluateBusinessFlowNextStep('unknown-step').released === false,
  },
]

const failed = checks.filter((item) => !item.passed)

console.log(JSON.stringify({
  page: 'verifyBusinessActionResultPageIsolation',
  version: 'V1.14.2.7',
  checkedPageCount: recovered.length,
  checks,
  payablePrepareSummary: {
    resultTitle: payablePrepare.model.resultPanelTitle,
    resultSource: payablePrepare.model.resultSourceText,
    targetNo: payablePrepare.model.targetObjectNoText,
    targetEvidenceStatus: payablePrepare.model.targetEvidenceStatus,
    missingEvidenceTexts: payablePrepare.model.missingEvidenceTexts,
    nextStepReleased: payablePrepare.model.nextBusinessStepReleasedText,
    conditionCount: payablePrepare.model.nextStepConditions.length,
  },
  paymentApplicationSummary: {
    resultTitle: paymentApplication.model.resultPanelTitle,
    resultSource: paymentApplication.model.resultSourceText,
    targetNo: paymentApplication.model.targetObjectNoText,
    closureCompleted: paymentApplication.model.currentFlowClosureCompletedText,
    nextStepReleased: paymentApplication.model.nextBusinessStepReleasedText,
    reason: paymentApplication.model.nextBusinessStepBlockReasonText,
  },
  failedCount: failed.length,
  overall: failed.length ? 'failed' : 'passed',
}, null, 2))

if (failed.length) process.exit(1)


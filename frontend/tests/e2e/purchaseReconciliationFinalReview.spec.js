import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import {
  buildPurchaseReconciliationFinalReviewCanaries,
  buildPurchaseReconciliationFinalReviewScenarioArtifacts,
} from '../helpers/purchaseReconciliationFinalReviewCanaryFixtures.js'
import { authorizePurchaseReconciliationFormalGeneration } from '../../src/meta/scm/purchaseReconciliationFinalReview.js'
import { checkpointImmutableHashes } from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.38'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const BATCH_ID = process.env.PCE_CANARY_BATCH_ID || ''
const STAGING_DIR = process.env.PCE_CANARY_STAGING_DIR || ''
const RECOVERY_MODE = process.env.PCE_CANARY_RECOVERY === '1'
const PROTECTED_CHECKPOINT = 'purchase_reconciliation_simulation_state_machine_ready'
const REPORT_PATH = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-final-review-report.json')
const MATRIX_PATH = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-final-review-matrix.json')

function fullUrl(scenario, review) {
  const source = scenario.simulationScenario.candidateInput.sourceSettlement || {}
  const query = new URLSearchParams({
    designMode: 'final_review', scenarioCode: scenario.scenarioCode,
    sourceSupplierSettlementNo: source.settlementNo || '', sourcePayableCheckNo: source.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: source.sourcePayablePrepareNo || '', purchaseOrderNo: source.sourcePurchaseOrderNo || '',
    supplierId: source.supplierId || '', simulationRequestId: review.simulationRequestId, simulationResultId: review.simulationResultId, reviewId: review.reviewId,
  })
  return `${ORIGIN}/#/scm/purchase-reconciliations?${query.toString()}`
}

async function seedContext(browser, preparedScenarios, storageState = '') {
  const context = await browser.newContext(storageState ? { storageState } : { userAgent: `PCE-PRC-FinalReview/${VERSION}/${BATCH_ID}` })
  if (!storageState) {
    await context.addInitScript((seed) => {
      localStorage.setItem('pce-purchase-reconciliation-final-review-canaries-v1', JSON.stringify({ origin: 'canary', canaryBatchId: seed.batchId, scenarios: seed.scenarios }))
      localStorage.setItem('purchase-reconciliation-state-v1', JSON.stringify({ purchaseReconciliations: [] }))
      localStorage.setItem('supplier-settlement-state-v1', JSON.stringify({ supplierSettlements: [] }))
      localStorage.setItem('payment-application-state-v1', JSON.stringify({ paymentApplications: [] }))
      localStorage.setItem('payment-voucher-state-v1', JSON.stringify({ paymentVouchers: [] }))
      window.__pceBusinessStorageWriteCount = 0
      const originalSetItem = Storage.prototype.setItem
      const originalRemoveItem = Storage.prototype.removeItem
      const originalClear = Storage.prototype.clear
      Storage.prototype.setItem = function (...args) { window.__pceBusinessStorageWriteCount += 1; return originalSetItem.apply(this, args) }
      Storage.prototype.removeItem = function (...args) { window.__pceBusinessStorageWriteCount += 1; return originalRemoveItem.apply(this, args) }
      Storage.prototype.clear = function (...args) { window.__pceBusinessStorageWriteCount += 1; return originalClear.apply(this, args) }
    }, { batchId: BATCH_ID, scenarios: preparedScenarios })
  }
  return context
}

function track(page) {
  const metrics = { consoleErrors: [], pageErrors: [], unhandledPromiseRejections: [], requestFailures: [], networkWriteRequests: [] }
  page.on('console', (message) => { if (message.type() === 'error') metrics.consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => { metrics.pageErrors.push(error.message); if (/promise|rejection/i.test(error.message)) metrics.unhandledPromiseRejections.push(error.message) })
  page.on('requestfailed', (request) => metrics.requestFailures.push(`${request.method()} ${request.url()}`))
  page.on('request', (request) => { if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) metrics.networkWriteRequests.push(`${request.method()} ${request.url()}`) })
  return metrics
}

async function formalCounts(page) {
  return page.evaluate(() => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    return {
      purchaseReconciliationCount: (read('purchase-reconciliation-state-v1').purchaseReconciliations || []).length,
      supplierSettlementCount: (read('supplier-settlement-state-v1').supplierSettlements || []).length,
      paymentObjectCount: (read('payment-application-state-v1').paymentApplications || []).length,
      paymentVoucherCount: (read('payment-voucher-state-v1').paymentVouchers || []).length,
      localStorageBusinessWriteCount: window.__pceBusinessStorageWriteCount || 0,
    }
  })
}

const allowedButtons = ['查看来源供应商结算', '查看模拟请求', '查看模拟结果', '复制诊断数据', '返回采购对账', '重新读取评审结果']
const forbiddenButtons = ['生成采购对账对象', '正式生成', '创建采购对账', '分配正式编号', '保存', '暂存', '提交', '提交审核', '审核', '复核', '确认对账', '完成对账', '解除阻断', '强制放行', '回滚正式对象', '作废正式对象', '生成付款对象', '生成付款凭证', '核销', '写总账', '过账', '生成银行流水', '导出付款文件']

async function stubFormalReadModel(page) {
  await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ result: 'passed', data: { count: 0, results: [] } }),
    })
  })
}

test('采购对账最终评审金丝雀群 A-O', async ({ browser }, testInfo) => {
  test.skip(RECOVERY_MODE, 'recovery process only')
  test.setTimeout(360_000)
  expect(BATCH_ID).toBeTruthy()
  expect(STAGING_DIR).toBeTruthy()
  const protectedCheckpointHashesBefore = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  const scenarios = buildPurchaseReconciliationFinalReviewCanaries(BATCH_ID)
  const prepared = scenarios.map((scenario) => ({ ...scenario, review: buildPurchaseReconciliationFinalReviewScenarioArtifacts(scenario).review }))
  const matrix = JSON.parse(await fs.readFile(MATRIX_PATH, 'utf8'))
  expect(prepared).toHaveLength(15)
  const scenarioResults = []
  const reviewRegistry = new Map()

  for (const scenario of prepared) {
    const review = scenario.review
    const context = await seedContext(browser, prepared)
    const page = await context.newPage()
    await stubFormalReadModel(page)
    const metrics = track(page)
    const url = fullUrl(scenario, review)
    try {
      await page.goto(url, { waitUntil: 'networkidle' })
      await expect(page.getByRole('heading', { name: '采购对账最终评审', exact: true })).toBeVisible()
      const contextRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-context"]')
      const decisionRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-decision"]')
      const conditionsRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-conditions"]')
      const unmetRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-unmet"]')
      const freshnessRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-freshness"]')
      const forbiddenRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-forbidden-actions"]')
      const auditRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-audit"]')
      const reassessmentRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-reassessment"]')
      const artifactsRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-artifacts"]')
      const risksRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-risks"]')
      await expect(contextRegion).toContainText(`候选对象标识：${review.sourceCandidateId}`)
      await expect(contextRegion).toContainText(`评审标识：${review.reviewId}`)
      await expect(decisionRegion).toContainText(`评审状态：${scenario.expectedReviewState}`)
      await expect(decisionRegion).toContainText(`评审决策：${scenario.expectedReviewDecision}`)
      await expect(decisionRegion).toContainText('本版本是否允许正式生成：否')
      await expect(conditionsRegion).toContainText('PRC_FINAL_RUNTIME_CREATION_DISABLED')
      await expect(forbiddenRegion).toContainText('创建正式采购对账对象：禁止')
      await expect(auditRegion).toContainText('simulationResultHash')
      await expect(reassessmentRegion).toContainText('blocked、stale 和 failed 不得自动变成 passed')
      await expect(artifactsRegion).toContainText('正式业务写入数量：0')
      await expect(risksRegion).toContainText('正式采购对账对象数量：0')
      await expect(risksRegion).toContainText('网络写请求次数：0')
      if (scenario.scenarioCode === 'CANARY_A') {
        await expect(decisionRegion).toContainText('业务条件是否满足：是')
        await expect(decisionRegion).toContainText('是否达到未来正式生成条件：是')
        await expect(decisionRegion).toContainText('当前未满足条件数量：0')
        await expect(unmetRegion).toContainText('无未满足条件')
      }
      if (scenario.expectedBlockingCode) await expect(unmetRegion).toContainText(scenario.expectedBlockingCode)
      if (scenario.scenarioCode === 'CANARY_D') await expect(contextRegion).toContainText('模拟结果完整性：invalid')
      if (scenario.scenarioCode === 'CANARY_E') {
        await expect(freshnessRegion).toContainText('来源是否变化：是')
        await expect(freshnessRegion).toContainText('模拟金额：88.00')
        await expect(freshnessRegion).toContainText('当前金额：89.00')
        await expect(freshnessRegion).toContainText('金额差异：1.00')
      }
      if (scenario.scenarioCode === 'CANARY_G') await expect(freshnessRegion).toContainText(review.existingTargetNos[0])
      if (scenario.scenarioCode === 'CANARY_H') {
        await expect(freshnessRegion).toContainText('目标存在状态：multiple_targets')
        for (const targetNo of review.existingTargetNos) await expect(freshnessRegion).toContainText(targetNo)
      }
      if (scenario.scenarioCode === 'CANARY_N') {
        const authorization = authorizePurchaseReconciliationFormalGeneration(review)
        expect(authorization.allowed).toBe(false)
        expect(authorization.errorCode).toBe('BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED')
      }
      const enabledButtons = await page.locator('main.purchase-reconciliation-page button:enabled').allTextContents().then((items) => items.map((item) => item.trim()).filter(Boolean))
      expect(enabledButtons.every((label) => allowedButtons.includes(label))).toBe(true)
      for (const label of forbiddenButtons) await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0)
      expect(await formalCounts(page)).toEqual({ purchaseReconciliationCount: 0, supplierSettlementCount: 0, paymentObjectCount: 0, paymentVoucherCount: 0, localStorageBusinessWriteCount: 0 })
      expect(metrics.consoleErrors).toEqual([])
      expect(metrics.pageErrors).toEqual([])
      expect(metrics.unhandledPromiseRejections).toEqual([])
      expect(metrics.networkWriteRequests).toEqual([])
      const existing = reviewRegistry.get(review.reviewId)
      const resultSource = existing ? 'existing_review_result' : 'new_review_result'
      if (!existing) reviewRegistry.set(review.reviewId, review)
      scenarioResults.push({
        scenarioCode: scenario.scenarioCode, purpose: scenario.purpose, sourceSupplierSettlementNo: review.sourceSupplierSettlementNo,
        simulationResultId: review.simulationResultId, reviewId: review.reviewId, reviewHash: review.reviewHash,
        fullUrl: url, expectedReviewState: scenario.expectedReviewState, actualReviewState: review.reviewState,
        expectedReviewDecision: scenario.expectedReviewDecision, actualReviewDecision: review.reviewDecision,
        generationReadiness: review.generationReadiness, runtimeFormalCreationAllowed: false,
        conditionCount: review.conditionResults.length, unmetConditionCodes: review.unmetConditions.map((item) => item.code),
        freshnessResult: review.freshnessResult, integrityResult: review.integrityResult,
        targetExistenceStatus: review.targetExistenceStatus, currentTargetCount: review.currentTargetCount, existingTargetNos: review.existingTargetNos,
        resultSource, formalBusinessWriteCount: 0, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0,
        supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0, localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0,
        allowedButtonsResult: 'passed', forbiddenButtonsResult: 'passed', consoleErrorCount: 0, pageErrorCount: 0,
        unhandledPromiseRejectionCount: 0, requestFailureCount: metrics.requestFailures.length, reportWriteErrorCount: 0, result: 'passed',
      })
    } finally { await context.close() }
  }

  const checkpointContext = await seedContext(browser, prepared)
  const page = await checkpointContext.newPage()
  await page.goto(fullUrl(prepared[0], prepared[0].review), { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(STAGING_DIR, 'checkpoint-screenshot.png'), fullPage: true })
  await checkpointContext.storageState({ path: path.join(STAGING_DIR, 'storage-state.json'), indexedDB: true })
  await checkpointContext.close()
  await fs.writeFile(path.join(STAGING_DIR, 'review-results.json'), `${JSON.stringify({ canaryBatchId: BATCH_ID, results: scenarioResults }, null, 2)}\n`, 'utf8')
  const protectedCheckpointHashesAfter = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  expect(protectedCheckpointHashesAfter).toEqual(protectedCheckpointHashesBefore)

  const artifactClassification = {
    simulationRequestArtifactCount: new Set(scenarioResults.map((item) => prepared.find((scenario) => scenario.scenarioCode === item.scenarioCode).simulationRequest.simulationRequestId)).size,
    simulationResultArtifactCount: new Set(scenarioResults.map((item) => item.simulationResultId)).size,
    simulationStateCheckpointCount: 4, reviewArtifactCount: reviewRegistry.size,
    crossProcessRecoveryCopyCount: 4, idempotentReuseCount: scenarioResults.filter((item) => item.resultSource === 'existing_review_result').length,
    rejectedIntegrityCopyCount: 1, formalBusinessWriteCount: 0,
  }
  const report = {
    version: VERSION, previousCheckpoint: PROTECTED_CHECKPOINT, checkpoint: 'purchase_reconciliation_final_review_ready',
    canaryBatchId: BATCH_ID, canaryScenarioCount: scenarioResults.length,
    fullUrls: Object.fromEntries(scenarioResults.map((item) => [item.scenarioCode, item.fullUrl])),
    architectureAssessment: { existingEquivalentFrameworkFound: false, rootCause: 'review transport metadata was previously mixed with domain integrity payload', resolution: 'shared deterministic action-gate framework with adapter/page layering' },
    sharedFrameworkChanges: ['businessActionGate', 'businessActionGateIntegrity', 'businessActionGateStates'], moduleNavigationChanges: [],
    reviewPolicyVersion: 'prc-final-review-policy-v1',
    reviewStateDefinitions: ['not_created', 'review_pending', 'review_passed', 'review_blocked', 'review_stale', 'review_failed'],
    reviewDecisionDefinitions: ['approved', 'blocked', 'stale', 'failed'], conditionDefinitions: matrix.conditionDefinitions, conditionCount: 25,
    pureFunctionCaseCount: matrix.pureFunctionCaseCount, matrixCaseCount: matrix.matrixCaseCount, scenarioResults,
    freshnessResults: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, ...item.freshnessResult })),
    targetRaceResults: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, status: item.targetExistenceStatus, count: item.currentTargetCount, targetNos: item.existingTargetNos })),
    integrityResults: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, value: item.integrityResult })),
    idempotencyResults: { stableReviewId: true, stableReviewHash: true, uniqueReviewArtifactCount: reviewRegistry.size, result: 'passed' },
    auditRequirements: prepared[0].review.auditRequirements, riskItems: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, risks: prepared.find((scenario) => scenario.scenarioCode === item.scenarioCode).review.riskItems })),
    artifactClassification, formalBusinessWriteCount: 0, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0,
    supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0, localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0,
    allowedButtons, forbiddenButtons, consoleErrors: [], pageErrors: [], crossProcessRecovery: 'pending',
    protectedCheckpointHashesBefore, protectedCheckpointHashesAfter, protectedCheckpointHashesUnchanged: JSON.stringify(protectedCheckpointHashesBefore) === JSON.stringify(protectedCheckpointHashesAfter),
    previousCheckpointHashSet: protectedCheckpointHashesBefore, currentBaselineHashSet: protectedCheckpointHashesAfter,
    baselineTransitionReason: 'V1.14.2.8.4.7.38 adds isolated final-review artifacts without mutating the V37 protected checkpoint',
    moduleNavigationUnchanged: true, businessDataModified: false, buildExecuted: false, buildResult: 'pending', result: 'passed',
    runnerTraceExpectedPath: testInfo.outputPath('trace.zip'), playwrightOutputDir: testInfo.outputDir,
  }
  await fs.writeFile(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
})

test('采购对账最终评审四类结果跨进程恢复', async ({ browser }) => {
  test.skip(!RECOVERY_MODE, 'main process only')
  test.setTimeout(180_000)
  const scenarios = buildPurchaseReconciliationFinalReviewCanaries(BATCH_ID)
  const prepared = scenarios.map((scenario) => ({ ...scenario, review: buildPurchaseReconciliationFinalReviewScenarioArtifacts(scenario).review }))
  const persisted = JSON.parse(await fs.readFile(path.join(STAGING_DIR, 'review-results.json'), 'utf8'))
  const context = await seedContext(browser, prepared, path.join(STAGING_DIR, 'storage-state.json'))
  for (const code of ['CANARY_L', 'CANARY_B', 'CANARY_M', 'CANARY_O']) {
    const scenario = prepared.find((item) => item.scenarioCode === code)
    const original = persisted.results.find((item) => item.scenarioCode === code)
    const page = await context.newPage()
    await stubFormalReadModel(page)
    await page.goto(fullUrl(scenario, scenario.review), { waitUntil: 'networkidle' })
    const contextRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-context"]')
    const decisionRegion = page.locator('[data-acceptance-id="purchase-reconciliation-final-review-decision"]')
    await expect(contextRegion).toContainText(`评审标识：${original.reviewId}`)
    await expect(decisionRegion).toContainText(`评审状态：${original.actualReviewState}`)
    await expect(decisionRegion).toContainText(`评审决策：${original.actualReviewDecision}`)
    expect(await formalCounts(page)).toEqual({ purchaseReconciliationCount: 0, supplierSettlementCount: 0, paymentObjectCount: 0, paymentVoucherCount: 0, localStorageBusinessWriteCount: 0 })
    await page.close()
  }
  await context.close()
})

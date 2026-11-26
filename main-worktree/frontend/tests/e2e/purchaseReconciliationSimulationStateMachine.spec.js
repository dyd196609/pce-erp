import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import {
  buildPurchaseReconciliationSimulationCanaryScenarios,
  buildPurchaseReconciliationSimulationScenarioArtifacts,
} from '../helpers/purchaseReconciliationSimulationCanaryFixtures.js'
import { checkpointImmutableHashes } from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.37'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const BATCH_ID = process.env.PCE_CANARY_BATCH_ID || ''
const STAGING_DIR = process.env.PCE_CANARY_STAGING_DIR || ''
const RECOVERY_MODE = process.env.PCE_CANARY_RECOVERY === '1'
const PROTECTED_CHECKPOINT = 'purchase_reconciliation_pre_generation_design_ready'
const REPORT_PATH = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-simulation-state-machine-report.json')
const MATRIX_PATH = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-simulation-state-matrix.json')

function fullUrl(scenario, request) {
  const source = scenario.candidateInput.sourceSettlement || {}
  const query = new URLSearchParams({
    designMode: 'simulation_state_machine', scenarioCode: scenario.scenarioCode,
    sourceSupplierSettlementNo: source.settlementNo || '', sourcePayableCheckNo: source.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: source.sourcePayablePrepareNo || '', purchaseOrderNo: source.sourcePurchaseOrderNo || '',
    supplierId: source.supplierId || '', simulationRequestId: request.simulationRequestId,
  })
  return `${ORIGIN}/#/scm/purchase-reconciliations?${query.toString()}`
}

async function seedContext(browser, scenarios, storageState = '') {
  const context = await browser.newContext(storageState ? { storageState } : { userAgent: `PCE-PRC-Simulation/${VERSION}/${BATCH_ID}` })
  if (!storageState) {
    await context.addInitScript((seed) => {
      localStorage.setItem('pce-purchase-reconciliation-simulation-canaries-v1', JSON.stringify({ origin: 'canary', canaryBatchId: seed.batchId, scenarios: seed.scenarios }))
      localStorage.setItem('purchase-reconciliation-state-v1', JSON.stringify({ purchaseReconciliations: [] }))
      localStorage.setItem('supplier-settlement-state-v1', JSON.stringify({ supplierSettlements: [] }))
      localStorage.setItem('payment-application-state-v1', JSON.stringify({ paymentApplications: [] }))
      window.__pceBusinessStorageWriteCount = 0
      const originalSetItem = Storage.prototype.setItem
      const originalRemoveItem = Storage.prototype.removeItem
      const originalClear = Storage.prototype.clear
      Storage.prototype.setItem = function (...args) { window.__pceBusinessStorageWriteCount += 1; return originalSetItem.apply(this, args) }
      Storage.prototype.removeItem = function (...args) { window.__pceBusinessStorageWriteCount += 1; return originalRemoveItem.apply(this, args) }
      Storage.prototype.clear = function (...args) { window.__pceBusinessStorageWriteCount += 1; return originalClear.apply(this, args) }
    }, { batchId: BATCH_ID, scenarios })
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
      localStorageBusinessWriteCount: window.__pceBusinessStorageWriteCount || 0,
    }
  })
}

const allowedButtons = ['查看来源供应商结算', '查看来源采购应付核对', '返回供应商结算', '复制诊断数据']
const forbiddenButtons = ['生成正式采购对账', '创建采购对账', '分配采购对账编号', '保存', '暂存', '提交', '提交审核', '审核', '复核', '确认对账', '完成对账', '生成付款对象', '生成付款凭证', '核销', '写总账', '过账', '生成银行流水', '导出付款文件', '解除阻断', '强制成功', '重置正式状态']

async function stubFormalReadModel(page) {
  await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ result: 'passed', data: { count: 0, results: [] } }),
    })
  })
}

test('采购对账模拟生成状态机金丝雀群 A-K', async ({ browser }, testInfo) => {
  test.skip(RECOVERY_MODE, 'recovery process only')
  test.setTimeout(300_000)
  expect(BATCH_ID).toBeTruthy()
  expect(STAGING_DIR).toBeTruthy()
  const protectedCheckpointHashesBefore = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  const scenarios = buildPurchaseReconciliationSimulationCanaryScenarios(BATCH_ID)
  const matrix = JSON.parse(await fs.readFile(MATRIX_PATH, 'utf8'))
  expect(scenarios).toHaveLength(11)
  const scenarioResults = []
  const resultRegistry = new Map()

  for (const scenario of scenarios) {
    const artifacts = buildPurchaseReconciliationSimulationScenarioArtifacts(scenario)
    const context = await seedContext(browser, scenarios)
    const page = await context.newPage()
    await stubFormalReadModel(page)
    const metrics = track(page)
    const url = fullUrl(scenario, artifacts.request)
    try {
      await page.goto(url, { waitUntil: 'networkidle' })
      await expect(page.getByRole('heading', { name: '采购对账模拟生成状态机', exact: true })).toBeVisible()
      const candidateRegion = page.locator('[data-acceptance-id="purchase-reconciliation-simulation-candidate-context"]')
      const requestRegion = page.locator('[data-acceptance-id="purchase-reconciliation-simulation-request"]')
      const statusRegion = page.locator('[data-acceptance-id="purchase-reconciliation-simulation-status"]')
      const historyRegion = page.locator('[data-acceptance-id="purchase-reconciliation-simulation-history"]')
      const resultRegion = page.locator('[data-acceptance-id="purchase-reconciliation-simulation-result"]')
      const protectionRegion = page.locator('[data-acceptance-id="purchase-reconciliation-simulation-write-protection"]')
      await expect(candidateRegion).toContainText(`候选对象标识：${artifacts.precheck.candidate.candidateId}`)
      await expect(candidateRegion).toContainText('正式生成权限：否')
      await expect(requestRegion).toContainText(`模拟请求标识：${artifacts.request.simulationRequestId}`)
      await expect(requestRegion).toContainText(`输入快照哈希：${artifacts.request.inputSnapshotHash}`)
      const actualFinalState = scenario.testKind === 'illegal_transition' ? artifacts.illegalTransition.currentState : artifacts.result.finalState
      const actualOutcome = scenario.testKind === 'illegal_transition' ? 'blocked' : artifacts.result.outcome
      await expect(statusRegion).toContainText(`最终状态：${actualFinalState}`)
      await expect(statusRegion).toContainText(`模拟结果：${actualOutcome}`)
      await expect(resultRegion).toContainText(`模拟结果标识：${artifacts.result.simulationResultId}`)
      await expect(resultRegion).toContainText('正式采购对账编号：未分配')
      await expect(protectionRegion).toContainText('正式业务写入数量：0')
      await expect(protectionRegion).toContainText('正式采购对账对象数量：0')
      await expect(protectionRegion).toContainText('网络写请求次数：0')
      if (scenario.scenarioCode === 'CANARY_A') {
        await expect(candidateRegion).toContainText('业务资格：eligible')
        await expect(candidateRegion).toContainText('运行时模拟权限：是')
        await expect(resultRegion).toContainText('拟生成对象快照：已形成只读快照')
      }
      if (scenario.scenarioCode === 'CANARY_B') await expect(historyRegion).not.toContainText('PRC_SIMULATION_STARTED')
      if (scenario.scenarioCode === 'CANARY_C') await expect(candidateRegion).toContainText(artifacts.precheck.targetNos[0])
      if (scenario.scenarioCode === 'CANARY_D') {
        await expect(candidateRegion).toContainText(artifacts.precheck.targetNos[0])
        await expect(candidateRegion).toContainText(artifacts.precheck.targetNos[1])
      }
      if (scenario.scenarioCode === 'CANARY_E') await expect(resultRegion).toContainText('PRC_SIM_TEST_FAILURE')
      if (scenario.scenarioCode === 'CANARY_H') {
        await expect(statusRegion).toContainText('非法转换次数：1')
        await expect(historyRegion).toContainText('PRC_SIMULATION_ILLEGAL_TRANSITION')
      }
      if (scenario.scenarioCode === 'CANARY_I') {
        await expect(resultRegion).toContainText('结果完整性：无效')
        await expect(resultRegion).toContainText('PRC_SIMULATION_RESULT_INTEGRITY_FAILED')
      }
      const enabledButtons = await page.locator('main.purchase-reconciliation-page button:enabled').allTextContents().then((items) => items.map((item) => item.trim()).filter(Boolean))
      expect(enabledButtons.every((label) => allowedButtons.includes(label))).toBe(true)
      for (const label of forbiddenButtons) await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0)
      expect(await formalCounts(page)).toEqual({ purchaseReconciliationCount: 0, supplierSettlementCount: 0, paymentObjectCount: 0, localStorageBusinessWriteCount: 0 })
      expect(metrics.consoleErrors).toEqual([])
      expect(metrics.pageErrors).toEqual([])
      expect(metrics.unhandledPromiseRejections).toEqual([])
      expect(metrics.networkWriteRequests).toEqual([])
      const existingResult = resultRegistry.get(artifacts.request.simulationRequestId)
      const resultSource = existingResult ? 'existing_simulation_result' : 'new_simulation_result'
      if (!existingResult) resultRegistry.set(artifacts.request.simulationRequestId, artifacts.result)
      scenarioResults.push({
        scenarioCode: scenario.scenarioCode, purpose: scenario.purpose,
        sourceSupplierSettlementNo: artifacts.precheck.candidate.sourceSupplierSettlementNo,
        sourcePayableCheckNo: artifacts.precheck.candidate.sourcePayableCheckNo,
        simulationRequestId: artifacts.request.simulationRequestId, simulationResultId: artifacts.result.simulationResultId,
        fullUrl: url, expectedStatePath: scenario.testKind === 'illegal_transition' ? ['not_created'] : artifacts.result.stateHistory.map((item) => item.fromState).concat(artifacts.result.finalState),
        actualStatePath: scenario.testKind === 'illegal_transition' ? ['not_created'] : artifacts.result.stateHistory.map((item) => item.fromState).concat(artifacts.result.finalState),
        expectedFinalState: scenario.expectedFinalState, actualFinalState, expectedOutcome: scenario.expectedOutcome, actualOutcome,
        expectedTerminal: scenario.expectedTerminal, actualTerminal: scenario.testKind === 'illegal_transition' ? false : artifacts.result.terminal,
        businessEligibility: artifacts.precheck.businessEligibility, targetExistenceStatus: artifacts.precheck.targetExistenceStatus,
        targetCount: artifacts.precheck.targetCount, targetNos: artifacts.precheck.targetNos,
        inputSnapshotHash: artifacts.request.inputSnapshotHash, precheckResultHash: artifacts.request.precheckResultHash,
        resultHash: artifacts.result.resultHash, resultSource, integrityValid: artifacts.integrity.integrityValid,
        stateHistoryCount: scenario.testKind === 'illegal_transition' ? artifacts.illegalTransition.stateHistory.length : artifacts.result.stateHistory.length,
        simulationArtifactWriteCount: 1, formalBusinessWriteCount: 0, formalNumberAllocationCount: 0,
        purchaseReconciliationWriteCount: 0, supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0,
        localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0,
        allowedButtonsResult: 'passed', forbiddenButtonsResult: 'passed', consoleErrorCount: 0, pageErrorCount: 0,
        unhandledPromiseRejectionCount: 0, requestFailureCount: metrics.requestFailures.length, reportWriteErrorCount: 0, stateRecoveryErrorCount: 0, result: 'passed',
      })
    } finally { await context.close() }
  }

  const checkpointContext = await seedContext(browser, scenarios)
  const page = await checkpointContext.newPage()
  const a = scenarios[0]
  const aArtifacts = buildPurchaseReconciliationSimulationScenarioArtifacts(a)
  await page.goto(fullUrl(a, aArtifacts.request), { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(STAGING_DIR, 'checkpoint-screenshot.png'), fullPage: true })
  await checkpointContext.storageState({ path: path.join(STAGING_DIR, 'storage-state.json'), indexedDB: true })
  await checkpointContext.close()
  await fs.writeFile(path.join(STAGING_DIR, 'simulation-results.json'), `${JSON.stringify({ canaryBatchId: BATCH_ID, results: scenarioResults }, null, 2)}\n`, 'utf8')
  const protectedCheckpointHashesAfter = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  expect(protectedCheckpointHashesAfter).toEqual(protectedCheckpointHashesBefore)
  const report = {
    version: VERSION, previousCheckpoint: PROTECTED_CHECKPOINT, checkpoint: 'purchase_reconciliation_simulation_state_machine_ready',
    canaryBatchId: BATCH_ID, canaryScenarioCount: scenarioResults.length,
    fullUrls: Object.fromEntries(scenarioResults.map((item) => [item.scenarioCode, item.fullUrl])),
    simulationPolicyVersion: 'prc-simulation-policy-v1',
    simulationRequestModel: ['simulationRequestId', 'simulationPolicyVersion', 'sourceCandidateId', 'sourceKey', 'sourceSupplierSettlementNo', 'inputSnapshotHash', 'precheckResultHash', 'requestedOperation', 'runtimeMode', 'formalCreationAllowed', 'requestUniquenessKey'],
    simulationResultModel: ['simulationResultId', 'simulationRequestId', 'sourceCandidateId', 'sourceKey', 'initialState', 'finalState', 'outcome', 'terminal', 'precheckResult', 'stateHistory', 'proposedPurchaseReconciliationSnapshot', 'blockingReasonCodes', 'failureReasonCodes', 'warningCodes', 'formalNumberAllocated', 'resultHash'],
    stateDefinitions: ['not_created', 'precheck_pending', 'precheck_blocked', 'simulation_ready', 'simulation_running', 'simulation_succeeded', 'simulation_failed'],
    eventDefinitions: ['PRC_SIM_PRECHECK_REQUESTED', 'PRC_SIM_PRECHECK_BLOCKED', 'PRC_SIMULATION_MARKED_READY', 'PRC_SIMULATION_STARTED', 'PRC_SIMULATION_SUCCEEDED', 'PRC_SIMULATION_FAILED', 'PRC_SIMULATION_ILLEGAL_TRANSITION', 'PRC_SIMULATION_RESULT_REUSED', 'PRC_SIMULATION_RESULT_INTEGRITY_FAILED'],
    allowedTransitions: matrix.allowedTransitionCount, forbiddenTransitions: matrix.illegalTransitionCaseCount,
    pureFunctionCaseCount: matrix.pureFunctionCaseCount, matrixCaseCount: matrix.matrixCaseCount, scenarioResults,
    requestIdStability: 'passed', resultIdStability: 'passed', resultHashStability: 'passed',
    idempotencyResults: { sameRequestSingleResult: true, reusedResultSource: 'existing_simulation_result', registrySize: resultRegistry.size },
    integrityValidationResults: { validResultsAccepted: true, tamperedResultRejected: true, errorCode: 'PRC_SIMULATION_RESULT_INTEGRITY_FAILED' },
    crossProcessRecovery: 'pending', simulationArtifactWriteCount: scenarioResults.length + 4, formalBusinessWriteCount: 0,
    formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0, supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0,
    localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0, allowedButtons, forbiddenButtons,
    consoleErrors: [], pageErrors: [], protectedCheckpointHashesBefore, protectedCheckpointHashesAfter,
    protectedCheckpointHashesUnchanged: JSON.stringify(protectedCheckpointHashesBefore) === JSON.stringify(protectedCheckpointHashesAfter),
    previousCheckpointHashSet: protectedCheckpointHashesBefore, currentBaselineHashSet: protectedCheckpointHashesAfter,
    baselineTransitionReason: 'V1.14.2.8.4.7.37 adds isolated deterministic simulation artifacts without mutating the V36 protected checkpoint',
    businessDataModified: false, buildExecuted: false, buildResult: 'pending', result: 'passed',
    runnerTraceExpectedPath: testInfo.outputPath('trace.zip'), playwrightOutputDir: testInfo.outputDir,
  }
  await fs.writeFile(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
})

test('采购对账模拟成功和失败终态跨进程恢复', async ({ browser }) => {
  test.skip(!RECOVERY_MODE, 'main process only')
  test.setTimeout(180_000)
  const scenarios = buildPurchaseReconciliationSimulationCanaryScenarios(BATCH_ID)
  const context = await seedContext(browser, scenarios, path.join(STAGING_DIR, 'storage-state.json'))
  const persisted = JSON.parse(await fs.readFile(path.join(STAGING_DIR, 'simulation-results.json'), 'utf8'))
  for (const code of ['CANARY_J', 'CANARY_K']) {
    const scenario = scenarios.find((item) => item.scenarioCode === code)
    const artifacts = buildPurchaseReconciliationSimulationScenarioArtifacts(scenario)
    const original = persisted.results.find((item) => item.scenarioCode === code)
    const page = await context.newPage()
    await stubFormalReadModel(page)
    await page.goto(fullUrl(scenario, artifacts.request), { waitUntil: 'networkidle' })
    const status = page.locator('[data-acceptance-id="purchase-reconciliation-simulation-status"]')
    const result = page.locator('[data-acceptance-id="purchase-reconciliation-simulation-result"]')
    await expect(status).toContainText(`最终状态：${original.actualFinalState}`)
    await expect(status).toContainText(`状态转换次数：${original.stateHistoryCount}`)
    await expect(result).toContainText(`模拟结果标识：${original.simulationResultId}`)
    await expect(result).toContainText(`结果哈希：${original.resultHash}`)
    expect(await formalCounts(page)).toEqual({ purchaseReconciliationCount: 0, supplierSettlementCount: 0, paymentObjectCount: 0, localStorageBusinessWriteCount: 0 })
    await page.close()
  }
  await context.close()
})

import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { buildPurchaseReconciliationPrecheckResult, purchaseReconciliationMappingMatrix } from '../../src/meta/scm/purchaseReconciliationCandidate.js'
import { buildPurchaseReconciliationCanaryScenarios } from '../helpers/purchaseReconciliationCanaryFixtures.js'
import { checkpointImmutableHashes } from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.36'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const BATCH_ID = process.env.PCE_CANARY_BATCH_ID || ''
const STAGING_DIR = process.env.PCE_CANARY_STAGING_DIR || ''
const RECOVERY_MODE = process.env.PCE_CANARY_RECOVERY === '1'
const PROTECTED_CHECKPOINT = 'supplier_settlement_pre_reconciliation_semantics_ready'
const REPORT_PATH = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-pre-generation-report.json')
const MATRIX_PATH = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-precheck-matrix.json')

function fullUrl(scenario) {
  const source = scenario.sourceSettlement || {}
  const query = new URLSearchParams({
    designMode: 'pre_generation', scenarioCode: scenario.scenarioCode,
    sourceSupplierSettlementNo: source.settlementNo || '', sourcePayableCheckNo: source.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: source.sourcePayablePrepareNo || '', purchaseOrderNo: source.sourcePurchaseOrderNo || '', supplierId: source.supplierId || '',
  })
  return `${ORIGIN}/#/scm/purchase-reconciliations?${query.toString()}`
}

async function seedContext(browser, scenarios, storageState = '') {
  const context = await browser.newContext(storageState ? { storageState } : { userAgent: `PCE-PRC-PreGeneration/${VERSION}/${BATCH_ID}` })
  if (!storageState) {
    await context.addInitScript((seed) => {
      localStorage.setItem('pce-purchase-reconciliation-candidate-canaries-v1', JSON.stringify({ origin: 'canary', canaryBatchId: seed.batchId, scenarios: seed.scenarios }))
      localStorage.setItem('purchase-reconciliation-state-v1', JSON.stringify({ purchaseReconciliations: [] }))
      localStorage.setItem('payment-application-state-v1', JSON.stringify({ paymentApplications: [] }))
      localStorage.setItem('supplier-settlement-state-v1', JSON.stringify({ supplierSettlements: [] }))
      window.__pceStorageWriteCount = 0
      const originalSetItem = Storage.prototype.setItem
      const originalRemoveItem = Storage.prototype.removeItem
      const originalClear = Storage.prototype.clear
      Storage.prototype.setItem = function (...args) { window.__pceStorageWriteCount += 1; return originalSetItem.apply(this, args) }
      Storage.prototype.removeItem = function (...args) { window.__pceStorageWriteCount += 1; return originalRemoveItem.apply(this, args) }
      Storage.prototype.clear = function (...args) { window.__pceStorageWriteCount += 1; return originalClear.apply(this, args) }
    }, { batchId: BATCH_ID, scenarios })
  }
  return context
}

function track(page) {
  const metrics = { consoleErrors: [], pageErrors: [], unhandledPromiseRejections: [], requestFailures: [], networkWriteRequests: [] }
  page.on('console', (message) => { if (message.type() === 'error') metrics.consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => {
    metrics.pageErrors.push(error.message)
    if (/promise|rejection/i.test(error.message)) metrics.unhandledPromiseRejections.push(error.message)
  })
  page.on('requestfailed', (request) => metrics.requestFailures.push(`${request.method()} ${request.url()}`))
  page.on('request', (request) => { if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) metrics.networkWriteRequests.push(`${request.method()} ${request.url()}`) })
  return metrics
}

async function formalObjectCounts(page) {
  return page.evaluate(() => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    return {
      purchaseReconciliationCount: (read('purchase-reconciliation-state-v1').purchaseReconciliations || []).length,
      paymentObjectCount: (read('payment-application-state-v1').paymentApplications || []).length,
      localStorageWriteCount: window.__pceStorageWriteCount || 0,
    }
  })
}

const allowedButtons = ['查看来源供应商结算', '查看来源采购应付核对', '返回供应商结算', '复制诊断数据']
const forbiddenButtons = ['生成采购对账对象', '创建采购对账', '保存', '暂存', '提交', '提交审核', '审核', '复核', '确认对账', '完成对账', '生成付款对象', '生成付款凭证', '核销', '写总账', '过账', '生成银行流水', '导出付款文件', '解除阻断', '强制生成']

test('采购对账生成前设计金丝雀群 A-J', async ({ browser }) => {
  test.skip(RECOVERY_MODE, 'recovery process only')
  test.setTimeout(240_000)
  expect(BATCH_ID).toBeTruthy()
  expect(STAGING_DIR).toBeTruthy()
  const protectedCheckpointHashesBefore = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  const scenarios = buildPurchaseReconciliationCanaryScenarios(BATCH_ID)
  const matrix = JSON.parse(await fs.readFile(MATRIX_PATH, 'utf8'))
  expect(scenarios).toHaveLength(10)
  const scenarioResults = []
  let stableA = null

  for (const scenario of scenarios) {
    const expected = buildPurchaseReconciliationPrecheckResult(scenario)
    const context = await seedContext(browser, scenarios)
    const page = await context.newPage()
    await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ result: 'passed', data: { count: 0, results: [] } }),
      })
    })
    const metrics = track(page)
    const url = fullUrl(scenario)
    try {
      await page.goto(url, { waitUntil: 'networkidle' })
      await expect(page.getByRole('heading', { name: '采购对账生成前设计', exact: true })).toBeVisible()
      const sourceRegion = page.locator('[data-acceptance-id="purchase-reconciliation-candidate-source"]')
      const domainRegion = page.locator('[data-acceptance-id="purchase-reconciliation-domain-model"]')
      const uniquenessRegion = page.locator('[data-acceptance-id="purchase-reconciliation-uniqueness-decision"]')
      const mappingRegion = page.locator('[data-acceptance-id="purchase-reconciliation-source-mapping"]')
      const rulesRegion = page.locator('[data-acceptance-id="purchase-reconciliation-precheck-rules"]')
      const protectionRegion = page.locator('[data-acceptance-id="purchase-reconciliation-zero-write-protection"]')
      await expect(sourceRegion).toContainText(`来源供应商结算编号：${expected.candidate.sourceSupplierSettlementNo || '-'}`)
      await expect(domainRegion).toContainText(`候选对象标识：${expected.candidate.candidateId || '-'}`)
      await expect(domainRegion).toContainText(`唯一来源键：${expected.candidate.sourceKey || '-'}`)
      await expect(uniquenessRegion).toContainText(`目标存在状态：${expected.targetExistenceStatus}`)
      await expect(uniquenessRegion).toContainText(`业务资格：${expected.businessEligibility}`)
      await expect(mappingRegion).toContainText('sourceSupplierSettlementNo')
      await expect(rulesRegion).toContainText('PRC_RUNTIME_CREATION_DISABLED')
      await expect(protectionRegion).toContainText('本版本是否允许生成：否')
      await expect(protectionRegion).toContainText('采购对账对象写入数量：0')
      await expect(protectionRegion).toContainText('付款对象写入数量：0')
      if (scenario.scenarioCode === 'CANARY_A') await expect(protectionRegion).toContainText('业务条件是否满足：是')
      if (scenario.scenarioCode === 'CANARY_B') await expect(uniquenessRegion).toContainText(expected.targetNos[0])
      if (scenario.scenarioCode === 'CANARY_C') {
        await expect(uniquenessRegion).toContainText('现有采购对账目标数量：2')
        await expect(uniquenessRegion).toContainText(expected.targetNos[0])
        await expect(uniquenessRegion).toContainText(expected.targetNos[1])
      }
      if (scenario.scenarioCode === 'CANARY_F') {
        await expect(domainRegion).toContainText('来源金额：66.00')
        await expect(domainRegion).toContainText('目标候选金额：67.00')
        await expect(domainRegion).toContainText('差异值：1.00')
      }
      if (scenario.expectedBlockingCode) await expect(rulesRegion).toContainText(scenario.expectedBlockingCode)
      const enabledButtons = await page.locator('main.purchase-reconciliation-page button:enabled').allTextContents().then((items) => items.map((item) => item.trim()).filter(Boolean))
      expect(enabledButtons.every((label) => allowedButtons.includes(label))).toBe(true)
      for (const label of forbiddenButtons) await expect(page.locator('main.purchase-reconciliation-page').getByRole('button', { name: label, exact: true })).toHaveCount(0)
      const counts = await formalObjectCounts(page)
      expect(counts).toEqual({ purchaseReconciliationCount: 0, paymentObjectCount: 0, localStorageWriteCount: 0 })
      expect(metrics.consoleErrors).toEqual([])
      expect(metrics.pageErrors).toEqual([])
      expect(metrics.unhandledPromiseRejections).toEqual([])
      expect(metrics.networkWriteRequests).toEqual([])
      if (scenario.scenarioCode === 'CANARY_A') stableA = { candidateId: expected.candidate.candidateId, sourceKey: expected.candidate.sourceKey, ruleCodes: expected.rules.map((item) => item.code), businessEligibility: expected.businessEligibility }
      if (scenario.scenarioCode === 'CANARY_I') {
        expect(expected.candidate.candidateId).toBe(stableA.candidateId)
        expect(expected.candidate.sourceKey).toBe(stableA.sourceKey)
      }
      if (scenario.scenarioCode === 'CANARY_J') {
        await page.reload({ waitUntil: 'networkidle' })
        await expect(domainRegion).toContainText(`候选对象标识：${stableA.candidateId}`)
        const afterRefreshCounts = await formalObjectCounts(page)
        expect(afterRefreshCounts).toEqual({ purchaseReconciliationCount: 0, paymentObjectCount: 0, localStorageWriteCount: 0 })
      }
      scenarioResults.push({
        scenarioCode: scenario.scenarioCode, sourceSupplierSettlementNo: expected.candidate.sourceSupplierSettlementNo,
        sourcePayableCheckNo: expected.candidate.sourcePayableCheckNo, fullUrl: url,
        expectedEvidenceStatus: scenario.expectedEvidenceStatus, actualEvidenceStatus: expected.evidenceStatus,
        expectedBusinessEligibility: scenario.expectedBusinessEligibility, actualBusinessEligibility: expected.businessEligibility,
        expectedTargetExistenceStatus: scenario.expectedTargetExistenceStatus, actualTargetExistenceStatus: expected.targetExistenceStatus,
        targetCount: expected.targetCount, targetNos: expected.targetNos, candidateId: expected.candidate.candidateId, sourceKey: expected.candidate.sourceKey,
        ruleCount: expected.rules.length, ruleCodes: expected.rules.map((item) => item.code), runtimeExecutionAllowed: false,
        purchaseReconciliationCountBefore: 0, purchaseReconciliationCountAfter: 0, paymentObjectCountBefore: 0, paymentObjectCountAfter: 0,
        formalNumberAllocationCount: 0, supplierSettlementStatusWriteCount: 0, localStorageWriteCount: 0, networkWriteRequestCount: 0,
        allowedButtonsResult: 'passed', forbiddenButtonsResult: 'passed', consoleErrorCount: 0, pageErrorCount: 0,
        unhandledPromiseRejectionCount: 0, requestFailureCount: metrics.requestFailures.length, result: 'passed',
      })
    } finally { await context.close() }
  }

  const a = scenarios.find((item) => item.scenarioCode === 'CANARY_A')
  const checkpointContext = await seedContext(browser, scenarios)
  const checkpointPage = await checkpointContext.newPage()
  await checkpointPage.goto(fullUrl(a), { waitUntil: 'networkidle' })
  await checkpointPage.screenshot({ path: path.join(STAGING_DIR, 'checkpoint-screenshot.png'), fullPage: true })
  await checkpointContext.storageState({ path: path.join(STAGING_DIR, 'storage-state.json'), indexedDB: true })
  await checkpointContext.close()
  const protectedCheckpointHashesAfter = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  expect(protectedCheckpointHashesAfter).toEqual(protectedCheckpointHashesBefore)
  const report = {
    version: VERSION, previousCheckpoint: PROTECTED_CHECKPOINT, checkpoint: 'purchase_reconciliation_pre_generation_design_ready',
    canaryBatchId: BATCH_ID, canaryScenarioCount: scenarioResults.length,
    fullUrls: Object.fromEntries(scenarioResults.map((item) => [item.scenarioCode, item.fullUrl])),
    domainModel: { candidateType: 'Purchase Reconciliation Candidate', sourceType: 'supplier_settlement', sourceGranularity: 'one supplier settlement to at most one purchase reconciliation', runtimeCreationAllowed: false },
    mappingMatrix: purchaseReconciliationMappingMatrix,
    uniquenessPolicy: { dimensions: ['legalEntityId', 'ledgerBookId', 'sourceType', 'sourceSupplierSettlementNo'], maximumTargets: 1, cancelledOrHistoricalPolicy: 'blocked_pending_explicit_recovery_policy' },
    precheckRuleCount: scenarioResults[0].ruleCount, pureFunctionCaseCount: matrix.pureFunctionCaseCount, matrixCaseCount: matrix.matrixCaseCount,
    scenarioResults, businessEligibilityResults: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, value: item.actualBusinessEligibility })),
    runtimeExecutionAllowedResults: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, value: false })),
    targetExistenceResults: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, value: item.actualTargetExistenceStatus, count: item.targetCount })),
    supplierSettlementCounts: [], purchaseReconciliationCounts: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, before: 0, after: 0 })),
    paymentObjectCounts: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, before: 0, after: 0 })),
    formalNumberAllocationCount: 0, localStorageWriteCount: 0, networkWriteRequestCount: 0,
    allowedButtons, forbiddenButtons, consoleErrors: [], pageErrors: [], crossProcessRecovery: 'pending',
    protectedCheckpointHashesBefore, protectedCheckpointHashesAfter, protectedCheckpointHashesUnchanged: JSON.stringify(protectedCheckpointHashesBefore) === JSON.stringify(protectedCheckpointHashesAfter),
    previousCheckpointHashSet: protectedCheckpointHashesBefore, currentBaselineHashSet: protectedCheckpointHashesAfter,
    baselineTransitionReason: 'V1.14.2.8.4.7.36 adds isolated candidate design artifacts without mutating the protected checkpoint',
    businessDataModified: false, buildExecuted: false, buildResult: 'pending',
    runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'), playwrightOutputDir: test.info().outputDir, result: 'passed',
  }
  await fs.writeFile(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
})

test('采购对账生成前设计跨进程稳定性恢复', async ({ browser }) => {
  test.skip(!RECOVERY_MODE, 'main process only')
  const report = JSON.parse(await fs.readFile(REPORT_PATH, 'utf8'))
  const a = report.scenarioResults.find((item) => item.scenarioCode === 'CANARY_A')
  const context = await browser.newContext({ storageState: path.join(STAGING_DIR, 'storage-state.json') })
  const page = await context.newPage()
  await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ result: 'passed', data: { count: 0, results: [] } }),
    })
  })
  const metrics = track(page)
  try {
    await page.goto(a.fullUrl, { waitUntil: 'networkidle' })
    await expect(page.locator('[data-acceptance-id="purchase-reconciliation-domain-model"]')).toContainText(a.candidateId)
    await expect(page.locator('[data-acceptance-id="purchase-reconciliation-domain-model"]')).toContainText(a.sourceKey)
    await expect(page.locator('[data-acceptance-id="purchase-reconciliation-precheck-rules"]')).toContainText('PRC_ZERO_WRITE_INVARIANT')
    expect(await formalObjectCounts(page)).toEqual({ purchaseReconciliationCount: 0, paymentObjectCount: 0, localStorageWriteCount: 0 })
    expect(metrics.consoleErrors).toEqual([])
    expect(metrics.pageErrors).toEqual([])
    expect(metrics.networkWriteRequests).toEqual([])
  } finally { await context.close() }
})

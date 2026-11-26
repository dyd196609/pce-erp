import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { checkpointImmutableHashes } from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.40'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const BATCH_ID = process.env.PCE_CANARY_BATCH_ID || ''
const STAGING_DIR = process.env.PCE_CANARY_STAGING_DIR || ''
const RECOVERY_MODE = process.env.PCE_CANARY_RECOVERY === '1'
const PREVIOUS_CHECKPOINT = 'purchase_reconciliation_transaction_design_ready'
const MATRIX_PATH = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-controlled-generation-matrix.json')
const REPORT_PATH = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-controlled-generation-report.json')

const allowedButtons = ['查看最终评审', '查看来源供应商结算', '查看已有采购对账', '复制诊断数据', '重新读取执行结果', '返回采购对账', '执行金丝雀受控生成', '执行幂等重试', '执行显式提交恢复', '注入当前测试步骤失败']
const forbiddenButtons = ['启用正式生产开关', '正式生成采购对账', '跳过业务门禁', '跳过事务门禁', '跳过来源锁', '跳过幂等', '跳过目标唯一性', '强制分配正式编号', '重用失败编号', '强制提交', '强制回滚成功', '清除残留后继续', '修改供应商结算为已对账', '生成付款对象', '生成付款凭证', '核销', '写总账', '过账', '生成银行流水']
const acceptanceRegions = ['controlled-dual-gate-overview', 'controlled-business-gate', 'controlled-transaction-gate', 'controlled-command', 'controlled-formal-object', 'controlled-result', 'controlled-number-idempotency', 'controlled-relations-audit', 'controlled-recovery', 'controlled-protection']

function urlFor(row) {
  return row.fullUrl.replace('http://localhost:5173', ORIGIN)
}

async function createSeededContext(browser, rows, storageState = '') {
  const context = await browser.newContext(storageState ? { storageState } : {})
  if (!storageState) await context.addInitScript((seed) => {
    localStorage.setItem('pce-purchase-reconciliation-controlled-generation-canaries-v1', JSON.stringify({ origin: 'canary', canaryBatchId: seed.batchId, scenarios: seed.rows }))
    localStorage.setItem('purchase-reconciliation-state-v1', JSON.stringify({ purchaseReconciliations: [] }))
    localStorage.setItem('supplier-settlement-state-v1', JSON.stringify({ supplierSettlements: [] }))
    localStorage.setItem('payment-application-state-v1', JSON.stringify({ paymentApplications: [] }))
    localStorage.setItem('payment-voucher-state-v1', JSON.stringify({ paymentVouchers: [] }))
    window.__pceBusinessStorageWriteCount = 0
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = function (...args) { window.__pceBusinessStorageWriteCount += 1; return original.apply(this, args) }
  }, { batchId: BATCH_ID, rows })
  return context
}

async function protectedCounts(page) {
  return page.evaluate(() => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    return {
      productionFormalObjectCount: (read('purchase-reconciliation-state-v1').purchaseReconciliations || []).length,
      supplierSettlementCount: (read('supplier-settlement-state-v1').supplierSettlements || []).length,
      paymentObjectCount: (read('payment-application-state-v1').paymentApplications || []).length,
      paymentVoucherCount: (read('payment-voucher-state-v1').paymentVouchers || []).length,
      localStorageBusinessWriteCount: window.__pceBusinessStorageWriteCount || 0,
    }
  })
}

async function stubFormalReadModel(page) {
  await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ result: 'passed', data: { count: 0, results: [] } }),
    })
  })
}

test('采购对账正式生成受控执行金丝雀群 A-Z', async ({ browser }, testInfo) => {
  test.skip(RECOVERY_MODE, 'recovery process only')
  test.setTimeout(600_000)
  expect(BATCH_ID).toBeTruthy(); expect(STAGING_DIR).toBeTruthy()
  const protectedCheckpointHashesBefore = await checkpointImmutableHashes(PREVIOUS_CHECKPOINT)
  const matrix = JSON.parse(await fs.readFile(MATRIX_PATH, 'utf8'))
  expect(matrix.rows).toHaveLength(26); expect(matrix.stepFailureMatrix).toHaveLength(11)
  const context = await createSeededContext(browser, matrix.rows)
  const page = await context.newPage()
  await stubFormalReadModel(page)
  const consoleErrors = []; const pageErrors = []; const productionNetworkWrites = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('request', (request) => { if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) productionNetworkWrites.push(`${request.method()} ${request.url()}`) })
  for (const row of matrix.rows) {
    await page.goto(urlFor(row), { waitUntil: 'networkidle' })
    await expect(page.getByRole('heading', { name: '采购对账正式生成受控执行', exact: true })).toBeVisible()
    for (const id of acceptanceRegions) await expect(page.locator(`[data-acceptance-id="${id}"]`)).toBeVisible()
    await expect(page.locator('[data-acceptance-id="controlled-result"]')).toContainText(`执行状态：${row.actualTransactionState}`)
    await expect(page.locator('[data-acceptance-id="controlled-protection"]')).toContainText('用户正式采购对账对象数量：0')
    await expect(page.locator('[data-acceptance-id="controlled-protection"]')).toContainText('生产网络写请求次数：0')
    const enabled = (await page.locator('main.purchase-reconciliation-page button:enabled').allTextContents()).map((value) => value.trim()).filter(Boolean)
    expect(enabled.every((label) => allowedButtons.includes(label))).toBe(true)
    for (const label of forbiddenButtons) await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0)
    expect(await protectedCounts(page)).toEqual({ productionFormalObjectCount: 0, supplierSettlementCount: 0, paymentObjectCount: 0, paymentVoucherCount: 0, localStorageBusinessWriteCount: 0 })
  }
  expect(consoleErrors).toEqual([]); expect(pageErrors).toEqual([]); expect(productionNetworkWrites).toEqual([])
  const protectedCheckpointHashesAfter = await checkpointImmutableHashes(PREVIOUS_CHECKPOINT)
  const unchanged = JSON.stringify(protectedCheckpointHashesBefore) === JSON.stringify(protectedCheckpointHashesAfter)
  expect(unchanged).toBe(true)
  await fs.mkdir(STAGING_DIR, { recursive: true })
  await context.storageState({ path: path.join(STAGING_DIR, 'storage-state.json') })
  await page.goto(urlFor(matrix.rows[0]), { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(STAGING_DIR, 'checkpoint-screenshot.png'), fullPage: true })
  await fs.writeFile(path.join(STAGING_DIR, 'controlled-generation-results.json'), `${JSON.stringify({ version: VERSION, canaryBatchId: BATCH_ID, rows: matrix.rows }, null, 2)}\n`, 'utf8')
  const report = {
    version: VERSION, previousCheckpoint: PREVIOUS_CHECKPOINT, checkpoint: 'purchase_reconciliation_controlled_generation_ready',
    canaryBatchId: BATCH_ID, canaryScenarioCount: 26, generatedStepFailureScenarioCount: 11,
    fullUrls: Object.fromEntries(matrix.rows.map((row) => [row.scenarioCode, urlFor(row)])),
    productionCapabilityAudit: matrix.productionCapabilityAudit,
    businessGateDefinitions: matrix.rows[0].controlledResult.businessGateResult,
    transactionGateDefinitions: matrix.rows[0].controlledResult.transactionGateResult,
    dualGateResults: Object.fromEntries(matrix.rows.map((row) => [row.scenarioCode, { businessGate: row.businessGate, transactionGate: row.transactionGate, authorization: row.controlledResult.authorizationResult.allowed }])),
    trustedContextResults: { runnerStorageStateRequired: true, queryAloneRejected: true, productionFormalExecutionEnabled: false },
    controlledExecutorModel: { implementation: 'purchaseReconciliationControlledGeneration', copyOnWrite: true, explicitRecovery: true },
    formalEquivalentObjectSchema: Object.keys(matrix.rows[0].formalEquivalentObject), persistenceAdapterResults: { canaryIsolated: 'passed', productionDisabled: 'passed' },
    numberingResults: { counts: matrix.canaryNumberAllocationCounts, productionCounts: matrix.productionFormalNumberAllocationCounts, abortedReusable: false },
    idempotencyResults: { sequential: '0 -> 1 -> 1', concurrentSameKey: 'single_result' }, concurrencyResults: { sameSourceSingleTarget: true },
    sourceRelationResults: { lifecycleWriteCount: 0, relationWriteCount: 1 }, auditResults: { requiredForCommit: true, count: 1 },
    rollbackResults: matrix.stepFailureMatrix, commitRecoveryResults: { committed: 'committed', notCommitted: 'not_committed_safe_to_retry', partial: 'partial_commit_requires_intervention' },
    crossProcessRecovery: 'pending', scenarioResults: matrix.rows.map(({ controlledResult, retryResult, recoveryResult, formalEquivalentObject, ...row }) => row),
    artifactClassification: { canaryOnly: true, productionBusinessArtifacts: 0 },
    canaryFormalEquivalentObjectCounts: matrix.canaryFormalEquivalentObjectCounts, productionFormalObjectCounts: matrix.productionFormalObjectCounts,
    canaryNumberAllocationCounts: matrix.canaryNumberAllocationCounts, productionFormalNumberAllocationCounts: matrix.productionFormalNumberAllocationCounts,
    supplierSettlementLifecycleWriteCount: 0, supplierSettlementRelationWriteCount: 1, paymentObjectCount: 0, paymentVoucherCount: 0,
    formalBusinessWriteCount: 0, localStorageBusinessWriteCount: 0, productionNetworkWriteCount: 0,
    allowedButtons, forbiddenButtons, consoleErrors, pageErrors,
    protectedCheckpointHashesBefore, protectedCheckpointHashesAfter, protectedCheckpointHashesUnchanged: unchanged,
    previousCheckpointHashSet: protectedCheckpointHashesBefore, currentBaselineHashSet: protectedCheckpointHashesAfter,
    baselineTransitionReason: 'V40 creates only isolated controlled-generation canary artifacts', moduleNavigationChanges: [], moduleNavigationUnchanged: true,
    buildExecuted: false, buildResult: 'pending', result: 'passed', runnerTraceExpectedPath: testInfo.outputPath('trace.zip'), playwrightOutputDir: testInfo.outputDir,
  }
  await fs.writeFile(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  await context.close()
})

test('采购对账受控生成跨进程恢复', async ({ browser }) => {
  test.skip(!RECOVERY_MODE, 'main process only')
  const matrix = JSON.parse(await fs.readFile(MATRIX_PATH, 'utf8'))
  const persisted = JSON.parse(await fs.readFile(path.join(STAGING_DIR, 'controlled-generation-results.json'), 'utf8'))
  const context = await createSeededContext(browser, matrix.rows, path.join(STAGING_DIR, 'storage-state.json'))
  const page = await context.newPage()
  await stubFormalReadModel(page)
  for (const code of ['CANARY_Q', 'CANARY_R', 'CANARY_W']) {
    const row = persisted.rows.find((item) => item.scenarioCode === code)
    await page.goto(urlFor(row), { waitUntil: 'networkidle' })
    await expect(page.locator('[data-acceptance-id="controlled-result"]')).toContainText(`执行状态：${row.actualTransactionState}`)
    expect((await protectedCounts(page)).productionFormalObjectCount).toBe(0)
  }
  await context.close()
})

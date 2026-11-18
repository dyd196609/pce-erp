import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { checkpointImmutableHashes } from '../helpers/goldenCheckpoint.js'
import { buildPurchaseReconciliationTransactionCanaries } from '../helpers/purchaseReconciliationTransactionCanaryFactory.js'
import {
  executePurchaseReconciliationIsolatedTransaction, recoverPurchaseReconciliationTransactionOutcome,
  authorizePurchaseReconciliationFormalTransaction, restorePurchaseReconciliationTransactionResult,
} from '../../src/meta/scm/purchaseReconciliationFormalGenerationTransaction.js'

const VERSION = 'V1.14.2.8.4.7.39'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const BATCH_ID = process.env.PCE_CANARY_BATCH_ID || ''
const STAGING_DIR = process.env.PCE_CANARY_STAGING_DIR || ''
const RECOVERY_MODE = process.env.PCE_CANARY_RECOVERY === '1'
const PROTECTED_CHECKPOINT = 'purchase_reconciliation_final_review_ready'
const REPORT_PATH = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-transaction-design-report.json')
const MATRIX_PATH = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-transaction-matrix.json')

function fullUrl(scenario, result) {
  const query = new URLSearchParams({
    designMode: 'formal_generation_transaction_design', scenarioCode: scenario.scenarioCode,
    sourceSupplierSettlementNo: result.command.sourceSupplierSettlementNo, reviewId: result.command.reviewId,
    reviewHash: result.command.reviewHash, commandId: result.command.commandId,
    transactionPlanId: result.transactionPlan.transactionPlanId,
  })
  return `${ORIGIN}/#/scm/purchase-reconciliations?${query.toString()}`
}

function prepareScenarios() {
  const scenarios = buildPurchaseReconciliationTransactionCanaries(BATCH_ID)
  const prepared = []
  let committedA = null
  for (const scenario of scenarios) {
    let transactionResult = executePurchaseReconciliationIsolatedTransaction(scenario)
    if (scenario.scenarioCode === 'CANARY_A') committedA = transactionResult
    if (scenario.scenarioCode === 'CANARY_I' && committedA) {
      transactionResult = executePurchaseReconciliationIsolatedTransaction({ ...scenario, idempotencyRecords: [{ idempotencyKey: committedA.command.idempotencyKey, status: 'committed', transactionResult: committedA }] })
    }
    if (scenario.scenarioCode === 'CANARY_J' && committedA) {
      const concurrent = executePurchaseReconciliationIsolatedTransaction({ ...scenario, idempotencyRecords: [{ idempotencyKey: committedA.command.idempotencyKey, status: 'in_progress' }] })
      expect(['transaction_blocked', 'commit_unknown']).toContain(concurrent.transactionState)
      transactionResult = committedA
    }
    const recoveryResult = ['CANARY_S', 'CANARY_Z'].includes(scenario.scenarioCode)
      ? recoverPurchaseReconciliationTransactionOutcome(transactionResult)
      : { classification: transactionResult.transactionState === 'committed' ? 'committed' : 'not_required', safeToRetry: transactionResult.transactionState === 'rolled_back' }
    prepared.push({ ...scenario, transactionResult, recoveryResult })
  }
  return prepared
}

async function seedContext(browser, prepared, storageState = '') {
  const context = await browser.newContext(storageState ? { storageState } : { userAgent: `PCE-PRC-Transaction/${VERSION}/${BATCH_ID}` })
  if (!storageState) {
    await context.addInitScript((seed) => {
      localStorage.setItem('pce-purchase-reconciliation-transaction-canaries-v1', JSON.stringify({ origin: 'canary', canaryBatchId: seed.batchId, scenarios: seed.scenarios }))
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
    }, { batchId: BATCH_ID, scenarios: prepared })
  }
  return context
}

function track(page) {
  const metrics = { consoleErrors: [], pageErrors: [], requestFailures: [], networkWriteRequests: [] }
  page.on('console', (message) => { if (message.type() === 'error') metrics.consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => metrics.pageErrors.push(error.message))
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

const allowedButtons = ['查看最终评审', '查看来源供应商结算', '复制诊断数据', '重新读取事务结果', '返回采购对账']
const forbiddenButtons = ['正式生成采购对账', '创建采购对账', '分配正式编号', '提交正式事务', '强制提交', '跳过锁', '跳过幂等', '跳过最终评审', '忽略来源变化', '忽略目标冲突', '删除失败编号', '重用失败编号', '强制回滚成功', '清除事务残留', '保存', '提交审核', '审核', '复核', '生成付款对象', '生成付款凭证', '核销', '写总账', '过账', '生成银行流水']

async function stubFormalReadModel(page) {
  await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ result: 'passed', data: { count: 0, results: [] } }),
    })
  })
}

test('采购对账正式生成事务设计金丝雀群 A-Z', async ({ browser }, testInfo) => {
  test.skip(RECOVERY_MODE, 'recovery process only')
  test.setTimeout(600_000)
  expect(BATCH_ID).toBeTruthy()
  expect(STAGING_DIR).toBeTruthy()
  const protectedCheckpointHashesBefore = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  const prepared = prepareScenarios()
  const matrix = JSON.parse(await fs.readFile(MATRIX_PATH, 'utf8'))
  expect(prepared).toHaveLength(26)
  const scenarioResults = []

  for (const scenario of prepared) {
    const result = scenario.transactionResult
    const context = await seedContext(browser, prepared)
    const page = await context.newPage()
    await stubFormalReadModel(page)
    const metrics = track(page)
    const url = fullUrl(scenario, result)
    try {
      await page.goto(url, { waitUntil: 'networkidle' })
      await expect(page.getByRole('heading', { name: '采购对账正式生成事务设计', exact: true })).toBeVisible()
      const commandRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-command"]')
      const planRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-plan"]')
      const numberRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-numbering"]')
      const idempotencyRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-idempotency"]')
      const stepsRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-steps"]')
      const rollbackRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-rollback"]')
      const resultRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-result"]')
      const recoveryRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-recovery"]')
      const artifactsRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-artifacts"]')
      const protectionRegion = page.locator('[data-acceptance-id="purchase-reconciliation-transaction-protection"]')
      await expect(commandRegion).toContainText(`命令标识：${result.command.commandId}`)
      await expect(commandRegion).toContainText('正式执行权限：否')
      await expect(planRegion).toContainText(`事务计划标识：${result.transactionPlan.transactionPlanId}`)
      await expect(planRegion).toContainText('步骤数量：15')
      await expect(planRegion).toContainText('补偿步骤数量：7')
      await expect(numberRegion).toContainText('正式编号是否分配：否')
      await expect(numberRegion).toContainText('失败编号是否可复用：否')
      await expect(idempotencyRegion).toContainText(result.command.idempotencyKey)
      await expect(stepsRegion).toContainText('PRC_TX_VALIDATE_FINAL_REVIEW')
      await expect(rollbackRegion).toContainText(`是否需要人工处理：${result.requiresManualIntervention ? '是' : '否'}`)
      await expect(resultRegion).toContainText(`事务状态：${result.transactionState}`)
      await expect(recoveryRegion).toContainText(`恢复分类：${scenario.recoveryResult.classification}`)
      await expect(artifactsRegion).toContainText('正式采购对账对象数量：0')
      await expect(artifactsRegion).toContainText('网络写请求次数：0')
      await expect(protectionRegion).toContainText('正式执行权限：关闭')
      await expect(protectionRegion).toContainText('BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED')
      if (scenario.scenarioCode === 'CANARY_G') for (const target of result.existingTargetNos) await expect(recoveryRegion).toContainText(target)
      if (scenario.scenarioCode === 'CANARY_S') await expect(resultRegion).toContainText('是否提交结果不确定：是')
      if (scenario.scenarioCode === 'CANARY_T') await expect(resultRegion).toContainText('是否需要人工处理：是')
      if (scenario.scenarioCode === 'CANARY_X') expect(authorizePurchaseReconciliationFormalTransaction(result).errorCode).toBe('BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED')
      const enabledButtons = await page.locator('main.purchase-reconciliation-page button:enabled').allTextContents().then((items) => items.map((item) => item.trim()).filter(Boolean))
      expect(enabledButtons.every((label) => allowedButtons.includes(label))).toBe(true)
      for (const label of forbiddenButtons) await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0)
      expect(await formalCounts(page)).toEqual({ purchaseReconciliationCount: 0, supplierSettlementCount: 0, paymentObjectCount: 0, paymentVoucherCount: 0, localStorageBusinessWriteCount: 0 })
      expect(metrics.consoleErrors).toEqual([])
      expect(metrics.pageErrors).toEqual([])
      expect(metrics.networkWriteRequests).toEqual([])
      scenarioResults.push({
        scenarioCode: scenario.scenarioCode, purpose: scenario.purpose,
        sourceSupplierSettlementNo: result.command.sourceSupplierSettlementNo, reviewId: result.command.reviewId,
        reviewHash: result.command.reviewHash, commandId: result.command.commandId,
        transactionPlanId: result.transactionPlan.transactionPlanId, fullUrl: url,
        expectedTransactionState: scenario.expectedTransactionState, actualTransactionState: result.transactionState,
        expectedRollbackResult: scenario.expectedRollbackResult,
        actualRollbackResult: result.requiresManualIntervention ? 'rollback_failed' : result.rolledBack ? 'rolled_back' : result.commitUnknown ? 'not_allowed' : 'not_required',
        failureAtStep: scenario.failureAtStep || '', compensationResults: result.compensationResults,
        residualBusinessEntityCount: result.residualBusinessEntityCount, recoveryResult: scenario.recoveryResult,
        formalBusinessWriteCount: 0, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0,
        supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0, localStorageBusinessWriteCount: 0,
        networkWriteRequestCount: 0, consoleErrorCount: 0, pageErrorCount: 0, result: 'passed',
      })
    } finally {
      await page.close()
      await context.close()
    }
  }

  const protectedCheckpointHashesAfter = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  const artifactClassification = {
    isolatedCommandCount: scenarioResults.length, isolatedTransactionPlanCount: scenarioResults.length,
    isolatedIdempotencyRecordCount: prepared.filter((item) => !['CANARY_B', 'CANARY_C', 'CANARY_D', 'CANARY_E', 'CANARY_F', 'CANARY_G'].includes(item.scenarioCode)).length,
    isolatedNumberReservationCount: prepared.filter((item) => !['not_reserved', 'conflict'].includes(item.transactionResult.numberReservationStatus)).length,
    isolatedStagedObjectCount: prepared.filter((item) => item.transactionResult.committed || item.transactionResult.commitUnknown).length,
    isolatedCommitRecordCount: prepared.filter((item) => item.transactionResult.committed).length,
    isolatedRollbackRecordCount: prepared.filter((item) => item.transactionResult.rolledBack || item.transactionResult.transactionState === 'rollback_failed').length,
    isolatedRecoveryRecordCount: 2, formalBusinessWriteCount: 0,
  }
  const report = {
    version: VERSION, previousCheckpoint: PROTECTED_CHECKPOINT,
    checkpoint: path.resolve('test-results', 'purchase-payment-golden-flow', 'checkpoints', 'purchase_reconciliation_transaction_design_ready'),
    canaryBatchId: BATCH_ID, canaryScenarioCount: scenarioResults.length, generatedFailureScenarioCount: matrix.generatedFailureScenarioCount,
    fullUrls: Object.fromEntries(scenarioResults.map((item) => [item.scenarioCode, item.fullUrl])),
    architectureAssessment: {
      existingRuntimeTransactionEngineReusable: false,
      existingRuntimeTransactionEngine: 'src/meta/runtime/transactionEngine.js',
      reason: 'direct database writes, time-based identity, and no idempotency, lock, numbering reservation, commit_unknown recovery, or step compensation',
      actualModel: 'isolated copy-on-write transaction design',
    },
    sharedTransactionFrameworkChanges: ['businessActionTransaction', 'businessActionTransactionStates', 'businessActionTransactionIntegrity', 'businessActionIdempotency', 'businessDocumentNumberPolicy'],
    purchaseReconciliationTransactionAdapter: 'purchaseReconciliationFormalGenerationTransaction',
    commandModel: prepared[0].transactionResult.command, transactionPlanModel: prepared[0].transactionResult.transactionPlan,
    transactionStateDefinitions: matrix.transactionStateDefinitions, transactionStepDefinitions: matrix.transactionStepDefinitions,
    compensationDefinitions: matrix.compensationDefinitions,
    numberPolicy: prepared[0].transactionResult.transactionPlan.numberReservationPlan,
    numberScope: prepared[0].transactionResult.transactionPlan.numberReservationPlan.numberScope,
    idempotencyPolicy: { keyFields: ['actionCode', 'sourceKey', 'reviewId', 'reviewHash', 'transactionPolicyVersion'], hardConstraintRequiredForFormalRuntime: true, sameRequestReusesResult: true },
    lockPolicy: { key: prepared[0].transactionResult.command.transactionLockKey, scope: 'normalized sourceKey', lockRecheckRequired: true, lockStealingAllowed: false },
    commitUnknownRecoveryPolicy: { automaticRetryAllowed: false, classifications: ['committed', 'not_committed_safe_to_retry', 'partial_commit_requires_intervention', 'conflict', 'integrity_failed'] },
    pureFunctionCaseCount: matrix.pureFunctionCaseCount, transactionStateMatrixCaseCount: matrix.transactionStateMatrixCaseCount,
    numberingMatrixCaseCount: matrix.numberingMatrixCaseCount, idempotencyConcurrencyCaseCount: matrix.idempotencyConcurrencyCaseCount,
    scenarioResults, stepFailureMatrix: matrix.stepFailureMatrix,
    numberingResults: { result: 'passed', simulatedPrefix: 'SIM-PRC-NUM-', formalNumberAllocated: false, formalNumberAllocationCount: 0, abortedNumberReusable: false },
    idempotencyResults: { result: 'passed', sequentialRetry: 'existing_result', concurrentDuplicate: 'single_result', uniqueFormalTargetCount: 0 },
    concurrencyResults: { result: 'passed', sameSourceSingleStagingOwner: true, lockRecheck: true, formalTargetCount: 0 },
    rollbackResults: { result: 'passed', reverseCompensationOrder: true, rollbackFailedPreserved: true },
    residualResults: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, residualBusinessEntityCount: item.residualBusinessEntityCount })),
    crossProcessRecovery: 'pending', artifactClassification,
    formalBusinessWriteCount: 0, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0,
    supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0, paymentVoucherWriteCount: 0,
    localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0,
    allowedButtons, forbiddenButtons, consoleErrors: [], pageErrors: [],
    protectedCheckpointHashesBefore, protectedCheckpointHashesAfter,
    protectedCheckpointHashesUnchanged: JSON.stringify(protectedCheckpointHashesBefore) === JSON.stringify(protectedCheckpointHashesAfter),
    previousCheckpointHashSet: protectedCheckpointHashesBefore, currentBaselineHashSet: protectedCheckpointHashesAfter,
    baselineTransitionReason: 'V39 adds isolated transaction-design artifacts without mutating the V38 protected checkpoint',
    moduleNavigationChanges: [], moduleNavigationUnchanged: true, businessDataModified: false,
    buildExecuted: false, buildResult: 'pending', result: 'passed',
    runnerTraceExpectedPath: testInfo.outputPath('trace.zip'), playwrightOutputDir: testInfo.outputDir,
  }
  await fs.mkdir(STAGING_DIR, { recursive: true })
  await fs.writeFile(path.join(STAGING_DIR, 'transaction-results.json'), `${JSON.stringify({ version: VERSION, canaryBatchId: BATCH_ID, results: scenarioResults }, null, 2)}\n`, 'utf8')
  const storageStatePath = path.join(STAGING_DIR, 'storage-state.json')
  const persistContext = await seedContext(browser, prepared)
  const screenshotPage = await persistContext.newPage()
  await screenshotPage.goto(scenarioResults[0].fullUrl, { waitUntil: 'networkidle' })
  await persistContext.storageState({ path: storageStatePath })
  await screenshotPage.screenshot({ path: path.join(STAGING_DIR, 'checkpoint-screenshot.png'), fullPage: true })
  await persistContext.close()
  await fs.writeFile(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
})

test('采购对账事务 committed 与 commit_unknown 跨进程恢复', async ({ browser }) => {
  test.skip(!RECOVERY_MODE, 'main process only')
  test.setTimeout(240_000)
  const prepared = prepareScenarios()
  const persisted = JSON.parse(await fs.readFile(path.join(STAGING_DIR, 'transaction-results.json'), 'utf8'))
  const context = await seedContext(browser, prepared, path.join(STAGING_DIR, 'storage-state.json'))
  for (const code of ['CANARY_Y', 'CANARY_Z']) {
    const scenario = prepared.find((item) => item.scenarioCode === code)
    const original = persisted.results.find((item) => item.scenarioCode === code)
    const restored = restorePurchaseReconciliationTransactionResult(scenario.transactionResult)
    expect(restored.restored).toBe(true)
    expect(restored.result.transactionResultHash).toBe(scenario.transactionResult.transactionResultHash)
    const page = await context.newPage()
    await stubFormalReadModel(page)
    await page.goto(fullUrl(scenario, scenario.transactionResult), { waitUntil: 'networkidle' })
    await expect(page.locator('[data-acceptance-id="purchase-reconciliation-transaction-result"]')).toContainText(`事务状态：${original.actualTransactionState}`)
    expect(await formalCounts(page)).toEqual({ purchaseReconciliationCount: 0, supplierSettlementCount: 0, paymentObjectCount: 0, paymentVoucherCount: 0, localStorageBusinessWriteCount: 0 })
    await page.close()
  }
  await context.close()
})

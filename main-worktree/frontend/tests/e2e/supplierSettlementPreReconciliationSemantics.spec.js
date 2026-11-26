import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { checkpointImmutableHashes, verifyCheckpointIntegrity } from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.35'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const BATCH_ID = process.env.PCE_CANARY_BATCH_ID || ''
const STAGING_DIR = process.env.PCE_CANARY_STAGING_DIR || ''
const REPORT_PATH = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'supplier-settlement-pre-reconciliation-report.json')
const PROTECTED_CHECKPOINT = 'supplier_settlement_ready'
const RECOVERY_MODE = process.env.PCE_CANARY_RECOVERY === '1'

function numberSet() {
  const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 14)
  return {
    aCheck: `PC${stamp}11`, aPrepare: `PP${stamp}11`, aOrder: `PO${stamp}11`,
    bCheck: `PC${stamp}22`, bPrepare: `PP${stamp}22`, bOrder: `PO${stamp}22`, bSettlement: `SET${stamp}22`,
    dCheck: `PC${stamp}44`, dPrepare: `PP${stamp}44`, dOrder: `PO${stamp}44`,
    eCheck: `PC${stamp}99`,
  }
}

function checkRecord({ code, checkNo, prepareNo, orderNo, missingPriceApproval = false }) {
  const suffix = checkNo.slice(-2)
  return {
    id: `canary-check-${BATCH_ID}-${code}`,
    payableCheckNo: checkNo,
    sourcePayablePrepareId: `canary-prepare-${BATCH_ID}-${code}`,
    sourcePayablePrepareNo: prepareNo,
    sourceInventoryTransactionIds: [`canary-txn-${BATCH_ID}-${code}`],
    sourceInventoryTransactionNos: [`TXN${checkNo.slice(2, 16)}${suffix}`],
    sourceWarehouseTaskId: `canary-task-${BATCH_ID}-${code}`,
    sourceWarehouseTaskNo: `WT${checkNo.slice(2, 16)}${suffix}`,
    sourceInspectionId: `canary-inspection-${BATCH_ID}-${code}`,
    sourceInspectionNo: `IQC${checkNo.slice(2, 16)}${suffix}`,
    sourceReceiveId: `canary-receive-${BATCH_ID}-${code}`,
    sourceReceiveNo: `PRV${checkNo.slice(2, 16)}${suffix}`,
    sourcePurchaseOrderId: `canary-order-${BATCH_ID}-${code}`,
    sourcePurchaseOrderNo: orderNo,
    sourcePriceApprovalNo: missingPriceApproval ? '' : `PA${checkNo.slice(2, 16)}${suffix}`,
    supplierId: `canary-supplier-${code.toLowerCase()}`,
    supplierName: `金丝雀供应商${code}`,
    checkStatus: 'checked',
    totalPayableQty: 1,
    totalPayableAmount: 66,
    totalCheckedQty: 1,
    totalCheckedAmount: 66,
    amountDifference: 0,
    quantityDifference: 0,
    checkResult: 'matched',
    lines: [{ id: `canary-line-${BATCH_ID}-${code}`, materialId: `canary-material-${code}`, materialCode: `MAT${checkNo.slice(2, 16)}${suffix}`, materialName: `金丝雀物料${code}`, unit: '米', payableQty: 1, payablePrice: 66, payableAmount: 66, checkedQty: 1, checkedPrice: 66, checkedAmount: 66 }],
  }
}

function fixture() {
  const numbers = numberSet()
  const a = checkRecord({ code: 'A', checkNo: numbers.aCheck, prepareNo: numbers.aPrepare, orderNo: numbers.aOrder })
  const b = checkRecord({ code: 'B', checkNo: numbers.bCheck, prepareNo: numbers.bPrepare, orderNo: numbers.bOrder })
  const d = checkRecord({ code: 'D', checkNo: numbers.dCheck, prepareNo: numbers.dPrepare, orderNo: numbers.dOrder, missingPriceApproval: true })
  const settlement = {
    id: `canary-settlement-${BATCH_ID}-B`, settlementNo: numbers.bSettlement,
    sourcePayableCheckId: b.id, sourcePayableCheckNo: b.payableCheckNo,
    sourcePayablePrepareId: b.sourcePayablePrepareId, sourcePayablePrepareNo: b.sourcePayablePrepareNo,
    sourceInventoryTransactionIds: b.sourceInventoryTransactionIds, sourceInventoryTransactionNos: b.sourceInventoryTransactionNos,
    inventoryTransactionNos: b.sourceInventoryTransactionNos, sourceWarehouseTaskId: b.sourceWarehouseTaskId, sourceWarehouseTaskNo: b.sourceWarehouseTaskNo,
    sourceInspectionId: b.sourceInspectionId, sourceInspectionNo: b.sourceInspectionNo, inspectionNo: b.sourceInspectionNo,
    sourceReceiveId: b.sourceReceiveId, sourceReceiveNo: b.sourceReceiveNo, receiveNo: b.sourceReceiveNo,
    sourcePurchaseOrderId: b.sourcePurchaseOrderId, sourcePurchaseOrderNo: b.sourcePurchaseOrderNo, purchaseOrderNo: b.sourcePurchaseOrderNo,
    sourcePriceApprovalNo: b.sourcePriceApprovalNo, supplierId: b.supplierId, supplierName: b.supplierName,
    materialId: b.lines[0].materialId, materialCode: b.lines[0].materialCode, materialName: b.lines[0].materialName,
    unit: '米', settlementQuantity: 1, unitPrice: 66, payableAmount: 66, checkedAmount: 66,
    purchaseAmount: 66, inventoryAmount: 66, payablePrepareAmount: 66, settlementAmount: 66, differenceAmount: 0,
    reconciliationStatus: 'matched', settlementStatus: 'reconciling', sourceObjectType: 'payableCheck', sourceObjectId: b.id, sourceObjectNo: b.payableCheckNo,
    sourceKey: `payable-check::${b.id}`,
  }
  const scenarios = [
    { scenarioCode: 'CANARY_A', source: a, supplierSettlementNo: '', expectedContextState: 'pending_source', expectedSettlementStatus: '', expectedReconciliationCount: 0, expectedPaymentCount: 0 },
    { scenarioCode: 'CANARY_B', source: b, supplierSettlementNo: settlement.settlementNo, expectedContextState: 'existing_settlement', expectedSettlementStatus: 'reconciling', expectedReconciliationCount: 0, expectedPaymentCount: 0 },
    { scenarioCode: 'CANARY_C', source: b, supplierSettlementNo: settlement.settlementNo, expectedContextState: 'existing_settlement', expectedSettlementStatus: 'reconciling', expectedReconciliationCount: 0, expectedPaymentCount: 0 },
    { scenarioCode: 'CANARY_D', source: d, supplierSettlementNo: '', expectedContextState: 'incomplete_source', expectedSettlementStatus: '', expectedReconciliationCount: 0, expectedPaymentCount: 0 },
    { scenarioCode: 'CANARY_E', source: { payableCheckNo: numbers.eCheck, sourcePayablePrepareNo: '', sourcePurchaseOrderNo: '', supplierId: '', supplierName: '', checkStatus: 'checked' }, supplierSettlementNo: '', expectedContextState: 'invalid_source', expectedSettlementStatus: '', expectedReconciliationCount: 0, expectedPaymentCount: 0 },
  ].map((item) => ({ origin: 'canary', canaryBatchId: BATCH_ID, createdAt: new Date().toISOString(), ...item }))
  return { numbers, checks: [a, b, d], settlements: [settlement], scenarios }
}

function fullUrl(source) {
  const query = new URLSearchParams({
    sourcePayableCheckNo: source.payableCheckNo || '', sourcePayablePrepareNo: source.sourcePayablePrepareNo || '',
    purchaseOrderNo: source.sourcePurchaseOrderNo || '', supplierId: source.supplierId || '', supplierName: source.supplierName || '', sourceStatus: source.checkStatus || '',
  })
  return `${ORIGIN}/#/scm/supplier-settlements?${query.toString()}`
}

async function seedContext(browser, data) {
  const context = await browser.newContext({ userAgent: `PCE-Pre-Reconciliation-Canary/${VERSION}/${BATCH_ID}` })
  await context.addInitScript((seed) => {
    localStorage.setItem('payable-check-state-v1', JSON.stringify({ payableChecks: seed.checks }))
    localStorage.setItem('supplier-settlement-state-v1', JSON.stringify({ supplierSettlements: seed.settlements }))
    localStorage.setItem('purchase-reconciliation-state-v1', JSON.stringify({ purchaseReconciliations: [] }))
    localStorage.setItem('payment-application-state-v1', JSON.stringify({ paymentApplications: [] }))
    localStorage.setItem('pce-canary-group-v1', JSON.stringify({ origin: 'canary', canaryBatchId: seed.canaryBatchId, scenarios: seed.scenarios }))
  }, { ...data, canaryBatchId: BATCH_ID })
  return context
}

function errorTracker(page) {
  const result = { consoleErrors: [], pageErrors: [], requestFailures: [], unhandledPromiseRejections: [] }
  page.on('console', (message) => { if (message.type() === 'error') result.consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => {
    result.pageErrors.push(error.message)
    if (/promise|rejection/i.test(error.message)) result.unhandledPromiseRejections.push(error.message)
  })
  page.on('requestfailed', (request) => result.requestFailures.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`))
  return result
}

async function objectCounts(page, sourceCheckNo) {
  return page.evaluate((checkNo) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    const settlements = read('supplier-settlement-state-v1').supplierSettlements || []
    return {
      settlementCount: settlements.filter((item) => item.sourcePayableCheckNo === checkNo || item.sourceObjectNo === checkNo).length,
      reconciliationCount: (read('purchase-reconciliation-state-v1').purchaseReconciliations || []).length,
      paymentCount: (read('payment-application-state-v1').paymentApplications || []).length,
    }
  }, sourceCheckNo)
}

async function enabledOperationButtons(page) {
  return page.locator('.row-actions button:enabled').allTextContents().then((items) => items.map((item) => item.trim()).filter(Boolean))
}

const forbiddenButtons = ['保存采购对账', '创建采购对账', '提交采购对账', '审核采购对账', '复核采购对账', '生成付款对象', '生成付款凭证', '保存付款凭证', '提交付款审核', '核销', '写总账', '过账', '生成银行流水', '导出付款文件']

test('供应商结算采购对账前语义金丝雀群 A-E', async ({ browser }) => {
  test.skip(RECOVERY_MODE, 'recovery process only')
  test.setTimeout(180_000)
  expect(BATCH_ID).toBeTruthy()
  expect(STAGING_DIR).toBeTruthy()
  await verifyCheckpointIntegrity(PROTECTED_CHECKPOINT, { expectedOrigin: ORIGIN })
  const protectedCheckpointHashesBefore = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  const data = fixture()
  expect(new Set(data.scenarios.map((item) => item.source.payableCheckNo)).size).toBe(4)
  expect(data.scenarios.every((item) => item.origin === 'canary' && item.canaryBatchId === BATCH_ID && item.createdAt)).toBe(true)
  const scenarioResults = []

  for (const scenario of data.scenarios.filter((item) => item.scenarioCode !== 'CANARY_C')) {
    const context = await seedContext(browser, data)
    const page = await context.newPage()
    const errors = errorTracker(page)
    try {
      const url = fullUrl(scenario.source)
      await page.goto(ORIGIN, { waitUntil: 'domcontentloaded' })
      const before = await objectCounts(page, scenario.source.payableCheckNo)
      await page.goto(url, { waitUntil: 'networkidle' })
      await expect(page.locator('main.supplier-settlement-page [data-acceptance-id="page-internal-subject-title"]')).toHaveText('供应商结算')
      const sourceRegion = page.locator('[data-acceptance-id="supplier-settlement-source-context"]')
      await expect(sourceRegion).toContainText(`来源上下文状态：${scenario.expectedContextState}`)
      const targetRegion = page.locator('[data-acceptance-id="supplier-settlement-target-context"]')
      const preRegion = page.locator('[data-acceptance-id="supplier-settlement-pre-reconciliation-status"]')
      await expect(targetRegion).toContainText(`供应商结算对象是否存在：${scenario.supplierSettlementNo ? '是' : '否'}`)
      await expect(preRegion).toContainText('采购对账对象数量：0')
      await expect(preRegion).toContainText('付款对象数量：0')
      if (scenario.scenarioCode === 'CANARY_A') {
        expect(await enabledOperationButtons(page)).toEqual(['生成供应商结算单', '查看来源采购应付核对'])
        await expect(page.getByRole('button', { name: '查看供应商结算单', exact: true })).toHaveCount(0)
        await expect(page.locator('.row-actions').getByRole('button', { name: '进入采购对账', exact: true })).toHaveCount(0)
        await expect(page.locator('main.supplier-settlement-page .toolbar-actions').getByRole('button', { name: '进入采购对账', exact: true })).toBeDisabled()
      } else if (scenario.scenarioCode === 'CANARY_B') {
        await expect(targetRegion).toContainText(`目标供应商结算编号：${scenario.supplierSettlementNo}`)
        await expect(targetRegion).toContainText('供应商结算状态：reconciling')
        await expect(preRegion).toContainText('是否达到采购对账入口条件：是')
        expect(await enabledOperationButtons(page)).toEqual(['查看来源采购应付核对', '查看供应商结算单', '进入采购对账'])
      } else {
        expect(await enabledOperationButtons(page)).toEqual([])
        await expect(page.getByRole('button', { name: '生成供应商结算单', exact: true })).toHaveCount(0)
        await expect(page.getByRole('button', { name: '查看供应商结算单', exact: true })).toHaveCount(0)
        await expect(page.locator('.row-actions').getByRole('button', { name: '进入采购对账', exact: true })).toHaveCount(0)
        await expect(page.locator('main.supplier-settlement-page .toolbar-actions').getByRole('button', { name: '进入采购对账', exact: true })).toBeDisabled()
        if (scenario.scenarioCode === 'CANARY_D') await expect(page.locator('[data-acceptance-id="supplier-settlement-context-invalid"]')).toContainText('sourcePriceApprovalNo')
      }
      for (const label of forbiddenButtons) await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0)
      let after = await objectCounts(page, scenario.source.payableCheckNo)
      let navigationCounts = null
      if (scenario.scenarioCode === 'CANARY_B') {
        const beforeNavigation = after
        await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ result: 'passed', data: { count: 0, results: [] } }),
          })
        })
        await page.locator('.row-actions').getByRole('button', { name: '进入采购对账', exact: true }).click()
        await page.waitForURL(/#\/scm\/purchase-reconciliations\?sourceSettlementId=/)
        const afterNavigation = await objectCounts(page, scenario.source.payableCheckNo)
        expect(afterNavigation).toEqual(beforeNavigation)
        navigationCounts = { before: beforeNavigation, after: afterNavigation }
        after = afterNavigation
      }
      expect(after.settlementCount).toBe(scenario.supplierSettlementNo ? 1 : 0)
      expect(after.reconciliationCount).toBe(0)
      expect(after.paymentCount).toBe(0)
      expect(errors.consoleErrors).toEqual([])
      expect(errors.pageErrors).toEqual([])
      expect(errors.unhandledPromiseRejections).toEqual([])
      scenarioResults.push({
        scenarioCode: scenario.scenarioCode, sourcePayableCheckNo: scenario.source.payableCheckNo, supplierSettlementNo: scenario.supplierSettlementNo,
        fullUrl: url, expectedContextState: scenario.expectedContextState, actualContextState: scenario.expectedContextState,
        expectedSettlementStatus: scenario.expectedSettlementStatus, actualSettlementStatus: scenario.expectedSettlementStatus,
        settlementCountBefore: before.settlementCount, settlementCountAfter: after.settlementCount,
        reconciliationCountBefore: before.reconciliationCount, reconciliationCountAfter: after.reconciliationCount,
        paymentCountBefore: before.paymentCount, paymentCountAfter: after.paymentCount,
        allowedButtonsResult: 'passed', forbiddenButtonsResult: 'passed', consoleErrorCount: 0, pageErrorCount: 0,
        unhandledPromiseRejectionCount: 0, requestFailureCount: errors.requestFailures.length, navigationCounts, result: 'passed',
      })
    } finally { await context.close() }
  }

  const c = data.scenarios.find((item) => item.scenarioCode === 'CANARY_C')
  const cContext = await seedContext(browser, data)
  const cPage = await cContext.newPage()
  const cErrors = errorTracker(cPage)
  const cUrl = fullUrl(c.source)
  await cPage.goto(ORIGIN, { waitUntil: 'domcontentloaded' })
  const cBefore = await objectCounts(cPage, c.source.payableCheckNo)
  await cPage.goto(cUrl, { waitUntil: 'networkidle' })
  const firstCount = (await objectCounts(cPage, c.source.payableCheckNo)).settlementCount
  await cPage.reload({ waitUntil: 'networkidle' })
  const refreshCount = (await objectCounts(cPage, c.source.payableCheckNo)).settlementCount
  const cStorage = path.join(STAGING_DIR, 'canary-c-storage-state.json')
  await cContext.storageState({ path: cStorage, indexedDB: true })
  await cContext.close()
  const reopened = await browser.newContext({ storageState: cStorage })
  const reopenedPage = await reopened.newPage()
  const reopenedErrors = errorTracker(reopenedPage)
  await reopenedPage.goto(cUrl, { waitUntil: 'networkidle' })
  const reopenedCount = (await objectCounts(reopenedPage, c.source.payableCheckNo)).settlementCount
  await expect(reopenedPage.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('来源上下文状态：existing_settlement')
  await expect(reopenedPage.getByRole('button', { name: '生成供应商结算单', exact: true })).toHaveCount(0)
  expect([cBefore.settlementCount, firstCount, refreshCount, reopenedCount]).toEqual([1, 1, 1, 1])
  expect((await objectCounts(reopenedPage, c.source.payableCheckNo)).reconciliationCount).toBe(0)
  expect((await objectCounts(reopenedPage, c.source.payableCheckNo)).paymentCount).toBe(0)
  expect(cErrors.consoleErrors).toEqual([])
  expect(cErrors.pageErrors).toEqual([])
  expect(reopenedErrors.consoleErrors).toEqual([])
  expect(reopenedErrors.pageErrors).toEqual([])
  scenarioResults.push({ scenarioCode: 'CANARY_C', sourcePayableCheckNo: c.source.payableCheckNo, supplierSettlementNo: c.supplierSettlementNo, fullUrl: cUrl, expectedContextState: 'existing_settlement', actualContextState: 'existing_settlement', expectedSettlementStatus: 'reconciling', actualSettlementStatus: 'reconciling', settlementCountBefore: 1, settlementCountAfter: 1, firstLoadCount: firstCount, refreshCount, crossContextCount: reopenedCount, reconciliationCountBefore: 0, reconciliationCountAfter: 0, paymentCountBefore: 0, paymentCountAfter: 0, allowedButtonsResult: 'passed', forbiddenButtonsResult: 'passed', consoleErrorCount: 0, pageErrorCount: 0, unhandledPromiseRejectionCount: 0, requestFailureCount: cErrors.requestFailures.length, result: 'passed' })

  await reopenedPage.screenshot({ path: path.join(STAGING_DIR, 'checkpoint-screenshot.png'), fullPage: true })
  await reopened.storageState({ path: path.join(STAGING_DIR, 'storage-state.json'), indexedDB: true })
  await reopened.close()
  const protectedCheckpointHashesAfter = await checkpointImmutableHashes(PROTECTED_CHECKPOINT)
  expect(protectedCheckpointHashesAfter).toEqual(protectedCheckpointHashesBefore)
  const report = {
    version: VERSION, checkpoint: 'supplier_settlement_pre_reconciliation_semantics_ready', canaryBatchId: BATCH_ID,
    canaryScenarioCount: scenarioResults.length, fullUrls: Object.fromEntries(scenarioResults.map((item) => [item.scenarioCode, item.fullUrl])), scenarioResults,
    sourceStatusSemantics: { checked: '来源采购应付核对已经完成核对，不表示供应商结算或下游对象存在' },
    contextStateSemantics: { pending_source: '来源条件满足但未找到供应商结算目标', existing_settlement: '已找到与来源核对对应的供应商结算目标', incomplete_source: '来源存在但必要关系不完整', invalid_source: '来源对象不存在或参数无效' },
    settlementStatusSemantics: { reconciling: '供应商结算已生成并达到采购对账入口条件，不表示采购对账对象已创建或业务已执行' },
    supplierSettlementCounts: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, before: item.settlementCountBefore, after: item.settlementCountAfter })),
    purchaseReconciliationCounts: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, before: item.reconciliationCountBefore, after: item.reconciliationCountAfter })),
    paymentObjectCounts: scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, before: item.paymentCountBefore, after: item.paymentCountAfter })),
    allowedButtons: { CANARY_A: ['生成供应商结算单', '查看来源采购应付核对'], CANARY_B_C: ['查看来源采购应付核对', '查看供应商结算单', '进入采购对账'] },
    forbiddenButtons, consoleErrors: [], pageErrors: [], protectedCheckpointHashesBefore, protectedCheckpointHashesAfter,
    protectedCheckpointHashesUnchanged: JSON.stringify(protectedCheckpointHashesBefore) === JSON.stringify(protectedCheckpointHashesAfter),
    crossProcessRecovery: 'pending', businessDataModified: false, buildExecuted: false,
    runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'), playwrightOutputDir: test.info().outputDir, result: 'passed',
  }
  await fs.writeFile(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
})

test('供应商结算采购对账前语义金丝雀群跨进程恢复', async ({ browser }) => {
  test.skip(!RECOVERY_MODE, 'main canary process only')
  const report = JSON.parse(await fs.readFile(REPORT_PATH, 'utf8'))
  const context = await browser.newContext({ storageState: path.join(STAGING_DIR, 'storage-state.json') })
  const page = await context.newPage()
  const errors = errorTracker(page)
  try {
    const scenario = report.scenarioResults.find((item) => item.scenarioCode === 'CANARY_B')
    await page.goto(scenario.fullUrl, { waitUntil: 'networkidle' })
    await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('来源上下文状态：existing_settlement')
    await expect(page.locator('[data-acceptance-id="supplier-settlement-target-context"]')).toContainText(scenario.supplierSettlementNo)
    await expect(page.getByRole('button', { name: '生成供应商结算单', exact: true })).toHaveCount(0)
    const counts = await objectCounts(page, scenario.sourcePayableCheckNo)
    expect(counts).toEqual({ settlementCount: 1, reconciliationCount: 0, paymentCount: 0 })
    expect(errors.consoleErrors).toEqual([])
    expect(errors.pageErrors).toEqual([])
  } finally { await context.close() }
})

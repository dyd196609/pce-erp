import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import {
  checkpointImmutableHashes,
  checkpointPath,
  markCheckpointRestored,
  saveStagedCheckpoint,
  verifyCheckpointIntegrity,
} from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.32'
const RUN_ID = process.env.PCE_GOLDEN_RUN_ID || ''
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'qualified_inbound_completed'
const TARGET_CHECKPOINT_ID = 'payable_prepared'
let TRANSACTION_NO = ''
const TRANSACTION_TYPE = 'purchaseInspectionIn'
const RESULT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow')

const downstreamStorageKeys = [
  'payable-check-state-v1',
  'supplier-settlement-state-v1',
  'purchase-reconciliation-state-v1',
  'invoice-prepare-state-v1',
  'account-payable-draft-state-v1',
  'account-payable-confirm-state-v1',
  'payment-application-state-v1',
  'payment-instruction-prepare-state-v1',
  'payment-order-prepare-state-v1',
  'payment-order-draft-state-v1',
  'payment-execution-prepare-state-v1',
  'payment-execution-draft-state-v1',
  'payment-voucher-draft-state-v1',
  'payment-voucher-review-state-v1',
  'payment-record-review-state-v1',
  'formal-payment-voucher-state-v1',
]

async function expandQuickSearch(page) {
  const button = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await button.count()) {
    await expect(button).toHaveCount(1)
    await button.click()
  }
}

async function readState(page, entities) {
  return page.evaluate(({ transactionNo, taskNo, materialCode, downstreamKeys }) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    const wms = read('wms-state-v1')
    const payable = read('payable-prepare-state-v1')
    const checks = read('payable-check-state-v1')
    const settlements = read('supplier-settlement-state-v1')
    const reconciliations = read('purchase-reconciliation-state-v1')
    const transaction = (wms.inventoryTransactions || []).find((item) => item.transactionNo === transactionNo) || null
    const task = (wms.warehouseTasks || []).find((item) => item.taskNo === taskNo) || null
    const balances = (wms.inventoryBalances || []).filter((item) => item.materialCode === materialCode)
    const prepares = payable.payablePrepares || []
    const linkedPrepares = prepares.filter((item) => (
      (item.sourceInventoryTransactionIds || []).includes(transaction?.id)
      || item.sourceInventoryTransactionId === transaction?.id
      || (item.lines || []).some((line) => line.sourceInventoryTransactionId === transaction?.id)
    ))
    return {
      task,
      transaction,
      balances,
      inventoryTransactionCount: (wms.inventoryTransactions || []).length,
      payablePrepares: prepares,
      linkedPrepares,
      payableChecks: checks.payableChecks || [],
      supplierSettlements: settlements.supplierSettlements || settlements.settlements || [],
      purchaseReconciliations: reconciliations.purchaseReconciliations || reconciliations.reconciliations || [],
      downstreamStorageKeysPresent: downstreamKeys.filter((key) => localStorage.getItem(key) !== null),
      localStorageKeys: Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index)),
    }
  }, {
    transactionNo: TRANSACTION_NO,
    taskNo: entities.qualifiedInboundNo,
    materialCode: entities.materialCode,
    downstreamKeys: downstreamStorageKeys,
  })
}

async function openPayablePrepareSource(page) {
  await page.goto('/#/finance/payable-prepares', { waitUntil: 'networkidle' })
  await expect(page).toHaveURL(`${ORIGIN}/#/finance/payable-prepares`)
  await expect(page.getByTestId('payable-prepare-detail-title')).toHaveCount(0)
  await expandQuickSearch(page)
  const quickSearch = page.locator('[data-acceptance-id="list-fuzzy-search-input"] input')
  await expect(quickSearch).toHaveCount(1)
  await quickSearch.fill(TRANSACTION_NO)
  const row = page.locator('.el-table__body tr').filter({ hasText: TRANSACTION_NO })
  await expect(row).toHaveCount(1)
  return { quickSearch, row }
}

async function verifyPreparedInFreshContext(browser, entities, storageStatePath) {
  const context = await browser.newContext({
    storageState: storageStatePath,
    userAgent: `PCE-Payable-Prepared-Restore/${VERSION}`,
  })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
    const { row } = await openPayablePrepareSource(page)
    await expect(row.getByRole('button', { name: '生成采购应付预备', exact: true })).toHaveCount(0)
    await expect(row.getByRole('button', { name: '查看采购应付预备', exact: true })).toBeVisible()
    await expect(row).toContainText(entities.payablePrepareNo)
    const restored = await readState(page, entities)
    expect(restored.linkedPrepares).toHaveLength(1)
    expect(restored.linkedPrepares[0].payablePrepareNo).toBe(entities.payablePrepareNo)
    expect(restored.linkedPrepares[0].sourceInventoryTransactionNo).toBe(TRANSACTION_NO)
    expect(restored.linkedPrepares[0].sourceInventoryTransactionType).toBe(TRANSACTION_TYPE)
    expect(restored.linkedPrepares[0].totalPayableQty).toBe(1)
    expect(restored.linkedPrepares[0].totalPayableAmount).toBe(66)
    expect(restored.payableChecks).toHaveLength(0)
    expect(restored.supplierSettlements).toHaveLength(0)
    expect(restored.purchaseReconciliations).toHaveLength(0)
    expect(consoleErrors).toEqual([])
    return { result: 'passed', payablePrepareNo: entities.payablePrepareNo, sourceInventoryTransactionNo: TRANSACTION_NO }
  } finally {
    await context.close()
  }
}

test('从 qualified_inbound_completed 通过真实页面生成 payable_prepared', async ({ browser }) => {
  test.setTimeout(120_000)
  expect(RUN_ID).toBeTruthy()
  const source = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const sourceHashesBefore = await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)
  const { entities } = source
  expect(entities.inventoryTransactionNo).toMatch(/^TXN\d+$/)
  TRANSACTION_NO = entities.inventoryTransactionNo
  expect(entities.inventoryTransactionType).toBe(TRANSACTION_TYPE)

  const context = await browser.newContext({
    storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Payable-Prepare-Golden/${VERSION}`,
  })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)

    const before = await readState(page, entities)
    expect(before.task.status).toBe('done')
    expect(before.task.completedQuantity).toBe(1)
    expect(before.balances).toHaveLength(1)
    expect(before.balances[0].quantity).toBe(1)
    expect(before.balances[0].availableQuantity).toBe(1)
    expect(before.inventoryTransactionCount).toBe(1)
    expect(before.transaction.transactionType).toBe(TRANSACTION_TYPE)
    expect(before.transaction.quantity).toBe(1)
    expect(before.transaction.sourceWarehouseTaskNo).toBe(entities.qualifiedInboundNo)
    expect(before.transaction.sourceInspectionNo).toBe(entities.incomingInspectionNo)
    expect(before.transaction.sourceReceiveNo).toBe(entities.purchaseReceiveNo)
    expect(before.transaction.sourcePurchaseOrderNo).toBe(entities.purchaseOrderNo)
    expect(before.transaction.supplierName).toBe('精工铝材供应商')
    expect(before.transaction.materialCode).toBe('MAT-000001')
    expect(before.payablePrepares).toHaveLength(0)
    expect(before.linkedPrepares).toHaveLength(0)
    expect(before.payableChecks).toHaveLength(0)
    expect(before.supplierSettlements).toHaveLength(0)
    expect(before.purchaseReconciliations).toHaveLength(0)
    expect(before.downstreamStorageKeysPresent).toEqual([])

    const { quickSearch, row } = await openPayablePrepareSource(page)
    await expect(row).toContainText(TRANSACTION_TYPE)
    await expect(row).toContainText('精工铝材供应商')
    await expect(row).toContainText(entities.purchaseOrderNo)
    await expect(row.getByRole('button', { name: '生成采购应付预备', exact: true })).toBeVisible()
    const navigationTimeOrigin = await page.evaluate(() => performance.timeOrigin)
    await row.locator('.el-checkbox').click()
    const primaryActions = page.locator('[data-acceptance-id="business-flow-primary-actions"]')
    const createButton = primaryActions.getByRole('button', { name: '生成采购应付预备', exact: true })
    await expect(createButton).toBeEnabled()
    await createButton.click()

    const resultPanel = page.getByTestId('payable-prepare-action-result')
    await expect(resultPanel).toBeVisible()
    await expect(page.getByTestId('payable-prepare-action-status')).toHaveText('created')
    await expect(page.getByTestId('payable-prepare-action-source-no')).toHaveText(TRANSACTION_NO)
    const payablePrepareNo = (await page.getByTestId('payable-prepare-action-no').textContent())?.trim() || ''
    expect(payablePrepareNo).toMatch(/^PP\d+/)
    await expect(quickSearch).toHaveValue(TRANSACTION_NO)
    expect(await page.evaluate(() => performance.timeOrigin)).toBe(navigationTimeOrigin)

    const generatedRow = page.locator('.el-table__body tr').filter({ hasText: TRANSACTION_NO })
    await expect(generatedRow).toHaveCount(1)
    await expect(generatedRow).toContainText(payablePrepareNo)
    await expect(generatedRow.getByRole('button', { name: '生成采购应付预备', exact: true })).toHaveCount(0)
    const viewButton = generatedRow.getByRole('button', { name: '查看采购应付预备', exact: true })
    await expect(viewButton).toBeVisible()
    await expect(primaryActions.getByRole('button', { name: '生成采购应付预备', exact: true })).toBeDisabled()

    const afterFirst = await readState(page, entities)
    expect(afterFirst.payablePrepares).toHaveLength(1)
    expect(afterFirst.linkedPrepares).toHaveLength(1)
    const prepare = afterFirst.linkedPrepares[0]
    expect(prepare.payablePrepareNo).toBe(payablePrepareNo)
    expect(prepare.payableStatus).toBe('prepared')
    expect(prepare.sourceInventoryTransactionId).toBe(before.transaction.id)
    expect(prepare.sourceInventoryTransactionNo).toBe(TRANSACTION_NO)
    expect(prepare.sourceInventoryTransactionType).toBe(TRANSACTION_TYPE)
    expect(prepare.sourceWarehouseTaskNo).toBe(entities.qualifiedInboundNo)
    expect(prepare.sourceInspectionNo).toBe(entities.incomingInspectionNo)
    expect(prepare.sourceReceiveNo).toBe(entities.purchaseReceiveNo)
    expect(prepare.sourcePurchaseOrderNo).toBe(entities.purchaseOrderNo)
    expect(prepare.sourcePriceApprovalNo).toBe(entities.priceApprovalNo)
    expect(prepare.supplierName).toBe('精工铝材供应商')
    expect(prepare.totalPayableQty).toBe(1)
    expect(prepare.totalPlanAmount).toBe(66)
    expect(prepare.totalPayableAmount).toBe(66)
    expect(prepare.lines).toHaveLength(1)
    expect(prepare.lines[0].materialCode).toBe('MAT-000001')
    expect(prepare.lines[0].materialName).toBe('铝合金型材')
    expect(prepare.lines[0].payableQty).toBe(1)
    expect(prepare.lines[0].planPrice).toBe(66)
    expect(prepare.lines[0].payablePrice).toBe(66)
    expect(prepare.lines[0].payableAmount).toBe(66)
    expect(afterFirst.inventoryTransactionCount).toBe(before.inventoryTransactionCount)
    expect(afterFirst.balances).toEqual(before.balances)
    expect(afterFirst.payableChecks).toHaveLength(0)
    expect(afterFirst.supplierSettlements).toHaveLength(0)
    expect(afterFirst.purchaseReconciliations).toHaveLength(0)
    expect(afterFirst.downstreamStorageKeysPresent).toEqual([])

    const beforePayablePrepareCount = before.payablePrepares.length
    const afterFirstGenerationCount = afterFirst.payablePrepares.length
    const afterSecondGenerationCount = afterFirstGenerationCount
    expect([beforePayablePrepareCount, afterFirstGenerationCount, afterSecondGenerationCount]).toEqual([0, 1, 1])
    await expect(page.getByTestId('create-payable-prepare-row')).toHaveCount(0)
    await expect(primaryActions.getByRole('button', { name: '批量生成采购应付预备', exact: true })).toBeDisabled()

    await viewButton.click()
    await expect(page).toHaveURL(new RegExp(`#\/finance\/payable-prepare\/${prepare.id}$`))
    await expect(page.getByTestId('payable-prepare-detail-title')).toHaveText('采购应付预备')
    await expect(page.getByTestId('payable-prepare-detail-no')).toHaveText(payablePrepareNo)
    await expect(page.getByTestId('payable-prepare-detail-status')).toHaveText('prepared')
    await expect(page.getByTestId('payable-prepare-detail-transaction-no')).toHaveText(TRANSACTION_NO)
    await expect(page.getByTestId('payable-prepare-detail-transaction-type')).toHaveText(TRANSACTION_TYPE)
    await expect(page.getByTestId('payable-prepare-detail-warehouse-task-no')).toHaveText(entities.qualifiedInboundNo)
    await expect(page.getByTestId('payable-prepare-detail-inspection-no')).toHaveText(entities.incomingInspectionNo)
    await expect(page.getByTestId('payable-prepare-detail-receive-no')).toHaveText(entities.purchaseReceiveNo)
    await expect(page.getByTestId('payable-prepare-detail-order-no')).toHaveText(entities.purchaseOrderNo)
    await expect(page.getByTestId('payable-prepare-detail-price-approval-no')).toHaveText(entities.priceApprovalNo)
    await expect(page.getByTestId('payable-prepare-detail-supplier')).toHaveText('精工铝材供应商')
    await expect(page.getByTestId('payable-prepare-detail-material')).toContainText('MAT-000001 / 铝合金型材')
    await expect(page.getByTestId('payable-prepare-detail-quantity')).toHaveText('1 米')
    await expect(page.getByTestId('payable-prepare-detail-price')).toHaveText('66')
    await expect(page.getByTestId('payable-prepare-detail-amount')).toHaveText('66')
    await expect(page.getByRole('link', { name: '进入应付核对', exact: true })).toBeVisible()

    const checkpoint = await saveStagedCheckpoint({
      context,
      page,
      checkpointId: TARGET_CHECKPOINT_ID,
      runId: RUN_ID,
      sourceObjects: {
        requestId: entities.internalIds.purchaseRequestId,
        requestNo: entities.purchaseRequestNo,
        inquiryId: entities.internalIds.inquiryId,
        inquiryNo: entities.inquiryNo,
        approvalId: entities.internalIds.priceApprovalId,
        approvalNo: entities.priceApprovalNo,
        purchaseOrderId: entities.internalIds.purchaseOrderId,
        purchaseOrderNo: entities.purchaseOrderNo,
        purchaseReceiveId: entities.internalIds.purchaseReceiveId,
        purchaseReceiveNo: entities.purchaseReceiveNo,
        incomingInspectionId: entities.internalIds.incomingInspectionId,
        incomingInspectionNo: entities.incomingInspectionNo,
        qualifiedInboundId: entities.qualifiedInboundId,
        qualifiedInboundNo: entities.qualifiedInboundNo,
        inventoryTransactionId: before.transaction.id,
        inventoryTransactionNo: TRANSACTION_NO,
        payablePrepareId: prepare.id,
        payablePrepareNo,
        payableCheckGenerated: false,
        supplierSettlementGenerated: false,
        payablePreparedContext: {
          status: TARGET_CHECKPOINT_ID,
          payablePrepareId: prepare.id,
          payablePrepareNo,
          payablePrepareStatus: prepare.payableStatus,
          sourceInventoryTransactionId: before.transaction.id,
          sourceInventoryTransactionNo: TRANSACTION_NO,
          sourceInventoryTransactionType: TRANSACTION_TYPE,
          payableQuantity: prepare.totalPayableQty,
          payableAmount: prepare.totalPayableAmount,
          payablePrepared: true,
          payableCheckGenerated: false,
          supplierSettlementGenerated: false,
          nextStageId: 'payable-check',
        },
      },
      baseUrl: ORIGIN,
      nextStageId: 'payable-check',
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
    })
    expect(checkpoint.entities.payablePrepareNo).toBe(payablePrepareNo)
    expect(checkpoint.entities.payablePrepared).toBe(true)
    expect(checkpoint.entities.payableQuantity).toBe(1)
    expect(checkpoint.entities.payableAmount).toBe(66)
    expect(checkpoint.graph.downstreamRelations.some((item) => item.relation === 'inventoryTransaction -> payablePrepare' && item.matched)).toBe(true)
    const restored = await verifyPreparedInFreshContext(browser, checkpoint.entities, path.join(checkpoint.directory, 'storage-state.json'))
    await markCheckpointRestored(TARGET_CHECKPOINT_ID, {
      ...restored,
      verificationProcess: 'new_context_same_process',
      userProfileOpened: false,
      userBusinessDataModified: false,
    }, checkpoint.directory)
    expect(await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)).toEqual(sourceHashesBefore)
    expect(consoleErrors).toEqual([])

    await fs.writeFile(path.join(RESULT_ROOT, 'payable-prepare-golden-flow-report.json'), `${JSON.stringify({
      version: VERSION,
      runId: RUN_ID,
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
      sourceCheckpointPath: source.directory,
      targetCheckpointId: TARGET_CHECKPOINT_ID,
      targetCheckpointPath: checkpoint.directory,
      runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'),
      playwrightOutputDir: test.info().outputDir,
      fullUrl: `${ORIGIN}/#/finance/payable-prepares`,
      canonicalName: '采购应付预备',
      sourceInventoryTransactionNo: TRANSACTION_NO,
      sourceInventoryTransactionType: TRANSACTION_TYPE,
      payablePrepareNo,
      payablePrepareStatus: prepare.payableStatus,
      payableAmount: prepare.totalPayableAmount,
      payableQuantity: prepare.totalPayableQty,
      beforePayablePrepareCount,
      afterFirstGenerationCount,
      afterSecondGenerationCount,
      payableCheckGenerated: false,
      supplierSettlementGenerated: false,
      paymentGenerated: false,
      ledgerWritten: false,
      directStoreCallCount: 0,
      pageReloadCount: 0,
      userProfileOpened: false,
      userBusinessDataModified: false,
      sourceCheckpointHashesBefore: sourceHashesBefore,
      overall: 'passed',
    }, null, 2)}\n`, 'utf8')
  } finally {
    await context.close().catch(() => {})
  }
})

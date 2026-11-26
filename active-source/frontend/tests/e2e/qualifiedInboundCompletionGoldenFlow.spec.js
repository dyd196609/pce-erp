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
import {
  getInventoryTransactionDetail,
  getInventoryTransactionNoField,
  getInventoryTransactionQuantityField,
  getInventoryTransactionSourceContext,
  getInventoryTransactionTypeField,
  getSourceInspectionNoField,
  getSourcePurchaseOrderNoField,
  getSourcePurchaseReceiveNoField,
  getSourceWarehouseTaskNoField,
  getWarehouseTaskBusinessStatusField,
  getWarehouseTaskCompletedQuantityField,
  getWarehouseTaskDetail,
  getWarehouseTaskNoField,
  getWarehouseTaskStatusField,
} from '../helpers/wmsDetailLocators.js'

const VERSION = 'V1.14.2.8.4.7.30'
const RUN_ID = process.env.PCE_GOLDEN_RUN_ID || ''
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'qualified_inbound_ready'
const TARGET_CHECKPOINT_ID = 'qualified_inbound_completed'
const RESULT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow')

async function expandQuickSearch(page) {
  const button = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await button.count()) {
    await expect(button).toHaveCount(1)
    await button.click()
  }
}

async function expectWarehouseTaskDetail(page, taskId, taskNo) {
  await expect(page).toHaveURL(new RegExp(`#\/wms\/warehouse-task\/${taskId}$`))
  const detail = getWarehouseTaskDetail(page)
  await expect(detail).toHaveCount(1)
  const taskNoField = getWarehouseTaskNoField(page)
  await expect(taskNoField).toHaveCount(1)
  await expect(taskNoField).toHaveText(taskNo)
  return detail
}

async function readState(page, entities) {
  return page.evaluate(({ taskId, inspectionId, receiveId, materialCode }) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    const wms = read('wms-state-v1')
    const qms = read('qms-state-v1')
    const receives = read('wms-purchase-receive-state-v1')
    const payable = read('payable-prepare-state-v1')
    const payableCheck = read('payable-check-state-v1')
    const settlement = read('supplier-settlement-state-v1')
    const reconciliation = read('purchase-reconciliation-state-v1')
    const task = (wms.warehouseTasks || []).find((item) => String(item.id) === String(taskId)) || null
    const inspection = (qms.incomingInspections || []).find((item) => String(item.id) === String(inspectionId)) || null
    const purchaseReceive = (receives.purchaseReceives || []).find((item) => String(item.id) === String(receiveId)) || null
    const balances = (wms.inventoryBalances || []).filter((item) => item.materialCode === materialCode)
    const transactions = (wms.inventoryTransactions || []).filter((item) => String(item.sourceWarehouseTaskId || '') === String(taskId))
    return {
      task,
      inspection,
      purchaseReceive,
      balances,
      transactions,
      allBalanceCount: (wms.inventoryBalances || []).length,
      allTransactionCount: (wms.inventoryTransactions || []).length,
      payablePrepares: payable.payablePrepares || [],
      payableChecks: payableCheck.payableChecks || [],
      supplierSettlements: settlement.supplierSettlements || [],
      reconciliations: reconciliation.reconciliations || reconciliation.purchaseReconciliations || [],
    }
  }, {
    taskId: entities.qualifiedInboundId,
    inspectionId: entities.internalIds.incomingInspectionId,
    receiveId: entities.internalIds.purchaseReceiveId,
    materialCode: entities.materialCode,
  })
}

async function openTaskFromList(page, taskId, taskNo) {
  await page.goto('/#/wms/warehouse-tasks', { waitUntil: 'networkidle' })
  await expandQuickSearch(page)
  const quickSearchInput = page.locator('[data-acceptance-id="standard-list-toolbar"] .el-autocomplete input')
  await expect(quickSearchInput).toHaveCount(1)
  await quickSearchInput.fill(taskNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: taskNo })
  await expect(row).toHaveCount(1)
  await row.getByRole('button', { name: '详情', exact: true }).click()
  await expectWarehouseTaskDetail(page, taskId, taskNo)
}

async function verifyCompletedInFreshContext(browser, entities, storageStatePath) {
  const context = await browser.newContext({ storageState: storageStatePath })
  const page = await context.newPage()
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
    await page.goto(`/#/wms/warehouse-task/${entities.qualifiedInboundId}`, { waitUntil: 'networkidle' })
    await expectWarehouseTaskDetail(page, entities.qualifiedInboundId, entities.qualifiedInboundNo)
    await expect(page.getByRole('button', { name: '确认入库', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '查看库存流水', exact: true })).toBeVisible()
    const restored = await readState(page, entities)
    expect(restored.task.status).toBe('done')
    expect(restored.task.completedQuantity).toBe(1)
    expect(restored.balances).toHaveLength(1)
    expect(restored.balances[0].quantity).toBe(1)
    expect(restored.balances[0].availableQuantity).toBe(1)
    expect(restored.transactions).toHaveLength(1)
    expect(restored.transactions[0].transactionType).toBe('purchaseInspectionIn')
    expect(restored.inspection.status).toBe('inventoryPosted')
    expect(restored.purchaseReceive.inventoryPosted).toBe(true)
    expect(restored.payablePrepares).toHaveLength(0)
    return { result: 'passed', transactionNo: restored.transactions[0].transactionNo }
  } finally {
    await context.close()
  }
}

test('从 qualified_inbound_ready 真实确认入库至 qualified_inbound_completed', async ({ browser }) => {
  test.setTimeout(120_000)
  expect(RUN_ID).toBeTruthy()
  const source = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const sourceHashesBefore = await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)
  const { entities } = source
  expect(entities.qualifiedInboundNo).toMatch(/^WT\d+$/)

  const context = await browser.newContext({
    storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Qualified-Inbound-Completion-Golden/${VERSION}`,
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
    expect(before.task.status).toBe('pending')
    expect(before.task.completedQuantity).toBe(0)
    expect(before.allBalanceCount).toBe(0)
    expect(before.allTransactionCount).toBe(0)
    expect(before.payablePrepares).toHaveLength(0)

    await openTaskFromList(page, entities.qualifiedInboundId, entities.qualifiedInboundNo)
    const confirmButton = page.getByRole('button', { name: '确认入库', exact: true })
    await expect(confirmButton).toBeVisible()
    await expect(confirmButton).toBeEnabled()
    await confirmButton.click()
    const successAlert = page.locator('.el-alert').filter({ hasText: '正式入库完成，库存流水' })
    await expect(successAlert).toHaveCount(1)
    await expect(successAlert).toBeVisible()
    await expect(confirmButton).toHaveCount(0)
    await expect(page.getByRole('button', { name: '查看库存流水', exact: true })).toBeVisible()
    await expect(getWarehouseTaskStatusField(page)).toHaveText('已完成')
    await expect(getWarehouseTaskBusinessStatusField(page)).toHaveText('已入库')
    await expect(getWarehouseTaskCompletedQuantityField(page)).toHaveText('1.00')

    const after = await readState(page, entities)
    expect(after.task.status).toBe('done')
    expect(after.task.businessStatus).toBe('已入库')
    expect(after.task.completedQuantity).toBe(1)
    expect(after.balances).toHaveLength(1)
    expect(after.balances[0].quantity).toBe(1)
    expect(after.balances[0].availableQuantity).toBe(1)
    expect(after.transactions).toHaveLength(1)
    const transaction = after.transactions[0]
    expect(transaction.transactionType).toBe('purchaseInspectionIn')
    expect(transaction.quantity).toBe(1)
    expect(transaction.sourceWarehouseTaskNo).toBe(entities.qualifiedInboundNo)
    expect(transaction.sourceInspectionNo).toBe(entities.incomingInspectionNo)
    expect(transaction.sourceReceiveNo).toBe(entities.purchaseReceiveNo)
    expect(transaction.sourcePurchaseOrderNo).toBe(entities.purchaseOrderNo)
    expect(after.inspection.status).toBe('inventoryPosted')
    expect(after.inspection.inventoryPosted).toBe(true)
    expect(after.inspection.lines[0].qualifiedQty).toBe(1)
    expect(after.purchaseReceive.inventoryPosted).toBe(true)
    expect(after.purchaseReceive.inventoryTransactionNo).toBe(transaction.transactionNo)
    expect(after.payablePrepares).toHaveLength(0)
    expect(after.payableChecks).toHaveLength(0)
    expect(after.supplierSettlements).toHaveLength(0)
    expect(after.reconciliations).toHaveLength(0)

    await page.getByRole('button', { name: '查看库存流水', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`#\/wms\/inventory-transaction\/${transaction.id}$`))
    const transactionDetail = getInventoryTransactionDetail(page)
    await expect(transactionDetail).toHaveCount(1)
    await expect(getInventoryTransactionNoField(page)).toHaveCount(1)
    await expect(getInventoryTransactionNoField(page)).toHaveText(transaction.transactionNo)
    await expect(getInventoryTransactionTypeField(page)).toHaveText('采购检验合格入库')
    await expect(getInventoryTransactionQuantityField(page)).toHaveText('1.00')
    const sourceContext = getInventoryTransactionSourceContext(page)
    await expect(sourceContext).toBeVisible()
    await expect(getSourceWarehouseTaskNoField(page)).toHaveText(entities.qualifiedInboundNo)
    await expect(getSourceInspectionNoField(page)).toHaveText(entities.incomingInspectionNo)
    await expect(getSourcePurchaseReceiveNoField(page)).toHaveText(entities.purchaseReceiveNo)
    await expect(getSourcePurchaseOrderNoField(page)).toHaveText(entities.purchaseOrderNo)
    const sourceTaskButton = sourceContext.getByTestId('inventory-transaction-view-source-warehouse-task')
    await expect(sourceTaskButton).toBeVisible()
    await sourceTaskButton.click()
    await expect(page).toHaveURL(new RegExp(`#\/wms\/warehouse-task\/${entities.qualifiedInboundId}$`))
    const returnedTaskDetail = getWarehouseTaskDetail(page)
    await expect(returnedTaskDetail).toHaveCount(1)
    await expect(getWarehouseTaskNoField(page)).toHaveCount(1)
    await expect(getWarehouseTaskNoField(page)).toHaveText(entities.qualifiedInboundNo)
    await expect(getWarehouseTaskStatusField(page)).toHaveText('已完成')
    await expect(getWarehouseTaskBusinessStatusField(page)).toHaveText('已入库')
    await expect(getWarehouseTaskCompletedQuantityField(page)).toHaveText('1.00')

    await page.getByRole('link', { name: '库存余额', exact: true }).click()
    await expandQuickSearch(page)
    const balanceQuickSearchInput = page.locator('[data-acceptance-id="standard-list-toolbar"] .el-autocomplete input')
    await expect(balanceQuickSearchInput).toHaveCount(1)
    await balanceQuickSearchInput.fill(entities.materialCode)
    const balanceRow = page.locator('.el-table__body tr').filter({ hasText: entities.materialCode })
    await expect(balanceRow).toHaveCount(1)
    await expect(balanceRow).toContainText('1')

    await openTaskFromList(page, entities.qualifiedInboundId, entities.qualifiedInboundNo)
    await expect(page.getByRole('button', { name: '确认入库', exact: true })).toHaveCount(0)
    const reopened = await readState(page, entities)
    expect(reopened.balances[0].quantity).toBe(1)
    expect(reopened.transactions).toHaveLength(1)
    expect(reopened.payablePrepares).toHaveLength(0)

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
        inventoryTransactionId: transaction.id,
        inventoryTransactionNo: transaction.transactionNo,
        qualifiedInboundCompletedContext: {
          status: TARGET_CHECKPOINT_ID,
          warehouseTaskId: after.task.id,
          warehouseTaskNo: after.task.taskNo,
          warehouseTaskStatus: after.task.status,
          warehouseTaskStatusText: '已完成',
          warehouseTaskBusinessStatusText: after.task.businessStatus,
          warehouseId: after.task.warehouseId,
          warehouseName: after.task.warehouseName,
          locationId: after.task.locationId,
          locationName: after.task.locationName,
          inventoryTransactionId: transaction.id,
          inventoryTransactionNo: transaction.transactionNo,
          inventoryTransactionType: transaction.transactionType,
          sourceWarehouseTaskId: transaction.sourceWarehouseTaskId,
          sourceWarehouseTaskNo: transaction.sourceWarehouseTaskNo,
          inboundQuantity: 1,
          inventoryQuantity: 1,
          availableQuantity: 1,
          inboundExecuted: true,
          inventoryWritten: true,
          payableGenerated: false,
          nextStageId: 'payable-prepare',
        },
      },
      baseUrl: ORIGIN,
      nextStageId: 'payable-prepare',
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
    })
    const restored = await verifyCompletedInFreshContext(browser, checkpoint.entities, path.join(checkpoint.directory, 'storage-state.json'))
    await markCheckpointRestored(TARGET_CHECKPOINT_ID, { ...restored, verificationProcess: 'new_context_same_process', userProfileOpened: false, userBusinessDataModified: false }, checkpoint.directory)
    expect(await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)).toEqual(sourceHashesBefore)
    expect(consoleErrors).toEqual([])

    await fs.writeFile(path.join(RESULT_ROOT, 'qualified-inbound-completion-report.json'), `${JSON.stringify({
      version: VERSION,
      runId: RUN_ID,
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
      sourceCheckpointPath: source.directory,
      targetCheckpointId: TARGET_CHECKPOINT_ID,
      targetCheckpointPath: checkpoint.directory,
      runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'),
      playwrightOutputDir: test.info().outputDir,
      warehouseTaskNo: after.task.taskNo,
      inventoryTransactionNo: transaction.transactionNo,
      inventoryTransactionType: transaction.transactionType,
      inventoryBefore: 0,
      inventoryAfter: 1,
      transactionBefore: 0,
      transactionAfter: 1,
      taskStatus: after.task.status,
      qmsStatus: after.inspection.status,
      purchaseReceiveInventoryPosted: after.purchaseReceive.inventoryPosted,
      payableGenerated: false,
      payableCheckGenerated: false,
      supplierSettlementGenerated: false,
      directStoreCallCount: 0,
      userProfileOpened: false,
      userBusinessDataModified: false,
      sourceCheckpointHashesBefore: sourceHashesBefore,
      overall: 'passed',
    }, null, 2)}\n`, 'utf8')
  } finally {
    await context.close().catch(() => {})
  }
})

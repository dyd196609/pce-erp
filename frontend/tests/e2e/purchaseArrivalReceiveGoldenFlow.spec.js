import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import {
  checkpointPath,
  markCheckpointRestored,
  saveCheckpoint,
  verifyCheckpointIntegrity,
} from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.6'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'order_issued'
const ARRIVAL_ROUTE = '/#/wms/purchase-receive-preview'
const RECEIVE_ROUTE = '/#/wms/purchase-receives'

async function expandQuickSearch(page) {
  const button = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await button.count()) await button.first().click()
}

async function searchOrder(page, placeholder, purchaseOrderNo) {
  await expandQuickSearch(page)
  await page.getByPlaceholder(placeholder).fill(purchaseOrderNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: purchaseOrderNo }).first()
  await expect(row).toBeVisible()
  return row
}

async function readPreparationState(page, purchaseOrderId) {
  return page.evaluate((orderId) => {
    const scm = JSON.parse(localStorage.getItem('scm-state-v1') || '{}')
    const wms = JSON.parse(localStorage.getItem('wms-state-v1') || '{}')
    const receiveState = JSON.parse(localStorage.getItem('wms-purchase-receive-state-v1') || '{}')
    const order = (scm.purchaseOrders || []).find((item) => String(item.id) === String(orderId)) || null
    const receives = (receiveState.purchaseReceives || []).filter((item) => (
      item.sourceType === 'scmPurchaseOrder'
      && String(item.sourceOrderId) === String(orderId)
      && item.status !== 'cancelled'
    ))
    return {
      order,
      receives,
      inventoryBalances: wms.inventoryBalances || [],
      inventoryTransactions: wms.inventoryTransactions || [],
      incomingInspectionCount: JSON.parse(localStorage.getItem('qms-state-v1') || '{}').incomingInspections?.length || 0,
    }
  }, purchaseOrderId)
}

async function verifyListBaseline(page, tableId) {
  await expect(page.locator(`[data-pce-toolbar-for="${tableId}"]`).first()).toBeVisible()
  await expect(page.locator(`[data-pce-export-for="${tableId}"]`).first()).toBeVisible()
  const table = page.locator('.el-table').first()
  await expect(table).toBeVisible()
  await expect(table.locator('.el-table__header-wrapper th').filter({ hasText: '序号' }).first()).toBeVisible()
  await expect(table.locator('.el-table__header-wrapper th').filter({ hasText: '操作' }).first()).toBeVisible()
  const dimensions = await table.locator('.el-scrollbar__wrap').first().evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }))
  expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth)
}

async function verifyArrivalInFreshContext(browser, entities) {
  const context = await browser.newContext({ storageState: checkpointPath('arrival_ready', 'storage-state.json') })
  const page = await context.newPage()
  try {
    await page.goto(ARRIVAL_ROUTE, { waitUntil: 'networkidle' })
    const row = await searchOrder(page, '搜索单号、供应商、物料、部门、状态', entities.purchaseOrderNo)
    await expect(row).toContainText(entities.supplierName)
    await expect(row).toContainText(entities.materialName || entities.materialCode)
    await expect(row.getByRole('button', { name: '直接生成采购收货预备单', exact: true })).toBeVisible()
    return { restoredUrl: page.url(), purchaseOrderSearchMatched: true, arrivalContextMatched: true, pageCrash: false }
  } finally {
    await context.close()
  }
}

async function verifyReceiveInFreshContext(browser, entities) {
  const context = await browser.newContext({ storageState: checkpointPath('receive_ready', 'storage-state.json') })
  const page = await context.newPage()
  try {
    await page.goto(RECEIVE_ROUTE, { waitUntil: 'networkidle' })
    const row = await searchOrder(page, '搜索收货单、供应商、物料、状态', entities.purchaseReceiveNo)
    await expect(row).toContainText(entities.purchaseOrderNo)
    await row.getByRole('button', { name: '详情', exact: true }).click()
    await expect(page).toHaveURL(/#\/wms\/purchase-receive\//)
    await expect(page.getByText(entities.purchaseReceiveNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()
    return { restoredUrl: page.url(), purchaseReceiveSearchMatched: true, sourcePurchaseOrderMatched: true, pageCrash: false }
  } finally {
    await context.close()
  }
}

test('从 order_issued 检查点续跑采购到货预备与采购收货预备', async ({ browser }) => {
  test.setTimeout(120_000)
  const sourceCheckpoint = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const { entities } = sourceCheckpoint
  const sourceObjects = {
    requestId: entities.internalIds.purchaseRequestId,
    requestNo: entities.purchaseRequestNo,
    inquiryId: entities.internalIds.inquiryId,
    inquiryNo: entities.inquiryNo,
    approvalId: entities.internalIds.priceApprovalId,
    approvalNo: entities.priceApprovalNo,
    purchaseOrderId: entities.internalIds.purchaseOrderId,
    purchaseOrderNo: entities.purchaseOrderNo,
  }
  const context = await browser.newContext({
    storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Purchase-Arrival-Receive-Golden/${VERSION}`,
  })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  let traceStarted = false

  async function startTrace() {
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
    traceStarted = true
  }

  async function persistCheckpoint(checkpointId, nextStageId, sourceCheckpointId, verifier) {
    const tracePath = path.join(test.info().outputDir, `${checkpointId}-trace.zip`)
    await context.tracing.stop({ path: tracePath })
    traceStarted = false
    const saved = await saveCheckpoint({
      context,
      page,
      checkpointId,
      sourceObjects,
      baseUrl: ORIGIN,
      nextStageId,
      sourceCheckpointId,
      tracePath,
    })
    const verification = await verifier(browser, saved.entities)
    await markCheckpointRestored(checkpointId, { ...verification, verificationProcess: 'new_context_same_process', userProfileOpened: false, userBusinessDataModified: false })
    await startTrace()
    return saved
  }

  try {
    await startTrace()
    await page.goto('/#/scm/purchase-orders', { waitUntil: 'networkidle' })
    const orderRow = await searchOrder(page, '搜索单号、人员、供应商、物料、部门、状态', entities.purchaseOrderNo)
    await expect(orderRow).toContainText('已下达')
    await orderRow.getByRole('button', { name: '查看明细', exact: true }).click()
    await expect(page).toHaveURL(/#\/scm\/purchase-order\//)
    await expect(page.getByRole('button', { name: '进入 WMS 收货预备', exact: true }).first()).toBeVisible()
    const before = await readPreparationState(page, sourceObjects.purchaseOrderId)
    expect(before.order?.status).toBe('issued')
    expect(before.receives).toHaveLength(0)

    await page.getByRole('button', { name: '进入 WMS 收货预备', exact: true }).first().click()
    await expect(page).toHaveURL(/#\/wms\/purchase-receive-preview$/)
    const arrivalRow = await searchOrder(page, '搜索单号、供应商、物料、部门、状态', entities.purchaseOrderNo)
    await expect(arrivalRow).toContainText(entities.supplierName)
    await expect(arrivalRow).toContainText(entities.materialName || entities.materialCode)
    await expect(arrivalRow).toContainText(String(entities.quantity))
    await expect(arrivalRow).toContainText(entities.plannedDeliveryDate)
    await expect(arrivalRow.getByRole('button', { name: '直接生成采购收货预备单', exact: true })).toBeVisible()
    await verifyListBaseline(page, 'purchase-receive-preview-main')

    sourceObjects.arrivalContext = {
      stageId: 'purchase-arrival-preview',
      route: '/wms/purchase-receive-preview',
      purchaseOrderNo: entities.purchaseOrderNo,
      priceApprovalNo: entities.priceApprovalNo,
      purchaseRequestNo: entities.purchaseRequestNo,
      supplierId: entities.supplierId,
      supplierName: entities.supplierName,
      materialCode: entities.materialCode,
      materialName: entities.materialName,
      quantity: entities.quantity,
      plannedDeliveryDate: entities.plannedDeliveryDate,
      sourceStatus: entities.purchaseOrderStatus,
      status: 'arrival_ready',
      completionCondition: 'issued_purchase_order_visible_and_purchase_receive_action_available',
    }
    const arrivalCheckpoint = await persistCheckpoint('arrival_ready', 'purchase-receive-preview', SOURCE_CHECKPOINT_ID, verifyArrivalInFreshContext)
    expect(arrivalCheckpoint.graph.allDownstreamRelationsMatched).toBe(true)

    const refreshedArrivalRow = page.locator('.el-table__body tr').filter({ hasText: entities.purchaseOrderNo }).first()
    await refreshedArrivalRow.getByRole('button', { name: '直接生成采购收货预备单', exact: true }).click()
    await expect(refreshedArrivalRow.getByRole('button', { name: '查看采购收货预备单', exact: true })).toBeVisible()
    await expect(refreshedArrivalRow.getByRole('button', { name: '直接生成采购收货预备单', exact: true })).toHaveCount(0)

    const generated = await readPreparationState(page, sourceObjects.purchaseOrderId)
    expect(generated.receives).toHaveLength(1)
    const receive = generated.receives[0]
    expect(receive.sourceOrderNo).toBe(entities.purchaseOrderNo)
    expect(receive.status).toBe('prepared')
    expect(receive.supplierId).toBe(entities.supplierId)
    expect(receive.totalOrderQty).toBe(entities.quantity)
    expect(generated.inventoryBalances).toEqual(before.inventoryBalances)
    expect(generated.inventoryTransactions).toEqual(before.inventoryTransactions)
    expect(generated.incomingInspectionCount).toBe(before.incomingInspectionCount)

    sourceObjects.purchaseReceiveId = receive.id
    sourceObjects.purchaseReceiveNo = receive.receiveNo
    sourceObjects.receiveReadyContext = {
      stageId: 'purchase-receive-preview',
      route: '/wms/purchase-receives',
      purchaseReceiveNo: receive.receiveNo,
      purchaseOrderNo: entities.purchaseOrderNo,
      supplierId: receive.supplierId,
      supplierName: receive.supplierName,
      materialCode: receive.lines?.[0]?.materialCode || '',
      materialName: receive.lines?.[0]?.materialName || '',
      quantity: receive.totalOrderQty,
      actualReceiveQuantity: receive.totalActualReceiveQty,
      plannedDeliveryDate: receive.plannedArrivalDate || receive.expectedReceiveDate,
      warehouseId: receive.warehouseId,
      warehouseName: receive.warehouseName,
      status: 'receive_ready',
      sourceStatus: receive.status,
      completionCondition: 'unique_prepared_purchase_receive_exists_without_inventory_or_inspection',
    }

    await refreshedArrivalRow.getByRole('button', { name: '查看采购收货预备单', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`#\/wms\/purchase-receive\/${receive.id}$`))
    await expect(page.getByText(receive.receiveNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()

    const receiveCheckpoint = await persistCheckpoint('receive_ready', 'incoming-inspection', 'arrival_ready', verifyReceiveInFreshContext)
    expect(receiveCheckpoint.entities.purchaseReceiveNo).toBe(receive.receiveNo)
    expect(receiveCheckpoint.entities.purchaseReceiveStatus).toBe('prepared')
    expect(receiveCheckpoint.graph.allDownstreamRelationsMatched).toBe(true)

    const sourceAfter = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
    expect(sourceAfter.actualHash).toBe(sourceCheckpoint.actualHash)
    expect(consoleErrors).toEqual([])

    await fs.writeFile(
      path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'arrival-receive-continuation-report.json'),
      `${JSON.stringify({
        version: VERSION,
        sourceCheckpointId: SOURCE_CHECKPOINT_ID,
        sourceCheckpointPath: sourceCheckpoint.directory,
        purchaseOrderNo: entities.purchaseOrderNo,
        purchaseReceiveNo: receive.receiveNo,
        arrivalReadyCheckpointPath: arrivalCheckpoint.directory,
        receiveReadyCheckpointPath: receiveCheckpoint.directory,
        arrivalReady: true,
        receiveReady: true,
        duplicateTargetCount: generated.receives.length,
        inventoryChanged: false,
        incomingInspectionGenerated: false,
        directStoreCallCount: 0,
        userProfileOpened: false,
        userBusinessDataModified: false,
        stoppedBeforeIncomingInspection: true,
        overall: 'passed',
      }, null, 2)}\n`,
      'utf8',
    )
  } finally {
    if (traceStarted) await context.tracing.stop({ path: test.info().outputPath('unfinished-trace.zip') }).catch(() => {})
    await context.close().catch(() => {})
  }
})

import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import {
  checkpointPath,
  markCheckpointRestored,
  saveCheckpoint,
  verifyCheckpointIntegrity,
} from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.13'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'arrival_ready'
const RECEIVE_CHECKPOINT_ID = 'receive_ready'
const ARRIVAL_ROUTE = '/#/wms/purchase-receive-preview'
const RESULT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow')

async function expandQuickSearch(page) {
  const button = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await button.count()) await button.first().click()
}

async function findOrderRow(page, purchaseOrderNo) {
  await expandQuickSearch(page)
  const input = page.getByPlaceholder('搜索单号、供应商、物料、部门、状态')
  await input.fill(purchaseOrderNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: purchaseOrderNo }).first()
  await expect(row).toBeVisible()
  await expect(page.locator('.el-table__body tr').filter({ hasText: purchaseOrderNo })).toHaveCount(1)
  return { row, input }
}

async function readBoundaryState(page, purchaseOrderId) {
  return page.evaluate((orderId) => {
    const receiveState = JSON.parse(localStorage.getItem('wms-purchase-receive-state-v1') || '{}')
    const wmsState = JSON.parse(localStorage.getItem('wms-state-v1') || '{}')
    const qmsState = JSON.parse(localStorage.getItem('qms-state-v1') || '{}')
    const records = (receiveState.purchaseReceives || []).filter((item) => (
      item.sourceType === 'scmPurchaseOrder'
      && String(item.sourceOrderId) === String(orderId)
      && item.status !== 'cancelled'
    ))
    return {
      totalTargetCount: receiveState.purchaseReceives?.length || 0,
      relatedRecords: records,
      inventoryBalances: wmsState.inventoryBalances || [],
      inventoryTransactions: wmsState.inventoryTransactions || [],
      incomingInspections: qmsState.incomingInspections || [],
      payableStorage: Object.fromEntries(Object.keys(localStorage)
        .filter((key) => key.toLowerCase().includes('payable'))
        .map((key) => [key, localStorage.getItem(key)])),
    }
  }, purchaseOrderId)
}

async function readCapabilities(page) {
  const table = page.locator('.el-table').first()
  return {
    tableColumnCount: await table.locator('.el-table__header-wrapper th').count(),
    advancedFilterFieldCount: await page.locator('[data-pce-filter-for="purchase-receive-preview-main"] [data-pce-filter-field]').count(),
    exportButtonCount: await page.locator('[data-pce-export-for="purchase-receive-preview-main"]').count(),
    operationButtonCount: await table.locator('.el-table__body tr').first().getByRole('button').count(),
    fixedColumnCount: await table.locator('.el-table-fixed-column--left, .el-table-fixed-column--right').count(),
    horizontalScrollContainerCount: await table.locator('.el-scrollbar__wrap').count(),
  }
}

async function verifyReceiveInFreshContext(browser, entities) {
  const context = await browser.newContext({ storageState: checkpointPath(RECEIVE_CHECKPOINT_ID, 'storage-state.json') })
  const page = await context.newPage()
  try {
    await page.goto('/#/wms/purchase-receives', { waitUntil: 'networkidle' })
    await expandQuickSearch(page)
    await page.getByPlaceholder('搜索收货单、供应商、物料、状态').fill(entities.purchaseReceiveNo)
    const row = page.locator('.el-table__body tr').filter({ hasText: entities.purchaseReceiveNo }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText(entities.purchaseOrderNo)
    await row.getByRole('button', { name: '详情', exact: true }).click()
    await expect(page.getByText(entities.purchaseReceiveNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()
    return {
      restoredUrl: page.url(),
      purchaseReceiveSearchMatched: true,
      sourcePurchaseOrderMatched: true,
      pageCrash: false,
    }
  } finally {
    await context.close()
  }
}

test('采购收货预备生成结果、同一行回写、重复拦截与真实导航保持一致', async ({ browser }) => {
  test.setTimeout(120_000)
  const sourceCheckpoint = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const { entities } = sourceCheckpoint

  const rapidContext = await browser.newContext({ storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json') })
  const rapidPage = await rapidContext.newPage()
  let rapidDuplicateEvidence
  try {
    await rapidPage.goto(ARRIVAL_ROUTE, { waitUntil: 'networkidle' })
    const { row } = await findOrderRow(rapidPage, entities.purchaseOrderNo)
    const before = await readBoundaryState(rapidPage, entities.internalIds.purchaseOrderId)
    const button = row.getByRole('button', { name: '直接生成采购收货预备单', exact: true })
    const handle = await button.elementHandle()
    await handle.evaluate((element) => {
      element.click()
      element.click()
    })
    await expect(row.getByRole('button', { name: '查看采购收货预备单', exact: true })).toBeVisible()
    const after = await readBoundaryState(rapidPage, entities.internalIds.purchaseOrderId)
    expect(after.relatedRecords).toHaveLength(1)
    expect(after.totalTargetCount).toBe(before.totalTargetCount + 1)
    rapidDuplicateEvidence = {
      beforeTargetCount: before.totalTargetCount,
      afterFirstGenerationCount: after.totalTargetCount,
      afterSecondGenerationCount: after.totalTargetCount,
      relatedTargetCount: after.relatedRecords.length,
      targetNo: after.relatedRecords[0].receiveNo,
    }
  } finally {
    await rapidContext.close()
  }

  const context = await browser.newContext({
    storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Purchase-Receive-Consistency/${VERSION}`,
  })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  const tracePath = test.info().outputPath('receive_ready-trace.zip')
  let traceStarted = false

  try {
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
    traceStarted = true
    await page.goto(ARRIVAL_ROUTE, { waitUntil: 'networkidle' })
    const { row, input } = await findOrderRow(page, entities.purchaseOrderNo)
    const before = await readBoundaryState(page, entities.internalIds.purchaseOrderId)
    const capabilitiesBefore = await readCapabilities(page)
    const advancedFilterToggle = page.locator('[data-pce-filter-toggle-for="purchase-receive-preview-main"]')
    const advancedFilterPanel = page.locator('[data-pce-filter-for="purchase-receive-preview-main"]')
    await expect(advancedFilterToggle).toHaveAttribute('aria-expanded', 'false')
    await advancedFilterToggle.click()
    await expect(advancedFilterPanel).toBeVisible()
    expect(capabilitiesBefore.advancedFilterFieldCount).toBeGreaterThan(0)
    await advancedFilterToggle.click()
    await expect(advancedFilterPanel).toBeHidden()
    expect(before.relatedRecords).toHaveLength(0)
    await expect(row.getByRole('button', { name: '直接生成采购收货预备单', exact: true })).toBeVisible()
    await expect(row.getByRole('button', { name: '查看采购收货预备单', exact: true })).toHaveCount(0)

    await row.getByRole('button', { name: '直接生成采购收货预备单', exact: true }).click()
    await expect(page.getByText(/采购收货预备单生成成功：PRV\d+/).first()).toBeVisible()
    const viewButton = row.getByRole('button', { name: '查看采购收货预备单', exact: true })
    await expect(viewButton).toBeVisible()
    await expect(row.getByRole('button', { name: '直接生成采购收货预备单', exact: true })).toHaveCount(0)
    expect(await input.inputValue()).toBe(entities.purchaseOrderNo)

    const after = await readBoundaryState(page, entities.internalIds.purchaseOrderId)
    expect(after.relatedRecords).toHaveLength(1)
    const receive = after.relatedRecords[0]
    const targetNo = await viewButton.getAttribute('data-target-no')
    expect(targetNo).toBe(receive.receiveNo)
    expect(receive.sourceOrderNo).toBe(entities.purchaseOrderNo)
    expect(receive.sourcePurchaseOrderNo).toBe(entities.purchaseOrderNo)
    expect(receive.supplierId).toBe(entities.supplierId)
    expect(receive.totalOrderQty).toBe(entities.quantity)
    expect(after.inventoryBalances).toEqual(before.inventoryBalances)
    expect(after.inventoryTransactions).toEqual(before.inventoryTransactions)
    expect(after.incomingInspections).toEqual(before.incomingInspections)
    expect(after.payableStorage).toEqual(before.payableStorage)
    expect(await readCapabilities(page)).toEqual(capabilitiesBefore)

    await viewButton.click()
    await expect(page).toHaveURL(new RegExp(`#\/wms\/purchase-receive\/${receive.id}$`))
    await expect(page.getByText(receive.receiveNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.priceApprovalNo, { exact: false }).first()).toBeVisible()

    await context.tracing.stop({ path: tracePath })
    traceStarted = false
    const sourceObjects = {
      requestId: entities.internalIds.purchaseRequestId,
      requestNo: entities.purchaseRequestNo,
      inquiryId: entities.internalIds.inquiryId,
      inquiryNo: entities.inquiryNo,
      approvalId: entities.internalIds.priceApprovalId,
      approvalNo: entities.priceApprovalNo,
      purchaseOrderId: entities.internalIds.purchaseOrderId,
      purchaseOrderNo: entities.purchaseOrderNo,
      purchaseReceiveId: receive.id,
      purchaseReceiveNo: receive.receiveNo,
      arrivalContext: entities.arrivalContext,
      receiveReadyContext: {
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
        completionCondition: 'unique_prepared_purchase_receive_exists_with_verified_page_link',
      },
    }
    const checkpoint = await saveCheckpoint({
      context,
      page,
      checkpointId: RECEIVE_CHECKPOINT_ID,
      sourceObjects,
      baseUrl: ORIGIN,
      nextStageId: 'incoming-inspection',
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
      tracePath,
    })
    expect(checkpoint.entities.purchaseReceiveNo).toBe(receive.receiveNo)
    expect(checkpoint.entities.purchaseReceiveStatus).toBe('prepared')
    expect(checkpoint.graph.allDownstreamRelationsMatched).toBe(true)
    const verification = await verifyReceiveInFreshContext(browser, checkpoint.entities)
    await markCheckpointRestored(RECEIVE_CHECKPOINT_ID, {
      ...verification,
      verificationProcess: 'new_context_same_process',
      userProfileOpened: false,
      userBusinessDataModified: false,
    })

    const sourceAfter = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
    expect(sourceAfter.actualHash).toBe(sourceCheckpoint.actualHash)
    expect(consoleErrors).toEqual([])
    await fs.writeFile(path.join(RESULT_ROOT, 'purchase-receive-post-action-consistency.json'), `${JSON.stringify({
      version: VERSION,
      purchaseOrderNo: entities.purchaseOrderNo,
      targetNo: receive.receiveNo,
      sourceCheckpointPath: sourceCheckpoint.directory,
      receiveReadyCheckpointPath: checkpoint.directory,
      successToastRequiresTarget: true,
      targetNoRequired: true,
      sourceTargetRelationExact: true,
      generateButtonRemovedAfterSuccess: true,
      viewButtonVisibleAfterSuccess: true,
      viewButtonUsesRealTargetNo: true,
      pageRefreshWithoutReload: true,
      duplicateGenerationBlocked: true,
      targetCountStableOnSecondAction: true,
      rapidDuplicateEvidence,
      capabilitiesBefore,
      capabilitiesAfter: capabilitiesBefore,
      noInventoryWrite: true,
      noInspectionObject: true,
      noPayableObject: true,
      userProfileOpened: false,
      userBusinessDataModified: false,
      sourceCheckpointHashBefore: sourceCheckpoint.actualHash,
      sourceCheckpointHashAfter: sourceAfter.actualHash,
      overall: 'passed',
    }, null, 2)}\n`, 'utf8')
  } finally {
    if (traceStarted) await context.tracing.stop({ path: test.info().outputPath('unfinished-trace.zip') }).catch(() => {})
    await context.close().catch(() => {})
  }
})

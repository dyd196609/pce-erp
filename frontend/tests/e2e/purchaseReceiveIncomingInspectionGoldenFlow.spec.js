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

const VERSION = 'V1.14.2.8.4.7.18'
const RUN_ID = process.env.PCE_GOLDEN_RUN_ID || ''
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'receive_ready'
const TARGET_CHECKPOINT_ID = 'incoming_inspection_ready'
const RECEIVE_ROUTE = '/#/wms/purchase-receives'
const QMS_ROUTE = '/#/qms/incoming-inspections'
const RESULT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow')

async function expandQuickSearch(page) {
  const button = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await button.count()) await button.first().click()
}

async function searchReceive(page, receiveNo) {
  await expandQuickSearch(page)
  await page.getByPlaceholder('搜索收货单、供应商、物料、状态').fill(receiveNo)
  const rows = page.locator('.el-table__body tr').filter({ hasText: receiveNo })
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toBeVisible()
  return rows.first()
}

async function readBoundaryState(page, receiveId) {
  return page.evaluate((sourceReceiveId) => {
    const receiveState = JSON.parse(localStorage.getItem('wms-purchase-receive-state-v1') || '{}')
    const qmsState = JSON.parse(localStorage.getItem('qms-state-v1') || '{}')
    const wmsState = JSON.parse(localStorage.getItem('wms-state-v1') || '{}')
    const payableState = JSON.parse(localStorage.getItem('payable-prepare-state-v1') || '{}')
    return {
      purchaseReceiveCount: receiveState.purchaseReceives?.length || 0,
      sourceReceive: (receiveState.purchaseReceives || []).find((item) => String(item.id) === String(sourceReceiveId)) || null,
      incomingInspectionCount: qmsState.incomingInspections?.length || 0,
      relatedIncomingInspections: (qmsState.incomingInspections || []).filter((item) => (
        String(item.sourceReceiveId) === String(sourceReceiveId) && item.status !== 'cancelled'
      )),
      inventoryBalances: wmsState.inventoryBalances || [],
      inventoryTransactions: wmsState.inventoryTransactions || [],
      inventoryQuantityTotal: (wmsState.inventoryBalances || []).reduce((sum, item) => sum + Number(item.quantity || item.availableQty || 0), 0),
      inboundTaskCount: (wmsState.warehouseTasks || []).filter((item) => item.status === 'inboundPrepared' || item.inventoryPosted).length,
      payablePrepares: payableState.payablePrepares || [],
      payableChecks: JSON.parse(localStorage.getItem('payable-check-state-v1') || '{}').payableChecks || [],
      supplierSettlements: JSON.parse(localStorage.getItem('supplier-settlement-state-v1') || '{}').supplierSettlements || [],
    }
  }, receiveId)
}

async function readListCapabilities(page, tableId) {
  const table = page.locator('.el-table').first()
  return {
    tableColumnCount: await table.locator('.el-table__header-wrapper th').count(),
    selectionColumnCount: await table.locator('.el-table__header-wrapper th').filter({ has: table.locator('input[type="checkbox"]') }).count(),
    indexColumnCount: await table.locator('.el-table__header-wrapper th').filter({ hasText: '序号' }).count(),
    operationColumnCount: await table.locator('.el-table__header-wrapper th').filter({ hasText: '操作' }).count(),
    toolbarCount: await page.locator(`[data-pce-toolbar-for="${tableId}"]`).count(),
    exportButtonCount: await page.locator(`[data-pce-export-for="${tableId}"]`).count(),
    advancedFilterToggleCount: await page.locator(`[data-pce-filter-toggle-for="${tableId}"]`).count(),
    horizontalScrollOwnerCount: await table.locator('.el-scrollbar__wrap').count(),
  }
}

async function enterReceiveDetail(page, entities) {
  await page.goto(RECEIVE_ROUTE, { waitUntil: 'networkidle' })
  const row = await searchReceive(page, entities.purchaseReceiveNo)
  await expect(row).toContainText(entities.purchaseOrderNo)
  await expect(row).toContainText(entities.supplierName)
  await row.getByRole('button', { name: '详情', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`#\/wms\/purchase-receive\/${entities.internalIds.purchaseReceiveId}$`))
  await expect(page.getByText(entities.purchaseReceiveNo, { exact: true }).first()).toBeVisible()
  await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()
}

async function submitReceiveByPage(page, entities, { rapidRepeat = false } = {}) {
  await enterReceiveDetail(page, entities)
  await page.getByRole('button', { name: '编辑收货信息', exact: true }).click()
  const quantityInput = page.locator('.el-table__body .el-input-number input').first()
  await expect(quantityInput).toBeVisible()
  await quantityInput.fill(String(entities.quantity))
  const submitButton = page.getByRole('button', { name: '提交收货预备', exact: true })
  if (rapidRepeat) {
    const handle = await submitButton.elementHandle()
    await handle.evaluate((element) => {
      element.click()
      element.click()
    })
  } else {
    await submitButton.click()
  }
  await expect(page.getByText('收货预备已提交，库存余额不变', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '生成来料检验单', exact: true })).toBeVisible()
}

async function verifyTargetInFreshContext(browser, entities, storageStatePath) {
  const context = await browser.newContext({ storageState: storageStatePath })
  const page = await context.newPage()
  try {
    await page.goto(QMS_ROUTE, { waitUntil: 'networkidle' })
    await expandQuickSearch(page)
    await page.getByPlaceholder('搜索检验单、收货单、供应商、物料、状态').fill(entities.incomingInspectionNo)
    const rows = page.locator('.el-table__body tr').filter({ hasText: entities.incomingInspectionNo })
    await expect(rows).toHaveCount(1)
    await expect(rows.first()).toContainText(entities.purchaseReceiveNo)
    await expect(rows.first()).toContainText(entities.purchaseOrderNo)
    await expect(rows.first()).toContainText('待检')
    return {
      restoredUrl: page.url(),
      incomingInspectionSearchMatched: true,
      sourcePurchaseReceiveMatched: true,
      sourcePurchaseOrderMatched: true,
      pendingInspectionStatusMatched: true,
      pageCrash: false,
    }
  } finally {
    await context.close()
  }
}

test('从 receive_ready 通过真实页面动作续跑至 incoming_inspection_ready', async ({ browser }) => {
  test.setTimeout(150_000)
  const sourceCheckpoint = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const sourceImmutableHashesBefore = await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)
  const { entities } = sourceCheckpoint

  const duplicateContext = await browser.newContext({ storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json') })
  const duplicatePage = await duplicateContext.newPage()
  let duplicateEvidence
  try {
    await duplicatePage.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await duplicatePage.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await duplicatePage.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
    const beforeSubmit = await readBoundaryState(duplicatePage, entities.internalIds.purchaseReceiveId)
    await submitReceiveByPage(duplicatePage, entities, { rapidRepeat: true })
    const afterSubmit = await readBoundaryState(duplicatePage, entities.internalIds.purchaseReceiveId)
    expect(afterSubmit.sourceReceive.status).toBe('received')
    expect(afterSubmit.purchaseReceiveCount).toBe(beforeSubmit.purchaseReceiveCount)
    const button = duplicatePage.getByRole('button', { name: '生成来料检验单', exact: true })
    const handle = await button.elementHandle()
    await handle.evaluate((element) => {
      element.click()
      element.click()
    })
    const state = await readBoundaryState(duplicatePage, entities.internalIds.purchaseReceiveId)
    expect(state.relatedIncomingInspections).toHaveLength(1)
    expect(state.sourceReceive.status).toBe('inspectionPrepared')
    duplicateEvidence = {
      attemptedActionCount: 2,
      repeatedSubmitAttemptCount: 2,
      afterFirstAndSecondSubmitState: afterSubmit.sourceReceive.status,
      purchaseReceiveCountAfterRepeatedSubmit: afterSubmit.purchaseReceiveCount,
      relatedTargetCount: state.relatedIncomingInspections.length,
      targetNo: state.relatedIncomingInspections[0].inspectionNo,
      duplicateBlocked: true,
    }
  } finally {
    await duplicateContext.close()
  }

  const context = await browser.newContext({
    storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Receive-Incoming-Inspection-Golden/${VERSION}`,
  })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  try {
    await page.goto(RECEIVE_ROUTE, { waitUntil: 'networkidle' })
    const capabilitiesBefore = await readListCapabilities(page, 'purchase-receive-preview-main')
    const before = await readBoundaryState(page, entities.internalIds.purchaseReceiveId)
    expect(before.sourceReceive.status).toBe('prepared')
    expect(before.relatedIncomingInspections).toHaveLength(0)

    await submitReceiveByPage(page, entities)
    const submitted = await readBoundaryState(page, entities.internalIds.purchaseReceiveId)
    expect(submitted.sourceReceive.status).toBe('received')
    expect(submitted.sourceReceive.totalActualReceiveQty).toBe(entities.quantity)
    expect(submitted.inventoryBalances).toEqual(before.inventoryBalances)
    expect(submitted.inventoryTransactions).toEqual(before.inventoryTransactions)
    expect(submitted.payablePrepares).toEqual(before.payablePrepares)

    await page.getByRole('button', { name: '生成来料检验单', exact: true }).click()
    await expect(page.getByText(/已生成来料检验单 IQC\d+，库存余额不变/).first()).toBeVisible()
    const generated = await readBoundaryState(page, entities.internalIds.purchaseReceiveId)
    expect(generated.relatedIncomingInspections).toHaveLength(1)
    expect(generated.sourceReceive.status).toBe('inspectionPrepared')
    const inspection = generated.relatedIncomingInspections[0]
    expect(inspection.status).toBe('pending')
    expect(inspection.sourceReceiveNo).toBe(entities.purchaseReceiveNo)
    expect(inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo).toBe(entities.purchaseOrderNo)
    expect(inspection.sourcePriceApprovalNo).toBe(entities.priceApprovalNo)
    expect(inspection.supplierId).toBe(entities.supplierId)
    expect(inspection.lines?.[0]?.materialCode).toBe(entities.materialCode)
    expect(inspection.lines?.[0]?.receivedQty).toBe(entities.quantity)
    expect(generated.inventoryBalances).toEqual(before.inventoryBalances)
    expect(generated.inventoryTransactions).toEqual(before.inventoryTransactions)
    expect(generated.payablePrepares).toEqual(before.payablePrepares)
    expect(generated.payableChecks).toEqual(before.payableChecks)
    expect(generated.supplierSettlements).toEqual(before.supplierSettlements)
    expect(generated.inventoryQuantityTotal).toBe(before.inventoryQuantityTotal)
    expect(generated.inboundTaskCount).toBe(before.inboundTaskCount)

    await expect(page.getByRole('button', { name: '生成来料检验单', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '查看来料检验单', exact: true })).toBeVisible()

    await page.getByRole('button', { name: '返回列表', exact: true }).click()
    const sourceRow = await searchReceive(page, entities.purchaseReceiveNo)
    await expect(sourceRow).toContainText('已生成检验预备')
    await expect(sourceRow.getByRole('button', { name: '生成检验预备', exact: true })).toHaveCount(0)
    const viewTargetButton = sourceRow.getByRole('button', { name: '查看来料检验', exact: true })
    await expect(viewTargetButton).toBeVisible()
    await viewTargetButton.click()
    await expect(page).toHaveURL(new RegExp(`#\/qms\/incoming-inspection\/${inspection.id}$`))
    await expect(page.getByText(inspection.inspectionNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseReceiveNo, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(entities.priceApprovalNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '开始检验', exact: true })).toBeVisible()

    await page.getByRole('button', { name: '返回列表', exact: true }).click()
    await expect(page).toHaveURL(new RegExp('#/qms/incoming-inspections$'))
    const qmsCapabilities = await readListCapabilities(page, 'incoming-inspections-main')
    await expandQuickSearch(page)
    await page.getByPlaceholder('搜索检验单、收货单、供应商、物料、状态').fill(inspection.inspectionNo)
    const inspectionRow = page.locator('.el-table__body tr').filter({ hasText: inspection.inspectionNo }).first()
    await expect(inspectionRow).toBeVisible()
    await expect(inspectionRow).toContainText(entities.purchaseReceiveNo)
    await expect(inspectionRow).toContainText(entities.purchaseOrderNo)

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
        incomingInspectionId: inspection.id,
        incomingInspectionNo: inspection.inspectionNo,
        arrivalContext: entities.arrivalContext,
        receiveReadyContext: entities.receiveReadyContext,
        incomingInspectionReadyContext: {
          stageId: 'incoming-inspection',
          route: '/qms/incoming-inspections',
          inspectionNo: inspection.inspectionNo,
          purchaseReceiveNo: entities.purchaseReceiveNo,
          purchaseOrderNo: entities.purchaseOrderNo,
          supplierId: inspection.supplierId,
          supplierName: inspection.supplierName,
          materialCode: inspection.lines?.[0]?.materialCode || '',
          materialName: inspection.lines?.[0]?.materialName || '',
          quantity: inspection.lines?.[0]?.receivedQty || 0,
          inspectionExecuted: false,
          inventoryWritten: false,
          payableGenerated: false,
          status: 'incoming_inspection_ready',
          sourceStatus: inspection.status,
          completionCondition: 'unique_pending_incoming_inspection_exists_without_inspection_result_inventory_or_payable',
        },
      },
      baseUrl: ORIGIN,
      nextStageId: 'incoming-inspection-execution',
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
    })
    expect(checkpoint.entities.incomingInspectionNo).toBe(inspection.inspectionNo)
    expect(checkpoint.entities.incomingInspectionStatus).toBe('pending')
    expect(checkpoint.graph.allDownstreamRelationsMatched).toBe(true)

    const restored = await verifyTargetInFreshContext(browser, checkpoint.entities, path.join(checkpoint.directory, 'storage-state.json'))
    await markCheckpointRestored(TARGET_CHECKPOINT_ID, {
      ...restored,
      verificationProcess: 'new_context_same_process',
      userProfileOpened: false,
      userBusinessDataModified: false,
    }, checkpoint.directory)
    const sourceAfter = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
    expect(sourceAfter.actualHash).toBe(sourceCheckpoint.actualHash)
    expect(await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)).toEqual(sourceImmutableHashesBefore)
    expect(consoleErrors).toEqual([])

    await fs.writeFile(path.join(RESULT_ROOT, 'receive-incoming-inspection-continuation-report.json'), `${JSON.stringify({
      version: VERSION,
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
      sourceCheckpointPath: sourceCheckpoint.directory,
      targetCheckpointId: TARGET_CHECKPOINT_ID,
      targetCheckpointPath: checkpoint.directory,
      runId: RUN_ID,
      runnerTraceOwner: 'runner',
      runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'),
      playwrightOutputDir: test.info().outputDir,
      purchaseReceiveNo: entities.purchaseReceiveNo,
      incomingInspectionNo: inspection.inspectionNo,
      actionPath: ['编辑收货信息', '提交收货预备', '生成来料检验单', '返回列表', '查看来料检验'],
      countsBefore: {
        purchaseReceiveCount: before.purchaseReceiveCount,
        incomingInspectionCount: before.incomingInspectionCount,
        relatedIncomingInspectionCount: before.relatedIncomingInspections.length,
        inventoryBalanceCount: before.inventoryBalances.length,
        inventoryTransactionCount: before.inventoryTransactions.length,
        payablePrepareCount: before.payablePrepares.length,
        payableCheckCount: before.payableChecks.length,
        supplierSettlementCount: before.supplierSettlements.length,
      },
      countsAfter: {
        purchaseReceiveCount: generated.purchaseReceiveCount,
        incomingInspectionCount: generated.incomingInspectionCount,
        relatedIncomingInspectionCount: generated.relatedIncomingInspections.length,
        inventoryBalanceCount: generated.inventoryBalances.length,
        inventoryTransactionCount: generated.inventoryTransactions.length,
        payablePrepareCount: generated.payablePrepares.length,
        payableCheckCount: generated.payableChecks.length,
        supplierSettlementCount: generated.supplierSettlements.length,
      },
      duplicateEvidence,
      capabilitiesBefore,
      qmsCapabilities,
      noInspectionExecution: inspection.status === 'pending',
      noInventoryWrite: true,
      noPayableGeneration: true,
      directStoreCallCount: 0,
      directDownstreamRouteJumpCount: 0,
      userProfileOpened: false,
      userBusinessDataModified: false,
      sourceCheckpointHashBefore: sourceCheckpoint.actualHash,
      sourceCheckpointHashAfter: sourceAfter.actualHash,
      overall: 'passed',
    }, null, 2)}\n`, 'utf8')
  } finally {
    await context.close().catch(() => {})
  }
})

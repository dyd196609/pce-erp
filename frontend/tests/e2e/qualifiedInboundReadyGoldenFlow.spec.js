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

const VERSION = 'V1.14.2.8.4.7.21'
const RUN_ID = process.env.PCE_GOLDEN_RUN_ID || ''
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'incoming_inspection_passed'
const TARGET_CHECKPOINT_ID = 'qualified_inbound_ready'
const QMS_LIST_ROUTE = '/#/qms/incoming-inspections'
const RESULT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow')

async function expandQuickSearch(page) {
  const button = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await button.count()) await button.first().click()
}

async function readBoundaryState(page, inspectionId) {
  return page.evaluate((targetInspectionId) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    const qms = read('qms-state-v1')
    const wms = read('wms-state-v1')
    const payablePrepare = read('payable-prepare-state-v1')
    const payableCheck = read('payable-check-state-v1')
    const supplierSettlement = read('supplier-settlement-state-v1')
    const invoicePrepare = read('invoice-prepare-state-v1')
    const inspections = qms.incomingInspections || []
    const relatedTasks = (wms.warehouseTasks || []).filter((task) => (
      task.businessType === 'qualifiedInboundPrepare'
      && String(task.sourceInspectionId || task.sourceId) === String(targetInspectionId)
      && task.status !== 'cancelled'
    ))
    return {
      inspectionCount: inspections.length,
      inspection: inspections.find((item) => String(item.id) === String(targetInspectionId)) || null,
      relatedTasks,
      inventoryBalances: wms.inventoryBalances || [],
      inventoryTransactions: wms.inventoryTransactions || [],
      warehouseTasks: wms.warehouseTasks || [],
      payablePrepares: payablePrepare.payablePrepares || [],
      payableChecks: payableCheck.payableChecks || [],
      supplierSettlements: supplierSettlement.supplierSettlements || [],
      invoicePrepares: invoicePrepare.invoicePrepares || [],
    }
  }, inspectionId)
}

async function openInspectionFromList(page, entities) {
  await page.goto(QMS_LIST_ROUTE, { waitUntil: 'networkidle' })
  await expect(page.locator('[data-pce-toolbar-for="incoming-inspections-main"]')).toBeVisible()
  await expect(page.locator('[data-pce-export-for="incoming-inspections-main"]').first()).toBeVisible()
  await expandQuickSearch(page)
  await page.locator('.el-autocomplete input').first().fill(entities.incomingInspectionNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.incomingInspectionNo })
  await expect(row).toHaveCount(1)
  await expect(row.first()).toContainText(entities.purchaseReceiveNo)
  await expect(row.first()).toContainText(entities.purchaseOrderNo)
  await expect(row.first()).toContainText('已检验')
  await row.first().getByRole('button', { name: '详情', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`#\/qms\/incoming-inspection\/${entities.internalIds.incomingInspectionId}$`))
  await expect(page.getByText(entities.incomingInspectionNo, { exact: true }).first()).toBeVisible()
}

async function verifyReadyInFreshContext(browser, entities, storageStatePath) {
  const context = await browser.newContext({ storageState: storageStatePath })
  const page = await context.newPage()
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
    await page.goto(`/#/wms/warehouse-task/${entities.qualifiedInboundId}`, { waitUntil: 'networkidle' })
    await expect(page.getByText(entities.qualifiedInboundNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.incomingInspectionNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseReceiveNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()
    return {
      result: 'passed',
      qualifiedInboundNo: entities.qualifiedInboundNo,
      targetPendingInboundStatusMatched: true,
      sourceIncomingInspectionMatched: true,
      sourcePurchaseReceiveMatched: true,
      sourcePurchaseOrderMatched: true,
      inventoryNotWritten: true,
      payableNotGenerated: true,
    }
  } finally {
    await context.close()
  }
}

test('从 incoming_inspection_passed 真实生成合格入库预备至 qualified_inbound_ready', async ({ browser }) => {
  test.setTimeout(120_000)
  expect(RUN_ID).toBeTruthy()
  const source = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const sourceHashesBefore = await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)
  const { entities } = source
  expect(entities.incomingInspectionNo).toMatch(/^IQC\d+$/)
  expect(entities.incomingInspectionStatus).toBe('inspected')

  const context = await browser.newContext({
    storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Qualified-Inbound-Ready-Golden/${VERSION}`,
  })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
    const before = await readBoundaryState(page, entities.internalIds.incomingInspectionId)
    expect(before.inspection?.status).toBe('inspected')
    expect(before.inspection?.inventoryPosted).toBe(false)
    expect(before.inspection?.inventoryPostStatus).toBe('notPosted')
    expect(before.inspection?.lines?.[0]?.qualifiedQty).toBe(1)
    expect(before.inspection?.lines?.[0]?.unqualifiedQty).toBe(0)
    expect(before.relatedTasks).toHaveLength(0)

    await openInspectionFromList(page, entities)
    const generateButton = page.getByRole('button', { name: '生成检验合格入库预备', exact: true })
    await expect(generateButton).toBeVisible()
    await expect(page.getByRole('button', { name: '确认入库', exact: true })).toHaveCount(0)
    await generateButton.click()
    await expect(page.getByText(/已生成检验合格入库预备 1 条/).first()).toBeVisible()
    await expect(generateButton).toHaveCount(0)
    await expect(page.getByRole('button', { name: '查看入库预备', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '确认入库', exact: true })).toHaveCount(0)
    await expect(page.getByText('已生成入库预备', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('待确认入库', { exact: true }).first()).toBeVisible()

    const after = await readBoundaryState(page, entities.internalIds.incomingInspectionId)
    expect(after.inspectionCount).toBe(before.inspectionCount)
    expect(after.relatedTasks).toHaveLength(1)
    const task = after.relatedTasks[0]
    const inspection = after.inspection
    expect(task.id).toBeTruthy()
    expect(task.taskNo).toBeTruthy()
    expect(task.businessType).toBe('qualifiedInboundPrepare')
    expect(task.status).toBe('pending')
    expect(task.businessStatus).toBe('待确认入库')
    expect(task.sourceInspectionId).toBe(inspection.id)
    expect(task.sourceInspectionNo).toBe(entities.incomingInspectionNo)
    expect(task.sourceReceiveNo).toBe(entities.purchaseReceiveNo)
    expect(task.sourcePurchaseOrderNo).toBe(entities.purchaseOrderNo)
    expect(task.materialCode).toBe(entities.materialCode)
    expect(task.materialName).toBe(entities.materialName)
    expect(task.plannedQuantity).toBe(1)
    expect(task.completedQuantity).toBe(0)
    expect(inspection.status).toBe('inboundPrepared')
    expect(inspection.inventoryPosted).toBe(false)
    expect(inspection.inventoryPostStatus).toBe('inboundPrepared')
    expect(inspection.lines[0].qualifiedQty).toBe(1)
    expect(inspection.lines[0].unqualifiedQty).toBe(0)
    expect(inspection.inboundPrepareTaskIds).toEqual([task.id])
    expect(after.inventoryBalances).toEqual(before.inventoryBalances)
    expect(after.inventoryTransactions).toEqual(before.inventoryTransactions)
    expect(after.payablePrepares).toEqual(before.payablePrepares)
    expect(after.payableChecks).toEqual(before.payableChecks)
    expect(after.supplierSettlements).toEqual(before.supplierSettlements)
    expect(after.invoicePrepares).toEqual(before.invoicePrepares)

    await page.getByRole('button', { name: '查看入库预备', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`#\/wms\/warehouse-task\/${task.id}$`))
    await expect(page.getByText(task.taskNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.incomingInspectionNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseReceiveNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText('待确认入库', { exact: true }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '确认入库', exact: true })).toBeVisible()

    const afterNavigation = await readBoundaryState(page, entities.internalIds.incomingInspectionId)
    expect(afterNavigation.relatedTasks).toHaveLength(1)
    expect(afterNavigation.relatedTasks[0].id).toBe(task.id)
    expect(afterNavigation.inventoryBalances).toEqual(before.inventoryBalances)
    expect(afterNavigation.inventoryTransactions).toEqual(before.inventoryTransactions)
    expect(afterNavigation.payablePrepares).toEqual(before.payablePrepares)

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
        qualifiedInboundId: task.id,
        qualifiedInboundNo: task.taskNo,
        arrivalContext: entities.arrivalContext,
        receiveReadyContext: entities.receiveReadyContext,
        incomingInspectionReadyContext: entities.incomingInspectionReadyContext,
        qualifiedInboundReadyContext: {
          status: 'qualified_inbound_ready',
          stageId: 'qualified-inbound',
          canonicalName: '合格入库',
          sourceInspectionNo: inspection.inspectionNo,
          sourceReceiveNo: inspection.sourceReceiveNo,
          sourcePurchaseOrderNo: inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo,
          qualifiedInboundId: task.id,
          qualifiedInboundNo: task.taskNo,
          supplierId: inspection.supplierId,
          supplierName: inspection.supplierName,
          materialCode: task.materialCode,
          materialName: task.materialName,
          qualifiedQuantity: 1,
          pendingInboundQuantity: task.plannedQuantity,
          inboundStatus: task.status,
          inboundExecuted: false,
          inventoryWritten: false,
          payableGenerated: false,
          wmsInitializationMode: 'canonical_empty',
          demoSeedActivated: false,
          completionCondition: 'qualified_inbound_prepare_task_created_without_inventory_or_payable',
        },
      },
      baseUrl: ORIGIN,
      nextStageId: 'qualified-inbound',
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
    })
    expect(checkpoint.entities.qualifiedInboundNo).toBe(task.taskNo)
    expect(checkpoint.entities.qualifiedInboundStatus).toBe('pending')
    expect(checkpoint.entities.records.qualifiedInbound.sourceInspectionNo).toBe(entities.incomingInspectionNo)
    const restored = await verifyReadyInFreshContext(browser, checkpoint.entities, path.join(checkpoint.directory, 'storage-state.json'))
    await markCheckpointRestored(TARGET_CHECKPOINT_ID, {
      ...restored,
      verificationProcess: 'new_context_same_process',
      userProfileOpened: false,
      userBusinessDataModified: false,
    }, checkpoint.directory)
    expect(await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)).toEqual(sourceHashesBefore)
    expect(consoleErrors).toEqual([])

    const resultEnvelope = {
      ok: true,
      status: 'created',
      targetId: task.id,
      targetNo: task.taskNo,
      sourceInspectionId: inspection.id,
      sourceInspectionNo: inspection.inspectionNo,
      sourceReceiveNo: inspection.sourceReceiveNo,
      sourcePurchaseOrderNo: inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo,
      record: task,
    }
    await fs.writeFile(path.join(RESULT_ROOT, 'qualified-inbound-ready-report.json'), `${JSON.stringify({
      version: VERSION,
      runId: RUN_ID,
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
      sourceCheckpointPath: source.directory,
      targetCheckpointId: TARGET_CHECKPOINT_ID,
      targetCheckpointPath: checkpoint.directory,
      runnerTraceOwner: 'runner',
      runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'),
      playwrightOutputDir: test.info().outputDir,
      stageId: 'qualified-inbound',
      canonicalName: '合格入库',
      targetRoute: `/wms/warehouse-task/${task.id}`,
      actionName: '生成检验合格入库预备',
      viewActionName: '查看入库预备',
      targetCountBefore: before.relatedTasks.length,
      targetCountAfterFirstGeneration: after.relatedTasks.length,
      targetCountAfterDuplicateGuard: afterNavigation.relatedTasks.length,
      resultEnvelope,
      sourceSupplierId: inspection.supplierId,
      sourceSupplierName: inspection.supplierName,
      inventoryWritten: false,
      inboundExecuted: false,
      payableGenerated: false,
      wmsInitializationMode: 'canonical_empty',
      demoSeedActivated: false,
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

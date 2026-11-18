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

const VERSION = 'V1.14.2.8.4.7.19'
const RUN_ID = process.env.PCE_GOLDEN_RUN_ID || ''
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'incoming_inspection_ready'
const TARGET_CHECKPOINT_ID = 'incoming_inspection_passed'
const QMS_LIST_ROUTE = '/#/qms/incoming-inspections'
const RESULT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow')

async function expandQuickSearch(page) {
  const button = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await button.count()) await button.first().click()
}

async function readBoundaryState(page, inspectionId) {
  return page.evaluate((targetInspectionId) => {
    const qms = JSON.parse(localStorage.getItem('qms-state-v1') || '{}')
    const wms = JSON.parse(localStorage.getItem('wms-state-v1') || '{}')
    const payablePrepare = JSON.parse(localStorage.getItem('payable-prepare-state-v1') || '{}')
    const payableCheck = JSON.parse(localStorage.getItem('payable-check-state-v1') || '{}')
    const supplierSettlement = JSON.parse(localStorage.getItem('supplier-settlement-state-v1') || '{}')
    const inspections = qms.incomingInspections || []
    return {
      inspectionCount: inspections.length,
      inspection: inspections.find((item) => String(item.id) === String(targetInspectionId)) || null,
      inventoryBalances: wms.inventoryBalances || [],
      inventoryTransactions: wms.inventoryTransactions || [],
      warehouseTasks: wms.warehouseTasks || [],
      payablePrepares: payablePrepare.payablePrepares || [],
      payableChecks: payableCheck.payableChecks || [],
      supplierSettlements: supplierSettlement.supplierSettlements || [],
    }
  }, inspectionId)
}

async function openTargetFromList(page, entities) {
  const targetInspectionNo = entities.incomingInspectionNo
  await page.goto(QMS_LIST_ROUTE, { waitUntil: 'networkidle' })
  await expandQuickSearch(page)
  await page.getByPlaceholder('搜索检验单、收货单、供应商、物料、状态').fill(targetInspectionNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: targetInspectionNo })
  await expect(row).toHaveCount(1)
  await expect(row.first()).toContainText(entities.purchaseReceiveNo)
  await expect(row.first()).toContainText(entities.purchaseOrderNo)
  await expect(row.first()).toContainText('待检')
  await row.first().getByRole('button', { name: '详情', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`#\/qms\/incoming-inspection\/${entities.internalIds.incomingInspectionId}$`))
  await expect(page.getByText(targetInspectionNo, { exact: true }).first()).toBeVisible()
}

async function verifyPassedInFreshContext(browser, entities, storageStatePath) {
  const context = await browser.newContext({ storageState: storageStatePath })
  const page = await context.newPage()
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
    await page.goto(QMS_LIST_ROUTE, { waitUntil: 'networkidle' })
    await expandQuickSearch(page)
    await page.getByPlaceholder('搜索检验单、收货单、供应商、物料、状态').fill(entities.incomingInspectionNo)
    const row = page.locator('.el-table__body tr').filter({ hasText: entities.incomingInspectionNo }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText('已检验')
    await expect(row).toContainText(entities.purchaseReceiveNo)
    return {
      result: 'passed',
      incomingInspectionNo: entities.incomingInspectionNo,
      inspectedStatusMatched: true,
      sourcePurchaseReceiveMatched: true,
      inventoryNotWritten: true,
      payableNotGenerated: true,
    }
  } finally {
    await context.close()
  }
}

test('从 incoming_inspection_ready 真实完成合格检验至 incoming_inspection_passed', async ({ browser }) => {
  test.setTimeout(120_000)
  expect(RUN_ID).toBeTruthy()
  const source = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const sourceHashesBefore = await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)
  const { entities } = source
  expect(entities.incomingInspectionNo).toMatch(/^IQC\d+$/)
  expect(entities.incomingInspectionStatus).toBe('pending')

  const context = await browser.newContext({
    storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Incoming-Inspection-Execution-Golden/${VERSION}`,
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
    expect(before.inspection?.status).toBe('pending')
    expect(before.inspection?.inventoryPosted).toBe(false)
    expect(before.inspection?.inventoryPostStatus).toBe('notPosted')

    await openTargetFromList(page, entities)
    await expect(page.getByRole('button', { name: '开始检验', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '开始检验', exact: true }).click()
    await expect(page.getByText('已开始检验', { exact: true })).toBeVisible()
    await expect(page.getByText('检验中', { exact: true }).first()).toBeVisible()

    const quantityInputs = page.locator('.qms-inspection-table .qms-number-input input')
    await expect(quantityInputs).toHaveCount(6)
    await quantityInputs.nth(0).fill('1')
    await quantityInputs.nth(0).press('Tab')
    await expect(page.getByRole('button', { name: '提交检验结果', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '提交检验结果', exact: true }).click()
    await expect(page.getByText('检验结果已提交', { exact: true })).toBeVisible()
    await expect(page.getByText('已检验', { exact: true }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '生成检验合格入库预备', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '确认入库', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '提交检验结果', exact: true })).toHaveCount(0)

    const after = await readBoundaryState(page, entities.internalIds.incomingInspectionId)
    const inspection = after.inspection
    expect(after.inspectionCount).toBe(before.inspectionCount)
    expect(inspection.status).toBe('inspected')
    expect(inspection.lines?.[0]?.qualifiedQty).toBe(1)
    expect(inspection.lines?.[0]?.unqualifiedQty).toBe(0)
    expect(inspection.lines?.[0]?.inspectResult).toBe('qualified')
    expect(inspection.lines?.[0]?.qualityStatus).toBe('qualified')
    expect(inspection.lines?.[0]?.inventoryPosted).toBe(false)
    expect(inspection.inventoryPosted).toBe(false)
    expect(inspection.inventoryPostStatus).toBe('notPosted')
    expect(inspection.inboundPrepareTaskIds || []).toHaveLength(0)
    expect(after.inventoryBalances).toEqual(before.inventoryBalances)
    expect(after.inventoryTransactions).toEqual(before.inventoryTransactions)
    expect(after.warehouseTasks).toEqual(before.warehouseTasks)
    expect(after.payablePrepares).toEqual(before.payablePrepares)
    expect(after.payableChecks).toEqual(before.payableChecks)
    expect(after.supplierSettlements).toEqual(before.supplierSettlements)

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
          ...(entities.incomingInspectionReadyContext || {}),
          status: 'incoming_inspection_passed',
          sourceStatus: inspection.status,
          inspectionExecuted: true,
          inspectionPassed: true,
          qualifiedQuantity: 1,
          unqualifiedQuantity: 0,
          inboundPrepared: false,
          inventoryWritten: false,
          payableGenerated: false,
          completionCondition: 'qualified_inspection_submitted_without_inbound_inventory_or_payable',
        },
      },
      baseUrl: ORIGIN,
      nextStageId: 'incoming-inspection-inbound-prepare',
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
    })
    expect(checkpoint.entities.incomingInspectionStatus).toBe('inspected')
    expect(checkpoint.entities.records.incomingInspection.lines[0].qualifiedQty).toBe(1)
    const restored = await verifyPassedInFreshContext(browser, checkpoint.entities, path.join(checkpoint.directory, 'storage-state.json'))
    await markCheckpointRestored(TARGET_CHECKPOINT_ID, {
      ...restored,
      verificationProcess: 'new_context_same_process',
      userProfileOpened: false,
      userBusinessDataModified: false,
    }, checkpoint.directory)
    expect(await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)).toEqual(sourceHashesBefore)
    expect(consoleErrors).toEqual([])

    await fs.writeFile(path.join(RESULT_ROOT, 'incoming-inspection-execution-report.json'), `${JSON.stringify({
      version: VERSION,
      runId: RUN_ID,
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
      sourceCheckpointPath: source.directory,
      targetCheckpointId: TARGET_CHECKPOINT_ID,
      targetCheckpointPath: checkpoint.directory,
      runnerTraceOwner: 'runner',
      runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'),
      playwrightOutputDir: test.info().outputDir,
      incomingInspectionNo: inspection.inspectionNo,
      incomingInspectionId: inspection.id,
      statusBefore: before.inspection.status,
      statusAfter: inspection.status,
      qualifiedQuantity: inspection.lines[0].qualifiedQty,
      unqualifiedQuantity: inspection.lines[0].unqualifiedQty,
      inspectionResult: inspection.lines[0].inspectResult,
      inventoryWritten: false,
      inboundPrepared: false,
      payableGenerated: false,
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

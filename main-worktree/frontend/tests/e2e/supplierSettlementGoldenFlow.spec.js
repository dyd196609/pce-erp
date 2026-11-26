import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { checkpointImmutableHashes, checkpointPath, markCheckpointRestored, saveStagedCheckpoint, verifyCheckpointIntegrity } from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.34'
const RUN_ID = process.env.PCE_GOLDEN_RUN_ID || ''
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'payable_checked'
const TARGET_CHECKPOINT_ID = 'supplier_settlement_ready'
const RESULT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow')
const RESUME_STORAGE_STATE = process.env.PCE_SUPPLIER_SETTLEMENT_RESUME_STORAGE_STATE || ''
const EXPECTED_SETTLEMENT_NO = process.env.PCE_EXPECTED_SUPPLIER_SETTLEMENT_NO || ''

async function state(page) {
  return page.evaluate(() => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    return {
      checks: read('payable-check-state-v1').payableChecks || [],
      settlements: read('supplier-settlement-state-v1').supplierSettlements || [],
      reconciliations: read('purchase-reconciliation-state-v1').purchaseReconciliations || [],
      invoicePrepares: read('invoice-prepare-state-v1').invoicePrepares || [],
      payments: read('payment-application-state-v1').paymentApplications || [],
    }
  })
}

async function verifyFreshContext(browser, entities, storageStatePath) {
  const context = await browser.newContext({ storageState: storageStatePath, userAgent: `PCE-Supplier-Settlement-Restore/${VERSION}` })
  const page = await context.newPage()
  try {
    await page.goto(`${ORIGIN}/#/scm/supplier-settlements`, { waitUntil: 'networkidle' })
    await page.locator('[data-acceptance-id="list-fuzzy-search-input"] input').fill(entities.supplierSettlementNo)
    const row = page.locator('.el-table__body tr').filter({ hasText: entities.supplierSettlementNo })
    await expect(row).toHaveCount(1)
    await expect(row).toContainText(entities.payableCheckNo)
    const restored = await state(page)
    expect(restored.settlements).toHaveLength(1)
    expect(restored.reconciliations).toHaveLength(0)
    expect(restored.payments).toHaveLength(0)
    return { result: 'passed', supplierSettlementNo: entities.supplierSettlementNo, purchaseReconciliationGenerated: false, paymentGenerated: false }
  } finally { await context.close() }
}

test('从 payable_checked 通过真实页面形成 supplier_settlement_ready', async ({ browser }) => {
  test.setTimeout(180_000)
  expect(RUN_ID).toBeTruthy()
  const source = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const sourceCheckpointHashesBefore = await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)
  const { entities } = source
  expect(entities.payableCheckNo).toMatch(/^PC\d+$/)
  const context = await browser.newContext({ storageState: RESUME_STORAGE_STATE || checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'), userAgent: `PCE-Supplier-Settlement-Golden/${VERSION}` })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  try {
    await page.goto(`${ORIGIN}/#/finance/payable-checks`, { waitUntil: 'networkidle' })
    const initial = await state(page)
    expect(initial.checks).toHaveLength(1)
    expect(initial.checks[0].checkStatus).toBe('checked')
    expect(initial.settlements.length).toBeLessThanOrEqual(1)
    expect(initial.reconciliations).toHaveLength(0)
    expect(initial.payments).toHaveLength(0)

    await page.locator('[data-acceptance-id="list-fuzzy-search-input"] input').fill(entities.payableCheckNo)
    const sourceRow = page.locator('.el-table__body tr').filter({ hasText: entities.payableCheckNo })
    await expect(sourceRow).toHaveCount(1)
    await sourceRow.locator('.el-checkbox').click()
    await page.locator('[data-acceptance-id="go-supplier-settlement-selected-button"]').click()
    await page.waitForURL((url) => url.hash.includes(`/scm/supplier-settlements?sourcePayableCheckNo=${entities.payableCheckNo}`))
    const fullSourceUrl = page.url()
    expect(page.url()).toContain(`sourcePayablePrepareNo=${entities.payablePrepareNo}`)
    expect(page.url()).toContain(`purchaseOrderNo=${entities.purchaseOrderNo}`)
    expect(page.url()).toContain(`supplierId=${entities.supplierId}`)
    await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('66.00')
    const beforeSupplierSettlementCount = (await state(page)).settlements.length
    if (beforeSupplierSettlementCount === 0) {
      await expect(page.locator('[data-acceptance-id="supplier-settlement-context-pending"]')).toBeVisible()
      await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('页面来源状态：pending_source')
      const pendingRow = page.locator('.el-table__body tr').filter({ hasText: entities.payableCheckNo })
      const generate = pendingRow.locator('[data-acceptance-id="generate-supplier-settlement"]')
      await expect(generate).toBeEnabled()
      await generate.click()
    } else {
      expect(beforeSupplierSettlementCount).toBe(1)
      expect(initial.settlements[0].settlementNo).toBe(EXPECTED_SETTLEMENT_NO)
      await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('页面来源状态：existing_settlement')
      await expect(page.locator('[data-acceptance-id="generate-supplier-settlement"]')).toHaveCount(0)
    }
    await expect(page.locator('[data-acceptance-id="supplier-settlement-context-existing"]')).toBeVisible()
    await expect(page.locator('[data-acceptance-id="generate-supplier-settlement"]')).toHaveCount(0)
    const generatedState = await state(page)
    expect(generatedState.settlements).toHaveLength(1)
    const settlement = generatedState.settlements[0]
    if (EXPECTED_SETTLEMENT_NO) expect(settlement.settlementNo).toBe(EXPECTED_SETTLEMENT_NO)
    expect(settlement.sourcePayableCheckNo).toBe(entities.payableCheckNo)
    expect(settlement.sourcePayablePrepareNo).toBe(entities.payablePrepareNo)
    expect(settlement.sourceInventoryTransactionNos).toContain(entities.inventoryTransactionNo)
    expect(settlement.sourceWarehouseTaskNo).toBe(entities.qualifiedInboundNo)
    expect(settlement.sourceInspectionNo).toBe(entities.incomingInspectionNo)
    expect(settlement.sourceReceiveNo).toBe(entities.purchaseReceiveNo)
    expect(settlement.sourcePurchaseOrderNo).toBe(entities.purchaseOrderNo)
    expect(settlement.sourcePriceApprovalNo).toBe(entities.priceApprovalNo)
    expect(settlement.supplierId).toBe(entities.supplierId)
    expect(settlement.materialCode).toBe(entities.materialCode)
    expect(settlement.settlementQuantity).toBe(1)
    expect(settlement.unit).toBe('米')
    expect(settlement.unitPrice).toBe(66)
    expect(settlement.payableAmount).toBe(66)
    expect(settlement.checkedAmount).toBe(66)
    expect(settlement.settlementAmount).toBe(66)
    expect(settlement.differenceAmount).toBe(0)
    expect(settlement.settlementStatus).toBe('reconciling')
    expect(settlement.reconciliationStatus).toBe('matched')

    const existingRow = page.locator('.el-table__body tr').filter({ hasText: settlement.settlementNo })
    await expect(existingRow).toContainText(entities.payableCheckNo)
    await expect(existingRow.locator('[data-acceptance-id="view-supplier-settlement"]')).toBeVisible()
    await expect(existingRow.locator('[data-acceptance-id="enter-purchase-reconciliation"]')).toBeVisible()
    await existingRow.locator('[data-acceptance-id="view-supplier-settlement"]').click()
    await expect(page.locator('[data-acceptance-id="supplier-settlement-detail-record"]')).toContainText(settlement.settlementNo)
    await expect(page.locator('[data-acceptance-id="supplier-settlement-detail-record"]')).toContainText(entities.inventoryTransactionNo)
    await expect(page.locator('[data-acceptance-id="supplier-settlement-detail-record"]')).toContainText('MAT-000001 / 铝合金型材')
    await expect(page.locator('[data-acceptance-id="supplier-settlement-detail-record"]')).toContainText('采购对账对象：未生成')

    await page.reload({ waitUntil: 'networkidle' })
    const afterSecondGenerationCount = (await state(page)).settlements.length
    expect(afterSecondGenerationCount).toBe(1)
    await expect(page.locator('[data-acceptance-id="generate-supplier-settlement"]')).toHaveCount(0)
    const rowAfterReload = page.locator('.el-table__body tr').filter({ hasText: settlement.settlementNo })
    await expect(rowAfterReload.locator('[data-acceptance-id="enter-purchase-reconciliation"]')).toBeVisible()
    expect((await state(page)).reconciliations).toHaveLength(0)
    expect((await state(page)).payments).toHaveLength(0)

    const checkpoint = await saveStagedCheckpoint({
      context, page, checkpointId: TARGET_CHECKPOINT_ID, runId: RUN_ID,
      sourceObjects: {
        requestId: source.entities.internalIds.purchaseRequestId, requestNo: source.entities.purchaseRequestNo,
        inquiryId: source.entities.internalIds.inquiryId, inquiryNo: source.entities.inquiryNo,
        approvalId: source.entities.internalIds.priceApprovalId, approvalNo: source.entities.priceApprovalNo,
        purchaseOrderId: source.entities.internalIds.purchaseOrderId, purchaseOrderNo: source.entities.purchaseOrderNo,
        purchaseReceiveId: source.entities.internalIds.purchaseReceiveId, purchaseReceiveNo: source.entities.purchaseReceiveNo,
        incomingInspectionId: source.entities.internalIds.incomingInspectionId, incomingInspectionNo: source.entities.incomingInspectionNo,
        qualifiedInboundId: source.entities.qualifiedInboundId, qualifiedInboundNo: source.entities.qualifiedInboundNo,
        inventoryTransactionId: source.entities.inventoryTransactionId, inventoryTransactionNo: source.entities.inventoryTransactionNo,
        payablePrepareId: source.entities.payablePrepareId, payablePrepareNo: source.entities.payablePrepareNo,
        payableCheckId: source.entities.payableCheckId, payableCheckNo: source.entities.payableCheckNo,
        supplierSettlementId: settlement.id, supplierSettlementNo: settlement.settlementNo,
        supplierSettlementGenerated: true, purchaseReconciliationGenerated: false, paymentGenerated: false,
      },
      baseUrl: ORIGIN, nextStageId: 'purchase-reconciliation', sourceCheckpointId: SOURCE_CHECKPOINT_ID,
    })
    expect(checkpoint.entities.supplierSettlementNo).toBe(settlement.settlementNo)
    expect(checkpoint.entities.settlementAmount).toBe(66)
    expect(checkpoint.graph.downstreamRelations.some((item) => item.relation === 'payableCheck -> supplierSettlement' && item.matched)).toBe(true)
    const fresh = await verifyFreshContext(browser, checkpoint.entities, path.join(checkpoint.directory, 'storage-state.json'))
    await markCheckpointRestored(TARGET_CHECKPOINT_ID, { ...fresh, verificationProcess: 'new_context_same_process', userProfileOpened: false, userBusinessDataModified: false }, checkpoint.directory)
    const sourceCheckpointHashesAfter = await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)
    expect(sourceCheckpointHashesAfter).toEqual(sourceCheckpointHashesBefore)
    expect(consoleErrors).toEqual([])
    await fs.writeFile(path.join(RESULT_ROOT, 'supplier-settlement-golden-flow-report.json'), `${JSON.stringify({
      version: VERSION, runId: RUN_ID, sourceCheckpointPath: source.directory, targetCheckpointPath: checkpoint.directory,
      runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'), playwrightOutputDir: test.info().outputDir,
      canonicalName: '供应商结算', moduleId: 'supplier-settlement', fullUrl: fullSourceUrl,
      aggregationRule: 'one_payable_check_to_one_supplier_settlement', createButtonName: '生成供应商结算单',
      beforeSupplierSettlementCount, afterFirstGenerationCount: generatedState.settlements.length, afterSecondGenerationCount,
      supplierSettlementId: settlement.id, supplierSettlementNo: settlement.settlementNo, supplierSettlementStatus: settlement.settlementStatus,
      sourcePayableCheckNo: settlement.sourcePayableCheckNo, sourcePayablePrepareNo: settlement.sourcePayablePrepareNo,
      settlementQuantity: settlement.settlementQuantity, unit: settlement.unit, settlementAmount: settlement.settlementAmount,
      purchaseReconciliationGenerated: false, paymentGenerated: false, ledgerWritten: false, directStoreCallCount: 0,
      userProfileOpened: false, userBusinessDataModified: false,
      sourceCheckpointHashesBefore,
      sourceCheckpointHashesAfter,
      sourceCheckpointHashesUnchanged: JSON.stringify(sourceCheckpointHashesBefore) === JSON.stringify(sourceCheckpointHashesAfter),
      businessConsoleErrorCount: consoleErrors.length,
      overall: 'passed',
    }, null, 2)}\n`, 'utf8')
  } finally { await context.close().catch(() => {}) }
})

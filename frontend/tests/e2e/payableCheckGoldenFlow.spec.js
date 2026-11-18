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

const VERSION = 'V1.14.2.8.4.7.33'
const RUN_ID = process.env.PCE_GOLDEN_RUN_ID || ''
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const SOURCE_CHECKPOINT_ID = 'payable_prepared'
const TARGET_CHECKPOINT_ID = 'payable_checked'
const RESULT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow')

function fixtureCheck(no, status = 'draft') {
  return {
    id: `fixture-${no}`,
    payableCheckNo: no,
    sourcePayablePrepareId: `prepare-${no}`,
    sourcePayablePrepareNo: `PP-${no}`,
    sourceInventoryTransactionNos: [`TXN-${no}`],
    sourceWarehouseTaskNo: `WT-${no}`,
    sourceInspectionNo: `IQC-${no}`,
    sourceReceiveNo: `PRV-${no}`,
    sourcePurchaseOrderNo: `PO-${no}`,
    sourcePriceApprovalNo: `PA-${no}`,
    supplierId: 'sup-001',
    supplierName: '精工铝材供应商',
    checkStatus: status,
    totalPayableQty: 1,
    totalPayableAmount: 66,
    totalCheckedQty: 1,
    totalCheckedAmount: 66,
    amountDifference: 0,
    quantityDifference: 0,
    lines: [{ id: `line-${no}`, materialCode: 'MAT-000001', materialName: '铝合金型材', unit: '米', payableQty: 1, payablePrice: 66, payableAmount: 66, checkedQty: 1, checkedPrice: 66, checkedAmount: 66 }],
  }
}

async function readBusinessState(page) {
  return page.evaluate(() => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    return {
      prepares: read('payable-prepare-state-v1').payablePrepares || [],
      checks: read('payable-check-state-v1').payableChecks || [],
      settlements: read('supplier-settlement-state-v1').supplierSettlements || read('supplier-settlement-state-v1').settlements || [],
      reconciliations: read('purchase-reconciliation-state-v1').purchaseReconciliations || read('purchase-reconciliation-state-v1').reconciliations || [],
      invoicePrepares: read('invoice-prepare-state-v1').invoicePrepares || [],
      payments: read('payment-application-state-v1').paymentApplications || [],
    }
  })
}

async function openPayableCheckList(page) {
  await page.goto('/#/finance/payable-checks', { waitUntil: 'networkidle' })
  await expect(page).toHaveURL(`${ORIGIN}/#/finance/payable-checks`)
}

async function newFixtureContext(browser, records) {
  const context = await browser.newContext({ userAgent: `PCE-Payable-Check-Fixture/${VERSION}` })
  await context.addInitScript((checks) => {
    localStorage.setItem('payable-check-state-v1', JSON.stringify({ payableChecks: checks }))
    localStorage.setItem('payable-prepare-state-v1', JSON.stringify({ payablePrepares: [] }))
    localStorage.setItem('supplier-settlement-state-v1', JSON.stringify({ supplierSettlements: [] }))
    localStorage.setItem('purchase-reconciliation-state-v1', JSON.stringify({ purchaseReconciliations: [] }))
  }, records)
  const page = await context.newPage()
  await openPayableCheckList(page)
  return { context, page }
}

async function selectRows(page, recordNos) {
  for (const no of recordNos) {
    const row = page.locator('.el-table__body tr').filter({ hasText: no })
    await expect(row).toHaveCount(1)
    await row.locator('.el-checkbox').click()
  }
}

async function runBatchMatrix(browser) {
  const matrix = {}

  {
    const { context, page } = await newFixtureContext(browser, [fixtureCheck('PC-B0-A')])
    try {
      const button = page.getByRole('button', { name: '批量完成应付核对', exact: true })
      await expect(button).toBeDisabled()
      await expect(button).toHaveAttribute('title', '请先选择记录')
      matrix.zero = { disabled: true, reason: '请先选择记录' }
    } finally { await context.close() }
  }

  {
    const records = [fixtureCheck('PC-B1-A'), fixtureCheck('PC-B1-B')]
    const { context, page } = await newFixtureContext(browser, records)
    try {
      await selectRows(page, ['PC-B1-A'])
      await page.getByRole('button', { name: '批量完成应付核对', exact: true }).click()
      await expect(page.locator('[data-acceptance-id="payable-check-batch-result"]')).toContainText('成功 1 条，失败 0 条')
      const state = await readBusinessState(page)
      expect(state.checks.find((item) => item.payableCheckNo === 'PC-B1-A').checkStatus).toBe('checked')
      expect(state.checks.find((item) => item.payableCheckNo === 'PC-B1-B').checkStatus).toBe('draft')
      await expect(page.getByTestId('batch-selected-record-nos')).toContainText('PC-B1-A')
      await expect(page.getByTestId('batch-processed-record-nos')).toContainText('PC-B1-A')
      await expect(page.getByTestId('batch-unselected-record-nos')).toContainText('PC-B1-B')
      matrix.one = { selectedRecordNos: ['PC-B1-A'], processedRecordNos: ['PC-B1-A'], unselectedRecordNos: ['PC-B1-B'], successCount: 1, failedCount: 0 }
    } finally { await context.close() }
  }

  {
    const records = [fixtureCheck('PC-B2-A'), fixtureCheck('PC-B2-B'), fixtureCheck('PC-B2-C')]
    const { context, page } = await newFixtureContext(browser, records)
    try {
      await selectRows(page, ['PC-B2-A', 'PC-B2-B'])
      await page.getByRole('button', { name: '批量完成应付核对', exact: true }).click()
      await expect(page.locator('[data-acceptance-id="payable-check-batch-result"]')).toContainText('成功 2 条，失败 0 条')
      const state = await readBusinessState(page)
      expect(state.checks.filter((item) => ['PC-B2-A', 'PC-B2-B'].includes(item.payableCheckNo)).every((item) => item.checkStatus === 'checked')).toBe(true)
      expect(state.checks.find((item) => item.payableCheckNo === 'PC-B2-C').checkStatus).toBe('draft')
      matrix.multiple = { selectedRecordNos: ['PC-B2-A', 'PC-B2-B'], processedRecordNos: ['PC-B2-A', 'PC-B2-B'], unselectedRecordNos: ['PC-B2-C'], successCount: 2, failedCount: 0 }
    } finally { await context.close() }
  }

  {
    const records = [fixtureCheck('PC-BM-A'), fixtureCheck('PC-BM-X', 'cancelled'), fixtureCheck('PC-BM-U')]
    const { context, page } = await newFixtureContext(browser, records)
    try {
      await selectRows(page, ['PC-BM-A', 'PC-BM-X'])
      await page.getByRole('button', { name: '批量完成应付核对', exact: true }).click()
      await expect(page.locator('[data-acceptance-id="payable-check-batch-result"]')).toContainText('成功 1 条，失败 1 条')
      const state = await readBusinessState(page)
      expect(state.checks.find((item) => item.payableCheckNo === 'PC-BM-A').checkStatus).toBe('checked')
      expect(state.checks.find((item) => item.payableCheckNo === 'PC-BM-X').checkStatus).toBe('cancelled')
      expect(state.checks.find((item) => item.payableCheckNo === 'PC-BM-U').checkStatus).toBe('draft')
      await expect(page.getByTestId('batch-failed-record-nos')).toContainText('PC-BM-X')
      matrix.mixed = { selectedRecordNos: ['PC-BM-A', 'PC-BM-X'], processedRecordNos: ['PC-BM-A', 'PC-BM-X'], unselectedRecordNos: ['PC-BM-U'], successRecordNos: ['PC-BM-A'], failedRecordNos: ['PC-BM-X'], successCount: 1, failedCount: 1 }
    } finally { await context.close() }
  }

  return matrix
}

async function runSupplierSelectionMatrix(browser) {
  const records = [fixtureCheck('PC-NAV-A', 'checked'), fixtureCheck('PC-NAV-B', 'checked')]
  const { context, page } = await newFixtureContext(browser, records)
  try {
    const button = page.locator('[data-acceptance-id="go-supplier-settlement-selected-button"]')
    await expect(button).toBeDisabled()
    await expect(button).toHaveAttribute('title', '请选择一条采购应付核对记录。')
    const zero = { disabled: true, reason: '请选择一条采购应付核对记录。' }

    await selectRows(page, ['PC-NAV-A'])
    await expect(button).toBeEnabled()
    await button.click()
    await page.waitForURL(/\/scm\/supplier-settlements\?sourcePayableCheckNo=PC-NAV-A/)
    await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('PC-NAV-A')
    await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('PP-PC-NAV-A')
    await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('PO-PC-NAV-A')
    await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('精工铝材供应商')
    await expect(page.locator('[data-acceptance-id="supplier-settlement-context-pending"]')).toBeVisible()
    expect((await readBusinessState(page)).settlements).toHaveLength(0)
    const one = { enabled: true, sourcePayableCheckNo: 'PC-NAV-A', status: 'pending_source', supplierSettlementGenerated: false }

    await openPayableCheckList(page)
    await selectRows(page, ['PC-NAV-A', 'PC-NAV-B'])
    await expect(button).toBeDisabled()
    await expect(button).toHaveAttribute('title', '供应商结算需要单条来源上下文，请仅选择1条记录。')
    const multiple = { disabled: true, reason: '供应商结算需要单条来源上下文，请仅选择1条记录。', navigationCount: 0 }
    expect((await readBusinessState(page)).settlements).toHaveLength(0)
    return { zero, one, multiple }
  } finally { await context.close() }
}

async function verifyCheckedInFreshContext(browser, entities, storageStatePath) {
  const context = await browser.newContext({ storageState: storageStatePath, userAgent: `PCE-Payable-Checked-Restore/${VERSION}` })
  const page = await context.newPage()
  try {
    await page.goto(`${ORIGIN}/#/finance/payable-check/${entities.payableCheckId}`, { waitUntil: 'networkidle' })
    await expect(page.getByTestId('payable-check-detail-no')).toHaveText(entities.payableCheckNo)
    await expect(page.getByTestId('payable-check-detail-status')).toHaveText('已核对')
    await expect(page.getByTestId('payable-check-detail-prepare-no')).toHaveText(entities.payablePrepareNo)
    const state = await readBusinessState(page)
    expect(state.checks).toHaveLength(1)
    expect(state.checks[0].checkStatus).toBe('checked')
    expect(state.settlements).toHaveLength(0)
    return { result: 'passed', payableCheckNo: entities.payableCheckNo, payableCheckStatus: 'checked', supplierSettlementGenerated: false }
  } finally { await context.close() }
}

test('从 payable_prepared 通过真实页面形成 payable_checked', async ({ browser }) => {
  test.setTimeout(180_000)
  expect(RUN_ID).toBeTruthy()
  const source = await verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const sourceHashesBefore = await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)
  const { entities } = source
  expect(entities.payablePrepareNo).toMatch(/^PP\d+$/)

  const context = await browser.newContext({
    storageState: checkpointPath(SOURCE_CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Payable-Check-Golden/${VERSION}`,
  })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    const before = await readBusinessState(page)
    expect(before.prepares).toHaveLength(1)
    expect(before.prepares[0].payableStatus).toBe('prepared')
    expect(before.checks).toHaveLength(0)
    expect(before.settlements).toHaveLength(0)
    expect(before.reconciliations).toHaveLength(0)

    await page.goto(`${ORIGIN}/#/finance/payable-prepare/${entities.payablePrepareId}`, { waitUntil: 'networkidle' })
    await expect(page.getByTestId('payable-prepare-detail-no')).toHaveText(entities.payablePrepareNo)
    const createButton = page.getByTestId('create-payable-check-from-detail')
    await expect(createButton).toHaveCount(1)
    await createButton.click()
    await page.waitForURL(/#\/finance\/payable-check\/[^/]+$/)

    const created = await readBusinessState(page)
    expect(created.checks).toHaveLength(1)
    const check = created.checks[0]
    expect(check.payableCheckNo).toMatch(/^PC\d+/)
    expect(check.checkStatus).toBe('draft')
    expect(check.sourcePayablePrepareId).toBe(entities.payablePrepareId)
    expect(check.sourcePayablePrepareNo).toBe(entities.payablePrepareNo)
    expect(check.sourceInventoryTransactionNos).toContain(entities.inventoryTransactionNo)
    expect(check.sourceWarehouseTaskNo).toBe(entities.qualifiedInboundNo)
    expect(check.sourceInspectionNo).toBe(entities.incomingInspectionNo)
    expect(check.sourceReceiveNo).toBe(entities.purchaseReceiveNo)
    expect(check.sourcePurchaseOrderNo).toBe(entities.purchaseOrderNo)
    expect(check.sourcePriceApprovalNo).toBe(entities.priceApprovalNo)
    expect(check.supplierId).toBe('sup-001')
    expect(check.supplierName).toBe('精工铝材供应商')
    expect(check.lines[0].materialCode).toBe('MAT-000001')
    expect(check.totalPayableQty).toBe(1)
    expect(check.totalPayableAmount).toBe(66)
    expect(check.totalCheckedAmount).toBe(66)
    expect(check.amountDifference).toBe(0)
    await expect(page.getByTestId('payable-check-detail-status')).toHaveText('未核对')

    const completeButton = page.getByTestId('complete-payable-check-detail')
    await expect(completeButton).toBeEnabled()
    await completeButton.click()
    await expect(page.getByTestId('payable-check-detail-status')).toHaveText('已核对')
    await expect(completeButton).toBeDisabled()
    const completed = await readBusinessState(page)
    const completedCheck = completed.checks[0]
    expect(completedCheck.checkStatus).toBe('checked')
    expect(completedCheck.checkedAt).toBeTruthy()
    expect(completedCheck.completedAt).toBeTruthy()
    expect(completed.settlements).toHaveLength(0)
    const completedAt = completedCheck.completedAt

    await page.reload({ waitUntil: 'networkidle' })
    await expect(page.getByTestId('complete-payable-check-detail')).toBeDisabled()
    const afterRepeatGuard = await readBusinessState(page)
    expect(afterRepeatGuard.checks).toHaveLength(1)
    expect(afterRepeatGuard.checks[0].completedAt).toBe(completedAt)
    expect(afterRepeatGuard.settlements).toHaveLength(0)
    expect(afterRepeatGuard.reconciliations).toHaveLength(0)
    expect(afterRepeatGuard.invoicePrepares).toHaveLength(0)
    expect(afterRepeatGuard.payments).toHaveLength(0)

    const batchMatrix = await runBatchMatrix(browser)
    const supplierSelectionMatrix = await runSupplierSelectionMatrix(browser)

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
        inventoryTransactionId: entities.inventoryTransactionId,
        inventoryTransactionNo: entities.inventoryTransactionNo,
        payablePrepareId: entities.payablePrepareId,
        payablePrepareNo: entities.payablePrepareNo,
        payableCheckId: completedCheck.id,
        payableCheckNo: completedCheck.payableCheckNo,
        supplierSettlementGenerated: false,
      },
      baseUrl: ORIGIN,
      nextStageId: 'supplier-settlement',
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
    })
    expect(checkpoint.entities.payableCheckNo).toBe(completedCheck.payableCheckNo)
    expect(checkpoint.entities.payableCheckStatus).toBe('checked')
    expect(checkpoint.entities.payableChecked).toBe(true)
    expect(checkpoint.entities.checkedAmount).toBe(66)
    expect(checkpoint.entities.differenceAmount).toBe(0)
    expect(checkpoint.graph.downstreamRelations.some((item) => item.relation === 'payablePrepare -> payableCheck' && item.matched)).toBe(true)
    const restored = await verifyCheckedInFreshContext(browser, checkpoint.entities, path.join(checkpoint.directory, 'storage-state.json'))
    await markCheckpointRestored(TARGET_CHECKPOINT_ID, { ...restored, verificationProcess: 'new_context_same_process', userProfileOpened: false, userBusinessDataModified: false }, checkpoint.directory)
    expect(await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID)).toEqual(sourceHashesBefore)
    expect(consoleErrors).toEqual([])

    await fs.writeFile(path.join(RESULT_ROOT, 'payable-check-golden-flow-report.json'), `${JSON.stringify({
      version: VERSION,
      runId: RUN_ID,
      sourceCheckpointId: SOURCE_CHECKPOINT_ID,
      sourceCheckpointPath: source.directory,
      targetCheckpointId: TARGET_CHECKPOINT_ID,
      targetCheckpointPath: checkpoint.directory,
      runnerTraceExpectedPath: path.join(test.info().outputDir, 'trace.zip'),
      playwrightOutputDir: test.info().outputDir,
      canonicalName: '采购应付核对',
      moduleId: 'payable-check',
      fullUrl: `${ORIGIN}/#/finance/payable-checks`,
      pageComponent: 'PayableCheckPage.vue',
      createButtonName: '生成采购应付核对',
      completeButtonName: '完成采购应付核对',
      beforePayableCheckCount: before.checks.length,
      payableCheckId: completedCheck.id,
      payableCheckNo: completedCheck.payableCheckNo,
      initialStatus: 'draft',
      completedStatus: completedCheck.checkStatus,
      completedAt,
      payableAmount: completedCheck.totalPayableAmount,
      checkedAmount: completedCheck.totalCheckedAmount,
      differenceAmount: completedCheck.amountDifference,
      duplicateCompletionBlocked: true,
      batchTransactionPolicy: 'per_item_partial_success',
      batchMatrix,
      supplierSelectionMatrix,
      supplierSettlementGenerated: false,
      purchaseReconciliationGenerated: false,
      paymentGenerated: false,
      directStoreCallCount: 0,
      userProfileOpened: false,
      userBusinessDataModified: false,
      sourceCheckpointHashesBefore: sourceHashesBefore,
      sourceCheckpointHashesAfter: await checkpointImmutableHashes(SOURCE_CHECKPOINT_ID),
      overall: 'passed',
    }, null, 2)}\n`, 'utf8')
  } finally {
    await context.close().catch(() => {})
  }
})

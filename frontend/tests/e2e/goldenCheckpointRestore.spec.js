import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import {
  checkpointImmutableHashes,
  checkpointPath,
  markCheckpointRestored,
  verifyCheckpointIntegrity,
} from '../helpers/goldenCheckpoint.js'

const CHECKPOINT_ID = process.env.PCE_CHECKPOINT_ID || 'order_issued'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'

function formItem(page, label) {
  return page.locator('.el-form-item').filter({ hasText: label }).first()
}

async function expandQuickSearch(page) {
  const button = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await button.count()) await button.first().click()
}

async function verifyPurchaseOrderCheckpoint(page, entities) {
  await page.goto('/#/scm/purchase-orders', { waitUntil: 'networkidle' })
  await expandQuickSearch(page)
  await page.getByPlaceholder('搜索单号、人员、供应商、物料、部门、状态').fill(entities.purchaseOrderNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.purchaseOrderNo }).first()
  await expect(row).toBeVisible()
  await expect(row).toContainText('已下达')
  await row.getByRole('button', { name: '查看明细', exact: true }).click()
  await expect(page).toHaveURL(/#\/scm\/purchase-order\//)
  expect(await formItem(page, '采购订单号').locator('input').first().inputValue()).toBe(entities.purchaseOrderNo)
  expect(await formItem(page, '来源核价单').locator('input').first().inputValue()).toBe(entities.priceApprovalNo)
  await expect(page.getByText(entities.materialName || entities.materialCode, { exact: false }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: '进入 WMS 收货预备', exact: true }).first()).toBeVisible()
  return { purchaseOrderSearchMatched: true, purchaseOrderStatus: entities.purchaseOrderStatus, sourcePriceApprovalMatched: true, sourceRelationshipMatched: true, nextStageEntryVisible: true }
}

async function verifyArrivalCheckpoint(page, entities) {
  await page.goto('/#/wms/purchase-receive-preview', { waitUntil: 'networkidle' })
  await expandQuickSearch(page)
  await page.getByPlaceholder('搜索单号、供应商、物料、部门、状态').fill(entities.purchaseOrderNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.purchaseOrderNo }).first()
  await expect(row).toBeVisible()
  await expect(row).toContainText(entities.supplierName)
  await expect(row).toContainText(entities.materialName || entities.materialCode)
  await expect(row.getByRole('button', { name: '直接生成采购收货预备单', exact: true })).toBeVisible()
  expect(entities.arrivalContext?.purchaseOrderNo).toBe(entities.purchaseOrderNo)
  expect(entities.arrivalContext?.status).toBe('arrival_ready')
  return { purchaseOrderSearchMatched: true, arrivalContextMatched: true, nextStageEntryVisible: true }
}

async function verifyReceiveCheckpoint(page, entities) {
  await page.goto('/#/wms/purchase-receives', { waitUntil: 'networkidle' })
  await expandQuickSearch(page)
  await page.getByPlaceholder('搜索收货单、供应商、物料、状态').fill(entities.purchaseReceiveNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.purchaseReceiveNo }).first()
  await expect(row).toBeVisible()
  await expect(row).toContainText(entities.purchaseOrderNo)
  await row.getByRole('button', { name: '详情', exact: true }).click()
  await expect(page).toHaveURL(/#\/wms\/purchase-receive\//)
  await expect(page.getByText(entities.purchaseReceiveNo, { exact: true }).first()).toBeVisible()
  await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()
  expect(entities.purchaseReceiveStatus).toBe('prepared')
  return { purchaseReceiveSearchMatched: true, sourcePurchaseOrderMatched: true, receiveReadyStatusMatched: true, nextStageEntryVisible: false }
}

async function verifyIncomingInspectionCheckpoint(page, entities) {
  await page.goto('/#/qms/incoming-inspections', { waitUntil: 'networkidle' })
  await expandQuickSearch(page)
  await page.getByPlaceholder('搜索检验单、收货单、供应商、物料、状态').fill(entities.incomingInspectionNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.incomingInspectionNo }).first()
  await expect(row).toBeVisible()
  await expect(row).toContainText(entities.purchaseReceiveNo)
  await expect(row).toContainText(entities.purchaseOrderNo)
  await expect(row).toContainText('待检')
  expect(entities.incomingInspectionStatus).toBe('pending')
  return {
    incomingInspectionSearchMatched: true,
    sourcePurchaseReceiveMatched: true,
    sourcePurchaseOrderMatched: true,
    incomingInspectionReadyStatusMatched: true,
    nextStageEntryVisible: true,
  }
}

async function verifyIncomingInspectionPassedCheckpoint(page, entities) {
  await page.goto('/#/qms/incoming-inspections', { waitUntil: 'networkidle' })
  await expandQuickSearch(page)
  await page.getByPlaceholder('搜索检验单、收货单、供应商、物料、状态').fill(entities.incomingInspectionNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.incomingInspectionNo }).first()
  await expect(row).toBeVisible()
  await expect(row).toContainText(entities.purchaseReceiveNo)
  await expect(row).toContainText(entities.purchaseOrderNo)
  await expect(row).toContainText('已检验')
  expect(entities.incomingInspectionStatus).toBe('inspected')
  const inspection = entities.records?.incomingInspection
  expect(inspection?.inventoryPosted).toBe(false)
  expect(inspection?.inventoryPostStatus).toBe('notPosted')
  expect(inspection?.lines?.[0]?.qualifiedQty).toBe(1)
  expect(inspection?.lines?.[0]?.unqualifiedQty).toBe(0)
  expect(inspection?.lines?.[0]?.inspectResult).toBe('qualified')
  return {
    incomingInspectionSearchMatched: true,
    sourcePurchaseReceiveMatched: true,
    sourcePurchaseOrderMatched: true,
    incomingInspectionPassedStatusMatched: true,
    inventoryNotWritten: true,
    payableNotGenerated: true,
    nextStageEntryVisible: true,
  }
}

async function verifyQualifiedInboundReadyCheckpoint(page, entities) {
  await page.goto(`/#/wms/warehouse-task/${entities.qualifiedInboundId}`, { waitUntil: 'networkidle' })
  await expect(page.getByText(entities.qualifiedInboundNo, { exact: true }).first()).toBeVisible()
  await expect(page.getByText(entities.incomingInspectionNo, { exact: true }).first()).toBeVisible()
  await expect(page.getByText(entities.purchaseReceiveNo, { exact: true }).first()).toBeVisible()
  await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()
  const task = entities.records?.qualifiedInbound
  const inspection = entities.records?.incomingInspection
  expect(task?.businessType).toBe('qualifiedInboundPrepare')
  expect(task?.status).toBe('pending')
  expect(task?.plannedQuantity).toBe(1)
  expect(task?.completedQuantity).toBe(0)
  expect(inspection?.status).toBe('inboundPrepared')
  expect(inspection?.inventoryPosted).toBe(false)
  expect(inspection?.inventoryPostStatus).toBe('inboundPrepared')
  return {
    qualifiedInboundTargetVisible: true,
    sourceIncomingInspectionMatched: true,
    sourcePurchaseReceiveMatched: true,
    sourcePurchaseOrderMatched: true,
    targetPendingInboundStatusMatched: true,
    inventoryNotWritten: true,
    payableNotGenerated: true,
    nextStageEntryVisible: true,
  }
}

async function verifyQualifiedInboundCompletedCheckpoint(page, entities) {
  await page.goto(`/#/wms/warehouse-task/${entities.qualifiedInboundId}`, { waitUntil: 'networkidle' })
  await expect(page.getByText(entities.qualifiedInboundNo, { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: '确认入库', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '查看库存流水', exact: true })).toBeVisible()
  const task = entities.records?.qualifiedInbound
  const inspection = entities.records?.incomingInspection
  const receive = entities.records?.purchaseReceive
  const transaction = entities.records?.inventoryTransaction
  expect(task?.status).toBe('done')
  expect(task?.completedQuantity).toBe(1)
  expect(task?.inventoryTransactionNo).toBe(entities.inventoryTransactionNo)
  expect(inspection?.status).toBe('inventoryPosted')
  expect(inspection?.inventoryPosted).toBe(true)
  expect(receive?.inventoryPosted).toBe(true)
  expect(transaction?.transactionType).toBe('purchaseInspectionIn')
  expect(transaction?.sourceWarehouseTaskNo).toBe(entities.qualifiedInboundNo)
  return {
    qualifiedInboundTargetVisible: true,
    targetCompletedStatusMatched: true,
    inventoryTransactionMatched: true,
    sourceIncomingInspectionMatched: true,
    sourcePurchaseReceiveMatched: true,
    sourcePurchaseOrderMatched: true,
    inventoryWritten: true,
    payableNotGenerated: true,
    nextStageEntryVisible: true,
  }
}

async function verifyPayablePreparedCheckpoint(page, entities) {
  await page.goto('/#/finance/payable-prepares', { waitUntil: 'networkidle' })
  await expandQuickSearch(page)
  const quickSearch = page.locator('[data-acceptance-id="list-fuzzy-search-input"] input')
  await expect(quickSearch).toHaveCount(1)
  await quickSearch.fill(entities.inventoryTransactionNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.inventoryTransactionNo })
  await expect(row).toHaveCount(1)
  await expect(row).toContainText(entities.payablePrepareNo)
  await expect(row.getByRole('button', { name: '生成采购应付预备', exact: true })).toHaveCount(0)
  const viewButton = row.getByRole('button', { name: '查看采购应付预备', exact: true })
  await expect(viewButton).toBeVisible()
  await viewButton.click()
  await expect(page).toHaveURL(new RegExp(`#\/finance\/payable-prepare\/${entities.payablePrepareId}$`))
  await expect(page.getByTestId('payable-prepare-detail-no')).toHaveText(entities.payablePrepareNo)
  await expect(page.getByTestId('payable-prepare-detail-transaction-no')).toHaveText(entities.inventoryTransactionNo)
  await expect(page.getByTestId('payable-prepare-detail-warehouse-task-no')).toHaveText(entities.qualifiedInboundNo)
  await expect(page.getByTestId('payable-prepare-detail-inspection-no')).toHaveText(entities.incomingInspectionNo)
  await expect(page.getByTestId('payable-prepare-detail-receive-no')).toHaveText(entities.purchaseReceiveNo)
  await expect(page.getByTestId('payable-prepare-detail-order-no')).toHaveText(entities.purchaseOrderNo)
  await expect(page.getByTestId('payable-prepare-detail-price-approval-no')).toHaveText(entities.priceApprovalNo)
  await expect(page.getByTestId('payable-prepare-detail-supplier')).toHaveText(entities.supplierName)
  await expect(page.getByTestId('payable-prepare-detail-material')).toContainText(`${entities.materialCode} / ${entities.materialName}`)
  await expect(page.getByTestId('payable-prepare-detail-quantity')).toHaveText(`${entities.payableQuantity} ${entities.unit}`)
  await expect(page.getByTestId('payable-prepare-detail-amount')).toHaveText(String(entities.payableAmount))
  const restored = await page.evaluate((payablePrepareId) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    const payable = read('payable-prepare-state-v1')
    const checks = read('payable-check-state-v1')
    const settlements = read('supplier-settlement-state-v1')
    return {
      prepare: (payable.payablePrepares || []).find((item) => String(item.id) === String(payablePrepareId)),
      payableCount: (payable.payablePrepares || []).length,
      checkCount: (checks.payableChecks || []).length,
      settlementCount: (settlements.supplierSettlements || settlements.settlements || []).length,
    }
  }, entities.payablePrepareId)
  expect(restored.prepare?.payableStatus).toBe('prepared')
  expect(restored.prepare?.sourceInventoryTransactionNo).toBe(entities.inventoryTransactionNo)
  expect(restored.prepare?.sourceInventoryTransactionType).toBe('purchaseInspectionIn')
  expect(restored.prepare?.totalPayableQty).toBe(1)
  expect(restored.prepare?.totalPayableAmount).toBe(66)
  expect(restored.payableCount).toBe(1)
  expect(restored.checkCount).toBe(0)
  expect(restored.settlementCount).toBe(0)
  return {
    payablePrepareSearchMatched: true,
    sourceInventoryTransactionMatched: true,
    payablePrepareStatusMatched: true,
    payableCheckGenerated: false,
    supplierSettlementGenerated: false,
    nextStageEntryVisible: true,
  }
}

async function verifyPayableCheckedCheckpoint(page, entities) {
  await page.goto(`/#/finance/payable-check/${entities.payableCheckId}`, { waitUntil: 'networkidle' })
  await expect(page.getByTestId('payable-check-detail-no')).toHaveText(entities.payableCheckNo)
  await expect(page.getByTestId('payable-check-detail-status')).toHaveText('已核对')
  await expect(page.getByTestId('payable-check-detail-prepare-no')).toHaveText(entities.payablePrepareNo)
  await expect(page.getByTestId('payable-check-detail-transaction-no')).toHaveText(entities.inventoryTransactionNo)
  await expect(page.getByTestId('payable-check-detail-order-no')).toHaveText(entities.purchaseOrderNo)
  await expect(page.getByTestId('payable-check-detail-supplier')).toHaveText(entities.supplierName)
  await expect(page.getByTestId('payable-check-detail-material')).toContainText(entities.materialCode)
  await expect(page.getByTestId('payable-check-detail-settlement-status')).toHaveText('尚未生成')
  const restored = await page.evaluate(({ payableCheckId, payablePrepareId }) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    return {
      prepare: (read('payable-prepare-state-v1').payablePrepares || []).find((item) => String(item.id) === String(payablePrepareId)),
      check: (read('payable-check-state-v1').payableChecks || []).find((item) => String(item.id) === String(payableCheckId)),
      checkCount: (read('payable-check-state-v1').payableChecks || []).length,
      settlementCount: (read('supplier-settlement-state-v1').supplierSettlements || read('supplier-settlement-state-v1').settlements || []).length,
    }
  }, entities)
  expect(restored.prepare?.payableStatus).toBe('prepared')
  expect(restored.checkCount).toBe(1)
  expect(restored.check?.checkStatus).toBe('checked')
  expect(restored.check?.sourcePayablePrepareNo).toBe(entities.payablePrepareNo)
  expect(restored.check?.totalPayableAmount).toBe(66)
  expect(restored.check?.totalCheckedAmount).toBe(66)
  expect(restored.check?.amountDifference).toBe(0)
  expect(restored.check?.completedAt).toBeTruthy()
  expect(restored.settlementCount).toBe(0)
  return {
    payableCheckSearchMatched: true,
    payableCheckStatusMatched: true,
    sourcePayablePrepareMatched: true,
    supplierSettlementGenerated: false,
    nextStageEntryVisible: true,
  }
}

async function verifySupplierSettlementReadyCheckpoint(page, entities) {
  await page.goto('/#/scm/supplier-settlements', { waitUntil: 'networkidle' })
  const search = page.locator('[data-acceptance-id="list-fuzzy-search-input"] input')
  await search.fill(entities.supplierSettlementNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.supplierSettlementNo })
  await expect(row).toHaveCount(1)
  await expect(row).toContainText(entities.payableCheckNo)
  await expect(row).toContainText('66.00')
  const restored = await page.evaluate((settlementId) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    return {
      settlement: (read('supplier-settlement-state-v1').supplierSettlements || []).find((item) => String(item.id) === String(settlementId)),
      settlementCount: (read('supplier-settlement-state-v1').supplierSettlements || []).length,
      reconciliationCount: (read('purchase-reconciliation-state-v1').purchaseReconciliations || []).length,
      paymentCount: (read('payment-application-state-v1').paymentApplications || []).length,
    }
  }, entities.supplierSettlementId)
  expect(restored.settlementCount).toBe(1)
  expect(restored.settlement?.sourcePayableCheckNo).toBe(entities.payableCheckNo)
  expect(restored.settlement?.sourcePayablePrepareNo).toBe(entities.payablePrepareNo)
  expect(restored.settlement?.sourceInventoryTransactionNos).toContain(entities.inventoryTransactionNo)
  expect(restored.settlement?.sourcePurchaseOrderNo).toBe(entities.purchaseOrderNo)
  expect(restored.settlement?.sourcePriceApprovalNo).toBe(entities.priceApprovalNo)
  expect(restored.settlement?.settlementQuantity).toBe(1)
  expect(restored.settlement?.settlementAmount).toBe(66)
  expect(restored.reconciliationCount).toBe(0)
  expect(restored.paymentCount).toBe(0)
  return { supplierSettlementSearchMatched: true, sourcePayableCheckMatched: true, purchaseReconciliationGenerated: false, paymentGenerated: false, nextStageEntryVisible: true }
}

test(`跨进程恢复金丝雀检查点 ${CHECKPOINT_ID}`, async ({ browser }) => {
  test.setTimeout(60_000)
  const checkpoint = await verifyCheckpointIntegrity(CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const immutableHashesBefore = await checkpointImmutableHashes(CHECKPOINT_ID)
  const { entities, graph } = checkpoint
  const context = await browser.newContext({
    storageState: checkpointPath(CHECKPOINT_ID, 'storage-state.json'),
    userAgent: 'PCE-Golden-Checkpoint-Restore/V1.14.2.8.4.7.5',
  })
  const page = await context.newPage()
  if (CHECKPOINT_ID === 'purchase_reconciliation_matched_ready') {
    await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.fulfill({ status: 405, contentType: 'application/json', body: JSON.stringify({ result: 'rejected' }) })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          result: 'passed',
          data: {
            count: 1,
            results: [{
              id: entities.matchedCanary.id,
              reconciliationNo: entities.matchedCanary.reconciliationNo,
              sourceSettlementNo: 'PCE-REG-v42-a',
              sourcePayableCheckNo: 'PAYABLE-v42-a',
              purchaseOrderNo: 'PO-v42-a',
              supplierName: 'V42 Canary Supplier',
              settlementAmount: '100.00',
              status: 'matched',
              differenceCount: 0,
              version: 2,
              nextStepReadiness: 'ready_for_invoice_prepare',
              invoicePrepareEligibility: entities.matchedCanary.eligibility,
            }],
          },
        }),
      })
    })
  } else if (CHECKPOINT_ID === 'purchase_accounts_payable_draft_controlled_generation_ready') {
    const source = entities.sourcePurchaseInvoicePrepare
    const draft = entities.purchaseAccountsPayableDraft
    const currentState = entities.currentState
    await page.route('**/api/scm/purchase-accounts-payable-drafts/**', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.fulfill({ status: 405, contentType: 'application/json', body: JSON.stringify({ result: 'rejected' }) })
        return
      }
      const pathname = new URL(route.request().url()).pathname
      let data
      if (pathname.includes('/by-source/')) {
        data = {
          source: {
            ...source,
            id: source.id,
            prepareNo: source.prepareNo,
            sourcePurchaseReconciliationNo: draft.sourcePurchaseReconciliationNo,
            sourcePurchaseReconciliationStatus: 'matched',
          },
          count: 1,
          results: [draft],
          ...currentState,
          preActionBusinessGate: entities.preActionBusinessGate,
        }
      } else if (pathname.includes('/generation-results/')) {
        data = { classification: 'existing_result', currentState }
      } else if (/\/purchase-accounts-payable-drafts\/\d+$/.test(pathname)) {
        data = { ...draft, source, currentState }
      } else {
        data = { currentStateSource: 'server', count: 1, results: [draft] }
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ result: 'passed', data }),
      })
    })
  } else if ([
    'purchase_invoice_prepare_controlled_generation_ready',
    'purchase_invoice_prepare_current_state_consistent_ready',
    'purchase_invoice_prepare_validated_ready',
  ].includes(CHECKPOINT_ID)) {
    const prepare = entities.purchaseInvoicePrepare
    const isValidatedReady = CHECKPOINT_ID === 'purchase_invoice_prepare_validated_ready'
    const validationReadModel = isValidatedReady ? {
      currentStateSource: 'server',
      purchaseInvoicePrepare: prepare,
      invoiceData: entities.invoiceData,
      validation: entities.validation,
      validationIssues: [],
      invoiceIdentity: entities.invoiceIdentity,
      accountsPayableDraftEligibility: entities.accountsPayableDraftEligibility,
      versionsAndAudit: entities.versionsAndAudit,
      downstreamCounts: entities.downstreamCounts,
    } : null
    const currentState = {
      currentStateSource: 'server',
      targetExistenceStatus: 'single_target',
      targetCount: 1,
      preActionTargetCount: 0,
      generationAllowed: false,
      generationStatus: 'existing_target',
      preActionBusinessGateResult: 'passed',
      currentIdempotencyStatus: 'committed',
      currentNumberReservationStatus: 'consumed',
      currentTransactionStatus: 'committed',
      currentAuditStatus: 'committed',
      currentSourceRelationStatus: 'generated_from',
      generationResultIdempotencyKey: prepare.idempotencyKey,
      testTenant: true,
      productionRolloutEnabled: false,
      purchaseInvoicePrepare: prepare,
    }
    await page.route('**/api/scm/purchase-invoice-prepares/**', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.fulfill({ status: 405, contentType: 'application/json', body: JSON.stringify({ result: 'rejected' }) })
        return
      }
      const pathname = new URL(route.request().url()).pathname
      let body
      if (pathname.endsWith('/invoice-data')) {
        body = { result: 'passed', data: validationReadModel }
      } else if (pathname.endsWith('/validation-issues')) {
        body = { result: 'passed', data: { validation: entities.validation, issues: [] } }
      } else if (pathname.endsWith('/accounts-payable-draft-eligibility')) {
        body = { result: 'passed', data: entities.accountsPayableDraftEligibility }
      } else if (pathname.includes('/validation-results/')) {
        body = { result: 'passed', classification: 'existing_result', ...validationReadModel }
      } else if (pathname.includes('/generation-results/')) {
        body = { result: 'passed', classification: 'existing_result', created: false, data: prepare, currentState }
      } else if (pathname.includes('/by-source/')) {
        body = { result: 'passed', data: { count: 1, results: [prepare], ...currentState } }
      } else if (/\/purchase-invoice-prepares\/\d+$/.test(pathname)) {
        body = {
          result: 'passed',
          data: { ...prepare, currentState, ...(isValidatedReady ? { validationReadModel } : {}) },
        }
      } else {
        body = { result: 'passed', data: { count: 1, results: [prepare] } }
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })
    await page.route('**/api/scm/purchase-reconciliations/*/invoice-prepare-eligibility', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          result: 'passed',
          data: {
            eligible: true,
            reconciliationNo: entities.sourcePurchaseReconciliation.reconciliationNo,
            status: 'matched',
            checkResultCode: 'PRC_CHECK_MATCHED',
            differenceCount: 0,
            nextStepReadiness: 'ready_for_invoice_prepare',
            evidenceIntegrity: 'passed',
            evidenceSourceCount: 2,
            evidenceSourcesIndependent: true,
            reconciliationVersion: entities.sourcePurchaseReconciliation.version,
            checkVersion: entities.sourcePurchaseReconciliation.checkVersion,
          },
        }),
      })
    })
  }
  const consoleErrors = []
  const failedResponses = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  page.on('response', (response) => {
    if (response.status() >= 500) failedResponses.push(`${response.status()} ${response.request().method()} ${response.url()}`)
  })
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
    const restoredStorage = await page.evaluate(() => ({
      origin: window.location.origin,
      localStorageKeyCount: localStorage.length,
      hasScmState: Boolean(localStorage.getItem('scm-state-v1')),
      hasPurchaseReceiveState: Boolean(localStorage.getItem('wms-purchase-receive-state-v1')),
    }))
    expect(restoredStorage.origin).toBe(ORIGIN)
    if ([
      'purchase_reconciliation_matched_ready',
      'purchase_invoice_prepare_controlled_generation_ready',
      'purchase_invoice_prepare_current_state_consistent_ready',
      'purchase_invoice_prepare_validated_ready',
      'purchase_accounts_payable_draft_controlled_generation_ready',
      'purchase_canary_normal_pages_visible_ready',
      'purchase_canary_downstream_capacity_ready',
      'payable_confirmation_prepare_validated_ready',
      'payment_request_prepare_validated_ready',
      'payment_request_prepare_page_semantics_consistent_ready',
      'payment_request_prepare_page_structure_consistent_ready',
      'payment_request_approved_ready',
      'payment_instruction_prepare_validated_ready',
      'payment_instruction_prepare_observability_ready',
      'payment_order_prepare_validated_ready',
      'payment_order_prepare_standard_list_ready',
      'payment_order_draft_reviewed_ready',
      'payment_order_draft_fact_consistency_ready',
      'payment_risk_review_validated_ready',
      'formal_payment_order_ready',
      'formal_payment_order_page_contract_ready',
      'formal_payment_order_filter_control_ready',
      'formal_payment_order_scenario_filter_ready',
      'pce_web_acceptance_v1_1_ready',
      'pce_web_acceptance_v1_1_framework_ready',
      'pce_web_acceptance_v1_1_finance_chain_ready',
      'pce_web_acceptance_v1_1_full_project_ready',
      'pce_web_acceptance_v11_strict_pages_ready',
    ].includes(CHECKPOINT_ID)) {
      expect(restoredStorage.hasScmState).toBe(false)
      expect(restoredStorage.hasPurchaseReceiveState).toBe(false)
    } else {
      expect(restoredStorage.hasScmState).toBe(true)
      expect(restoredStorage.hasPurchaseReceiveState).toBe([
        'receive_ready',
        'incoming_inspection_ready',
        'incoming_inspection_passed',
        'qualified_inbound_ready',
        'qualified_inbound_completed',
        'payable_prepared',
        'payable_checked',
        'supplier_settlement_ready',
      ].includes(CHECKPOINT_ID))
    }
    let stageVerification
    if (CHECKPOINT_ID === 'supplier_settlement_ready') stageVerification = await verifySupplierSettlementReadyCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'payable_checked') stageVerification = await verifyPayableCheckedCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'payable_prepared') stageVerification = await verifyPayablePreparedCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'qualified_inbound_completed') stageVerification = await verifyQualifiedInboundCompletedCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'qualified_inbound_ready') stageVerification = await verifyQualifiedInboundReadyCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'incoming_inspection_passed') stageVerification = await verifyIncomingInspectionPassedCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'incoming_inspection_ready') stageVerification = await verifyIncomingInspectionCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'arrival_ready') stageVerification = await verifyArrivalCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'receive_ready') stageVerification = await verifyReceiveCheckpoint(page, entities)
    else if (CHECKPOINT_ID === 'purchase_reconciliation_matched_ready') {
      await page.goto(`${ORIGIN}/#/scm/purchase-reconciliations`)
      await expect(page.getByText(entities.matchedCanary.reconciliationNo).first()).toBeVisible()
      await expect(page.getByText('对账一致').first()).toBeVisible()
      expect(entities.matchedCanary.status).toBe('matched')
      expect(entities.matchedCanary.eligibility.eligible).toBe(true)
      expect(entities.matchedCanary.eligibility.nextStepReadiness).toBe('ready_for_invoice_prepare')
      expect(graph.matchedCanaryEvidenceCount).toBe(2)
      expect(new Set(graph.authorityProviders).size).toBe(2)
      expect(Object.values(entities.downstreamCounts).every((count) => count === 0)).toBe(true)
      stageVerification = {
        purchaseReconciliationMatched: true,
        independentAuthorityEvidenceCount: 2,
        invoicePrepareNavigationEligible: true,
        downstreamObjectWriteCount: 0,
      }
    } else if (CHECKPOINT_ID === 'purchase_accounts_payable_draft_controlled_generation_ready') {
      const source = entities.sourcePurchaseInvoicePrepare
      const draft = entities.purchaseAccountsPayableDraft
      await page.goto(`${ORIGIN}/#/process-center`)
      await page.getByRole('link', { name: '采购应付账款草稿', exact: true }).first().click()
      await page.evaluate((sourceId) => {
        window.location.hash = `/finance/ap-drafts?sourcePurchaseInvoicePrepareId=${sourceId}&canary=tenant-v45`
      }, source.id)
      await page.reload()
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-source"]')).toContainText(source.prepareNo)
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-business-gate"]')).toContainText('当前目标数量1')
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-object"]')).toContainText(draft.draftNo)
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-business-gate"]')).toContainText('committed')
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-business-gate"]')).toContainText('consumed')
      expect(entities.currentState.targetCount).toBe(1)
      expect(entities.counts.sourceSnapshots).toBe(1)
      expect(entities.counts.sourceRelations).toBe(1)
      expect(entities.counts.audits).toBe(1)
      expect(Object.values(entities.downstreamCounts).every((count) => count === 0)).toBe(true)
      stageVerification = {
        purchaseAccountsPayableDraftRestoredFromServer: true,
        accountsPayableDraftCountAfterRetry: 1,
        sourceSnapshotCount: 1,
        sourceRelationCount: 1,
        auditCount: 1,
        idempotencyStatus: 'committed',
        numberReservationStatus: 'consumed',
        transactionStatus: 'committed',
        localStorageBusinessWrites: 0,
        downstreamObjectWriteCount: 0,
      }
    } else if (CHECKPOINT_ID === 'purchase_canary_downstream_capacity_ready') {
      await page.goto(`${ORIGIN}/#/finance/ap-drafts`)
      await expect(page.locator('[data-acceptance-id="purchase-canary-capacity"]'))
        .toContainText('金丝雀群测试容量')
      await expect(page.locator('[data-acceptance-id="purchase-canary-capacity"]'))
        .toContainText('8')
      await expect(page.locator('[data-acceptance-id="purchase-canary-scenario-overview"]'))
        .toContainText('SUCCESS_STANDARD_01')
      await expect(page.locator('[data-acceptance-id="purchase-canary-scenario-overview"]'))
        .toContainText('AMOUNT_DIFFERENCE')
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-formal-list"]'))
        .toContainText('APD20260700000001')
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-formal-list"]'))
        .toContainText('APD20260700000008')
      expect(entities.sourceOfTruth).toBe('persistent_server_formal_domain_tables_and_lineage_registry')
      expect(entities.counts.purchaseAccountsPayableDrafts).toBeGreaterThanOrEqual(8)
      expect(entities.counts.purchaseInvoicePrepares).toBeGreaterThanOrEqual(8)
      expect(entities.lineages).toHaveLength(8)
      expect(new Set(entities.lineages.map(item => item.sourceRelationHash)).size).toBe(8)
      expect(entities.lineages.every(item => item.downstreamEligible && !item.nextStageConsumed)).toBe(true)
      expect(graph.relationships).toHaveLength(8)
      expect(Object.values(graph.downstreamObjects).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        passThroughLineageCount: entities.lineages.length,
        purchaseAccountsPayableDraftCount: entities.counts.purchaseAccountsPayableDrafts,
        uniqueSourceRelationCount: new Set(entities.lineages.map(item => item.sourceRelationHash)).size,
        browserLocalStorageBusinessStateRequired: false,
        nextStageConsumedCount: entities.lineages.filter(item => item.nextStageConsumed).length,
        downstreamObjectWriteCount: 0,
      }
    } else if (CHECKPOINT_ID === 'payable_confirmation_prepare_validated_ready') {
      await page.goto(`${ORIGIN}/#/finance/account-payable-confirms`)
      await expect(page.locator('[data-acceptance-id="payable-confirmation-capacity"]'))
        .toContainText('8')
      await expect(page.locator('[data-acceptance-id="payable-confirmation-source"]'))
        .toContainText('purchaseAccountsPayableDraft')
      await expect(page.locator('[data-acceptance-id="accounting-validation-evidence"]'))
        .toContainText('ready_for_payment_request_prepare')
      await expect(page.locator('[data-acceptance-id="payable-confirmation-formal-list"]'))
        .toContainText('PCP20260700000001')
      await expect(page.locator('[data-acceptance-id="payable-confirmation-formal-list"]'))
        .toContainText('PCP20260700000008')
      await expect(page.locator('[data-acceptance-id="payment-request-prepare-zero-boundary"]'))
        .toContainText('paymentRequestPrepareCreated=false')
      expect(entities.version).toBe('V1.14.2.8.4.7.46')
      expect(entities.canonicalName).toBe('应付确认准备')
      expect(entities.sourceDocumentType).toBe('purchaseAccountsPayableDraft')
      expect(entities.counts.formalPayableConfirmationPrepares).toBeGreaterThanOrEqual(8)
      expect(entities.counts.downstreamEligibleSources).toBeGreaterThanOrEqual(8)
      expect(entities.counts.nextStageConsumed).toBe(0)
      expect(entities.nextModuleCode).toBe('payment_request_prepare')
      expect(entities.paymentRequestPrepareCreated).toBe(false)
      expect(entities.prepares).toHaveLength(8)
      expect(entities.prepares.every(item => (
        item.status === 'prepared'
        && item.validationStatus === 'passed'
        && item.validationIssueCount === 0
        && item.eligibility?.nextStepReadiness === 'ready_for_payment_request_prepare'
        && item.nextStageConsumed === false
      ))).toBe(true)
      expect(graph.relationships).toHaveLength(8)
      expect(Object.values(graph.downstreamObjects).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        formalPayableConfirmationPrepareCount: entities.counts.formalPayableConfirmationPrepares,
        downstreamEligibleSourceCount: entities.counts.downstreamEligibleSources,
        nextStageConsumedCount: entities.counts.nextStageConsumed,
        browserLocalStorageBusinessStateRequired: false,
        paymentRequestPrepareCreated: false,
        downstreamObjectWriteCount: 0,
      }
    } else if ([
      'payment_request_prepare_validated_ready',
      'payment_request_prepare_page_semantics_consistent_ready',
      'payment_request_prepare_page_structure_consistent_ready',
    ].includes(CHECKPOINT_ID)) {
      await page.goto(`${ORIGIN}/#/finance/payment-applications`)
      await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').last())
        .toHaveText('付款申请准备')
      await expect(page.locator('[data-acceptance-id="payment-request-prepare-capacity"]'))
        .toContainText('容量门禁：通过')
      await expect(page.locator('[data-acceptance-id="payment-request-prepare-source"]'))
        .toContainText('payableConfirmationPrepare')
      await expect(page.locator('[data-acceptance-id="payment-request-data"]'))
        .toContainText('****')
      await expect(page.locator('[data-acceptance-id="payment-element-validation"]'))
        .toContainText('validated')
      await expect(page.locator('[data-acceptance-id="payment-request-eligibility"]'))
        .toContainText('ready_for_payment_request')
      await expect(page.locator('[data-acceptance-id="payment-request-prepare-formal-list"]'))
        .toContainText('PRP20260700000001')
      await expect(page.locator('[data-acceptance-id="payment-request-prepare-formal-list"]'))
        .toContainText('PRP20260700000008')
      await expect(page.locator('[data-acceptance-id="payment-request-zero-boundary"]'))
        .toContainText('paymentRequestCreated=false')
      expect(entities.version).toBe(
        CHECKPOINT_ID === 'payment_request_prepare_page_structure_consistent_ready'
          ? 'V1.14.2.8.4.7.47.2'
          : CHECKPOINT_ID === 'payment_request_prepare_page_semantics_consistent_ready'
            ? 'V1.14.2.8.4.7.47.1'
            : 'V1.14.2.8.4.7.47',
      )
      expect(entities.canonicalName).toBe('付款申请准备')
      expect(entities.sourceDocumentType).toBe('payableConfirmationPrepare')
      expect(entities.counts.formalPaymentRequestPrepares).toBeGreaterThanOrEqual(8)
      expect(entities.counts.downstreamEligibleSources).toBeGreaterThanOrEqual(8)
      expect(entities.counts.nextStageConsumed).toBe(0)
      expect(entities.nextModuleCode).toBe('payment_request')
      expect(entities.paymentRequestCreated).toBe(false)
      expect(entities.prepares).toHaveLength(8)
      expect(entities.prepares.every(item => (
        item.status === 'prepared'
        && item.paymentDataStatus === 'complete'
        && item.validationStatus === 'passed'
        && item.validationResultCode === 'validated'
        && item.validationIssueCount === 0
        && item.eligibility?.nextStepReadiness === 'ready_for_payment_request'
        && item.nextStageConsumed === false
      ))).toBe(true)
      expect(graph.relationships).toHaveLength(8)
      expect(Object.values(graph.downstreamObjects).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        formalPaymentRequestPrepareCount: entities.counts.formalPaymentRequestPrepares,
        downstreamEligibleSourceCount: entities.counts.downstreamEligibleSources,
        nextStageConsumedCount: entities.counts.nextStageConsumed,
        browserLocalStorageBusinessStateRequired: false,
        paymentRequestCreated: false,
        downstreamObjectWriteCount: 0,
      }
    } else if (CHECKPOINT_ID === 'payment_request_approved_ready') {
      await page.goto(`${ORIGIN}/#/finance/payment-requests`)
      await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').last())
        .toHaveText('付款申请')
      await expect(page.locator('[data-acceptance-id="payment-request-capacity"]'))
        .toContainText('8')
      await expect(page.locator('[data-acceptance-id="payment-request-list-region"]'))
        .toContainText('PRQ20260700000001')
      await expect(page.locator('[data-acceptance-id="payment-request-list-region"]'))
        .toContainText('PRQ20260700000008')
      await expect(page.locator('[data-acceptance-id="payment-instruction-prepare-eligibility"]'))
        .toContainText('approved')
      await expect(page.locator('[data-acceptance-id="payment-request-zero-boundary"]'))
        .toContainText('paymentInstructionPrepareCreated=false')
      expect(entities.version).toBe('V1.14.2.8.4.7.48')
      expect(entities.canonicalName).toBe('付款申请')
      expect(entities.sourceDocumentType).toBe('paymentRequestPrepare')
      expect(entities.counts.formalPaymentRequests).toBeGreaterThanOrEqual(8)
      expect(entities.counts.approvedPaymentRequests).toBeGreaterThanOrEqual(8)
      expect(entities.counts.downstreamEligibleSources).toBeGreaterThanOrEqual(8)
      expect(entities.counts.nextStageConsumed).toBe(0)
      expect(entities.nextModuleCode).toBe('payment_instruction_prepare')
      expect(entities.paymentInstructionPrepareCreated).toBe(false)
      expect(entities.requests).toHaveLength(8)
      expect(entities.requests.every(item => (
        item.status === 'approved'
        && item.approvalStatus === 'approved'
        && item.approvalResultCode === 'approved'
        && item.eligible === true
      ))).toBe(true)
      expect(graph.relationships).toHaveLength(8)
      expect(Object.values(graph.downstreamObjects).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        formalPaymentRequestCount: entities.counts.formalPaymentRequests,
        approvedPaymentRequestCount: entities.counts.approvedPaymentRequests,
        downstreamEligibleSourceCount: entities.counts.downstreamEligibleSources,
        nextStageConsumedCount: entities.counts.nextStageConsumed,
        browserLocalStorageBusinessStateRequired: false,
        paymentInstructionPrepareCreated: false,
        downstreamObjectWriteCount: 0,
      }
    } else if ([
      'payment_instruction_prepare_validated_ready',
      'payment_instruction_prepare_observability_ready',
    ].includes(CHECKPOINT_ID)) {
      await page.goto(`${ORIGIN}/#/finance/payment-order-prepares`)
      await expect(page.locator('[data-acceptance-id="payment-instruction-prepare-capacity"]'))
        .toContainText('8')
      await expect(page.locator('[data-acceptance-id="payment-instruction-list-region"]'))
        .toContainText(entities.objects[0].prepareNo)
      await expect(page.locator('[data-acceptance-id="payment-instruction-list-region"]'))
        .toContainText(entities.objects.at(-1).prepareNo)
      await expect(page.locator('[data-acceptance-id="payment-order-prepare-eligibility"]'))
        .toContainText('ready_for_payment_order_prepare')
      expect(entities.version).toBe(
        CHECKPOINT_ID === 'payment_instruction_prepare_observability_ready'
          ? 'V1.14.2.8.4.7.49.1'
          : 'V1.14.2.8.4.7.49',
      )
      if (CHECKPOINT_ID === 'payment_instruction_prepare_observability_ready') {
        const actionBar = page.locator('[data-acceptance-id="page-observability-action-bar"]')
        await expect(actionBar).toBeVisible()
        await expect(actionBar).toHaveAttribute('data-action-location', 'page_action_bar')
        await expect(actionBar.getByRole('button', { name: '复制诊断数据', exact: true })).toBeVisible()
      }
      expect(entities.sourceDocumentType).toBe('paymentRequest')
      expect(entities.sourceOfTruth).toBe('persistent_server_payment_instruction_prepare_and_authority_tables')
      expect(entities.counts.formalPaymentInstructionPrepares).toBeGreaterThanOrEqual(8)
      expect(entities.counts.preparedPaymentInstructionPrepares).toBeGreaterThanOrEqual(8)
      expect(entities.counts.downstreamEligibleSources).toBeGreaterThanOrEqual(8)
      expect(entities.counts.nextStageConsumed).toBe(0)
      expect(entities.counts.blockedScenarios).toBeGreaterThanOrEqual(22)
      expect(entities.nextModuleCode).toBe('payment_order_prepare')
      expect(entities.nextModuleObjectCreated).toBe(false)
      expect(entities.formalPaymentInstructionCreated).toBe(false)
      expect(entities.paymentExecuted).toBe(false)
      expect(entities.objects).toHaveLength(8)
      expect(entities.objects.every(item => (
        item.instructionDataStatus === 'complete'
        && item.validationStatus === 'passed'
        && item.validationResultCode === 'validated'
        && item.eligibility?.nextStepReadiness === 'ready_for_payment_order_prepare'
        && item.eligibility?.serverDerived === true
        && item.previewReadOnly === true
        && item.previewSentExternally === false
      ))).toBe(true)
      expect(graph.relationships).toHaveLength(8)
      expect(Object.values(graph.downstreamObjects).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        formalPaymentInstructionPrepareCount: entities.counts.formalPaymentInstructionPrepares,
        preparedPaymentInstructionPrepareCount: entities.counts.preparedPaymentInstructionPrepares,
        downstreamEligibleSourceCount: entities.counts.downstreamEligibleSources,
        nextStageConsumedCount: entities.counts.nextStageConsumed,
        browserLocalStorageBusinessStateRequired: false,
        nextModuleObjectCreated: false,
        formalPaymentInstructionCreated: false,
        paymentExecuted: false,
        downstreamObjectWriteCount: 0,
      }
    } else if ([
      'payment_order_prepare_validated_ready',
      'payment_order_prepare_standard_list_ready',
      'pce_web_acceptance_v1_1_ready',
      'pce_web_acceptance_v1_1_framework_ready',
      'pce_web_acceptance_v1_1_finance_chain_ready',
      'pce_web_acceptance_v1_1_full_project_ready',
      'pce_web_acceptance_v11_strict_pages_ready',
    ].includes(CHECKPOINT_ID)) {
      await page.goto(`${ORIGIN}/#/finance/payment-prepares`)
      await expect(page.locator('[data-acceptance-id="payment-order-prepare-capacity"]'))
        .toContainText('8')
      await expect(page.locator('[data-acceptance-id="payment-order-prepare-list-region"]'))
        .toContainText(entities.objects[0].prepareNo)
      await expect(page.locator('[data-acceptance-id="payment-order-prepare-list-region"]'))
        .toContainText(entities.objects.at(-1).prepareNo)
      await expect(page.locator('[data-acceptance-id="payment-order-draft-eligibility"]'))
        .toContainText('ready_for_payment_order_draft')
      await expect(page.locator('[data-acceptance-id="payment-order-prepare-zero-boundary"]'))
        .toContainText('nextModuleObjects')
      expect(entities.version).toBe(
        CHECKPOINT_ID.startsWith('pce_web_acceptance_v1_1_')
          ? 'V1.14.2.8.4.7.50.2'
          : CHECKPOINT_ID === 'pce_web_acceptance_v11_strict_pages_ready'
            ? 'V1.14.2.8.4.7.50.1'
          : (CHECKPOINT_ID === 'payment_order_prepare_standard_list_ready'
              ? 'V1.14.2.8.4.7.50.1'
              : 'V1.14.2.8.4.7.50'),
      )
      expect(entities.sourceDocumentType).toBe('paymentInstructionPrepare')
      expect(entities.sourceOfTruth).toBe('persistent_server_payment_order_prepare_and_independent_authority_tables')
      expect(entities.counts.formalPaymentOrderPrepares).toBeGreaterThanOrEqual(8)
      expect(entities.counts.preparedPaymentOrderPrepares).toBeGreaterThanOrEqual(8)
      expect(entities.counts.downstreamEligibleSources).toBeGreaterThanOrEqual(8)
      expect(entities.counts.nextStageConsumed).toBe(0)
      expect(entities.counts.blockedScenarios).toBeGreaterThanOrEqual(30)
      expect(entities.nextModuleObjectCreated).toBe(false)
      expect(entities.formalPaymentOrderCreated).toBe(false)
      expect(entities.paymentExecuted).toBe(false)
      expect(entities.objects).toHaveLength(8)
      expect(entities.objects.every(item => (
        item.status === 'prepared'
        && item.orderDataStatus === 'complete'
        && item.validationStatus === 'passed'
        && item.validationResultCode === 'validated'
        && item.eligibility?.nextStepReadiness === 'ready_for_payment_order_draft'
        && item.eligibility?.serverDerived === true
        && item.preview?.readOnly === true
        && item.preview?.formalPaymentOrderCreated === false
        && item.preview?.signed === false
        && item.preview?.sentExternally === false
      ))).toBe(true)
      expect(graph.relationships).toHaveLength(8)
      expect(Object.values(graph.downstreamObjects).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        formalPaymentOrderPrepareCount: entities.counts.formalPaymentOrderPrepares,
        preparedPaymentOrderPrepareCount: entities.counts.preparedPaymentOrderPrepares,
        downstreamEligibleSourceCount: entities.counts.downstreamEligibleSources,
        nextStageConsumedCount: entities.counts.nextStageConsumed,
        browserLocalStorageBusinessStateRequired: false,
        nextModuleObjectCreated: false,
        formalPaymentOrderCreated: false,
        paymentExecuted: false,
        downstreamObjectWriteCount: 0,
      }
    } else if ([
      'payment_order_draft_reviewed_ready',
      'payment_order_draft_fact_consistency_ready',
    ].includes(CHECKPOINT_ID)) {
      await page.goto(`${ORIGIN}/#/finance/payment-order-drafts`)
      await expect(page.locator('[data-acceptance-id="payment-order-draft-capacity"]'))
        .toContainText('8')
      await expect(page.locator('[data-acceptance-id="payment-order-draft-list-region"]'))
        .toContainText(entities.entities[0].draftNo)
      await expect(page.locator('[data-acceptance-id="payment-order-draft-list-region"]'))
        .toContainText(entities.entities.at(-1).draftNo)
      await expect(page.locator('[data-acceptance-id="payment-order-draft-eligibility"]'))
        .toContainText(
          CHECKPOINT_ID === 'payment_order_draft_fact_consistency_ready'
            ? '可进入真实付款风险评审'
            : 'ready_for_payment_risk_review',
        )
      await expect(page.locator('[data-acceptance-id="payment-order-draft-zero-boundary"]'))
        .toContainText('0')
      expect(entities.version).toBe(
        CHECKPOINT_ID === 'payment_order_draft_fact_consistency_ready'
          ? 'V1.14.2.8.4.7.51.1'
          : 'V1.14.2.8.4.7.51',
      )
      expect(entities.entities).toHaveLength(8)
      expect(entities.entities.every(item => (
        item.status === 'reviewed'
        && item.draftDataStatus === 'complete'
        && item.reviewStatus === 'passed'
        && item.reviewResultCode === 'reviewed'
        && item.reviewIssueCount === 0
        && item.eligibility?.nextStepReadiness === 'ready_for_payment_risk_review'
        && item.eligibility?.serverDerived === true
        && item.preview?.readOnly === true
        && item.preview?.formalPaymentOrderCreated === false
        && item.preview?.signed === false
        && item.preview?.sentExternally === false
      ))).toBe(true)
      expect(graph.edges).toHaveLength(8)
      expect(Object.values(entities.downstreamCounts).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        formalPaymentOrderDraftCount: entities.entities.length,
        reviewedPaymentOrderDraftCount: entities.entities.filter(item => item.status === 'reviewed').length,
        downstreamEligibleSourceCount: entities.entities.filter(item => item.eligibility?.eligible).length,
        nextStageConsumedCount: graph.edges.filter(item => item.nextStageConsumed).length,
        browserLocalStorageBusinessStateRequired: false,
        nextModuleObjectCreated: false,
        formalPaymentOrderCreated: false,
        paymentExecuted: false,
        downstreamObjectWriteCount: 0,
      }
    } else if (CHECKPOINT_ID === 'payment_risk_review_validated_ready') {
      await page.goto(`${ORIGIN}/#/finance/payment-risk-reviews`)
      await expect(page.locator('[data-acceptance-id="payment-risk-review-capacity"]'))
        .toContainText('8')
      await expect(page.locator('[data-acceptance-id="payment-risk-review-list-region"]'))
        .toContainText(entities.entities[0].reviewNo)
      await expect(page.locator('[data-acceptance-id="payment-risk-review-list-region"]'))
        .toContainText(entities.entities.at(-1).reviewNo)
      await expect(page.locator('[data-acceptance-id="payment-risk-review-eligibility"]'))
        .toContainText('可进入正式付款单')
      await expect(page.locator('[data-acceptance-id="payment-risk-review-zero-boundary"]'))
        .toContainText('0')
      expect(entities.version).toBe('V1.14.2.8.4.7.52')
      expect(entities.entities).toHaveLength(8)
      expect(entities.entities.every(item => (
        item.status === 'passed'
        && item.riskResult === 'passed'
        && item.ruleExecution.passedCount === item.ruleExecution.ruleCount
        && item.ruleExecution.blockedCount === 0
        && item.riskIssues.length === 0
        && item.eligibility?.nextStepReadiness === 'ready_for_formal_payment_order'
        && item.eligibility?.serverDerived === true
      ))).toBe(true)
      expect(entities.blockedScenarios.length).toBeGreaterThanOrEqual(12)
      expect(graph.edges).toHaveLength(8)
      expect(Object.values(entities.downstreamCounts).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        sourceDraftCount: entities.entities.length,
        riskReviewCount: entities.entities.length,
        passedRiskReviewCount: entities.entities.filter(item => item.status === 'passed').length,
        blockedScenarioCount: entities.blockedScenarios.length,
        nextStageConsumedCount: graph.edges.filter(item => item.nextStageConsumed).length,
        browserLocalStorageBusinessStateRequired: false,
        formalPaymentOrderCreated: false,
        paymentExecuted: false,
        downstreamObjectWriteCount: 0,
      }
    } else if ([
      'formal_payment_order_ready',
      'formal_payment_order_page_contract_ready',
      'formal_payment_order_filter_control_ready',
      'formal_payment_order_scenario_filter_ready',
    ].includes(CHECKPOINT_ID)) {
      await page.goto(`${ORIGIN}/#/finance/formal-payment-orders`)
      await expect(page.locator('[data-acceptance-id="formal-payment-order-capacity"]'))
        .toContainText('8')
      await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"] tbody tr'))
        .toHaveCount(8)
      await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"]'))
        .toContainText(entities.formalPaymentOrders[0].orderNo)
      await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"]'))
        .toContainText(entities.formalPaymentOrders.at(-1).orderNo)
      await expect(page.locator('[data-acceptance-id="strict-server-row-count"]'))
        .toHaveText('8')
      await expect(page.locator('[data-acceptance-id="formal-payment-order-zero-boundary"]'))
        .toContainText('0')
      expect(entities.version).toBe(
        CHECKPOINT_ID === 'formal_payment_order_scenario_filter_ready'
          ? 'V1.14.2.8.4.7.53.3'
          : 'V1.14.2.8.4.7.53',
      )
      expect(entities.formalPaymentOrders).toHaveLength(8)
      expect(entities.formalPaymentOrders.every(item => item.status === 'prepared')).toBe(true)
      if (CHECKPOINT_ID === 'formal_payment_order_scenario_filter_ready') {
        expect(entities.formalPaymentOrders.map(item => item.sourceScenarioCode)).toEqual(
          Array.from({ length: 8 }, (_, index) => `SUCCESS_${String(index + 1).padStart(2, '0')}`),
        )
        expect(graph.nodes.filter(item => item.type === 'formalPaymentOrder').every(item => item.scenarioCode)).toBe(true)
        expect(graph.nodes.filter(item => item.type === 'paymentRiskReview').every(item => item.scenarioCode)).toBe(true)
      }
      expect(entities.blockedScenarios.length).toBeGreaterThanOrEqual(15)
      expect(graph.edges).toHaveLength(8)
      expect(graph.downstreamEdges).toHaveLength(0)
      expect(Object.values(entities.downstreamCounts).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        formalPaymentOrderCount: entities.formalPaymentOrders.length,
        preparedCount: entities.formalPaymentOrders.filter(item => item.status === 'prepared').length,
        blockedScenarioCount: entities.blockedScenarios.length,
        nextStageConsumedCount: entities.nextStageConsumedCount,
        browserLocalStorageBusinessStateRequired: false,
        bankMessageCreated: false,
        bankSendTaskCreated: false,
        paymentExecuted: false,
        downstreamObjectWriteCount: 0,
      }
    } else if (CHECKPOINT_ID === 'purchase_canary_normal_pages_visible_ready') {
      const draft = entities.formalObject
      await page.goto(`${ORIGIN}/#/finance/ap-drafts`)
      await expect(page.locator('[data-acceptance-id="purchase-canary-scenario-panel"]'))
        .toContainText('HAPPY_PATH')
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-source"]'))
        .toContainText(draft.sourcePurchaseInvoicePrepareNo)
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-object"]'))
        .toContainText(draft.draftNo)
      await expect(page.getByRole('row', { name: new RegExp(draft.draftNo) })).toHaveCount(1)
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-generation-result"]'))
        .toContainText('committed')
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-generation-result"]'))
        .toContainText('consumed')
      expect(entities.sourceOfTruth).toBe('persistent_server_database_formal_domain_tables')
      expect(entities.formalCounts.purchaseAccountsPayableDrafts).toBe(1)
      expect(entities.formalCounts.purchaseInvoicePrepares).toBe(1)
      expect(entities.formalCounts.purchaseReconciliations).toBe(1)
      expect(entities.evidenceSources).toHaveLength(2)
      expect(new Set(entities.evidenceSources.map(item => item.provider_code)).size).toBe(2)
      expect(Object.values(graph.downstreamObjects).every(count => count === 0)).toBe(true)
      stageVerification = {
        normalPageRestoredFromPersistentServerDatabase: true,
        purchaseAccountsPayableDraftCount: 1,
        purchaseAccountsPayableDraftNo: draft.draftNo,
        idempotencyStatus: draft.idempotencyStatus,
        numberReservationStatus: draft.numberReservationStatus,
        transactionStatus: draft.transactionStatus,
        independentAuthorityEvidenceCount: 2,
        browserLocalStorageBusinessStateRequired: false,
        downstreamObjectWriteCount: 0,
      }
    } else if ([
      'purchase_invoice_prepare_controlled_generation_ready',
      'purchase_invoice_prepare_current_state_consistent_ready',
      'purchase_invoice_prepare_validated_ready',
    ].includes(CHECKPOINT_ID)) {
      const source = entities.sourcePurchaseReconciliation
      const prepare = entities.purchaseInvoicePrepare
      await page.goto(
        `${ORIGIN}/#/finance/purchase-invoice-prepares`
        + `?sourcePurchaseReconciliationId=${source.sourceId}`
        + `&sourcePurchaseReconciliationNo=${encodeURIComponent(source.reconciliationNo)}`
        + `&reconciliationStatus=${source.status}`
        + `&reconciliationVersion=${source.version}`
        + `&checkVersion=${source.checkVersion}`
        + `&differenceCount=0&checkResultCode=PRC_CHECK_MATCHED&canary=${CHECKPOINT_ID === 'purchase_invoice_prepare_validated_ready' ? 'tenant-v44' : 'tenant-v43'}`,
      )
      if (CHECKPOINT_ID === 'purchase_invoice_prepare_validated_ready') {
        await expect(page.locator('[data-acceptance-id="purchase-invoice-data-collection"]')).toContainText('complete')
        await expect(page.locator('[data-acceptance-id="purchase-invoice-validation"]')).toContainText('passed')
        await expect(page.locator('[data-acceptance-id="purchase-invoice-ap-draft-eligibility"]'))
          .toContainText('ready_for_accounts_payable_draft')
        await expect(page.locator('[data-acceptance-id="purchase-invoice-version-idempotency-audit"]'))
          .toContainText('server')
        expect(prepare.status).toBe('prepared')
        expect(prepare.invoiceDataStatus).toBe('complete')
        expect(entities.validation.issueCount).toBe(0)
        expect(entities.accountsPayableDraftEligibility.eligible).toBe(true)
      } else {
        await expect(page.locator('[data-acceptance-id="purchase-invoice-prepare-object"]')).toContainText(prepare.prepareNo)
        await expect(page.locator('[data-acceptance-id="purchase-invoice-prepare-business-gate"]')).toContainText('server')
        await expect(page.locator('[data-acceptance-id="purchase-invoice-prepare-idempotency"]')).toContainText('committed')
        await expect(page.locator('[data-acceptance-id="purchase-invoice-prepare-idempotency"]')).toContainText('consumed')
        expect(prepare.status).toBe('draft')
        expect(prepare.invoiceDataStatus).toBe('not_collected')
      }
      expect(prepare.sourceDocumentType).toBe('purchaseReconciliation')
      expect(entities.invoicePrepareCountAfterRetry).toBe(1)
      expect(graph.sourceRelationCount).toBe(1)
      expect(graph.auditCount).toBe(CHECKPOINT_ID === 'purchase_invoice_prepare_validated_ready' ? 3 : 1)
      expect(Object.values(entities.downstreamCounts).every((count) => count === 0)).toBe(true)
      stageVerification = {
        purchaseInvoicePrepareRestoredFromServer: true,
        invoicePrepareCountAfterRetry: 1,
        sourceRelationCount: 1,
        auditCount: graph.auditCount,
        invoiceDataStatus: prepare.invoiceDataStatus,
        validationStatus: prepare.validationStatus || 'not_validated',
        nextStepReadiness: entities.accountsPayableDraftEligibility?.nextStepReadiness || 'blocked',
        localStorageBusinessWrites: 0,
        downstreamObjectWriteCount: 0,
      }
    } else {
      stageVerification = await verifyPurchaseOrderCheckpoint(page, entities)
      expect(entities.purchaseRequestNo).toBeTruthy()
      expect(entities.inquiryNo).toBeTruthy()
      expect(entities.supplierId).toBeTruthy()
      expect(entities.materialCode).toBeTruthy()
      expect(entities.quantity).toBeGreaterThan(0)
      expect(entities.plannedDeliveryDate).toBeTruthy()
      expect(entities.purchaseOrderStatus).toBe('issued')
      expect(graph.relationCount).toBe(3)
      expect(graph.allRelationsBidirectional).toBe(true)
    }
    expect({ consoleErrors, failedResponses }).toEqual({ consoleErrors: [], failedResponses: [] })

    const verification = await markCheckpointRestored(CHECKPOINT_ID, {
      verificationProcess: 'independent_node_playwright_process',
      processId: process.pid,
      browserContextId: `golden-restore-${CHECKPOINT_ID}-${process.pid}`,
      restoredUrl: page.url(),
      ...stageVerification,
      pageCrash: false,
      userProfileOpened: false,
      userBusinessDataModified: false,
      verifiedEntities: {
        purchaseOrderNo: entities.purchaseOrderNo,
        purchaseReceiveNo: entities.purchaseReceiveNo || '',
        incomingInspectionNo: entities.incomingInspectionNo || '',
        qualifiedInboundNo: entities.qualifiedInboundNo || '',
        payablePrepareNo: entities.payablePrepareNo || '',
        payableCheckNo: entities.payableCheckNo || '',
        supplierSettlementNo: entities.supplierSettlementNo || '',
      },
    })
    const immutableHashesAfter = await checkpointImmutableHashes(CHECKPOINT_ID)
    expect(immutableHashesAfter).toEqual(immutableHashesBefore)
    const reportPath = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'cross-process-restore-report.json')
    await fs.writeFile(reportPath, `${JSON.stringify({
      checkpointId: CHECKPOINT_ID,
      checkpointDirectory: checkpoint.directory,
      integrityHash: checkpoint.actualHash,
      purchaseOrderNo: entities.purchaseOrderNo,
      verification,
      immutableHashesBefore,
      immutableHashesAfter,
      checkpointImmutable: true,
      overall: 'passed',
    }, null, 2)}\n`, 'utf8')
  } finally {
    await context.close()
  }
})

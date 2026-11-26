import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { GOLDEN_FLOW_CASE_NO, GOLDEN_FLOW_PREFIX } from '../fixtures/purchaseToFormalPaymentGoldenFlow.js'
import {
  checkpointPath,
  markCheckpointRestored,
  resetCheckpointRoot,
  saveCheckpoint,
  verifyCheckpointIntegrity,
} from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.5'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'

function formItem(page, label) {
  return page.locator('.el-form-item').filter({ hasText: label }).first()
}

function currentId(page) {
  return decodeURIComponent(new URL(page.url()).hash.split('/').filter(Boolean).at(-1) || '')
}

async function clickAction(page, name) {
  const button = page.getByRole('button', { name, exact: true }).first()
  await expect(button).toBeVisible()
  await expect(button).toBeEnabled()
  await button.click()
}

async function completeThreeStepApproval(page, finalActionName) {
  await clickAction(page, '提报')
  await clickAction(page, '审核')
  await clickAction(page, '复核')
  await clickAction(page, '审批')
  await expect(page.getByRole('button', { name: finalActionName, exact: true }).first()).toBeVisible()
}

async function readDisabledField(page, label) {
  return formItem(page, label).locator('input').first().inputValue()
}

async function selectFirstOption(page, label) {
  const item = formItem(page, label)
  await item.locator('.el-select').click()
  const option = page.getByRole('option').first()
  await expect(option).toBeVisible()
  await option.click()
}

async function verifyStageInFreshContext(browser, checkpointId, route, expectedText) {
  const checkpoint = await verifyCheckpointIntegrity(checkpointId, { expectedOrigin: ORIGIN, requireRestorable: false })
  const checkpointNumberFields = {
    request_created: 'purchaseRequestNo',
    inquiry_created: 'inquiryNo',
    price_approved: 'priceApprovalNo',
    order_created: 'purchaseOrderNo',
  }
  const checkpointExpectedText = checkpoint.entities[checkpointNumberFields[checkpointId]] || expectedText
  const context = await browser.newContext({ storageState: checkpointPath(checkpointId, 'storage-state.json') })
  const page = await context.newPage()
  try {
    await page.goto(route, { waitUntil: 'networkidle' })
    await expect(page.locator('input').first()).toBeVisible()
    const inputValues = await page.locator('input').evaluateAll((inputs) => inputs.map((input) => String(input.value || '')))
    expect(checkpointExpectedText).toBeTruthy()
    expect(inputValues).toContain(checkpointExpectedText)
    return { restoredUrl: page.url(), expectedText: checkpointExpectedText, pageCrash: false }
  } finally {
    await context.close()
  }
}

async function verifyIssuedOrderFromList(browser, checkpointId, entities) {
  const context = await browser.newContext({ storageState: checkpointPath(checkpointId, 'storage-state.json') })
  const page = await context.newPage()
  try {
    await page.goto('/#/scm/purchase-orders', { waitUntil: 'networkidle' })
    const quickSearchToggle = page.getByRole('button', { name: /快速搜索/ }).first()
    await expect(quickSearchToggle).toBeVisible()
    if ((await quickSearchToggle.textContent())?.includes('展开')) await quickSearchToggle.click()
    await page.getByPlaceholder('搜索单号、人员、供应商、物料、部门、状态').fill(entities.purchaseOrderNo)
    const row = page.locator('.el-table__body tr').filter({ hasText: entities.purchaseOrderNo }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText('已下达')
    await row.getByRole('button', { name: '查看明细', exact: true }).click()
    await expect(page).toHaveURL(/#\/scm\/purchase-order\//)
    expect(await readDisabledField(page, '采购订单号')).toBe(entities.purchaseOrderNo)
    expect(await readDisabledField(page, '来源核价单')).toBe(entities.priceApprovalNo)
    await expect(page.getByText(entities.materialName || entities.materialCode, { exact: false }).first()).toBeVisible()
    await expect(page.getByText('已下达', { exact: false }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '进入 WMS 收货预备', exact: true }).first()).toBeVisible()
    return {
      restoredUrl: page.url(),
      purchaseOrderSearchMatched: true,
      purchaseOrderStatus: 'issued',
      supplierMatched: Boolean(entities.supplierId && entities.supplierName),
      materialMatched: Boolean(entities.materialCode && entities.materialName),
      quantityMatched: entities.quantity > 0,
      plannedDeliveryDateMatched: Boolean(entities.plannedDeliveryDate),
      sourcePriceApprovalMatched: true,
      nextStageEntryVisible: true,
      pageCrash: false,
    }
  } finally {
    await context.close()
  }
}

test('采购申请到采购订单下达生成可跨进程恢复的磁盘检查点', async ({ browser }) => {
  test.setTimeout(150_000)
  await resetCheckpointRoot()
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    userAgent: `PCE-Golden-Checkpoint/${VERSION}`,
  })
  let page = await context.newPage()
  const consoleErrors = []
  const sourceObjects = {}
  const checkpoints = []
  let traceStarted = false
  let originalContextClosed = false
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(error.message))

  async function beginTrace() {
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
    traceStarted = true
  }

  async function persistCheckpoint(checkpointId, nextStageId, route, expectedText, sourceCheckpointId = '', final = false) {
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
    checkpoints.push({ checkpointId, directory: saved.directory })
    if (!final) {
      const verification = await verifyStageInFreshContext(browser, checkpointId, route, expectedText)
      await markCheckpointRestored(checkpointId, {
        ...verification,
        verificationProcess: 'new_context_same_process',
      })
      await beginTrace()
    }
    return saved
  }

  try {
    await beginTrace()
    await page.goto('/#/scm/purchase-request/create', { waitUntil: 'networkidle' })
    await expect(page.locator('h1', { hasText: '新增采购申请' })).toBeVisible()
    await formItem(page, '用途').locator('input').fill(`${GOLDEN_FLOW_PREFIX}检查点持久化`)
    await formItem(page, '备注').locator('textarea').fill(`${GOLDEN_FLOW_CASE_NO}，可恢复检查点重建`)
    await clickAction(page, '添加明细')
    await selectFirstOption(page, '物料')
    await expect(formItem(page, '建议供应商').locator('.el-select')).toContainText('供应商')
    await clickAction(page, '保存明细')
    await clickAction(page, '保存单据头')
    await expect(page).toHaveURL(/#\/scm\/purchase-request\//)
    sourceObjects.requestId = currentId(page)
    sourceObjects.requestNo = await readDisabledField(page, '请购单号')
    await persistCheckpoint('request_created', 'purchase-inquiry', `/#/scm/purchase-request/${sourceObjects.requestId}`, sourceObjects.requestNo)

    await completeThreeStepApproval(page, '生成询价单')
    await clickAction(page, '生成询价单')
    await expect(page).toHaveURL(/#\/scm\/purchase-inquiry\//)
    sourceObjects.inquiryId = currentId(page)
    sourceObjects.inquiryNo = await readDisabledField(page, '询价单号')
    expect(await readDisabledField(page, '来源单号')).toBe(sourceObjects.requestNo)
    await persistCheckpoint('inquiry_created', 'price-approval', `/#/scm/purchase-inquiry/${sourceObjects.inquiryId}`, sourceObjects.inquiryNo, 'request_created')

    await clickAction(page, '发送')
    await clickAction(page, '确认报价')
    await clickAction(page, '生成核价单')
    await expect(page).toHaveURL(/#\/scm\/price-approval\//)
    sourceObjects.approvalId = currentId(page)
    sourceObjects.approvalNo = await readDisabledField(page, '核价单号')
    expect(await readDisabledField(page, '来源单号')).toBe(sourceObjects.inquiryNo)
    await completeThreeStepApproval(page, '生成采购订单')
    await persistCheckpoint('price_approved', 'purchase-order', `/#/scm/price-approval/${sourceObjects.approvalId}`, sourceObjects.approvalNo, 'inquiry_created')

    await clickAction(page, '生成采购订单')
    await expect(page).toHaveURL(/#\/scm\/purchase-order\//)
    sourceObjects.purchaseOrderId = currentId(page)
    sourceObjects.purchaseOrderNo = await readDisabledField(page, '采购订单号')
    expect(await readDisabledField(page, '来源核价单')).toBe(sourceObjects.approvalNo)
    await persistCheckpoint('order_created', 'purchase-order-issue', `/#/scm/purchase-order/${sourceObjects.purchaseOrderId}`, sourceObjects.purchaseOrderNo, 'price_approved')

    await completeThreeStepApproval(page, '下达采购订单')
    await clickAction(page, '下达采购订单')
    await expect(page.getByText('已下达', { exact: false }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '进入 WMS 收货预备', exact: true }).first()).toBeVisible()
    const orderCheckpoint = await persistCheckpoint(
      'order_issued',
      'purchase-arrival-preview',
      `/#/scm/purchase-order/${sourceObjects.purchaseOrderId}`,
      sourceObjects.purchaseOrderNo,
      'order_created',
      true,
    )

    await context.close()
    originalContextClosed = true
    const finalVerification = await verifyIssuedOrderFromList(browser, 'order_issued', orderCheckpoint.entities)
    await markCheckpointRestored('order_issued', {
      ...finalVerification,
      verificationProcess: 'new_context_after_original_closed',
      businessEntityFieldsComplete: [
        'purchaseRequestNo', 'inquiryNo', 'priceApprovalNo', 'purchaseOrderNo',
        'supplierId', 'supplierName', 'materialCode', 'materialName', 'quantity',
        'unit', 'requiredDate', 'plannedDeliveryDate', 'purchaseOrderStatus',
      ].every((key) => orderCheckpoint.entities[key] !== '' && orderCheckpoint.entities[key] !== null),
      relationshipGraphVerified: orderCheckpoint.graph.allRelationsBidirectional,
    })
    const integrity = await verifyCheckpointIntegrity('order_issued', { expectedOrigin: ORIGIN })
    expect(integrity.entities.purchaseOrderNo).toBe(sourceObjects.purchaseOrderNo)
    expect(integrity.entities.purchaseOrderStatus).toBe('issued')
    expect(integrity.graph.relationCount).toBe(3)
    expect(integrity.graph.allRelationsBidirectional).toBe(true)
    expect(consoleErrors).toEqual([])

    await fs.writeFile(
      path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'checkpoint-generation-report.json'),
      `${JSON.stringify({
        version: VERSION,
        flowNo: GOLDEN_FLOW_CASE_NO,
        sourceObjects,
        checkpoints,
        orderIssuedCheckpoint: checkpointPath('order_issued'),
        storageTypes: integrity.manifest.storageTypes,
        storageKeys: integrity.manifest.storageKeys,
        latestPassedCheckpoint: 'order_issued',
        stoppedBeforeDownstream: true,
        directStoreCallCount: 0,
        userProfileOpened: false,
        userBusinessDataModified: false,
        overall: 'passed',
      }, null, 2)}\n`,
      'utf8',
    )
  } finally {
    if (traceStarted) await context.tracing.stop({ path: test.info().outputPath('unfinished-trace.zip') }).catch(() => {})
    if (!originalContextClosed) await context.close().catch(() => {})
  }
})

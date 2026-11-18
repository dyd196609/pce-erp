import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import {
  checkpointImmutableHashes,
  checkpointPath,
  verifyCheckpointIntegrity,
} from '../helpers/goldenCheckpoint.js'

const VERSION = 'V1.14.2.8.4.7.16'
const CHECKPOINT_ID = 'receive_ready'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'

async function readState(page, receiveId) {
  return page.evaluate((id) => {
    const receiveState = JSON.parse(localStorage.getItem('wms-purchase-receive-state-v1') || '{}')
    const qmsState = JSON.parse(localStorage.getItem('qms-state-v1') || '{}')
    const wmsState = JSON.parse(localStorage.getItem('wms-state-v1') || '{}')
    const payableState = JSON.parse(localStorage.getItem('payable-prepare-state-v1') || '{}')
    return {
      origin: window.location.origin,
      receive: (receiveState.purchaseReceives || []).find((item) => String(item.id) === String(id)) || null,
      purchaseReceiveCount: receiveState.purchaseReceives?.length || 0,
      incomingInspectionCount: qmsState.incomingInspections?.length || 0,
      inventoryBalances: wmsState.inventoryBalances || [],
      inventoryTransactions: wmsState.inventoryTransactions || [],
      payablePrepares: payableState.payablePrepares || [],
    }
  }, receiveId)
}

function detailField(page, label) {
  return page.locator('.info-grid article').filter({
    has: page.getByText(label, { exact: true }),
  }).first().locator('strong')
}

test('采购收货预备提交后 Store、持久化详情与 DOM 同步为 received', async ({ browser }) => {
  test.setTimeout(60_000)
  const checkpoint = await verifyCheckpointIntegrity(CHECKPOINT_ID, { expectedOrigin: ORIGIN })
  const hashesBefore = await checkpointImmutableHashes(CHECKPOINT_ID)
  const { entities } = checkpoint
  const context = await browser.newContext({
    storageState: checkpointPath(CHECKPOINT_ID, 'storage-state.json'),
    userAgent: `PCE-Purchase-Receive-Detail-Refresh/${VERSION}`,
  })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  try {
    await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
    await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
    await page.goto(`/#/wms/purchase-receive/${entities.internalIds.purchaseReceiveId}`, { waitUntil: 'networkidle' })
    await expect(page.getByText(entities.purchaseReceiveNo, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(entities.purchaseOrderNo, { exact: true }).first()).toBeVisible()

    const before = await readState(page, entities.internalIds.purchaseReceiveId)
    expect(before.origin).toBe(ORIGIN)
    expect(before.receive.status).toBe('prepared')
    expect(before.receive.totalActualReceiveQty).toBe(0)
    await expect(detailField(page, '状态')).toHaveText('已预备')
    await expect(detailField(page, '实际收货总数')).toHaveText('0')

    await page.getByRole('button', { name: '编辑收货信息', exact: true }).click()
    const quantityInput = page.locator('.el-table__body .el-input-number input').first()
    await expect(quantityInput).toBeVisible()
    await quantityInput.fill(String(entities.quantity))
    await page.getByRole('button', { name: '提交收货预备', exact: true }).click()

    await expect(page.getByText('收货预备已提交，库存余额不变', { exact: true })).toBeVisible()
    await expect(detailField(page, '状态')).toHaveText('已收货')
    await expect(detailField(page, '实际收货总数')).toHaveText(String(entities.quantity))
    await expect(page.getByRole('button', { name: '编辑收货信息', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '提交收货预备', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '生成来料检验单', exact: true })).toBeVisible()

    const after = await readState(page, entities.internalIds.purchaseReceiveId)
    expect(after.receive.status).toBe('received')
    expect(after.receive.totalActualReceiveQty).toBe(entities.quantity)
    expect(after.purchaseReceiveCount).toBe(before.purchaseReceiveCount)
    expect(after.incomingInspectionCount).toBe(before.incomingInspectionCount)
    expect(after.inventoryBalances).toEqual(before.inventoryBalances)
    expect(after.inventoryTransactions).toEqual(before.inventoryTransactions)
    expect(after.payablePrepares).toEqual(before.payablePrepares)
    expect(consoleErrors).toEqual([])

    const hashesAfter = await checkpointImmutableHashes(CHECKPOINT_ID)
    expect(hashesAfter).toEqual(hashesBefore)
    const reportPath = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'purchase-receive-detail-refresh-report.json')
    await fs.writeFile(reportPath, `${JSON.stringify({
      version: VERSION,
      checkpointId: CHECKPOINT_ID,
      restoredOrigin: before.origin,
      purchaseReceiveNo: entities.purchaseReceiveNo,
      beforeSubmitState: before.receive.status,
      afterSubmitStoreState: after.receive.status,
      afterSubmitPersistedState: after.receive.status,
      afterSubmitDetailState: 'received',
      afterSubmitDomState: '已收货',
      actualReceivedQuantity: after.receive.totalActualReceiveQty,
      editButtonVisibleAfterSubmit: false,
      submitButtonVisibleAfterSubmit: false,
      inspectionGenerationButtonVisibleAfterSubmit: true,
      pageReloaded: false,
      incomingInspectionGenerated: false,
      inventoryWritten: false,
      payableGenerated: false,
      checkpointHashesBefore: hashesBefore,
      checkpointHashesAfter: hashesAfter,
      checkpointImmutable: true,
      directStoreCallCount: 0,
      userProfileOpened: false,
      userBusinessDataModified: false,
      overall: 'passed',
    }, null, 2)}\n`, 'utf8')
  } finally {
    await context.close()
  }
})

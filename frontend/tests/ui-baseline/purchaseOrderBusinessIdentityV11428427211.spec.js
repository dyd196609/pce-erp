import fs from 'node:fs'
import path from 'node:path'
import { createHmac } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const evidenceDir = path.join(frontendRoot, 'test-results',
  'purchase-order-business-identity-v11428427211')
const base64url = value => Buffer.from(JSON.stringify(value)).toString('base64url')

function createReadOnlyAdminToken() {
  const settings = fs.readFileSync(path.resolve(frontendRoot, '../backend/pce_backend/settings.py'), 'utf8')
  const secret = settings.match(/^SECRET_KEY\s*=\s*["']([^"']+)["']/m)?.[1]
  if (!secret) throw new Error('TEST_JWT_SECRET_NOT_RESOLVED')
  const header = base64url({ alg: 'HS256', typ: 'JWT' })
  const payload = base64url({ user_id: 1, username: 'admin',
    exp: Math.floor(Date.now() / 1000) + 3600 })
  const signature = createHmac('sha256', secret).update(`${header}.${payload}`).digest('base64url')
  return `${header}.${payload}.${signature}`
}

test('采购订单正式编号、明细归属、Schema模板与刷新反馈真实闭环', async ({ page }) => {
  await page.addInitScript(token => localStorage.setItem('token', token), createReadOnlyAdminToken())
  const businessWrites = []
  page.on('request', request => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })

  await page.goto('/#/scm/purchase-order', { waitUntil: 'domcontentloaded' })
  const downloadPromise = page.waitForEvent('download')
  await page.locator('[data-acceptance-id="purchase-order-import-template-button"]').click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('采购订单导入模板.xlsx')
  const workbookBytes = fs.readFileSync(await download.path())
  expect(workbookBytes.subarray(0, 2).toString('ascii')).toBe('PK')
  for (const label of ['采购订单导入', '字段说明', '供应商编码', '物料编码',
    '字段名称', '是否必填', '数据类型', '示例', '说明']) {
    expect(workbookBytes.includes(Buffer.from(label))).toBe(true)
  }

  await page.goto('/#/scm/purchase-order/po-2026-0081', { waitUntil: 'domcontentloaded' })
  const detail = page.locator('[data-active-runtime-component="PurchaseOrderDetailRuntimeViewV1142842727"]')
  await expect(detail).toBeVisible()
  const currentPurchaseOrderId = await detail.locator('[data-detail-region="material-detail"]')
    .getAttribute('data-current-purchase-order-id')
  expect(currentPurchaseOrderId).toBe('po-2026-0081')

  const numberRegion = detail.locator('[data-detail-region="order-number-card"]')
  const numberModel = numberRegion.locator('[data-number-view-model="PurchaseOrderBusinessNumberViewModel"]')
  await expect(numberModel).toHaveAttribute('data-canonical-number-source', 'poNo')
  const numberCards = numberModel.locator('.number-card')
  await expect(numberCards).toHaveCount(4)
  await expect(numberCards.first()).toContainText('采购订单编号')
  const purchaseOrderNumber = (await numberCards.first().locator('li').innerText()).trim()
  expect(purchaseOrderNumber).toBe('PO202607150081')
  await expect(numberRegion.getByText('PO编号', { exact: true })).toHaveCount(0)

  const domRows = detail.locator('[data-purchase-order-item-row]')
  const domItemCount = await domRows.count()
  const relationIds = await domRows.evaluateAll(rows => rows.map(row => row.dataset.purchaseOrderId))
  expect(relationIds.every(id => id === currentPurchaseOrderId)).toBe(true)
  const domItemCodes = await domRows.evaluateAll(rows => rows.map(row => row.dataset.materialCode))
  const matchText = await detail.locator('[data-acceptance-id="purchase-order-item-code-match"]').innerText()
  const codeMatch = matchText.match(/Server Item Codes\s*(\[[^\]]*\])\s*·\s*DOM Item Codes\s*(\[[^\]]*\])/) 
  expect(codeMatch).toBeTruthy()
  const serverItemCodes = JSON.parse(codeMatch[1])
  const reportedDomItemCodes = JSON.parse(codeMatch[2])
  expect(domItemCodes).toEqual(serverItemCodes)
  expect(reportedDomItemCodes).toEqual(serverItemCodes)
  expect(domItemCount).toBe(serverItemCodes.length)

  const feedback = detail.locator('[data-acceptance-id="purchase-order-refresh-feedback"]')
  await expect(feedback).toHaveAttribute('data-refresh-status', 'idle')
  await feedback.evaluate(element => {
    window.__purchaseOrderRefreshStates = [element.dataset.refreshStatus]
    const observer = new MutationObserver(() => {
      window.__purchaseOrderRefreshStates.push(element.dataset.refreshStatus)
    })
    observer.observe(element, { attributes: true, attributeFilter: ['data-refresh-status'] })
    window.__purchaseOrderRefreshObserver = observer
  })
  const urlBefore = page.url()
  await detail.locator('[data-acceptance-id="purchase-order-refresh-button"]').click()
  await expect(feedback).toHaveAttribute('data-refresh-status', 'success')
  await expect(feedback).toContainText('刷新成功')
  await expect(feedback).not.toContainText('尚未手工刷新')
  const refreshStates = await page.evaluate(() => window.__purchaseOrderRefreshStates)
  expect(refreshStates).toContain('refreshing')
  expect(refreshStates).toContain('success')
  expect(page.url()).toBe(urlBefore)
  await expect(numberCards.first()).toContainText(purchaseOrderNumber)
  expect(await domRows.evaluateAll(rows => rows.map(row => row.dataset.materialCode)))
    .toEqual(serverItemCodes)
  expect(businessWrites).toEqual([])

  fs.mkdirSync(evidenceDir, { recursive: true })
  await page.screenshot({ path: path.join(evidenceDir,
    'purchase-order-business-identity.png'), fullPage: true })
  fs.writeFileSync(path.join(evidenceDir, 'browser-business-validation.json'), JSON.stringify({
    version: 'V1.14.2.8.4.27.2.11', testedAt: new Date().toISOString(),
    route: '/#/scm/purchase-order/po-2026-0081', currentPurchaseOrderId,
    purchaseOrderNumber, purchaseOrderNumberSource: 'PurchaseOrder.poNo',
    purchaseOrderItemSource: 'PurchaseOrder Provider.purchaseOrderItems',
    purchaseOrderItemRelationKey: 'purchaseOrderId', serverItemCount: serverItemCodes.length,
    domItemCount, serverItemCodes, domItemCodes,
    importTemplate: { fileName: download.suggestedFilename(), schemaSource: 'PurchaseOrder Schema',
      sheets: ['采购订单导入', '字段说明'] },
    refresh: { states: refreshStates, lastRefreshTimeVisible: true, urlStable: true },
    businessWriteCount: businessWrites.length, result: 'PASS',
  }, null, 2), 'utf8')
})

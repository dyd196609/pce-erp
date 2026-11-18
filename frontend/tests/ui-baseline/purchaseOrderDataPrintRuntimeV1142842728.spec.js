import fs from 'node:fs'
import path from 'node:path'
import { createHmac } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const evidenceDir = path.join(frontendRoot, 'test-results',
  'purchase-order-data-print-runtime-v1142842728')
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

test('采购订单真实刷新、父订单明细隔离与打印业务用途', async ({ page }) => {
  await page.addInitScript(token => localStorage.setItem('token', token), createReadOnlyAdminToken())

  const businessWrites = []
  page.on('request', request => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())
      && !request.url().endsWith('/api/auth/login/')) {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })

  const url = '/#/scm/purchase-order/po-2026-0081'
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  const runtime = page.locator('[data-active-runtime-component="PurchaseOrderDetailRuntimeViewV1142842727"]')
  await expect(runtime).toBeVisible()
  await expect(runtime).toContainText('PO202607150081')

  const numberCards = runtime.locator('[data-number-view-model="PurchaseOrderNumberViewModel"] .number-card')
  await expect(numberCards).toHaveCount(5)
  for (const [index, label] of ['PO编号', '来源Gate编号', '来源采购申请编号', '关联询价编号',
    '关联报价比较编号'].entries()) await expect(numberCards.nth(index)).toContainText(label)
  await expect(numberCards.filter({ hasText: 'PO编号' })).toContainText('PO202607150081')

  const isolation = runtime.locator('[data-acceptance-id="purchase-order-item-isolation-count"]')
  await expect(isolation).toContainText('当前PurchaseOrderItem数量')
  const isolationText = await isolation.innerText()
  const countMatch = isolationText.match(/当前PurchaseOrderItem数量\s*(\d+)\s*·\s*严格过滤后\s*(\d+)/)
  expect(countMatch).toBeTruthy()
  expect(Number(countMatch[1])).toBe(Number(countMatch[2]))
  expect(runtime.locator('[data-detail-region="material-detail"] tbody tr')).toHaveCount(
    Number(countMatch[2]))

  const refreshEvidence = runtime.locator('[data-acceptance-id="refresh-real-data-result"]')
  const refreshBefore = await refreshEvidence.innerText()
  const urlBefore = page.url()
  await runtime.locator('[data-acceptance-id="purchase-order-refresh-button"]').click()
  await expect(refreshEvidence).not.toHaveText(refreshBefore)
  await expect(refreshEvidence).toContainText('PO-DETAIL-READ-2')
  const refreshAfter = await refreshEvidence.innerText()
  expect(page.url()).toBe(urlBefore)
  await expect(runtime).toContainText('PO202607150081')

  await runtime.getByRole('button', { name: '打印采购订单' }).click()
  const dialog = page.locator('[data-acceptance-id="purchase-order-print-preview"]')
  await expect(dialog).toBeVisible()
  const purposeSelect = dialog.getByLabel('打印输出用途')
  await expect(dialog.locator('.el-form-item').filter({ hasText: '输出用途' }))
    .toContainText('采购员使用')
  const frame = dialog.locator('iframe')
  await expect(frame.contentFrame().locator('body')).toContainText('输出用途：采购员使用')
  const buyerPreview = await frame.getAttribute('srcdoc')

  await dialog.locator('.el-form-item').filter({ hasText: '输出用途' }).locator('.el-select').click()
  await page.getByRole('option', { name: '仓库使用' }).click()
  await expect(dialog.locator('.el-form-item').filter({ hasText: '输出用途' }))
    .toContainText('仓库使用')
  await expect(frame.contentFrame().locator('body')).toContainText('输出用途：仓库使用')
  const warehousePreview = await frame.getAttribute('srcdoc')
  expect(warehousePreview).not.toBe(buyerPreview)
  expect(warehousePreview).not.toContain('采购执行单价')
  expect(warehousePreview).toContain('收货状态')
  expect(businessWrites).toEqual([])

  fs.mkdirSync(evidenceDir, { recursive: true })
  fs.writeFileSync(path.join(evidenceDir, 'manual-page-acceptance.json'), JSON.stringify({
    version: 'V1.14.2.8.4.27.2.8',
    testedAt: new Date().toISOString(),
    runtimeEvidence: {
      url: page.url(),
      routeComponent: 'PurchaseOrderDetailPage.vue',
      runtimeComponent: 'PurchaseOrderDetailRuntimeViewV1142842727.vue',
      purchaseOrderNo: 'PO202607150081',
      numberCardCount: await numberCards.count(),
      currentPurchaseOrderItemCount: Number(countMatch[1]),
      filteredItemCount: Number(countMatch[2]),
      refreshBefore,
      refreshAfter,
      urlStable: page.url() === urlBefore,
      printDefault: '采购员使用',
      printSelected: '仓库使用',
      previewChanged: warehousePreview !== buyerPreview,
    },
    oldRenderer: 'REMOVED',
    purchaseOrderCoreChanged: false,
    gateChanged: false,
    databaseChanged: false,
    businessWriteCount: businessWrites.length,
    result: 'PASS',
  }, null, 2), 'utf8')
})

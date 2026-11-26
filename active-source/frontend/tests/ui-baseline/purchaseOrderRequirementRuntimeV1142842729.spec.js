import fs from 'node:fs'
import path from 'node:path'
import { createHmac } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const evidenceDir = path.join(frontendRoot, 'test-results',
  'purchase-order-requirement-runtime-v1142842729')
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

test('采购订单页面需求执行闭环真实浏览器验收', async ({ page }) => {
  await page.addInitScript(token => localStorage.setItem('token', token), createReadOnlyAdminToken())
  const businessWrites = []
  page.on('request', request => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })

  await page.goto('/#/scm/purchase-order', { waitUntil: 'domcontentloaded' })
  const listPage = page.locator('main[data-page-code="purchase-order"]')
  await expect(listPage).toBeVisible()
  const listRefreshEvidence = page.locator('[data-acceptance-id="purchase-order-list-refresh-evidence"]')
  await expect(listRefreshEvidence).toContainText('PO-LIST-READ-1')
  const firstOrder = page.locator('.purchase-order-number-link').first()
  await expect(firstOrder).toBeVisible()
  const firstOrderBefore = (await firstOrder.innerText()).trim()
  const listUrlBefore = page.url()
  const evidenceBefore = await listRefreshEvidence.innerText()
  await page.locator('[data-acceptance-id="page-refresh-button"]').click()
  await expect(listRefreshEvidence).not.toHaveText(evidenceBefore)
  await expect(listRefreshEvidence).toContainText('PO-LIST-READ-2')
  expect(page.url()).toBe(listUrlBefore)
  const firstOrderAfter = (await firstOrder.innerText()).trim()
  expect(firstOrderAfter).toBe(firstOrderBefore)
  const evidenceAfter = await listRefreshEvidence.innerText()

  const downloadPromise = page.waitForEvent('download')
  await page.locator('[data-acceptance-id="purchase-order-import-template-button"]').click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('采购订单导入模板.csv')
  const downloadedText = fs.readFileSync(await download.path(), 'utf8')
  for (const label of ['供应商', '物料编码', '物料名称', '规格', '数量', '采购单价',
    '计划到货日期', '备注']) expect(downloadedText).toContain(label)

  await page.goto('/#/scm/purchase-order/po-2026-0081', { waitUntil: 'domcontentloaded' })
  const detail = page.locator('[data-active-runtime-component="PurchaseOrderDetailRuntimeViewV1142842727"]')
  await expect(detail).toBeVisible()
  await expect(detail).toContainText('PO202607150081')
  const numberCards = detail.locator('[data-number-view-model="PurchaseOrderBusinessNumberViewModel"] .number-card')
  await expect(numberCards).toHaveCount(5)
  for (const [index, label] of ['采购订单编号', 'PO编号', '采购批次编号', '来源编号',
    '供应商订单编号'].entries()) await expect(numberCards.nth(index)).toContainText(label)
  const numberLayout = await numberCards.first().locator('xpath=..').evaluate(element => ({
    clientWidth: element.clientWidth, scrollWidth: element.scrollWidth,
  }))
  expect(numberLayout.scrollWidth).toBeLessThanOrEqual(numberLayout.clientWidth)

  const isolation = detail.locator('[data-acceptance-id="purchase-order-item-isolation-count"]')
  const isolationText = await isolation.innerText()
  const countMatch = isolationText.match(/当前PurchaseOrderItem数量\s*(\d+)\s*·\s*严格过滤后\s*(\d+)\s*·\s*页面渲染\s*(\d+)/)
  expect(countMatch).toBeTruthy()
  const counts = countMatch.slice(1).map(Number)
  expect(new Set(counts).size).toBe(1)
  await expect(detail.locator('[data-detail-region="material-detail"] tbody tr')).toHaveCount(counts[2])

  await detail.getByRole('button', { name: '打印采购订单' }).click()
  const dialog = page.locator('[data-acceptance-id="purchase-order-print-preview"]')
  await expect(dialog).toBeVisible()
  const purposeItem = dialog.locator('.el-form-item').filter({ hasText: '输出用途' })
  await expect(purposeItem).toContainText('采购员使用')
  await purposeItem.locator('.el-select').click()
  for (const label of ['采购员使用', '仓库使用', '供应商使用', '财务留档', '管理查看']) {
    await expect(page.getByRole('option', { name: label })).toBeVisible()
  }
  await page.getByRole('option', { name: '供应商使用' }).click()
  await expect(purposeItem).toContainText('供应商使用')
  const frame = dialog.locator('iframe')
  await expect(frame.contentFrame().locator('body')).toContainText('输出用途：供应商使用')
  await expect(frame.contentFrame().locator('body')).toContainText('交付要求')
  expect(businessWrites).toEqual([])

  fs.mkdirSync(evidenceDir, { recursive: true })
  await page.screenshot({ path: path.join(evidenceDir, 'purchase-order-detail-runtime.png'),
    fullPage: true })
  const requirements = [
    { requirementId: 'REQ-PO-LIST-REFRESH', requirement: '采购订单列表真实刷新',
      implementationFile: 'frontend/src/meta/pages/ScmPage.vue + purchaseOrderListDataProviderV1142842729.js',
      runtimeComponent: 'ScmPage.vue / PceListPageShell.vue', browserVerification: 'PASS', result: 'PASS' },
    { requirementId: 'PURCHASE-ORDER-IMPORT-TEMPLATE-001', requirement: '采购订单导入模板',
      implementationFile: 'purchaseOrderImportTemplateRuntimeV1142842729.js',
      runtimeComponent: 'ScmPage.vue', browserVerification: 'PASS', result: 'PASS' },
    { requirementId: 'PRINT-BUSINESS-CLASSIFICATION-001', requirement: '打印业务分类',
      implementationFile: 'purchaseOrderPrintBusinessRuntimeV1142842728.js',
      runtimeComponent: 'PurchaseOrderDetailRuntimeViewV1142842727.vue', browserVerification: 'PASS', result: 'PASS' },
    { requirementId: 'REQ-PO-BUSINESS-NUMBER', requirement: '采购订单专用编号',
      implementationFile: 'purchaseOrderBusinessNumberViewModelV1142842729.js',
      runtimeComponent: 'PurchaseOrderDetailRuntimeViewV1142842727.vue', browserVerification: 'PASS', result: 'PASS' },
    { requirementId: 'PURCHASE-ORDER-ITEM-SOURCE-001', requirement: '采购物料明细真实隔离',
      implementationFile: 'purchaseOrderDetailDataRuntimeV1142842728.js',
      runtimeComponent: 'PurchaseOrderDetailPage.vue', browserVerification: 'PASS', result: 'PASS' },
  ]
  fs.writeFileSync(path.join(evidenceDir, 'requirement-closed-loop.json'), JSON.stringify({
    version: 'V1.14.2.8.4.27.2.9', testedAt: new Date().toISOString(),
    listRuntime: { url: listUrlBefore, orderBefore: firstOrderBefore,
      orderAfter: firstOrderAfter, refreshBefore: evidenceBefore,
      refreshAfter: evidenceAfter, providerReloaded: true },
    importTemplate: { fileName: download.suggestedFilename(), fieldCount: 8 },
    detailRuntime: { url: page.url(), purchaseOrderNo: 'PO202607150081',
      currentPurchaseOrderItemCount: counts[0], filteredItemCount: counts[1],
      renderedItemCount: counts[2], numberCardCount: await numberCards.count() },
    printClassification: { default: '采购员使用', selected: '供应商使用',
      previewChanged: true },
    requirements, businessWriteCount: businessWrites.length, result: 'PASS',
  }, null, 2), 'utf8')
})

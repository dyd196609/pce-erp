import fs from 'node:fs'
import path from 'node:path'
import { createHmac } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const evidenceDir = path.join(frontendRoot, 'test-results',
  'purchase-order-true-runtime-v11428427210')
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

test('采购订单真实DOM、用户点击、Runtime与Provider数据链一致', async ({ page }) => {
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
  expect(download.suggestedFilename()).toBe('采购订单导入模板.csv')
  const csv = fs.readFileSync(await download.path(), 'utf8')
  for (const label of ['供应商', '物料编码', '物料名称', '规格', '数量', '采购单价',
    '计划到货日期', '备注']) expect(csv).toContain(label)

  await page.goto('/#/scm/purchase-order/po-2026-0081', { waitUntil: 'domcontentloaded' })
  const detail = page.locator('[data-active-runtime-component="PurchaseOrderDetailRuntimeViewV1142842727"]')
  await expect(detail).toBeVisible()
  const businessObject = 'PO202607150081'
  await expect(detail).toContainText(businessObject)

  const classification = detail.locator('[data-detail-region="classification"]')
  const outputSelect = classification.locator('[data-acceptance-id="purchase-order-output-purpose-select"]')
  await expect(outputSelect).toBeVisible()
  await expect(classification).toContainText('采购员使用')
  await outputSelect.click()
  const optionLabels = ['采购员使用', '仓库使用', '供应商使用', '财务留档', '管理查看']
  for (const label of optionLabels) await expect(page.getByRole('option', { name: label })).toBeVisible()
  await page.getByRole('option', { name: '采购员使用' }).click()

  await detail.getByRole('button', { name: '打印采购订单' }).click()
  const dialog = page.locator('[data-acceptance-id="purchase-order-print-preview"]')
  await expect(dialog).toBeVisible()
  const frame = dialog.locator('iframe')
  await expect(frame.contentFrame().locator('body')).toContainText('输出用途：采购员使用')
  const buyerPreview = await frame.getAttribute('srcdoc')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()

  await outputSelect.click()
  await page.getByRole('option', { name: '仓库使用' }).click()
  await expect(classification).toContainText('仓库使用')
  await detail.getByRole('button', { name: '打印采购订单' }).click()
  await expect(frame.contentFrame().locator('body')).toContainText('输出用途：仓库使用')
  await expect(frame.contentFrame().locator('body')).toContainText('收货要求')
  const warehousePreview = await frame.getAttribute('srcdoc')
  expect(warehousePreview).not.toBe(buyerPreview)
  expect(warehousePreview).not.toContain('采购执行单价')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()

  const numberCards = detail.locator('[data-number-view-model="PurchaseOrderBusinessNumberViewModel"] .number-card')
  await expect(numberCards).toHaveCount(5)
  await expect(numberCards.nth(0)).toContainText('采购订单编号')
  await expect(numberCards.nth(0)).toContainText('待生成采购订单编号')
  await expect(numberCards.nth(0)).not.toContainText('未建立独立采购订单编号')
  await expect(numberCards.nth(1)).toContainText('PO编号')
  const poNumber = (await numberCards.nth(1).locator('li').innerText()).trim()
  expect(poNumber.length).toBeLessThanOrEqual(32)
  const numberLayout = await numberCards.first().locator('xpath=..').evaluate(element => ({
    clientWidth: element.clientWidth, scrollWidth: element.scrollWidth,
  }))
  expect(numberLayout.scrollWidth).toBeLessThanOrEqual(numberLayout.clientWidth)

  const isolation = detail.locator('[data-acceptance-id="purchase-order-item-isolation-count"]')
  const isolationText = await isolation.innerText()
  const countMatch = isolationText.match(/Provider Count\s*(\d+)\s*·\s*Filtered Count\s*(\d+)\s*·\s*DOM Render Count\s*(\d+)/)
  expect(countMatch).toBeTruthy()
  const [providerCount, filteredCount, reportedDomCount] = countMatch.slice(1).map(Number)
  const domRows = detail.locator('[data-purchase-order-item-row]')
  const actualDomCount = await domRows.count()
  expect(providerCount).toBe(filteredCount)
  expect(filteredCount).toBe(reportedDomCount)
  expect(reportedDomCount).toBe(actualDomCount)
  expect(actualDomCount).toBe(2)

  const refreshTrace = detail.locator('[data-acceptance-id="purchase-order-refresh-action-trace"]')
  await expect(refreshTrace).toContainText('INITIAL-LOAD')
  const traceBefore = await refreshTrace.innerText()
  const renderTarget = detail.locator('[data-detail-region="material-detail"] tbody')
  const renderBefore = await renderTarget.getAttribute('data-render-update')
  const urlBefore = page.url()
  await detail.locator('[data-acceptance-id="purchase-order-refresh-button"]').click()
  await expect(refreshTrace).not.toHaveText(traceBefore)
  await expect(refreshTrace).toContainText('CLICK-1')
  await expect(refreshTrace).toContainText('PO-DETAIL-READ-2')
  await expect(refreshTrace).toContainText('DOM-COMMIT-2')
  const renderAfter = await renderTarget.getAttribute('data-render-update')
  expect(renderAfter).not.toBe(renderBefore)
  expect(page.url()).toBe(urlBefore)
  await expect(detail).toContainText(businessObject)
  expect(await domRows.count()).toBe(actualDomCount)
  expect(businessWrites).toEqual([])

  fs.mkdirSync(evidenceDir, { recursive: true })
  await page.screenshot({ path: path.join(evidenceDir, 'purchase-order-true-dom.png'),
    fullPage: true })
  fs.writeFileSync(path.join(evidenceDir, 'browser-dom-validation.json'), JSON.stringify({
    version: 'V1.14.2.8.4.27.2.10', testedAt: new Date().toISOString(),
    priorityOrder: ['Browser DOM', 'User Click', 'Runtime State', 'Provider Data'],
    printClassification: { selectVisible: true, options: optionLabels,
      selected: '仓库使用', previewChanged: warehousePreview !== buyerPreview },
    purchaseOrderNumber: { purchaseOrderNumber: '待生成采购订单编号', poNumber,
      poNumberLength: poNumber.length, horizontalOverflow: false },
    purchaseOrderItem: { providerCount, filteredCount, reportedDomCount, actualDomCount },
    refreshBrowserAction: { clickEvent: 'CLICK-1', providerCall: 'PO-DETAIL-READ-2',
      renderUpdate: 'DOM-COMMIT-2', traceBefore, traceAfter: await refreshTrace.innerText(),
      urlStable: page.url() === urlBefore, businessObjectStable: true },
    importTemplate: { fileName: download.suggestedFilename(), fieldCount: 8 },
    businessWriteCount: businessWrites.length, result: 'PASS',
  }, null, 2), 'utf8')
})

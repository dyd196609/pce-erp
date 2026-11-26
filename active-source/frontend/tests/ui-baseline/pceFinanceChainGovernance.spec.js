import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.50.2'
const ROOT = path.resolve('test-results', 'pce-web-acceptance-v1-1')
const pages = [
  ['payable-prepare', '采购应付预备', '/finance/payable-prepares'],
  ['payable-check', '采购应付核对', '/finance/payable-checks'],
  ['supplier-settlement', '供应商结算', '/scm/supplier-settlements'],
  ['purchase-reconciliation', '采购对账', '/scm/purchase-reconciliations'],
  ['invoice-prepare', '采购发票准备', '/finance/purchase-invoice-prepares'],
  ['account-payable-draft', '采购应付账款草稿', '/finance/ap-drafts'],
  ['account-payable-confirm', '应付确认准备', '/finance/account-payable-confirms'],
  ['payment-application', '付款申请准备', '/finance/payment-applications'],
  ['payment-request', '付款申请', '/finance/payment-requests'],
  ['payment-instruction-prepare', '付款指令准备', '/finance/payment-order-prepares'],
  ['payment-order-prepare', '正式付款单预备', '/finance/payment-prepares'],
]

test('eleven-page finance chain actions, diagnostics and reload are read-only', async ({ page, context }) => {
  fs.mkdirSync(path.join(ROOT, 'finance-chain-screenshots'), { recursive: true })
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://localhost:5173' })
  const writes = []
  page.on('request', request => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      writes.push({ method: request.method(), url: request.url() })
    }
  })
  const results = []
  for (const [pageCode, canonicalName, route] of pages) {
    const fullUrl = `http://localhost:5173/#${route}`
    await page.goto(fullUrl, { waitUntil: 'domcontentloaded' })
    const title = page.locator('[data-acceptance-id="page-business-title"]')
    await expect(title).toContainText(canonicalName)
    await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]')).toHaveCount(1)
    await expect(page.locator('[data-acceptance-id="page-observability-action-bar"]')).toBeVisible()
    const refresh = page.locator('[data-acceptance-id="page-refresh-button"]')
    const diagnostics = page.locator('[data-acceptance-id="copy-diagnostic-data-button"]').first()
    const returnButton = page.locator('[data-acceptance-id="return-process-center-button"]')
    await expect(refresh).toBeEnabled({ timeout: 15_000 })
    await expect(diagnostics).toBeEnabled({ timeout: 15_000 })
    await expect(returnButton).toBeVisible()
    const toolbarCount = await page.locator('[data-acceptance-id="standard-list-toolbar"]').count()
    expect(toolbarCount).toBeGreaterThan(0)
    const filterToggleCount = await page.locator('[data-acceptance-id="list-advanced-filter-toggle"]').count()
    expect(filterToggleCount).toBeGreaterThan(0)
    await diagnostics.click()
    const clipboardText = await page.evaluate(() => navigator.clipboard.readText())
    expect(clipboardText).toContain(route)
    await refresh.click()
    await expect(title).toContainText(canonicalName)
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(title).toContainText(canonicalName)
    await page.screenshot({
      path: path.join(ROOT, 'finance-chain-screenshots', `${pageCode}-page-full.png`),
      fullPage: true,
    })
    results.push({
      pageCode,
      canonicalName,
      fullUrl,
      pageExists: true,
      structureReady: true,
      standardToolbarCount: toolbarCount,
      advancedFilterToggleCount: filterToggleCount,
      diagnosticsCopied: true,
      diagnosticClipboardLength: clipboardText.length,
      refreshPassed: true,
      reloadPassed: true,
      businessWriteRequestCount: 0,
    })
  }
  expect(writes, `finance-chain browser gate issued writes: ${JSON.stringify(writes)}`).toEqual([])
  fs.writeFileSync(path.join(ROOT, 'finance-chain-browser-report.json'), `${JSON.stringify({
    result: 'passed',
    version: VERSION,
    financeChainPageCount: pages.length,
    financeChainPassedCount: results.length,
    financeChainBlockerCount: 0,
    businessWriteRequestCount: 0,
    results,
  }, null, 2)}\n`)
})

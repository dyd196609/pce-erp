import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const baseUrl = 'http://localhost:5173'
const evidenceDir = resolve('test-results/V1.14.2.8.4.27.2.46-Batch2-remediation')
mkdirSync(evidenceDir, { recursive: true })

const expected = Object.freeze({
  purchaseOrderId: '224', purchaseOrderNo: 'PO202608140001',
  purchaseRequestNo: 'PR202608040011', purchaseRequestItemId: '51',
  supplierCode: 'SUP001', supplierName: '华为技术有限公司',
  materialCode: 'MT005', materialName: '有线键盘',
  linkedPriceNo: 'SMP-PAP-REAL-SQ-202608040011-L1',
  linkedResultNo: 'PAR-PAP-REAL-SQ-202608040011-L1', linkedPrice: '132.0000',
  overlapPriceNo: 'SMP-PAP-QC-PI-202608040009-MT005',
  overlapResultNo: 'PAR-PAP-QC-PI-202608040009-MT005', overlapPrice: '120.0000',
  taxRate: '13', currency: 'CNY', effectiveDate: '2026-08-13',
})
const mustContain = (text, values, scope) => {
  const missing = values.filter(value => !text.includes(String(value)))
  if (missing.length) throw new Error(`${scope}_MISSING:${missing.join(',')}`)
}

const browser = await chromium.launch({ headless: true,
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' })
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
const page = await context.newPage()
const consoleErrors = []
page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('pageerror', error => consoleErrors.push(error.message))

try {
  await page.goto(`${baseUrl}/#/login`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  if (await page.locator('input[autocomplete="username"]').count()) {
    await page.locator('input[autocomplete="username"]').fill('admin')
    await page.locator('input[autocomplete="current-password"]').fill('admin123')
    await page.getByRole('button', { name: /Enter|登录|进入/ }).click()
    await page.waitForTimeout(1200)
  }

  await page.goto(`${baseUrl}/#/scm/purchase-order/${expected.purchaseOrderId}`,
    { waitUntil: 'networkidle' })
  await page.getByText(expected.purchaseOrderNo, { exact: true }).first().waitFor({ timeout: 15000 })
  const orderText = await page.locator('main').innerText()
  mustContain(orderText, [expected.purchaseOrderNo, expected.purchaseRequestNo,
    expected.purchaseRequestItemId, expected.supplierName, expected.materialCode,
    expected.materialName, expected.linkedPriceNo, expected.linkedResultNo,
    '132.00', '13.00', expected.currency, expected.effectiveDate, '标准采购'], 'PO224')
  await page.screenshot({ path: resolve(evidenceDir, '02-po224-same-object-trace.png'), fullPage: true })

  await page.goto(`${baseUrl}/#/foundation/erp/supplier-material-prices`,
    { waitUntil: 'networkidle' })
  const pageSize = page.getByLabel('每页数量')
  if (await pageSize.count()) await pageSize.selectOption('100')
  const priceSearch = page.getByPlaceholder('输入编号、来源单号、供应商或关键字')
  await priceSearch.fill(expected.linkedPriceNo)
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await page.getByText(expected.linkedPriceNo, { exact: true }).first().waitFor({ timeout: 15000 })
  const linkedRow = await page.locator('tbody tr').filter({ hasText: expected.linkedResultNo }).first().innerText()
  await priceSearch.fill(expected.overlapPriceNo)
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await page.getByText(expected.overlapPriceNo, { exact: true }).first().waitFor({ timeout: 15000 })
  const overlapRow = await page.locator('tbody tr').filter({ hasText: expected.overlapResultNo }).first().innerText()
  const priceRows = [linkedRow, overlapRow]
  const priceText = priceRows.join('\n')
  mustContain(priceText, [expected.supplierCode, expected.supplierName, expected.materialCode,
    expected.materialName, expected.linkedPriceNo, expected.linkedResultNo, expected.linkedPrice,
    expected.overlapPriceNo, expected.overlapResultNo, expected.overlapPrice,
    'OVERLAPPING_EFFECTIVE_PRICE', 'CONTEXT_SELECTION_REQUIRED',
    expected.taxRate, expected.currency, expected.effectiveDate], 'MT005_PRICES')
  await page.screenshot({ path: resolve(evidenceDir, '01-mt005-overlapping-prices.png'), fullPage: true })

  await page.goto(`${baseUrl}/#/scm/purchase-order-gate`, { waitUntil: 'networkidle' })
  await page.getByText(/EXPLICIT_DECISION_BATCH_REQUIRED/).waitFor({ timeout: 15000 })
  const noContextText = await page.locator('body').innerText()
  mustContain(noContextText, ['EXPLICIT_DECISION_BATCH_REQUIRED'], 'NO_IMPLICIT_GATE')
  const creationEnabled = await page.getByRole('button', { name: '人工进入采购订单创建' }).isEnabled()
  if (creationEnabled) throw new Error('NO_IMPLICIT_GATE_CREATION_MUST_BE_DISABLED')

  console.log(JSON.stringify({ result: 'PASS', expected, priceRowCount: priceRows.length,
    noImplicitGate: true, businessWriteCount: 0, consoleErrorCount: consoleErrors.length,
    consoleErrors }, null, 2))
} finally {
  await context.close()
  await browser.close()
}

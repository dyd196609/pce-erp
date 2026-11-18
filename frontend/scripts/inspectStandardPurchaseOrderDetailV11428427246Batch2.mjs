import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const orderId = process.argv[2] || '224'
const evidenceDir = resolve('test-results/V1.14.2.8.4.27.2.46-Batch2')
mkdirSync(evidenceDir, { recursive: true })
const browser = await chromium.launch({ headless: true,
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
const errors = []
const failedResponses = []
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
page.on('pageerror', error => errors.push(error.message))
page.on('response', response => { if (response.status() >= 400) failedResponses.push({
  status: response.status(), url: response.url(),
}) })
try {
  await page.goto('http://localhost:5173/#/login', { waitUntil: 'networkidle' })
  await page.locator('input[autocomplete="username"]').fill('admin')
  await page.locator('input[autocomplete="current-password"]').fill('admin123')
  await page.getByRole('button', { name: /Enter|登录|进入/ }).click()
  await page.waitForTimeout(1000)
  await page.goto('http://localhost:5173/#/scm/purchase-order', { waitUntil: 'networkidle' })
  await page.locator('td:visible', { hasText: 'PO202608140001' }).first().waitFor({ timeout: 15000 })
  await page.screenshot({ path: resolve(evidenceDir, '04-standard-order-list.png'), fullPage: true })
  await page.goto(`http://localhost:5173/#/scm/purchase-order/${orderId}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1800)
  await page.screenshot({ path: resolve(evidenceDir, '05-standard-order-detail.png'), fullPage: true })
  const body = await page.locator('body').innerText()
  console.log(JSON.stringify({ result: /PO202608140001/.test(body) ? 'PASS' : 'FAIL',
    url: page.url(), consoleErrorCount: errors.length, consoleErrors: errors, failedResponses,
    body: body.slice(0, 9000) }, null, 2))
} finally { await browser.close() }

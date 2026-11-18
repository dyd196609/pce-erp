import { test, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import path from 'node:path'

const evidenceDir = path.resolve('test-results/page-evidence-engine-v11428421/browser-evidence')
const databasePath = path.resolve('../backend/db.sqlite3')
const fileHash = async file => createHash('sha256').update(await readFile(file)).digest('hex')
const isBusinessWrite = request => ['POST','PUT','PATCH','DELETE'].includes(request.method()) && !request.url().endsWith('/api/auth/login/')

async function authenticate(page) {
  const response = await page.request.post('/api/auth/login/', { data: { username: 'admin', password: 'admin123' } })
  expect(response.status()).toBe(200)
  const payload = await response.json()
  await page.addInitScript(token => localStorage.setItem('token', token), payload.token)
}

async function collectMode(page, relativeUrl, expectedMode, expectedBusinessNo, screenshotName) {
  const requests = []
  const responses = []
  const writes = []
  const requestHandler = request => {
    requests.push({ method: request.method(), url: request.url() })
    if (isBusinessWrite(request)) writes.push(`${request.method()} ${request.url()}`)
  }
  page.on('request', requestHandler)
  const responseHandler = response => responses.push({ status: response.status(), url: response.url() })
  page.on('response', responseHandler)
  const startedAt = Date.now()
  await page.goto(relativeUrl, { waitUntil: 'domcontentloaded' })
  const root = page.locator('[data-acceptance-id="purchase-request-business-page"]')
  await expect(root).toHaveAttribute('data-page-code', 'purchase-request')
  await expect(page.locator('[data-acceptance-id="scm-business-data-mode"]')).toHaveText(expectedMode)
  const table = page.locator('[data-acceptance-id="purchase-request-table"]')
  await expect(table).toBeVisible()
  if (expectedBusinessNo) await expect(table).toContainText(expectedBusinessNo)
  else await expect.poll(() => table.locator('.el-table__body tbody tr').count()).toBeGreaterThan(0)
  const beforeRefresh = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.locator('[data-acceptance-id="scm-business-data-mode"]')).toHaveText(expectedMode)
  if (expectedBusinessNo) await expect(page.locator('[data-acceptance-id="purchase-request-table"]')).toContainText(expectedBusinessNo)
  await expect.poll(() => page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__?.dataMode || '')).toBe(expectedMode)
  const afterRefresh = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  const dom = {
    visibleRegions: await page.locator('[data-acceptance-id="page-identity-region"], [data-acceptance-id="business-process-navigation"], [data-acceptance-id="purchase-request-list-region"], [data-acceptance-id="purchase-request-business-boundary"]').evaluateAll(nodes => nodes.filter(node => { const style = getComputedStyle(node); return style.display !== 'none' && style.visibility !== 'hidden' }).map(node => node.getAttribute('data-acceptance-id'))),
    keyTexts: await page.locator('h1, h2').evaluateAll(nodes => nodes.map(node => node.textContent?.trim()).filter(Boolean)),
    navigationText: await page.locator('[data-acceptance-id="business-process-navigation"]').textContent(),
  }
  const screenshotPath = path.join(evidenceDir, screenshotName)
  await page.screenshot({ path: screenshotPath, fullPage: true })
  const performance = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0]
    return {
      routeLoadTime: Math.round(nav?.responseStart || 0),
      schemaLoadTime: Math.round(nav?.domInteractive || 0),
      apiTime: Math.round((nav?.responseEnd || 0) - (nav?.requestStart || 0)),
      renderTime: Math.round((nav?.domComplete || performance.now()) - (nav?.responseEnd || 0)),
      totalTime: Math.round(nav?.duration || performance.now()),
    }
  })
  page.off('request', requestHandler)
  page.off('response', responseHandler)
  return {
    url: page.url(),
    expectedMode,
    expectedBusinessNo,
    pageOpened: true,
    refreshPreserved: beforeRefresh?.dataMode === afterRefresh?.dataMode,
    diagnostics: afterRefresh,
    requests,
    responses,
    businessWrites: writes,
    screenshot: screenshotPath,
    elapsedMs: Date.now() - startedAt,
    performance,
    dom,
  }
}

test('采购申请正式与金丝雀双模式只读证据采集', async ({ browser }) => {
  await mkdir(evidenceDir, { recursive: true })
  const context = await browser.newContext({ baseURL: 'http://localhost:5173', viewport: { width: 1600, height: 1000 } })
  const page = await context.newPage()
  await authenticate(page)
  const databaseHashBefore = await fileHash(databasePath)
  const production = await collectMode(page, '/#/scm/purchase-request', 'production', '', 'purchase-request-production.png')
  const canary = await collectMode(page, '/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=HAPPY_PATH', 'canary_acceptance', 'PRQ-CAN-001', 'purchase-request-canary.png')
  const productionCalls = production.requests.filter(item => item.url.includes('/api/procurement/scm-page-facts/purchase-request/')).length
  const productionCanaryCalls = production.requests.filter(item => item.url.includes('/api/pce/purchase-canary/context')).length
  const canaryProductionCalls = canary.requests.filter(item => item.url.includes('/api/procurement/scm-page-facts/purchase-request/')).length
  const canaryCalls = canary.requests.filter(item => item.url.includes('/api/pce/purchase-canary/context')).length
  expect(productionCalls).toBeGreaterThan(0)
  expect(productionCanaryCalls).toBe(0)
  expect(canaryProductionCalls).toBe(0)
  expect(canaryCalls).toBeGreaterThan(0)
  expect([...production.businessWrites, ...canary.businessWrites]).toHaveLength(0)
  for (const captured of [production, canary]) {
    expect(captured.diagnostics.pageCode).toBe('purchase-request')
    expect(captured.diagnostics.factSource).toBe('server')
    expect(captured.diagnostics.apiFacts).toBeTruthy()
    expect(captured.diagnostics.pageFacts).toBeTruthy()
    expect(captured.diagnostics.strictFacts).toBeTruthy()
    expect(captured.dom.visibleRegions).toContain('purchase-request-list-region')
    expect(captured.dom.visibleRegions).toContain('business-process-navigation')
    expect(Object.values(captured.performance).every(Number.isFinite)).toBeTruthy()
  }
  const databaseHashAfter = await fileHash(databasePath)
  expect(databaseHashAfter).toBe(databaseHashBefore)
  await writeFile(path.resolve('test-results/page-evidence-engine-v11428421/browser-evidence.json'), JSON.stringify({
    version: 'V1.14.2.8.4.21',
    collectedAt: new Date().toISOString(),
    production: { ...production, productionApiCallCount: productionCalls, canaryApiCallCount: productionCanaryCalls },
    canary: { ...canary, productionApiCallCount: canaryProductionCalls, canaryApiCallCount: canaryCalls },
    businessWriteCount: 0,
    productionUserDataWritten: false,
    databaseProtection: { databasePath, beforeHash: databaseHashBefore, afterHash: databaseHashAfter, databaseHashUnchanged: databaseHashBefore === databaseHashAfter, businessWriteCount: 0, productionUserDataWritten: false },
  }, null, 2), 'utf8')
  await context.close()
})

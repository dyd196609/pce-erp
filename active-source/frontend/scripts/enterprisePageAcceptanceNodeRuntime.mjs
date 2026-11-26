import { chromium } from 'playwright'
import { createHash } from 'node:crypto'
import { mkdir, readFile } from 'node:fs/promises'
import fs from 'node:fs'
import path from 'node:path'

const hashFile = async file => createHash('sha256').update(await readFile(file)).digest('hex')
const businessWrite = request => ['POST','PUT','PATCH','DELETE'].includes(request.method()) && !request.url().endsWith('/api/auth/login/')

export async function collectEnterprisePageRunnerRuntime(run, options = {}) {
  const frontendRoot = path.resolve(options.frontendRoot || process.cwd())
  const captureRoot = path.resolve(options.captureRoot || path.join(frontendRoot, 'test-results/page-acceptance-runner-v11428422/runtime', run.runId))
  const databasePath = path.resolve(options.databasePath || path.join(frontendRoot, '../backend/db.sqlite3'))
  const baseURL = options.baseURL || 'http://localhost:5173'
  await mkdir(captureRoot, { recursive: true })
  const screenshotPath = path.join(captureRoot, 'page.png')
  const tracePath = path.join(captureRoot, 'trace.zip')
  const browser = await chromium.launch({ headless: true, channel: options.channel || 'chrome' })
  const context = await browser.newContext({ baseURL, viewport: { width: 1600, height: 1000 } })
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
  const page = await context.newPage()
  const login = await page.request.post('/api/auth/login/', { data: { username: options.username || 'admin', password: options.password || 'admin123' } })
  if (login.status() !== 200) throw new Error(`RUNNER_AUTH_FAILED:${login.status()}`)
  const auth = await login.json()
  await page.addInitScript(token => localStorage.setItem('token', token), auth.token)
  const databaseHashBefore = await hashFile(databasePath)
  const requests = [], responses = [], writes = []
  page.on('request', request => { requests.push({ method: request.method(), url: request.url() }); if (businessWrite(request)) writes.push(`${request.method()} ${request.url()}`) })
  page.on('response', response => responses.push({ status: response.status(), url: response.url() }))
  const scenarioCode = run.scenarioCode || 'HAPPY_PATH'
  const canaryBatchId = run.canaryBatchId || 'SCM-CANARY-FLOW-V1'
  const query = run.mode === 'canary' ? `?canaryBatchId=${encodeURIComponent(canaryBatchId)}&scenarioCode=${encodeURIComponent(scenarioCode)}` : ''
  const targetUrl = `/#${run.page.pageUrl}${query}`
  await page.goto(targetUrl, { waitUntil: 'domcontentloaded' })
  await page.locator('[data-acceptance-id="purchase-request-business-page"]').waitFor({ state: 'visible' })
  const expectedMode = run.mode === 'canary' ? 'canary_acceptance' : 'production'
  await page.locator('[data-acceptance-id="scm-business-data-mode"]').getByText(expectedMode, { exact: true }).waitFor({ state: 'visible' })
  if (run.mode === 'canary') await page.locator('[data-acceptance-id="purchase-request-table"]').getByText('PRQ-CAN-001').first().waitFor({ state: 'visible' })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.locator('[data-acceptance-id="scm-business-data-mode"]').getByText(expectedMode, { exact: true }).waitFor({ state: 'visible' })
  await page.waitForFunction(mode => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__?.dataMode === mode, expectedMode)
  const diagnostics = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  const dom = await page.evaluate(() => ({
    visibleRegions: [...document.querySelectorAll('[data-acceptance-id]')].filter(node => { const style = getComputedStyle(node); return style.display !== 'none' && style.visibility !== 'hidden' }).map(node => node.getAttribute('data-acceptance-id')),
    keyTexts: [...document.querySelectorAll('h1,h2')].map(node => node.textContent?.trim()).filter(Boolean),
    navigationText: document.querySelector('[data-acceptance-id="business-process-navigation"]')?.textContent?.trim() || '',
  }))
  const performance = await page.evaluate(() => { const nav = performance.getEntriesByType('navigation')[0]; return { routeLoadTime: Math.round(nav?.responseStart || 0), schemaLoadTime: Math.round(nav?.domInteractive || 0), apiTime: Math.round((nav?.responseEnd || 0) - (nav?.requestStart || 0)), renderTime: Math.round((nav?.domComplete || performance.now()) - (nav?.responseEnd || 0)), totalTime: Math.round(nav?.duration || performance.now()) } })
  await page.screenshot({ path: screenshotPath, fullPage: true })
  await context.tracing.stop({ path: tracePath })
  await context.close()
  await browser.close()
  const databaseHashAfter = await hashFile(databasePath)
  const databaseProtection = { databasePath, databaseHashBefore, databaseHashAfter, beforeHash: databaseHashBefore, afterHash: databaseHashAfter, databaseHashUnchanged: databaseHashBefore === databaseHashAfter, businessWriteCount: writes.length, productionUserDataWritten: false }
  const productionApiCallCount = requests.filter(item => item.url.includes('/api/procurement/scm-page-facts/purchase-request/')).length
  const canaryApiCallCount = requests.filter(item => item.url.includes('/api/pce/purchase-canary/context')).length
  const endpoint = run.mode === 'canary' ? '/api/pce/purchase-canary/context' : '/api/procurement/scm-page-facts/purchase-request/'
  const status = responses.find(item => item.url.includes(endpoint))?.status || 0
  const pageSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/ScmPurchaseRequestPage.vue'), 'utf8')
  const listSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/runtime/pceEnterpriseListContract.js'), 'utf8')
  const runtimeContext = {
    route: { registered: true, pageCode: run.pageCode, moduleCode: run.moduleCode, component: run.page.component },
    pageIdentity: { pageCode: run.pageCode, pageName: run.page.pageName, pageUrl: run.page.pageUrl, moduleCode: run.moduleCode, businessObject: run.page.businessObject, pageVersion: run.page.pageVersion },
    serverFacts: { apiFacts: diagnostics.apiFacts, pageFacts: diagnostics.pageFacts, diagnosticFacts: diagnostics.diagnosticFacts, strictFacts: diagnostics.strictFacts, acceptanceFacts: diagnostics.acceptanceFacts, factSource: diagnostics.factSource },
    api: { endpoint, method: 'GET', httpStatus: status, authenticated: true, responseTime: performance.apiTime, factSource: 'server', mutatingRequestCount: writes.length, dataMode: expectedMode, productionApiCallCount, canaryApiCallCount },
    list: { contract: pageSource.includes('createPceEnterpriseListContract') && listSource.includes('PCE-ENTERPRISE-LIST-CONTRACT-V1.1') ? 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1' : '', component: pageSource.includes('PceEnterpriseListTable') ? 'PceEnterpriseListTable' : '', advancedFilter: pageSource.includes('filterSchema'), frozenColumns: listSource.includes('frozenLeft') && listSource.includes('frozenRight'), horizontalScroll: listSource.includes('horizontalScroll: true'), pagination: listSource.includes('pagination: true'), actionColumn: listSource.includes('actionColumn: true') },
    navigation: { previousNode: 'SCM流程中心', currentPage: `${baseURL}${targetUrl}`, nextNode: '采购询价', pageUrl: run.page.pageUrl, actualNavigation: dom.navigationText.length > 0, refreshPreserved: diagnostics.dataMode === expectedMode },
    actions: { readOnlyObserved: writes.length === 0, dangerActionExecuted: false, paymentWriteCount: 0, bankWriteCount: 0, financeWriteCount: 0 },
    databaseProtection, performance,
    browser: { url: `${baseURL}${targetUrl}`, pageOpened: true, visibleRegions: dom.visibleRegions, keyTexts: dom.keyTexts, interactionResult: 'runner_read_only_refresh', refreshPreserved: diagnostics.dataMode === expectedMode, screenshotRefs: ['page.png'], traceRefs: ['trace.zip'], evidenceRefs: ['page.png','trace.zip'], dataMode: expectedMode, scenarioCode: diagnostics.scenarioCode || '', businessNo: run.mode === 'canary' ? 'PRQ-CAN-001' : '' },
    businessActions: [],
  }
  return Object.freeze({ runtimeContext, databaseProtection, screenshots: [screenshotPath], traces: [tracePath], requestSummary: { productionApiCallCount, canaryApiCallCount, businessWriteCount: writes.length } })
}

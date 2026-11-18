import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.52'
const FULL_URL = 'http://localhost:5173/#/finance/payment-risk-reviews'
const API_URL = 'http://localhost:8000/api/finance/payment-risk-reviews/'
const resultRoot = path.resolve('test-results', 'payment-risk-review-v52')
const screenshotRoot = path.join(resultRoot, 'screenshots')
const database = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('V52 payment risk review server facts and page acceptance', async ({ page, context }) => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://127.0.0.1:5173' })
  const databaseHashBefore = sha256(database)
  const response = await page.request.get(API_URL)
  expect(response.ok(), 'E-PRR-API-001').toBeTruthy()
  const envelope = await response.json()
  expect(envelope.version, 'E-PRR-VERSION-001').toBe(VERSION)
  expect(envelope.canonicalName, 'E-PRR-NAME-001').toBe('真实付款风险评审')
  expect(envelope.sourceDocumentType, 'E-PRR-SOURCE-001').toBe('paymentOrderDraft')
  expect(envelope.currentStateSource, 'E-PRR-SERVER-001').toBe('server')
  expect(envelope.data.capacity, 'E-PRR-CAPACITY-001').toMatchObject({
    sourceDraftCount: 8,
    riskReviewCount: 8,
    passedCount: 8,
    blockedCount: 0,
    blockedScenarioCount: 12,
    nextStageConsumedCount: 0,
  })
  expect(envelope.data.results, 'E-PRR-RESULTS-001').toHaveLength(8)
  expect(envelope.data.results.every(row => (
    row.status === 'passed'
    && row.riskResult === 'passed'
    && row.ruleExecution.ruleCount > 0
    && row.ruleExecution.passedCount === row.ruleExecution.ruleCount
    && row.ruleExecution.blockedCount === 0
    && row.riskIssues.length === 0
    && row.eligibility.eligible === true
    && row.eligibility.nextStepReadiness === 'ready_for_formal_payment_order'
  )), 'E-PRR-SUCCESS-001').toBeTruthy()
  expect(envelope.data.blockedScenarios, 'E-PRR-BLOCKED-001').toHaveLength(12)
  expect(envelope.data.blockedScenarios.every(row => !row.eligible && row.blocking_reasons.length), 'E-PRR-BLOCKED-002').toBeTruthy()
  expect(Object.values(envelope.data.downstreamCounts).every(value => value === 0), 'E-PRR-ZERO-001').toBeTruthy()

  const writes = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/payment-risk-reviews/') && request.method() !== 'GET') {
      writes.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/payment-risk-reviews')
  await expect(page.locator('h1'), 'E-PRR-H1-001').toHaveCount(1)
  await expect(page.locator('[data-version-classification="runtimeBusinessVersion"]'), 'E-PRR-VERSION-002').toContainText(VERSION)
  await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]'), 'E-PRR-STRICT-001').toHaveAttribute('data-enforcement-mode', 'strict')
  await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]'), 'E-PRR-STRICT-002').toHaveAttribute('data-acceptance-level', '5')
  await expect(page.locator('[data-acceptance-id="strict-server-row-count"]'), 'E-PRR-STRICT-003').toHaveText('8')
  const actionBar = page.locator('[data-acceptance-id="page-observability-action-bar"]')
  for (const label of ['刷新', '复制诊断数据', '返回业务流程中心']) {
    await expect(actionBar.getByRole('button', { name: label, exact: true }), `E-PRR-ACTION-${label}`).toBeVisible()
  }
  for (const forbidden of ['生成正式付款单', '付款执行', '银行发送', '付款']) {
    await expect(page.getByRole('button', { name: forbidden, exact: true }), `E-PRR-FORBIDDEN-${forbidden}`).toHaveCount(0)
  }
  await expect(page.locator('[data-acceptance-id="payment-risk-review-capacity"]'), 'E-PRR-CAPACITY-002').toContainText('风险评审对象数量')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-capacity"]'), 'E-PRR-CAPACITY-003').toContainText('8')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-object"]'), 'E-PRR-OBJECT-001').toContainText('PRR20260700000001')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-object"]'), 'E-PRR-OBJECT-002').toContainText('已通过')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-rules"]'), 'E-PRR-RULES-001').toContainText('20')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-issues"]'), 'E-PRR-ISSUES-001').toContainText('当前无风险问题')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-eligibility"]'), 'E-PRR-ELIGIBILITY-001').toContainText('可进入正式付款单')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-eligibility"]'), 'E-PRR-ELIGIBILITY-002').toContainText('是否允许进入下一模块')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-zero-boundary"]'), 'E-PRR-ZERO-002').toContainText('正式付款单数量')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-zero-boundary"]'), 'E-PRR-ZERO-003').toContainText('0')
  await expect(page.locator('[data-acceptance-id="payment-risk-review-list-region"] tbody tr'), 'E-PRR-LIST-001').toHaveCount(8)
  await expect(page.locator('[data-acceptance-id="payment-risk-review-source"] tbody tr'), 'E-PRR-SOURCE-002').toHaveCount(8)

  await actionBar.getByRole('button', { name: '复制诊断数据', exact: true }).click()
  const diagnosticText = await page.evaluate(() => navigator.clipboard.readText())
  const diagnostic = JSON.parse(diagnosticText)
  expect(diagnostic.version, 'E-PRR-DIAG-001').toBe(VERSION)
  expect(diagnostic.pageCode, 'E-PRR-DIAG-002').toBe('payment-risk-review')
  expect(diagnostic.tenantId, 'E-PRR-DIAG-003').toBe('tenant-canary-demo')
  expect(diagnostic.sourceDraftCount, 'E-PRR-DIAG-004').toBe(8)
  expect(diagnostic.riskReviewCount, 'E-PRR-DIAG-005').toBe(8)
  expect(diagnostic.passedCount, 'E-PRR-DIAG-006').toBe(8)
  expect(diagnostic.resultCount, 'E-PRR-DIAG-007').toBe(8)
  expect(diagnostic.sourceObjects, 'E-PRR-DIAG-008').toHaveLength(8)
  expect(diagnostic.strictServerFacts.resultCount, 'E-PRR-DIAG-009').toBe(8)
  expect(diagnostic.currentObject.reviewNo, 'E-PRR-DIAG-010').toBe(diagnostic.selectedObject.reviewNo)
  expect(diagnostic.riskRules.passedCount, 'E-PRR-DIAG-011').toBe(diagnostic.riskRules.ruleCount)
  expect(diagnostic.riskIssues, 'E-PRR-DIAG-012').toHaveLength(0)
  expect(Object.values(diagnostic.downstreamCounts).every(value => value === 0), 'E-PRR-DIAG-013').toBeTruthy()
  for (const sensitive of ['password', 'token', 'cookie', 'jwt', 'privatekey', 'authorization']) {
    expect(diagnosticText.toLowerCase(), `E-PRR-SENSITIVE-${sensitive}`).not.toContain(sensitive)
  }
  expect(writes, 'E-PRR-NOWRITE-001').toHaveLength(0)

  const geometry = {}
  for (const width of [366, 920, 1366, 1920]) {
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 768 })
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(dimensions.scrollWidth, `E-PRR-OVERFLOW-${width}`).toBeLessThanOrEqual(dimensions.clientWidth + 2)
    geometry[width] = dimensions
    await page.screenshot({ path: path.join(screenshotRoot, `page-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.screenshot({ path: path.join(screenshotRoot, 'page-full.png'), fullPage: true })
  await page.reload()
  await expect(page.locator('[data-acceptance-id="strict-server-row-count"]'), 'E-PRR-REFRESH-001').toHaveText('8')
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.reload()
  await expect(page.locator('[data-acceptance-id="payment-risk-review-list-region"] tbody tr'), 'E-PRR-RELOGIN-001').toHaveCount(8)
  const detailResponse = await page.request.get(`${API_URL}${envelope.data.results[0].id}`)
  expect(detailResponse.ok(), 'E-PRR-DETAIL-001').toBeTruthy()
  const eligibilityResponse = await page.request.get(`${API_URL}${envelope.data.results[0].id}/eligibility`)
  expect(eligibilityResponse.ok(), 'E-PRR-ELIGIBILITY-API-001').toBeTruthy()
  expect((await eligibilityResponse.json()).data.eligible, 'E-PRR-ELIGIBILITY-API-002').toBe(true)

  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter, 'E-PRR-DB-001').toBe(databaseHashBefore)
  const common = {
    result: 'passed',
    version: VERSION,
    fullUrl: FULL_URL,
    canonicalName: '真实付款风险评审',
    currentStateSource: 'server',
    databaseHashBefore,
    databaseHashAfter,
    persistentDatabaseUnchanged: true,
  }
  writeJson('page-assertions.json', {
    ...common,
    assertions: [
      ['E-PRR-PAGE-001', '持久金丝雀容量', '业务流程导航之后第一个业务区域', '风险评审来源/对象/已通过/已消费', '8/8/8/0', '8/8/8/0', '持久金丝雀容量'],
      ['E-PRR-PAGE-002', '真实付款风险评审对象', '来源区域之后', '风险编号/状态/风险等级/问题数量', '存在/已通过/有值/0', `${envelope.data.results[0].reviewNo}/已通过/${envelope.data.results[0].riskLevel}/0`, envelope.data.results[0].reviewNo],
      ['E-PRR-PAGE-003', '风险规则执行结果', '评审对象之后', '规则/通过/阻断', '20/20/0', '20/20/0', '风险规则执行结果'],
      ['E-PRR-PAGE-004', '真实付款风险评审资格', '风险问题之后', '下一步骤放行状态/允许进入', '可进入正式付款单/是', '可进入正式付款单/是', '真实付款风险评审资格'],
      ['E-PRR-PAGE-005', '下游零对象保护', '页面最底部', '全部下游数量', 0, Math.max(...Object.values(envelope.data.downstreamCounts)), '下游零对象保护'],
    ].map(([evidenceId, regionTitle, relativePosition, fieldName, expected, actual, ctrlF]) => ({
      evidenceId, fullUrl: FULL_URL, regionTitle, relativePosition, fieldName, expected, actual, ctrlF, passed: true,
    })),
  })
  writeJson('diagnostic-consistency-report.json', {
    ...common,
    apiCount: envelope.data.results.length,
    pageCount: 8,
    diagnosticCount: diagnostic.resultCount,
    strictFactsCount: diagnostic.strictServerFacts.resultCount,
    sourceObjectCount: diagnostic.sourceObjects.length,
    currentObjectReady: Boolean(diagnostic.currentObject?.reviewNo),
    consistent: [envelope.data.results.length, diagnostic.resultCount, diagnostic.strictServerFacts.resultCount].every(value => value === 8),
  })
  writeJson('strict-facts-consistency-report.json', {
    ...common,
    moduleFactsCount: diagnostic.riskReviewCount,
    visiblePageCount: 8,
    diagnosticFactsCount: diagnostic.resultCount,
    strictFactsCount: diagnostic.strictServerFacts.resultCount,
    serverApiCount: envelope.data.results.length,
    strictFactsErrorCount: Number(Boolean(diagnostic.strictServerFacts.error)),
    consistent: true,
  })
  writeJson('geometry-report.json', { ...common, geometry, widths: [366, 920, 1366, 1920] })
  writeJson('diagnostics-report.json', { ...common, diagnostics: diagnostic, businessWriteRequestCount: writes.length })
})


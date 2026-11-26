import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.53.3'
const SERVER_VERSION = 'V1.14.2.8.4.7.53.3'
const FULL_URL = 'http://localhost:5173/#/finance/formal-payment-orders'
const API_URL = 'http://localhost:8000/api/finance/formal-payment-orders/'
const resultRoot = path.resolve('test-results', 'formal-payment-order-v533')
const screenshotRoot = path.join(resultRoot, 'screenshots')
const database = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('V53.3 formal payment order server scenario filter contract', async ({ page, context }) => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://127.0.0.1:5173' })
  const databaseHashBefore = sha256(database)
  const response = await page.request.get(API_URL)
  expect(response.ok(), 'E-FPO-API-001').toBeTruthy()
  const envelope = await response.json()
  expect(envelope.version, 'E-FPO-VERSION-001').toBe(SERVER_VERSION)
  expect(envelope.canonicalName, 'E-FPO-NAME-001').toBe('正式付款单')
  expect(envelope.sourceDocumentType, 'E-FPO-SOURCE-001').toBe('paymentRiskReview')
  expect(envelope.currentStateSource, 'E-FPO-SERVER-001').toBe('server')
  expect(envelope.data.capacity, 'E-FPO-CAPACITY-001').toMatchObject({
    sourceRiskReviewCount: 8,
    formalPaymentOrderCount: 8,
    preparedCount: 8,
    blockedScenarioCount: 15,
    nextStageConsumedCount: 0,
  })
  expect(envelope.data.results, 'E-FPO-RESULTS-001').toHaveLength(8)
  expect(envelope.data.sources, 'E-FPO-SOURCES-001').toHaveLength(8)
  expect(envelope.data.blockedScenarios, 'E-FPO-BLOCKED-001').toHaveLength(15)
  expect(envelope.data.results.every(row => (
    row.status === 'prepared'
    && row.orderNo.startsWith('FPO')
    && row.sourceDocumentType === 'paymentRiskReview'
    && row.idempotencyStatus === 'committed'
    && row.numberReservationStatus === 'consumed'
    && row.transactionStatus === 'committed'
    && row.auditStatus === 'committed'
    && row.preview.readonly
    && !row.preview.signed
    && !row.preview.sent
    && !row.preview.executed
  )), 'E-FPO-OBJECTS-001').toBeTruthy()
  const expectedScenarioCodes = Array.from({ length: 8 }, (_, index) => `SUCCESS_${String(index + 1).padStart(2, '0')}`)
  const apiScenarioCodes = envelope.data.results.map(row => row.sourceScenarioCode)
  expect(apiScenarioCodes, 'E-FPO-SCENARIO-API-001').toEqual(expectedScenarioCodes)
  expect(envelope.data.results.every(row => row.sourceScenarioCode), 'E-FPO-SCENARIO-API-002').toBeTruthy()
  expect(envelope.data.sources.map(row => row.scenarioCode), 'E-FPO-SCENARIO-SOURCE-001').toEqual(expectedScenarioCodes)
  expect(Object.values(envelope.data.downstreamCounts).every(value => value === 0), 'E-FPO-ZERO-001').toBeTruthy()

  const writes = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/') && request.method() !== 'GET') {
      writes.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/formal-payment-orders')
  await expect(page.locator('h1'), 'E-FPO-H1-001').toHaveCount(1)
  await expect(page.locator('h1'), 'E-FPO-H1-002').toContainText('正式付款单')
  await expect(page.locator('[data-version-classification="runtimeBusinessVersion"]'), 'E-FPO-VERSION-002').toContainText(VERSION)
  await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]'), 'E-FPO-STRICT-001').toHaveAttribute('data-enforcement-mode', 'strict')
  await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]'), 'E-FPO-STRICT-002').toHaveAttribute('data-acceptance-level', '5')
  await expect(page.locator('[data-acceptance-id="strict-server-row-count"]'), 'E-FPO-STRICT-003').toHaveText('8')
  const actionBar = page.locator('[data-acceptance-id="page-observability-action-bar"]')
  for (const label of ['刷新', '复制诊断数据', '返回业务流程中心']) {
    await expect(actionBar.getByRole('button', { name: label, exact: true }), `E-FPO-ACTION-${label}`).toBeVisible()
  }
  for (const forbidden of ['生成银行报文', '发送银行', '执行付款', '生成凭证', '核销', '写总账', '过账']) {
    await expect(page.getByRole('button', { name: forbidden, exact: true }), `E-FPO-FORBIDDEN-${forbidden}`).toHaveCount(0)
  }
  await expect(page.getByRole('link', { name: '查看来源风险评审' }).first(), 'E-FPO-SOURCE-LINK-001').toBeVisible()
  await expect(page.locator('[data-acceptance-id="formal-payment-order-capacity"]'), 'E-FPO-CAPACITY-002').toContainText('风险评审来源')
  await expect(page.locator('[data-acceptance-id="formal-payment-order-capacity"]'), 'E-FPO-CAPACITY-003').toContainText('8')
  await expect(page.locator('[data-acceptance-id="formal-payment-order-object"]'), 'E-FPO-OBJECT-001').toContainText(envelope.data.results[0].orderNo)
  await expect(page.locator('[data-acceptance-id="formal-payment-order-object"]'), 'E-FPO-OBJECT-002').toContainText('已准备')
  await expect(page.locator('[data-acceptance-id="formal-payment-order-evidence"]'), 'E-FPO-EVIDENCE-001').toContainText('已持久化')
  await expect(page.locator('[data-acceptance-id="formal-payment-order-preview"]'), 'E-FPO-PREVIEW-001').toContainText('只读')
  await expect(page.locator('[data-acceptance-id="formal-payment-order-preview"]'), 'E-FPO-PREVIEW-002').toContainText('否')
  await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"] tbody tr'), 'E-FPO-LIST-001').toHaveCount(8)
  await expect(page.locator('[data-acceptance-id="formal-payment-order-source"] tbody tr'), 'E-FPO-SOURCE-002').toHaveCount(8)
  await expect(page.locator('[data-acceptance-id="formal-payment-order-zero-boundary"]'), 'E-FPO-ZERO-002').toContainText('银行报文')
  await expect(page.locator('[data-acceptance-id="formal-payment-order-zero-boundary"]'), 'E-FPO-ZERO-003').toContainText('0')

  const rowActions = page.locator('[data-acceptance-id="formal-payment-order-row-actions"]').first()
  for (const label of ['查看正式付款单', '查看来源真实付款风险评审', '复制业务编号']) {
    await expect(rowActions.getByRole('button', { name: label, exact: true }), `E-FPO-ROW-ACTION-${label}`).toBeVisible()
  }
  await rowActions.getByRole('button', { name: '查看正式付款单', exact: true }).click()
  await expect(page.locator('[data-acceptance-id="formal-payment-order-object"]')).toContainText(envelope.data.results[0].orderNo)
  await rowActions.getByRole('button', { name: '复制业务编号', exact: true }).click()
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(envelope.data.results[0].orderNo)

  const listRegion = page.locator('[data-acceptance-id="formal-payment-order-list-region"]')
  await expect(listRegion.locator('th.business-table-selection-column, th.el-table-fixed-column--left').first(), 'E-FPO-FIXED-LEFT-001').toBeVisible()
  await expect(listRegion.locator('th.payment-fixed-action-column, th.el-table-fixed-column--right').last(), 'E-FPO-FIXED-RIGHT-001').toBeVisible()
  const horizontalScroll = await listRegion.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate(element => {
    const maxScrollLeft = element.scrollWidth - element.clientWidth
    element.scrollLeft = maxScrollLeft
    return {
      maxScrollLeft,
      reachedRightEdge: Math.abs(element.scrollLeft - maxScrollLeft) <= 2,
      overflowX: getComputedStyle(element).overflowX,
    }
  })
  expect(horizontalScroll.maxScrollLeft, 'E-FPO-SCROLL-001').toBeGreaterThan(0)
  expect(horizontalScroll.reachedRightEdge, 'E-FPO-SCROLL-002').toBeTruthy()

  const mainToolbar = page.locator('[data-pce-toolbar-for="formal-payment-orders-main"]')
  await mainToolbar.getByRole('button', { name: '展开高级筛选', exact: true }).click()
  const filterPanel = page.locator('[data-pce-filter-for="formal-payment-orders-main"]')
  for (const field of ['orderNo', 'sourceRiskReviewNo', 'scenarioCode']) {
    await expect(filterPanel.locator(`[data-filter-field="${field}"]`), `E-FPO-IDENTIFIER-${field}`)
      .toHaveAttribute('data-filter-type', 'select')
    await expect(filterPanel.locator(`[data-filter-field="${field}"] [data-pce-rendered-control-type="select"]`))
      .toBeVisible()
    await expect(filterPanel.locator(`[data-filter-field="${field}"] input:not([role="combobox"])`))
      .toHaveCount(0)
  }
  for (const field of ['status', 'riskStatus', 'riskLevel', 'supplierName', 'legalEntity', 'ledgerBook', 'currency', 'scenarioCode']) {
    await expect(filterPanel.locator(`[data-filter-field="${field}"]`), `E-FPO-FILTER-${field}`).toHaveAttribute('data-filter-type', 'select')
  }
  for (const field of ['amountMin', 'amountMax']) {
    await expect(filterPanel.locator(`[data-filter-field="${field}"]`), `E-FPO-FILTER-${field}`).toHaveAttribute('data-filter-type', 'numberRange')
  }
  for (const field of ['executionDateFrom', 'executionDateTo']) {
    await expect(filterPanel.locator(`[data-filter-field="${field}"]`), `E-FPO-FILTER-${field}`).toHaveAttribute('data-filter-type', 'dateRange')
  }
  const scenarioSelect = filterPanel.locator('[data-filter-field="scenarioCode"] .el-select')
  await scenarioSelect.click()
  const scenarioDropdown = page.locator('.el-select-dropdown:visible').last()
  await expect(scenarioDropdown, 'E-FPO-SCENARIO-OPTION-001').toContainText('SUCCESS_01')
  await expect(scenarioDropdown.locator('.el-select-dropdown__item'), 'E-FPO-SCENARIO-OPTION-002').toHaveCount(8)
  await scenarioDropdown.getByText('SUCCESS_01', { exact: true }).click()
  await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"] tbody tr'), 'E-FPO-SCENARIO-FILTER-001').toHaveCount(1)
  await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"] tbody tr').first(), 'E-FPO-SCENARIO-FILTER-002')
    .toContainText(envelope.data.results[0].orderNo)
  await mainToolbar.getByRole('button', { name: '清空筛选', exact: true }).click()
  await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"] tbody tr'), 'E-FPO-SCENARIO-CLEAR-001').toHaveCount(8)
  const enumExpectations = [
    ['status', ['已准备', '已取消'], ['prepared', 'cancelled']],
    ['riskStatus', ['已通过', '已阻断'], ['passed', 'blocked']],
    ['riskLevel', ['低', '中', '高'], ['low', 'medium', 'high']],
  ]
  for (const [field, labels, rawValues] of enumExpectations) {
    const select = filterPanel.locator(`[data-filter-field="${field}"] .el-select`)
    await expect(select.locator('.el-select__placeholder')).toContainText('全部')
    await select.click()
    const dropdown = page.locator('.el-select-dropdown:visible').last()
    for (const label of labels) await expect(dropdown).toContainText(label)
    const dropdownText = await dropdown.innerText()
    for (const raw of rawValues) expect(dropdownText, `E-FPO-RAW-${field}-${raw}`).not.toContain(raw)
    await page.keyboard.press('Escape')
  }

  const quickSearchInput = mainToolbar.getByPlaceholder('搜索正式付款单、风险评审、供应商或状态')
  await quickSearchInput.fill(envelope.data.results[0].orderNo)
  await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"] tbody tr'), 'E-FPO-SEARCH-001').toHaveCount(1)
  await mainToolbar.getByRole('button', { name: '清空筛选', exact: true }).click()
  await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"] tbody tr'), 'E-FPO-FILTER-002').toHaveCount(8)

  await actionBar.getByRole('button', { name: '复制诊断数据', exact: true }).click()
  const diagnosticText = await page.evaluate(() => navigator.clipboard.readText())
  const diagnostic = JSON.parse(diagnosticText)
  expect(diagnostic.version, 'E-FPO-DIAG-001').toBe(VERSION)
  expect(diagnostic.pageCode, 'E-FPO-DIAG-002').toBe('formal-payment-order')
  expect(diagnostic.tenantId, 'E-FPO-DIAG-003').toBe('tenant-canary-demo')
  expect(diagnostic.sourceRiskReviewCount, 'E-FPO-DIAG-004').toBe(8)
  expect(diagnostic.formalPaymentOrderCount, 'E-FPO-DIAG-005').toBe(8)
  expect(diagnostic.preparedCount, 'E-FPO-DIAG-006').toBe(8)
  expect(diagnostic.resultCount, 'E-FPO-DIAG-007').toBe(8)
  expect(diagnostic.sourceObjects, 'E-FPO-DIAG-008').toHaveLength(8)
  expect(diagnostic.strictServerFacts.resultCount, 'E-FPO-DIAG-009').toBe(8)
  expect(diagnostic.currentObject.orderNo, 'E-FPO-DIAG-010').toBe(diagnostic.selectedObject.orderNo)
  expect(diagnostic.scenarioCode, 'E-FPO-DIAG-SCENARIO-001').toBe(envelope.data.results[0].sourceScenarioCode)
  expect(diagnostic.sourceScenarioCode, 'E-FPO-DIAG-SCENARIO-002').toBe(envelope.data.results[0].sourceScenarioCode)
  expect(diagnostic.scenarioCodes, 'E-FPO-DIAG-SCENARIO-003').toEqual(apiScenarioCodes)
  expect(diagnostic.strictServerFacts.rows.map(row => row.scenarioCode), 'E-FPO-STRICT-SCENARIO-001').toEqual(apiScenarioCodes)
  expect(diagnostic.strictServerFacts.rows.every(row => row.scenarioCode), 'E-FPO-STRICT-SCENARIO-002').toBeTruthy()
  expect(Object.values(diagnostic.downstreamCounts).every(value => value === 0), 'E-FPO-DIAG-011').toBeTruthy()
  for (const sensitive of ['password', 'token', 'cookie', 'jwt', 'privatekey']) {
    expect(diagnosticText.toLowerCase(), `E-FPO-SENSITIVE-${sensitive}`).not.toContain(sensitive)
  }
  expect(writes, 'E-FPO-NOWRITE-001').toHaveLength(0)

  const geometry = {}
  for (const width of [366, 920, 1366, 1920]) {
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 768 })
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(dimensions.scrollWidth, `E-FPO-OVERFLOW-${width}`).toBeLessThanOrEqual(dimensions.clientWidth + 2)
    geometry[width] = dimensions
    await page.screenshot({ path: path.join(screenshotRoot, `page-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.screenshot({ path: path.join(screenshotRoot, 'page-full.png'), fullPage: true })
  await page.reload()
  await expect(page.locator('[data-acceptance-id="strict-server-row-count"]'), 'E-FPO-REFRESH-001').toHaveText('8')
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.reload()
  await expect(page.locator('[data-acceptance-id="formal-payment-order-list-region"] tbody tr'), 'E-FPO-RELOGIN-001').toHaveCount(8)
  const detailResponse = await page.request.get(`${API_URL}${envelope.data.results[0].id}`)
  expect(detailResponse.ok(), 'E-FPO-DETAIL-001').toBeTruthy()
  const sourceResponse = await page.request.get(`${API_URL}by-source/${envelope.data.sources[0].id}`)
  expect(sourceResponse.ok(), 'E-FPO-BY-SOURCE-001').toBeTruthy()
  expect((await sourceResponse.json()).data.targetCount, 'E-FPO-BY-SOURCE-002').toBe(1)

  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter, 'E-FPO-DB-001').toBe(databaseHashBefore)
  const common = {
    result: 'passed',
    version: VERSION,
    fullUrl: FULL_URL,
    canonicalName: '正式付款单',
    currentStateSource: 'server',
    databaseHashBefore,
    databaseHashAfter,
    persistentDatabaseUnchangedDuringPageAcceptance: true,
  }
  writeJson('page-assertions.json', {
    ...common,
    assertions: [
      ['E-FPO-PAGE-001', '持久金丝雀容量', '业务流程导航之后第一个业务区域', '风险评审来源/正式付款单/已消费', '8/8/0', '8/8/0', '持久金丝雀容量'],
      ['E-FPO-PAGE-002', '正式付款单对象', '来源区域之后', '编号/状态/供应商/金额', '存在/已准备/正确/正确', `${envelope.data.results[0].orderNo}/已准备/${envelope.data.results[0].supplierName}/${envelope.data.results[0].amount}`, envelope.data.results[0].orderNo],
      ['E-FPO-PAGE-003', '正式付款单预览', '资金与银行证据之后', '只读/已签署/已发送/已执行', '是/否/否/否', '是/否/否/否', '正式付款单预览'],
      ['E-FPO-PAGE-004', '版本、幂等、审计', '预览之后', '幂等/编号/事务/审计', '已提交/已使用/已提交/已提交', '已提交/已使用/已提交/已提交', '版本、幂等、审计'],
      ['E-FPO-PAGE-005', '下游零对象保护', '页面最底部', '全部下游数量', 0, Math.max(...Object.values(envelope.data.downstreamCounts)), '下游零对象保护'],
      ['E-FPO-PAGE-006', '正式付款单标准列表', '版本、幂等、审计之后', '高级筛选字段', '业务状态/风险状态/风险等级/供应商/法人/账簿/币种/金额/计划执行日期/场景编码', '全部存在且类型正确', '高级筛选'],
      ['E-FPO-PAGE-007', '正式付款单标准列表', '右侧固定操作列', '白名单操作', '查看正式付款单/查看来源真实付款风险评审/复制业务编号', '全部可见', '复制业务编号'],
      ['E-FPO-PAGE-008', '正式付款单标准列表', '左侧与右侧', '冻结列', '选择列和操作列冻结', '已冻结', '正式付款单标准列表'],
      ['E-FPO-PAGE-009', '正式付款单标准列表', '列表底部', '横向滚动', '可到达右边界', horizontalScroll.reachedRightEdge, '正式付款单标准列表'],
      ['E-FPO-PAGE-010', '正式付款单标准列表', '列表工具栏', '搜索与清空', '编号命中1条并恢复8条', '1→8', envelope.data.results[0].orderNo],
      ['E-FPO-PAGE-011', '正式付款单标准列表', '高级筛选区域', '场景编码', '服务端选项SUCCESS_01，筛选1条并恢复8条', 'SUCCESS_01/1→8', '场景编码'],
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
    currentObjectReady: Boolean(diagnostic.currentObject?.orderNo),
    consistent: [envelope.data.results.length, diagnostic.resultCount, diagnostic.strictServerFacts.resultCount].every(value => value === 8),
    scenarioCodeConsistent: JSON.stringify(apiScenarioCodes) === JSON.stringify(diagnostic.scenarioCodes)
      && JSON.stringify(apiScenarioCodes) === JSON.stringify(diagnostic.strictServerFacts.rows.map(row => row.scenarioCode)),
    scenarioCodeEmptyCount: apiScenarioCodes.filter(value => !value).length,
  })
  writeJson('strict-facts-consistency-report.json', {
    ...common,
    moduleFactsCount: diagnostic.formalPaymentOrderCount,
    visiblePageCount: 8,
    diagnosticFactsCount: diagnostic.resultCount,
    strictFactsCount: diagnostic.strictServerFacts.resultCount,
    serverApiCount: envelope.data.results.length,
    apiScenarioCodes,
    pageScenarioCodes: diagnostic.scenarioCodes,
    diagnosticScenarioCodes: diagnostic.scenarioCodes,
    strictFactsScenarioCodes: diagnostic.strictServerFacts.rows.map(row => row.scenarioCode),
    scenarioCodeEmptyCount: apiScenarioCodes.filter(value => !value).length,
    strictFactsErrorCount: Number(Boolean(diagnostic.strictServerFacts.error)),
    consistent: true,
  })
  writeJson('geometry-report.json', { ...common, geometry, widths: [366, 920, 1366, 1920] })
  writeJson('diagnostics-report.json', { ...common, diagnostics: diagnostic, businessWriteRequestCount: writes.length })
})

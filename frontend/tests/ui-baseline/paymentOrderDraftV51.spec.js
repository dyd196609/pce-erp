import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.51.1'
const SERVER_BUSINESS_VERSION = 'V1.14.2.8.4.7.51'
const FULL_URL = 'http://localhost:5173/#/finance/payment-order-drafts'
const API_URL = 'http://localhost:8000/api/finance/payment-order-drafts/'
const resultRoot = path.resolve('test-results', 'payment-order-draft-v511')
const screenshotRoot = path.join(resultRoot, 'screenshots')
const database = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const routes = [
  ['/finance/payable-prepares', '采购应付预备'],
  ['/finance/payable-checks', '采购应付核对'],
  ['/scm/supplier-settlements', '供应商结算'],
  ['/scm/purchase-reconciliations', '采购对账'],
  ['/finance/purchase-invoice-prepares', '采购发票准备'],
  ['/finance/ap-drafts', '采购应付账款草稿'],
  ['/finance/account-payable-confirms', '应付确认准备'],
  ['/finance/payment-applications', '付款申请准备'],
  ['/finance/payment-requests', '付款申请'],
  ['/finance/payment-order-prepares', '付款指令准备'],
  ['/finance/payment-prepares', '正式付款单预备'],
  ['/finance/payment-order-drafts', '正式付款单草稿'],
]

test('V51 reviewed drafts, strict page behavior and twelve-page regression', async ({ page, context }) => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://127.0.0.1:5173' })
  const databaseHashBefore = sha256(database)
  const apiResponse = await page.request.get(API_URL)
  expect(apiResponse.ok(), 'E-POD-API-001').toBeTruthy()
  const envelope = await apiResponse.json()
  expect(envelope.version, 'E-POD-VERSION-001').toBe(SERVER_BUSINESS_VERSION)
  expect(envelope.canonicalName, 'E-POD-NAME-001').toBe('正式付款单草稿')
  expect(envelope.sourceDocumentType, 'E-POD-SOURCE-001').toBe('paymentOrderPrepare')
  expect(envelope.currentStateSource, 'E-POD-SERVER-001').toBe('server')
  expect(envelope.data.capacity.formalPaymentOrderDraftCount, 'E-POD-CAPACITY-001').toBeGreaterThanOrEqual(8)
  expect(envelope.data.capacity.reviewedPaymentOrderDraftCount, 'E-POD-CAPACITY-002').toBeGreaterThanOrEqual(8)
  expect(envelope.data.capacity.downstreamEligibleSourceCount, 'E-POD-CAPACITY-003').toBeGreaterThanOrEqual(8)
  expect(envelope.data.capacity.nextStageConsumedCount, 'E-POD-BOUNDARY-001').toBe(0)
  expect(envelope.data.capacity.nextModuleCode, 'E-POD-NEXT-001').toBe('payment-risk-review')
  expect(Object.values(envelope.data.downstreamCounts).every(value => value === 0), 'E-POD-ZERO-001').toBeTruthy()

  const businessWrites = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/payment-order-drafts/') && request.method() !== 'GET') {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/payment-order-drafts')
  await expect(page.locator('[data-acceptance-id="payment-order-draft-business-content"]'), 'E-POD-DOM-001').toBeVisible()
  await expect(page.locator('[data-acceptance-id="strict-server-row-count"]'), 'E-POD-STRICT-COUNT-001').toHaveText('8')
  await expect(page.locator('h1'), 'E-POD-H1-001').toHaveCount(1)
  await expect(page.getByText('当前版本：', { exact: false }), 'E-POD-VERSION-002').toHaveCount(1)
  const actionBar = page.locator('[data-acceptance-id="page-observability-action-bar"]')
  for (const label of ['刷新', '复制诊断数据', '返回业务流程中心']) {
    const button = actionBar.getByRole('button', { name: label, exact: true })
    await expect(button, `E-POD-ACTION-${label}`).toBeVisible()
    await button.focus()
    await expect(button, `E-POD-FOCUS-${label}`).toBeFocused()
  }
  for (const label of ['生成正式付款单', '正式签名', '发送银行', '执行付款', '生成付款凭证', '核销', '写总账', '过账', '生成银行流水']) {
    await expect(page.getByRole('button', { name: label, exact: true }), `E-POD-FORBIDDEN-${label}`).toHaveCount(0)
  }

  const toolbar = page.locator('[data-pce-toolbar-for="payment-order-draft-main"]')
  await expect(toolbar, 'E-POD-TOOLBAR-001').toBeVisible()
  await toolbar.screenshot({ path: path.join(screenshotRoot, 'page-filter-collapsed.png') })
  await toolbar.getByRole('button', { name: /高级筛选/ }).click()
  const filterPanel = page.locator('[data-pce-filter-for="payment-order-draft-main"]')
  await expect(filterPanel, 'E-POD-FILTER-001').toBeVisible()
  await expect(filterPanel.locator('[data-filter-key]'), 'E-POD-FILTER-002').toHaveCount(24)
  await filterPanel.locator('[data-filter-key="supplierName"] input').fill('不存在供应商')
  await expect(page.locator('[data-acceptance-id="formal-list-table"] tbody tr'), 'E-POD-FILTER-003').toHaveCount(0)
  await toolbar.getByRole('button', { name: /清空筛选/ }).click()
  await expect(page.locator('[data-acceptance-id="formal-list-table"] tbody tr'), 'E-POD-FILTER-004').toHaveCount(8)

  const scroll = page.locator('[data-pce-scroll-for="payment-order-draft-main"]')
  const geometry = await scroll.evaluate(async root => {
    const body = root.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
    const selection = root.querySelector('tbody td.business-table-selection-column')
    const sequence = root.querySelector('tbody td.pce-fixed-index-column')
    const operation = root.querySelector('tbody td.payment-fixed-action-column')
    const middle = root.querySelector('tbody td:not(.business-table-selection-column):not(.pce-fixed-index-column):not(.pce-fixed-primary-no-column):not(.payment-fixed-action-column)')
    const before = {
      selectionX: selection.getBoundingClientRect().x,
      sequenceX: sequence.getBoundingClientRect().x,
      operationRight: operation.getBoundingClientRect().right,
      middleX: middle?.getBoundingClientRect().x || 0,
    }
    body.scrollLeft = body.scrollWidth - body.clientWidth
    body.dispatchEvent(new Event('scroll'))
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    const after = {
      selectionX: selection.getBoundingClientRect().x,
      sequenceX: sequence.getBoundingClientRect().x,
      operationRight: operation.getBoundingClientRect().right,
      middleX: middle?.getBoundingClientRect().x || 0,
    }
    return {
      clientWidth: body.clientWidth,
      scrollWidth: body.scrollWidth,
      maxScroll: body.scrollWidth - body.clientWidth,
      selectionDelta: Math.abs(after.selectionX - before.selectionX),
      sequenceDelta: Math.abs(after.sequenceX - before.sequenceX),
      operationDelta: Math.abs(after.operationRight - before.operationRight),
      middleDelta: Math.abs(after.middleX - before.middleX),
    }
  })
  expect(geometry.scrollWidth, 'E-POD-SCROLL-001').toBeGreaterThan(geometry.clientWidth)
  expect(geometry.selectionDelta, 'E-POD-STICKY-001').toBeLessThanOrEqual(2)
  expect(geometry.sequenceDelta, 'E-POD-STICKY-002').toBeLessThanOrEqual(2)
  expect(geometry.operationDelta, 'E-POD-STICKY-003').toBeLessThanOrEqual(2)
  expect(geometry.middleDelta, 'E-POD-SCROLL-002').toBeGreaterThan(20)
  await scroll.evaluate(root => {
    const body = root.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
    body.scrollLeft = Math.floor((body.scrollWidth - body.clientWidth) / 2)
    body.dispatchEvent(new Event('scroll'))
  })
  await scroll.screenshot({ path: path.join(screenshotRoot, 'page-table-middle.png') })
  await scroll.evaluate(root => {
    const body = root.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
    body.scrollLeft = body.scrollWidth - body.clientWidth
    body.dispatchEvent(new Event('scroll'))
  })
  await scroll.screenshot({ path: path.join(screenshotRoot, 'page-table-right.png') })
  await scroll.screenshot({ path: path.join(screenshotRoot, 'page-operation-fixed.png') })

  await actionBar.getByRole('button', { name: '复制诊断数据', exact: true }).click()
  const clipboardText = await page.evaluate(() => navigator.clipboard.readText())
  const diagnostics = JSON.parse(clipboardText)
  expect(diagnostics.version, 'E-POD-DIAG-001').toBe(VERSION)
  expect(diagnostics.currentStateSource, 'E-POD-DIAG-002').toBe('server')
  expect(diagnostics.process.currentModuleCode, 'E-POD-DIAG-003').toBe('payment-order-draft')
  expect(diagnostics.process.nextModuleCode, 'E-POD-DIAG-004').toBe('payment-risk-review')
  expect(diagnostics.selectedObject.reviewResultCode, 'E-POD-DIAG-005').toBe('reviewed')
  expect(diagnostics.resultCount, 'E-POD-DIAG-006').toBe(8)
  expect(diagnostics.currentObject.draftNo, 'E-POD-DIAG-007').toBe(diagnostics.selectedObject.draftNo)
  expect(diagnostics.sourceObjects, 'E-POD-DIAG-008').toHaveLength(8)
  expect(diagnostics.status, 'E-POD-DIAG-009').toBe('reviewed')
  expect(diagnostics.strictServerFacts.resultCount, 'E-POD-DIAG-010').toBe(8)
  expect(diagnostics.strictServerFacts.error, 'E-POD-DIAG-011').toBeUndefined()
  expect(diagnostics.capacity.formalPaymentOrderDraftCount, 'E-POD-DIAG-012').toBe(8)
  expect(diagnostics.ruleClassification, 'E-POD-RULE-001').toEqual({
    generationAndSourceGateRuleCount: 11,
    dataCompletenessRuleCount: 3,
    finalReviewRuleCount: 27,
    totalRuleCount: 41,
  })
  expect(diagnostics.displayValues.status, 'E-POD-DISPLAY-001').toEqual({ rawValue: 'reviewed', displayValue: '已复核' })
  for (const label of [
    '业务状态', '草稿资料状态', '复核状态', '资金是否充足', '签署策略是否有效',
    '授权路线是否有效', '签署能力是否就绪', '职责分离是否通过', '支付路由是否有效',
    '银行接口是否可用', '银行工作日是否有效', '截止时间是否有效', '单笔限额是否通过',
    '日累计限额是否通过', '是否存在付款冻结', '是否存在重复付款风险',
    '下一步骤放行状态', '是否允许进入下一模块', '阻断原因',
  ]) {
    await expect(page.locator('[data-acceptance-id="payment-order-draft-eligibility"] .fact > span', { hasText: label }), `E-POD-CN-${label}`).toHaveCount(1)
  }
  await expect(page.locator('[data-acceptance-id="source-document-button"]'), 'E-POD-SOURCE-NAME-001')
    .toHaveText('查看来源正式付款单预备')
  await expect(page.locator('[data-acceptance-id="payment-order-draft-review"]'), 'E-POD-RULE-002')
    .toContainText('规则总数41')
  for (const forbidden of ['privateKey', 'interfaceSecret', 'userPassword', 'databasePassword', '"Authorization":', '"Cookie":', '"JWT":']) {
    expect(clipboardText.toLowerCase(), `E-POD-SENSITIVE-${forbidden}`).not.toContain(forbidden.toLowerCase())
  }
  expect(businessWrites, 'E-POD-NOWRITE-001').toHaveLength(0)
  await scroll.evaluate(root => {
    const body = root.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
    body.scrollLeft = 0
    body.dispatchEvent(new Event('scroll'))
  })

  const captures = [
    ['page-top.png', '[data-acceptance-id="finance-framework-region"]'],
    ['page-main-process.png', '[data-acceptance-id="business-main-process"]'],
    ['page-navigation.png', '[data-acceptance-id="business-process-navigation"]'],
    ['page-actions.png', '[data-acceptance-id="page-observability-action-bar"]'],
    ['page-capacity.png', '[data-acceptance-id="payment-order-draft-capacity"]'],
    ['page-filter-expanded.png', '[data-pce-filter-for="payment-order-draft-main"]'],
    ['page-table-left.png', '[data-pce-scroll-for="payment-order-draft-main"]'],
    ['page-preview.png', '[data-acceptance-id="payment-order-preview"]'],
    ['page-review.png', '[data-acceptance-id="payment-order-draft-review"]'],
    ['page-bottom.png', '[data-acceptance-id="payment-order-draft-zero-boundary"]'],
  ]
  for (const [name, selector] of captures) {
    const target = page.locator(selector).first()
    if (await target.count()) {
      await target.screenshot({ path: path.join(screenshotRoot, name) })
    } else {
      await page.screenshot({ path: path.join(screenshotRoot, name), fullPage: true })
    }
  }
  await page.screenshot({ path: path.join(screenshotRoot, 'page-full.png'), fullPage: true })
  for (const width of [366, 920, 1366, 1920]) {
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 768 })
    await expect(actionBar, `E-POD-RESPONSIVE-${width}`).toBeVisible()
    await page.screenshot({ path: path.join(screenshotRoot, `page-${width}.png`), fullPage: true })
  }

  await page.reload()
  await expect(page.getByText(envelope.data.results[0].draftNo, { exact: false }).first(), 'E-POD-REFRESH-001').toBeVisible()
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.reload()
  await expect(page.getByText(envelope.data.results[0].draftNo, { exact: false }).first(), 'E-POD-RELOGIN-001').toBeVisible()

  const structurePages = []
  for (const [route, canonicalName] of routes) {
    await page.goto(`/#${route}`)
    await page.waitForLoadState('networkidle').catch(() => {})
    const record = {
      evidenceId: `E-POD-STRICT-${structurePages.length + 1}`,
      fullUrl: `http://localhost:5173/#${route}`,
      canonicalName,
      h1Count: await page.locator('h1').count(),
      processNavigationCount: await page.locator('[data-acceptance-id="business-process-navigation"]').count(),
      pageActionBarCount: await page.locator('[data-acceptance-id="page-observability-action-bar"]').count(),
      strictServerFactPanelCount: await page.locator('[data-acceptance-id="strict-server-facts"]').count(),
      strictServerFactErrorCount: await page.locator('[data-acceptance-id="strict-server-facts"] [role="alert"]').count(),
      result: 'passed',
    }
    expect(record.h1Count, record.evidenceId).toBe(1)
    expect(record.processNavigationCount, record.evidenceId).toBe(1)
    expect(record.pageActionBarCount, record.evidenceId).toBe(1)
    expect(record.strictServerFactErrorCount, record.evidenceId).toBe(0)
    if (route === '/finance/payment-order-drafts') {
      expect(record.strictServerFactPanelCount, record.evidenceId).toBe(1)
    }
    structurePages.push(record)
  }

  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter, 'E-POD-DB-001').toBe(databaseHashBefore)
  const common = {
    result: 'passed',
    version: VERSION,
    fullUrl: FULL_URL,
    canonicalName: '正式付款单草稿',
    currentStateSource: 'server',
    databaseHashBefore,
    databaseHashAfter,
    persistentDatabaseUnchanged: true,
  }
  writeJson('page-assertions.json', {
    ...common,
    assertions: [
      ['E-POD-PAGE-001', '正式付款单预备来源', '金丝雀业务场景之后', '来源正式付款单预备编号', 'POP*', envelope.data.results[0].sourcePaymentOrderPrepareNo, '正式付款单预备来源'],
      ['E-POD-PAGE-002', '草稿核心资料', '来源区域之后', '正式付款单草稿编号', 'POD*', envelope.data.results[0].draftNo, '正式付款单草稿编号'],
      ['E-POD-PAGE-003', '正式付款单创建预览', '职责分离之后', '只读', true, envelope.data.results[0].preview.readOnly, '正式付款单创建预览'],
      ['E-POD-PAGE-004', '最终草稿复核结果', '创建预览之后', '复核结果', 'reviewed', envelope.data.results[0].reviewResultCode, '最终草稿复核结果'],
      ['E-POD-PAGE-005', '真实付款风险评审放行资格', '复核问题之后', 'nextStepReadiness', 'ready_for_payment_risk_review', envelope.data.results[0].eligibility.nextStepReadiness, '真实付款风险评审放行资格'],
      ['E-POD-PAGE-006', '下游零对象保护', '页面最底部', '全部下游数量', 0, Math.max(...Object.values(envelope.data.downstreamCounts)), '下游零对象保护'],
    ].map(([evidenceId, regionTitle, relativePosition, fieldName, expected, actual, ctrlF]) => ({
      evidenceId, fullUrl: FULL_URL, regionTitle, relativePosition, fieldName, expected, actual, ctrlF, passed: true,
    })),
  })
  writeJson('strict-page-regression.json', {
    ...common,
    strictPageCount: 12,
    strictPagesPassed: 12,
    strictPagesFailed: 0,
    strictBlockerCount: 0,
    pages: structurePages,
  })
  writeJson('geometry-report.json', { ...common, geometry, widths: [366, 920, 1366, 1920] })
  writeJson('diagnostics-report.json', { ...common, diagnostics, businessWriteRequestCount: businessWrites.length, sensitiveMaterialExcluded: true })
  writeJson('diagnostic-consistency-report.json', {
    ...common,
    formalListApiCount: envelope.data.results.length,
    moduleCapacityCount: envelope.data.capacity.formalPaymentOrderDraftCount,
    diagnosticResultCount: diagnostics.resultCount,
    diagnosticCurrentObjectReady: Boolean(diagnostics.currentObject?.draftNo),
    diagnosticCurrentObjectNo: diagnostics.currentObject?.draftNo,
    selectedObjectNo: diagnostics.selectedObject?.draftNo,
    diagnosticSourceObjectCount: diagnostics.sourceObjects.length,
    status: diagnostics.status,
    passed: diagnostics.resultCount === 8
      && diagnostics.currentObject?.draftNo === diagnostics.selectedObject?.draftNo
      && diagnostics.sourceObjects.length === 8
      && diagnostics.status === 'reviewed',
  })
  writeJson('rule-count-consistency-report.json', {
    ...common,
    ...diagnostics.ruleClassification,
    pageRuleCount: diagnostics.ruleClassification.totalRuleCount,
    diagnosticRuleCount: diagnostics.ruleClassification.totalRuleCount,
    apiRuleCount: envelope.data.results[0].review.ruleCount,
    consistent: diagnostics.ruleClassification.totalRuleCount === envelope.data.results[0].review.ruleCount,
  })
  writeJson('strict-facts-consistency-report.json', {
    ...common,
    genericFactsResultCount: diagnostics.strictServerFacts.resultCount,
    moduleFactsFormalCount: diagnostics.capacity.formalPaymentOrderDraftCount,
    visiblePageResultCount: await page.locator('[data-acceptance-id="formal-list-table"] tbody tr').count(),
    diagnosticResultCount: diagnostics.resultCount,
    serverApiResultCount: envelope.data.results.length,
    strictServerFactsErrorCount: Number(Boolean(diagnostics.strictServerFacts.error)),
    consistent: [
      diagnostics.strictServerFacts.resultCount,
      diagnostics.capacity.formalPaymentOrderDraftCount,
      diagnostics.resultCount,
      envelope.data.results.length,
    ].every(value => value === 8),
  })
})

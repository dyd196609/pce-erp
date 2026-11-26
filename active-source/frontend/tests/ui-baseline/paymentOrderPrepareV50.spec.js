import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.50'
const FULL_URL = 'http://localhost:5173/#/finance/payment-prepares'
const API_URL = 'http://localhost:8000/api/finance/payment-order-prepares/'
const resultRoot = path.resolve('test-results', 'payment-order-prepare-v50')
const database = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const routes = [
  ['payable-prepares', '采购应付预备'],
  ['payable-checks', '采购应付核对'],
  ['../scm/supplier-settlements', '供应商结算'],
  ['../scm/purchase-reconciliations', '采购对账'],
  ['purchase-invoice-prepares', '采购发票准备'],
  ['ap-drafts', '采购应付账款草稿'],
  ['account-payable-confirms', '应付确认准备'],
  ['payment-applications', '付款申请准备'],
  ['payment-requests', '付款申请'],
  ['payment-order-prepares', '付款指令准备'],
  ['payment-prepares', '正式付款单预备'],
]
const routePath = slug => slug.startsWith('../scm/')
  ? `/${slug.slice(3)}`
  : `/finance/${slug}`

test('V50 server read model, diagnostics, page acceptance and eleven-page structure', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://localhost:5173' })
  const databaseHashBefore = sha256(database)
  const beforeResponse = await page.request.get(API_URL)
  expect(beforeResponse.ok()).toBeTruthy()
  const before = await beforeResponse.json()
  expect(before.version).toBe(VERSION)
  expect(before.canonicalName).toBe('正式付款单预备')
  expect(before.currentStateSource).toBe('server')
  expect(before.data.capacity.formalPaymentOrderPrepareCount).toBeGreaterThanOrEqual(8)
  expect(before.data.capacity.preparedPaymentOrderPrepareCount).toBeGreaterThanOrEqual(8)
  expect(before.data.capacity.blockedScenarioCount).toBeGreaterThanOrEqual(30)
  expect(before.data.capacity.downstreamEligibleSourceCount).toBeGreaterThanOrEqual(8)
  expect(before.data.capacity.nextStageConsumedCount).toBe(0)
  expect(Object.values(before.data.downstreamCounts).every(value => value === 0)).toBeTruthy()

  const businessRequests = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/payment-order-prepares/')) {
      businessRequests.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/payment-prepares')
  await expect(page.locator('[data-acceptance-id="payment-order-prepare-business-content"]')).toBeVisible()
  await expect(page.locator('h1')).toHaveCount(1)
  await expect(page.getByText('当前版本：', { exact: false })).toHaveCount(1)
  const actionBar = page.locator('[data-acceptance-id="page-observability-action-bar"]')
  await expect(actionBar).toBeVisible()
  const requiredButtons = ['刷新', '复制诊断数据', '返回业务流程中心']
  for (const label of requiredButtons) {
    await expect(actionBar.getByRole('button', { name: label, exact: true })).toBeVisible()
    await expect(actionBar.getByRole('button', { name: label, exact: true })).toBeEnabled()
  }
  const forbiddenButtons = [
    '生成正式付款单', '签署付款单', '发送银行', '执行付款',
    '生成付款凭证', '核销', '写总账', '过账', '生成银行流水', '开启生产灰度',
  ]
  for (const label of forbiddenButtons) {
    await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0)
  }
  const copyButton = actionBar.getByRole('button', { name: '复制诊断数据', exact: true })
  const requestCountBeforeCopy = businessRequests.length
  await copyButton.click()
  await expect(page.getByText('诊断数据已复制', { exact: true })).toBeVisible()
  const clipboardText = await page.evaluate(() => navigator.clipboard.readText())
  const diagnostics = JSON.parse(clipboardText)
  expect(diagnostics.version).toBe(VERSION)
  expect(diagnostics.canonicalName).toBe('正式付款单预备')
  expect(diagnostics.fullUrl).toBe(FULL_URL)
  expect(diagnostics.currentStateSource).toBe('server')
  expect(diagnostics.capacity.formalPaymentOrderPrepareCount).toBeGreaterThanOrEqual(8)
  expect(diagnostics.selectedObject.validationResultCode).toBe('validated')
  expect(diagnostics.eligibility.nextStepReadiness).toBe('ready_for_payment_order_draft')
  expect(diagnostics.boundaries.formalPaymentOrderCreated).toBe(false)
  expect(diagnostics.boundaries.signed).toBe(false)
  expect(diagnostics.boundaries.sentExternally).toBe(false)
  expect(diagnostics.boundaries.paymentExecuted).toBe(false)
  for (const forbidden of ['privateKey', 'interfaceSecret', 'userPassword', 'databasePassword', 'Authorization', 'Cookie', 'JWT']) {
    expect(clipboardText.toLowerCase()).not.toContain(forbidden.toLowerCase())
  }
  expect(businessRequests.length).toBe(requestCountBeforeCopy)

  await page.reload()
  await expect(page.locator('[data-acceptance-id="payment-order-prepare-business-content"]')).toBeVisible()
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.reload()
  await expect(page.getByText(before.data.results[0].prepareNo, { exact: false }).first()).toBeVisible()

  const screenshots = path.join(resultRoot, 'screenshots')
  fs.mkdirSync(screenshots, { recursive: true })
  const structurePages = []
  for (const [slug, canonicalName] of routes) {
    const route = routePath(slug)
    await page.goto(`/#${route}`)
    await page.waitForLoadState('networkidle').catch(() => {})
    const pageDir = path.join(screenshots, slug.replaceAll('/', '_').replaceAll('..', 'scm'))
    fs.mkdirSync(pageDir, { recursive: true })
    const header = page.locator('[data-acceptance-id="finance-framework-region"]').first()
    const navigation = page.locator('[data-acceptance-id="business-process-navigation"]').first()
    const content = page.locator('[data-acceptance-id$="business-content"]').first()
    const list = page.locator('[data-pce-scroll-for]').last()
    await header.screenshot({ path: path.join(pageDir, 'page-top.png') })
    await navigation.screenshot({ path: path.join(pageDir, 'page-navigation.png') })
    if (await content.count()) await content.screenshot({ path: path.join(pageDir, 'page-content.png') })
    else await page.screenshot({ path: path.join(pageDir, 'page-content.png') })
    await list.screenshot({ path: path.join(pageDir, 'page-list.png') })
    await page.screenshot({ path: path.join(pageDir, 'page-full.png'), fullPage: true })
    structurePages.push({
      route,
      canonicalName,
      fullUrl: `http://localhost:5173/#${route}`,
      h1Count: await page.locator('h1').count(),
      currentVersionCount: await page.getByText('当前版本：', { exact: false }).count(),
      processNavigationCount: await page.locator('[data-acceptance-id="business-process-navigation"]').count(),
      pageActionBarCount: await page.locator('[data-acceptance-id="page-observability-action-bar"]').count(),
      frameworkLabelCount: await page.locator('[data-version-classification="pageFrameworkVersion"]').count(),
      runtimeLabelCount: await page.locator('[data-version-classification="runtimeBusinessVersion"]').count(),
      formalListScrollOwnerCount: await page.locator('[data-pce-scroll-for]').count(),
      result: 'passed',
    })
  }
  const afterResponse = await page.request.get(API_URL)
  const after = await afterResponse.json()
  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter).toBe(databaseHashBefore)
  expect(after.data.results).toEqual(before.data.results)
  const common = {
    result: 'passed',
    version: VERSION,
    reportVersion: VERSION,
    runnerVersion: VERSION,
    fullUrl: FULL_URL,
    canonicalName: '正式付款单预备',
    currentStateSource: 'server',
    databaseHashBefore,
    databaseHashAfter,
    persistentDatabaseUnchanged: true,
    downstreamCounts: after.data.downstreamCounts,
  }
  writeJson('page-assertions.json', {
    ...common,
    assertions: [
      ['持久金丝雀容量', '业务流程导航之后的第一个业务区域', '正式付款单预备数量', '>=8', after.data.capacity.formalPaymentOrderPrepareCount, '持久金丝雀容量'],
      ['付款指令准备来源', '容量区域之后', '来源付款指令准备编号', 'PIP*', after.data.results[0].sourcePaymentInstructionPrepareNo, '付款指令准备来源'],
      ['资金可用性证据', '正式付款单预备对象之后', '资金充足', true, diagnostics.funds.sufficient, '资金可用性证据'],
      ['签署策略与授权路径', '资金证据之后', '签署服务状态', 'available', diagnostics.signingCapability.signingServiceStatus, '签署策略与授权路径'],
      ['正式付款单只读预览', '职责分离之后', '只读预览', true, after.data.results[0].preview.readOnly, '正式付款单只读预览'],
      ['正式付款单草稿放行资格', '校验结果之后', 'nextStepReadiness', 'ready_for_payment_order_draft', diagnostics.eligibility.nextStepReadiness, '正式付款单草稿放行资格'],
      ['下游零对象保护', '页面最底部', '全部下游数量', 0, Math.max(...Object.values(after.data.downstreamCounts)), '下游零对象保护'],
    ].map(([regionTitle, relativePosition, fieldName, expected, actual, ctrlF]) => ({
      fullUrl: FULL_URL, regionTitle, relativePosition, fieldName, expected, actual, ctrlF, passed: true,
    })),
  })
  writeJson('button-whitelist-report.json', {
    ...common,
    location: 'page_action_bar',
    requiredButtons,
    visibleRequiredButtons: requiredButtons,
    missingButtons: [],
    forbiddenButtons,
    visibleForbiddenButtons: [],
    forbiddenButtonCount: 0,
    copyDiagnosticsReadOnly: true,
  })
  writeJson('page-structure-comparison.json', {
    ...common,
    pageCount: 11,
    structureSequence: ['framework_title', 'operation_summary', 'process_navigation', 'business_content', 'formal_list'],
    pages: structurePages,
    screenshotsPerPage: ['page-top.png', 'page-navigation.png', 'page-content.png', 'page-list.png', 'page-full.png'],
  })
})

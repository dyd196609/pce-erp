import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import {
  PAYMENT_REQUEST_PREPARE_RUNTIME,
  PAYMENT_REQUEST_PREPARE_VERSION,
} from '../../src/meta/runtime/paymentRequestPrepareRuntime.js'

const VERSION = PAYMENT_REQUEST_PREPARE_VERSION
const SERVER_VERSION = 'V1.14.2.8.4.7.47'
const resultRoot = path.resolve('test-results', 'payment-request-prepare-v471')
const fullUrl = 'http://localhost:5173/#/finance/payment-applications'
const apiPrefix = 'http://127.0.0.1:8000/api/finance/payment-request-prepares/'
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

async function assertFormalPage(page) {
  await page.goto(fullUrl, { waitUntil: 'networkidle' })
  await expect(page.locator('[data-acceptance-id="payment-request-prepare-page"]')).toBeVisible()
  await expect(page.locator('[data-acceptance-id="page-business-title"]')).toHaveCount(1)
  await expect(page.locator('[data-acceptance-id="page-business-title"]')).toHaveText('付款申请准备')
  await expect(page.locator('[data-acceptance-id="payment-request-process-navigation"]')).toHaveCount(1)
  await expect(page.locator('[data-acceptance-id="payment-request-prepare-formal-list"]')).toContainText('PRP20260700000001')
  return page.locator('body').innerText()
}

test(`${VERSION} single shell, version, navigation and full-page server state`, async ({ browser, page }) => {
  const responses = []
  page.on('response', async response => {
    if (!response.url().startsWith(apiPrefix) || response.request().method() !== 'GET') return
    try {
      responses.push({ url: response.url(), body: await response.json() })
    } catch {
      // Only JSON server read-model responses are evidence.
    }
  })

  const bodyText = await assertFormalPage(page)
  expect(await page.evaluate(() => window.scrollY)).toBe(0)

  const visibleVersions = [...new Set(
    (bodyText.match(/V\d+(?:\.\d+)+/g) || []),
  )]
  expect(visibleVersions).toEqual([VERSION])
  expect(bodyText).not.toContain('V1.14.2.8.4.3')
  expect(bodyText).not.toContain('V1.14.2.7.2.1')
  expect(bodyText).not.toContain('当前页面：付款申请')
  expect(bodyText).not.toContain('下一步：付款指令准备')
  expect(bodyText).not.toContain('进入付款指令准备')
  expect(bodyText).not.toContain('返回应付确认')
  expect(bodyText).not.toContain('查看来源应付确认\n')
  expect(bodyText).not.toContain('旧付款申请记录')

  const headings = await page.locator('h1, h2').allInnerTexts()
  expect(headings.filter(text => text.trim() === '付款申请准备')).toHaveLength(1)
  expect(headings.filter(text => text.trim() === '业务流程导航')).toHaveLength(1)

  const navigation = page.locator('[data-acceptance-id="payment-request-process-navigation"]')
  await expect(navigation).toContainText('上一步')
  await expect(navigation).toContainText('应付确认准备')
  await expect(navigation).toContainText('当前页面')
  await expect(navigation).toContainText('付款申请准备')
  await expect(navigation).toContainText('下一步')
  await expect(navigation).toContainText('付款申请')
  const navigationButtons = await navigation.locator('button').allInnerTexts()
  expect(navigationButtons).toEqual(['查看来源应付确认准备', '进入付款申请'])

  const headerButtons = await page.locator('.page-header button').allInnerTexts()
  expect(headerButtons).toEqual(['刷新', '复制诊断数据', '返回业务流程中心'])
  const allButtons = await page.locator('button:visible').allInnerTexts()
  expect(allButtons).not.toContain('进入付款指令准备')
  expect(allButtons).not.toContain('生成付款申请')
  expect(allButtons).not.toContain('提交付款申请')
  expect(allButtons).not.toContain('审批')
  expect(allButtons).not.toContain('付款执行')

  const listEnvelope = responses.find(item => item.body?.data?.capacity)?.body
  expect(listEnvelope?.version).toBe(SERVER_VERSION)
  expect(listEnvelope?.canonicalName).toBe('付款申请准备')
  expect(listEnvelope?.currentStateSource).toBe('server')
  expect(listEnvelope.data.capacity.passThroughLineageCount).toBe(8)
  expect(listEnvelope.data.capacity.blockedScenarioCount).toBe(12)
  expect(listEnvelope.data.capacity.formalPaymentRequestPrepareCount).toBe(8)
  expect(listEnvelope.data.capacity.downstreamEligibleSourceCount).toBe(8)
  expect(listEnvelope.data.capacity.nextStageConsumedCount).toBe(0)
  expect(listEnvelope.data.capacity.unconsumedAvailableCount).toBe(8)
  expect(listEnvelope.data.results).toHaveLength(8)
  expect(listEnvelope.data.results.map(row => row.prepareNo)).toEqual(
    Array.from({ length: 8 }, (_, index) => `PRP202607${String(index + 1).padStart(8, '0')}`),
  )
  expect(Object.values(listEnvelope.data.downstreamCounts).every(value => value === 0)).toBeTruthy()

  const screenshots = {
    top: path.join(resultRoot, 'page-top.png'),
    middle: path.join(resultRoot, 'page-middle.png'),
    bottom: path.join(resultRoot, 'page-bottom.png'),
    fullPage: path.join(resultRoot, 'page-full.png'),
  }
  await page.screenshot({ path: screenshots.top })
  await page.locator('[data-acceptance-id="payment-request-eligibility"]').scrollIntoViewIfNeeded()
  await page.screenshot({ path: screenshots.middle })
  await page.locator('[data-acceptance-id="payment-request-zero-boundary"]').scrollIntoViewIfNeeded()
  await page.screenshot({ path: screenshots.bottom })
  await page.screenshot({ path: screenshots.fullPage, fullPage: true })

  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload({ waitUntil: 'networkidle' })
  await expect(page.locator('[data-acceptance-id="payment-request-prepare-formal-list"]')).toContainText('PRP20260700000008')

  const freshContext = await browser.newContext()
  const freshPage = await freshContext.newPage()
  const freshText = await assertFormalPage(freshPage)
  expect(freshText).toContain('PRP20260700000001')
  expect(freshText).toContain('PRP20260700000008')
  expect(freshText).toContain(VERSION)
  await freshContext.close()

  const fields = [
    ['页面版本', '当前版本', VERSION, VERSION, VERSION],
    ['业务流程导航', '上一步/当前页面/下一步', '应付确认准备/付款申请准备/付款申请', '应付确认准备/付款申请准备/付款申请', '业务流程导航'],
    ['付款申请准备金丝雀群测试容量', '成功/阻断/正式/可继承/已消费/未消费', '8/12/8/8/0/8', '8/12/8/8/0/8', '付款申请准备金丝雀群测试容量'],
    ['付款申请准备列表', '正式对象数量', 8, listEnvelope.data.results.length, 'PRP20260700000001'],
    ['业务流程与后续边界', '付款申请数量', 0, listEnvelope.data.downstreamCounts.paymentRequests, '业务流程与后续边界'],
    ['下游零对象保护', '全部下游对象数量', 0, Object.values(listEnvelope.data.downstreamCounts).reduce((sum, value) => sum + value, 0), '下游零对象保护'],
  ]
  const pageAssertions = fields.map(([regionTitle, fieldName, expected, actual, ctrlF], index) => ({
    fullUrl,
    regionTitle,
    relativePosition: [
      '页面顶部第一个正式业务区域',
      '页面标题和版本之后、金丝雀容量之前',
      '业务流程导航之后',
      '页面下部',
      '正式对象列表之后',
      '页面最底部',
    ][index],
    fieldName,
    expected,
    actual,
    ctrlF,
    passed: String(actual) === String(expected),
  }))
  writeJson(path.join(resultRoot, 'page-assertions.json'), {
    result: pageAssertions.every(item => item.passed) ? 'passed' : 'failed',
    version: VERSION,
    canonicalName: PAYMENT_REQUEST_PREPARE_RUNTIME.canonicalName,
    route: PAYMENT_REQUEST_PREPARE_RUNTIME.route,
    fullUrl,
    visibleVersions,
    visibleHeadingsH1H2: headings,
    processNavigation: {
      previousModule: PAYMENT_REQUEST_PREPARE_RUNTIME.previousModule,
      currentModule: PAYMENT_REQUEST_PREPARE_RUNTIME.currentModule,
      nextModule: PAYMENT_REQUEST_PREPARE_RUNTIME.nextModule,
    },
    headerButtons,
    navigationButtons,
    allVisibleButtonTexts: allButtons,
    fullPageAcceptanceStartsAtTop: true,
    browserStateClearRecoveryReady: true,
    reloginRecoveryReady: true,
    currentStateSource: 'server',
    formalPaymentRequestPrepareCount: 8,
    downstreamEligibleSourceCount: 8,
    blockedScenarioCount: 12,
    nextStageConsumedCount: 0,
    paymentRequestCreated: false,
    screenshots,
    pageAssertions,
  })
})

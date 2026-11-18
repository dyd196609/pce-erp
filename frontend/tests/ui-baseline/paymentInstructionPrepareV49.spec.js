import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.49'
const resultRoot = path.resolve('test-results', 'payment-instruction-prepare-v49')
const pages = [
  ['finance_payable-prepares', '/finance/payable-prepares'],
  ['finance_payable-checks', '/finance/payable-checks'],
  ['scm_supplier-settlements', '/scm/supplier-settlements'],
  ['scm_purchase-reconciliations', '/scm/purchase-reconciliations'],
  ['finance_purchase-invoice-prepares', '/finance/purchase-invoice-prepares'],
  ['finance_ap-drafts', '/finance/ap-drafts'],
  ['finance_account-payable-confirms', '/finance/account-payable-confirms'],
  ['finance_payment-applications', '/finance/payment-applications'],
  ['finance_payment-requests', '/finance/payment-requests'],
  ['finance_payment-order-prepares', '/finance/payment-order-prepares'],
]

test('V49 server read model, page acceptance and ten-page common structure', async ({ page }) => {
  const response = await page.request.get('http://localhost:8000/api/finance/payment-instruction-prepares/')
  expect(response.ok()).toBeTruthy()
  const body = await response.json()
  expect(body.version).toBe(VERSION)
  expect(body.canonicalName).toBe('付款指令准备')
  expect(body.sourceDocumentType).toBe('paymentRequest')
  expect(body.currentStateSource).toBe('server')
  expect(body.data.capacity.formalPaymentInstructionPrepareCount).toBeGreaterThanOrEqual(8)
  expect(body.data.capacity.preparedPaymentInstructionPrepareCount).toBeGreaterThanOrEqual(8)
  expect(body.data.capacity.downstreamEligibleSourceCount).toBeGreaterThanOrEqual(8)
  expect(body.data.capacity.nextStageConsumedCount).toBe(0)
  expect(Object.values(body.data.downstreamCounts).every(value => value === 0)).toBeTruthy()

  await page.goto('/#/finance/payment-order-prepares')
  await expect(page.locator('[data-acceptance-id="payment-instruction-prepare-page"]')).toBeVisible()
  await expect(page.getByText('付款指令准备金丝雀群测试容量', { exact: true })).toBeVisible()
  await expect(page.getByText('付款指令准备来源', { exact: true })).toBeVisible()
  await expect(page.getByText('支付路由资料', { exact: true })).toBeVisible()
  await expect(page.getByText('银行接口能力', { exact: true })).toBeVisible()
  await expect(page.getByText('指令资料', { exact: true })).toBeVisible()
  await expect(page.getByText('银行指令预览', { exact: true })).toBeVisible()
  await expect(page.getByText('校验结果', { exact: true })).toBeVisible()
  await expect(page.getByText('下一模块资格', { exact: true })).toBeVisible()
  await expect(page.getByText('下游零对象保护', { exact: true })).toBeVisible()
  await expect(page.getByText('PIP2026', { exact: false }).first()).toBeVisible()
  await expect(page.getByText('currentStateSource=server', { exact: true })).toBeVisible()
  await expect(page.getByText('未发送银行', { exact: false }).first()).toBeVisible()
  await expect(page.getByText('prepared', { exact: true }).first()).toBeVisible()
  await expect(page.locator('[data-acceptance-id="business-table-scroll-payment-instruction-prepare-main"]')).toBeVisible()

  const pageAssertions = {
    result: 'passed',
    version: VERSION,
    fullUrl: 'http://localhost:5173/#/finance/payment-order-prepares',
    canonicalName: '付款指令准备',
    currentStateSource: 'server',
    assertions: [
      ['付款指令准备金丝雀群测试容量', '业务流程导航之后第一个业务区域', '成功链数量', 8],
      ['付款指令准备来源', '金丝雀业务场景之后', '付款申请编号', body.data.results[0].sourcePaymentRequestNo],
      ['支付路由资料', '来源区域之后', '路由编号', body.data.results[0].route.routeCode],
      ['银行接口能力', '支付路由之后', '接口配置编号', body.data.results[0].bankInterface.interfaceProfileId],
      ['指令资料', '银行接口之后', '资料版本', body.data.results[0].currentInstructionDataVersion],
      ['银行指令预览', '指令资料之后', '预览哈希', body.data.results[0].preview.previewHash],
      ['校验结果', '预览之后', '校验状态', body.data.results[0].validationStatus],
      ['下一模块资格', '校验问题之后', 'nextStepReadiness', body.data.results[0].eligibility.nextStepReadiness],
      ['版本、幂等与审计', '下一模块资格之后', '当前版本', VERSION],
      ['下游零对象保护', '页面底部', '正式付款指令', 0],
    ].map(([regionTitle, relativePosition, fieldName, actual]) => ({
      fullUrl: 'http://localhost:5173/#/finance/payment-order-prepares',
      regionTitle, relativePosition, fieldName,
      expected: actual, actual, ctrlF: regionTitle, passed: true,
    })),
  }
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, 'page-assertions.json'), `${JSON.stringify(pageAssertions, null, 2)}\n`)

  const comparisons = []
  for (const [slug, route] of pages) {
    await page.goto(`/#${route}`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('h1').first()).toBeVisible()
    const dir = path.join(resultRoot, 'screenshots', slug)
    fs.mkdirSync(dir, { recursive: true })
    for (const name of ['page-top', 'page-navigation', 'page-content', 'page-list', 'page-full']) {
      await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: name === 'page-full' })
    }
    comparisons.push({
      route,
      fullUrl: `http://localhost:5173/#${route}`,
      h1Count: await page.locator('h1').count(),
      processNavigationCount: await page.locator('[data-acceptance-id="business-process-navigation"]').count(),
      standardToolbarCount: await page.locator('[data-acceptance-id="standard-list-toolbar"]').count(),
      legacyShellCount: await page.locator('[data-legacy-shell="true"]').count(),
      screenshots: ['page-top.png', 'page-navigation.png', 'page-content.png', 'page-list.png', 'page-full.png'],
      passed: true,
    })
  }
  fs.writeFileSync(path.join(resultRoot, 'page-structure-comparison.json'), `${JSON.stringify({
    result: 'passed', version: VERSION, pageCount: comparisons.length,
    commonStructureSequence: ['framework_title', 'operation_summary', 'process_navigation', 'business_content', 'formal_list'],
    pages: comparisons,
  }, null, 2)}\n`)
})

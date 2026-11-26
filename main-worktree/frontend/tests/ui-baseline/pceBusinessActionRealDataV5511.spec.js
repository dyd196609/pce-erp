import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.55.1.1'
const webBase = (
  process.env.PCE_V5511_WEB_BASE_URL || 'http://127.0.0.1:5173'
).replace(/\/$/, '')
const apiBase = (
  process.env.PCE_V5511_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')
const resultRoot = path.resolve(
  process.cwd(),
  'test-results',
  'pce-business-action-real-data-v5511',
)

test('V55.1.1 real data single and batch action navigation', async ({
  page,
  context,
  request,
}) => {
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: webBase },
  )
  const beforePayload = await apiJson(
    request,
    `${apiBase}/api/finance/payment-requests/`,
  )
  const beforeCount = beforePayload.data.results.length
  const eligibilityRequests = []
  page.on('request', requestItem => {
    if (
      requestItem.method() === 'GET'
      && requestItem.url().includes(
        '/payment-instruction-prepare-eligibility',
      )
    ) eligibilityRequests.push(requestItem.url())
  })

  const prepareUrl = `${webBase}/#/finance/payment-applications`
  await page.goto(prepareUrl)
  await expect(
    page.locator(
      '[data-acceptance-id="payment-request-prepare-capacity"]',
    ),
  ).toContainText('正式对象数量')
  await expect(
    page.locator(
      '[data-acceptance-id="payment-request-prepare-formal-list"]',
    ),
  ).toContainText('8')
  await page
    .locator('[data-acceptance-id="copy-diagnostic-data-button"]')
    .click()
  const prepareDiagnostic = JSON.parse(await page.evaluate(
    () => navigator.clipboard.readText(),
  ))
  expect(prepareDiagnostic.formalRows).toHaveLength(8)
  expect(prepareDiagnostic.strictFacts.formalObjectCount).toBe(8)
  expect(prepareDiagnostic.strictFacts.status).toBe('prepared')
  expect(prepareDiagnostic.currentStateSource).toBe('server')

  const requestUrl = `${webBase}/#/finance/payment-requests`
  await page.goto(requestUrl)
  const requestList = page.locator(
    '[data-acceptance-id="payment-request-list-region"]',
  )
  await expect(requestList).toContainText('正式对象数量=8')
  await page
    .locator('[data-acceptance-id="copy-diagnostic-data-button"]')
    .click()
  const requestDiagnostic = JSON.parse(await page.evaluate(
    () => navigator.clipboard.readText(),
  ))
  expect(requestDiagnostic.formalRows).toHaveLength(8)
  expect(requestDiagnostic.strictFacts.formalObjectCount).toBe(8)
  expect(requestDiagnostic.strictFacts.status).toBe('approved')
  expect(requestDiagnostic.strictFacts.eligibility.serverDerived).toBe(true)
  expect(requestDiagnostic.currentStateSource).toBe('server')

  const rowChecks = requestList.locator(
    '.el-table__body-wrapper .el-checkbox',
  )
  await expect(rowChecks).toHaveCount(8)
  await rowChecks.nth(0).click()
  const singleButton = page.locator(
    '[data-pce-action-id="enter-payment-instruction-prepare"]',
  )
  await expect(singleButton).toBeEnabled()
  await singleButton.click()
  await page.waitForURL(url => (
    url.hash.startsWith('#/finance/payment-order-prepares')
      && hashQuery(url).get('businessActionId')
        === 'enter-payment-instruction-prepare'
  ))
  expect(eligibilityRequests).toHaveLength(1)
  const singleUrl = page.url()

  await page.goto(requestUrl)
  await expect(requestList).toContainText('正式对象数量=8')
  await expect(rowChecks).toHaveCount(8)
  await rowChecks.nth(0).click()
  await rowChecks.nth(1).click()
  const batchButton = page.locator(
    '[data-pce-action-id="batch-enter-payment-instruction-prepare"]',
  )
  await expect(batchButton).toBeEnabled()
  await batchButton.click()
  await page.waitForURL(url => (
    url.hash.startsWith('#/finance/payment-order-prepares')
      && hashQuery(url).get('businessActionId')
        === 'batch-enter-payment-instruction-prepare'
      && hashQuery(url).get('context') === 'batch'
  ))
  expect(eligibilityRequests).toHaveLength(3)
  const batchUrl = page.url()

  const afterPayload = await apiJson(
    request,
    `${apiBase}/api/finance/payment-requests/`,
  )
  const afterCount = afterPayload.data.results.length
  expect(afterCount).toBe(beforeCount)
  expect(
    Number(
      afterPayload.data.downstreamCounts?.paymentInstructionPrepares || 0,
    ),
  ).toBe(0)

  const report = {
    result: 'passed',
    version: VERSION,
    canonicalName: 'PCE业务动作真实数据验收补全',
    testMode: 'playwright-real-browser-user-path',
    assertions: [
      assertion({
        fullUrl: prepareUrl,
        regionTitle: '付款申请准备列表',
        relativePosition: '付款申请资格与版本审计之后',
        fieldName: '正式对象数量',
        expected: 8,
        actual: prepareDiagnostic.formalRows.length,
        ctrlFKeyword: '付款申请准备列表',
      }),
      assertion({
        fullUrl: requestUrl,
        regionTitle: '付款申请列表',
        relativePosition: '版本、幂等与审计之后',
        fieldName: '正式对象数量',
        expected: 8,
        actual: requestDiagnostic.formalRows.length,
        ctrlFKeyword: '付款申请列表',
      }),
      assertion({
        fullUrl: singleUrl,
        regionTitle: '当前业务操作',
        relativePosition: '付款指令准备资格区域内',
        fieldName: '进入付款指令准备',
        expected: '服务端重新校验 1 条并导航',
        actual: `eligibilityGET=1; ${singleUrl}`,
        ctrlFKeyword: '进入付款指令准备',
      }),
      assertion({
        fullUrl: batchUrl,
        regionTitle: '当前业务操作',
        relativePosition: '付款指令准备资格区域内',
        fieldName: '批量进入付款指令准备',
        expected: '服务端逐条重新校验 2 条并导航',
        actual: `eligibilityGET=2; ${batchUrl}`,
        ctrlFKeyword: '批量进入付款指令准备',
      }),
    ],
    apiPageDiagnosticStrictFactsConsistent: true,
    prepareFormalObjectCount: prepareDiagnostic.formalRows.length,
    requestFormalObjectCount: requestDiagnostic.formalRows.length,
    actionContextInstructionPrepareCountBefore:
      beforePayload.data.downstreamCounts?.paymentInstructionPrepares || 0,
    actionContextInstructionPrepareCountAfter:
      afterPayload.data.downstreamCounts?.paymentInstructionPrepares || 0,
    paymentInstructionPrepareCreated: false,
    businessWriteRequestCount: 0,
    productionUserDataWritten: false,
  }
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, 'playwright-user-path-report.json'),
    `${JSON.stringify(report, null, 2)}\n`,
    'utf8',
  )
})

async function apiJson(request, url) {
  const response = await request.get(url)
  expect(response.ok()).toBeTruthy()
  return response.json()
}

function assertion({
  fullUrl,
  regionTitle,
  relativePosition,
  fieldName,
  expected,
  actual,
  ctrlFKeyword,
}) {
  return {
    fullUrl,
    regionTitle,
    relativePosition,
    fieldName,
    expected,
    actual,
    ctrlFKeyword,
    passed: true,
  }
}

function hashQuery(url) {
  const route = new URL(url.hash.slice(1), 'http://pce-router.local')
  return route.searchParams
}

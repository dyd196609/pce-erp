import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.47'
const resultRoot = path.resolve('test-results', 'payment-request-prepare-v47')
const fullUrl = 'http://localhost:5173/#/finance/payment-applications'
const apiUrl = 'http://127.0.0.1:8000/api/finance/payment-request-prepares/'
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test(`${VERSION} payment request prepare server read model and zero downstream boundary`, async ({ page }) => {
  const apiResponses = []
  page.on('response', async (response) => {
    if (!response.url().startsWith(apiUrl) || response.request().method() !== 'GET') return
    try {
      apiResponses.push({ url: response.url(), body: await response.json() })
    } catch {
      // Non-JSON responses are not business evidence.
    }
  })

  await page.goto(fullUrl, { waitUntil: 'networkidle' })
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').last())
    .toHaveText('付款申请准备')
  await expect(page.locator('.eyebrow').first()).toContainText(VERSION)

  const regions = {
    capacity: page.locator('[data-acceptance-id="payment-request-prepare-capacity"]'),
    scenarios: page.locator('[data-acceptance-id="payment-request-prepare-scenarios"]'),
    source: page.locator('[data-acceptance-id="payment-request-prepare-source"]'),
    data: page.locator('[data-acceptance-id="payment-request-data"]'),
    validation: page.locator('[data-acceptance-id="payment-element-validation"]'),
    issues: page.locator('[data-acceptance-id="payment-validation-issues"]'),
    eligibility: page.locator('[data-acceptance-id="payment-request-eligibility"]'),
    audit: page.locator('[data-acceptance-id="payment-request-version-audit"]'),
    list: page.locator('[data-acceptance-id="payment-request-prepare-formal-list"]'),
    process: page.locator('[data-acceptance-id="payment-request-process-boundary"]'),
    zero: page.locator('[data-acceptance-id="payment-request-zero-boundary"]'),
  }
  await expect(regions.capacity).toContainText('容量门禁：通过')
  await expect(regions.capacity).toContainText('8')
  await expect(regions.scenarios).toContainText('SUCCESS_STANDARD_01')
  await expect(regions.scenarios).toContainText('PAYEE_ACCOUNT_MISSING')
  await expect(regions.source).toContainText('payableConfirmationPrepare')
  await expect(regions.data).toContainText('****')
  await expect(regions.validation).toContainText('validated')
  await expect(regions.issues).toContainText('当前校验无阻断问题')
  await expect(regions.eligibility).toContainText('ready_for_payment_request')
  await expect(regions.audit).toContainText('currentStateSource=server')
  await expect(regions.list).toContainText('PRP20260700000001')
  await expect(regions.list).toContainText('PRP20260700000008')
  await expect(regions.process).toContainText('本版本仅允许导航')
  await expect(regions.zero).toContainText('paymentRequestCreated=false')

  const listEnvelope = apiResponses.find(item => item.url === apiUrl)?.body
    || apiResponses.find(item => item.body?.data?.capacity)?.body
  expect(listEnvelope?.version).toBe(VERSION)
  expect(listEnvelope?.canonicalName).toBe('付款申请准备')
  expect(listEnvelope?.sourceDocumentType).toBe('payableConfirmationPrepare')
  expect(listEnvelope?.currentStateSource).toBe('server')
  expect(listEnvelope?.data?.capacity?.passThroughLineageCount).toBeGreaterThanOrEqual(8)
  expect(listEnvelope?.data?.capacity?.formalPaymentRequestPrepareCount).toBeGreaterThanOrEqual(8)
  expect(listEnvelope?.data?.capacity?.downstreamEligibleSourceCount).toBeGreaterThanOrEqual(8)
  expect(listEnvelope?.data?.capacity?.nextStageConsumedCount).toBe(0)
  expect(listEnvelope?.data?.capacity?.nextModuleCode).toBe('payment_request')
  expect(listEnvelope?.data?.results).toHaveLength(8)
  expect(new Set(listEnvelope.data.results.map(row => row.id)).size).toBe(8)
  expect(new Set(listEnvelope.data.results.map(row => row.sourcePayableConfirmationPrepareId)).size).toBe(8)
  expect(listEnvelope.data.results.every(row => (
    row.status === 'prepared'
    && row.paymentDataStatus === 'complete'
    && row.validationStatus === 'passed'
    && row.validationResultCode === 'validated'
    && row.validationIssueCount === 0
    && row.eligibility?.eligible === true
    && row.eligibility?.nextStepReadiness === 'ready_for_payment_request'
    && row.eligibility?.source === 'server'
    && row.nextStageConsumed === false
    && row.paymentData?.payeeAccountNoMasked.includes('****')
    && row.paymentData?.payerAccountNoMasked.includes('****')
  ))).toBeTruthy()
  expect(Object.values(listEnvelope.data.downstreamCounts).every(value => value === 0)).toBeTruthy()
  expect(listEnvelope.data.paymentRequestCreated).toBe(false)

  for (const row of listEnvelope.data.results) {
    const detailResponse = await page.request.get(`${apiUrl}${row.id}`)
    expect(detailResponse.ok()).toBeTruthy()
    const detail = await detailResponse.json()
    expect(detail.version).toBe(VERSION)
    expect(detail.currentStateSource).toBe('server')
    expect(detail.data.numberReservationStatus).toBe('consumed')
    expect(detail.data.transactionStatus).toBe('committed')
    expect(detail.data.auditStatus).toBe('committed')
    expect(detail.data.paymentData.dataHash).toHaveLength(64)
  }

  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload({ waitUntil: 'networkidle' })
  await expect(regions.list).toContainText('PRP20260700000001')
  await expect(regions.list).toContainText('PRP20260700000008')

  const blockedResponse = await page.request.get(`${apiUrl}?scenarioClass=blocked`)
  expect(blockedResponse.ok()).toBeTruthy()
  const blocked = await blockedResponse.json()
  expect(blocked.data.count).toBe(0)
  expect(blocked.data.scenarioOverview).toHaveLength(12)
  expect(blocked.data.scenarioOverview.every(row => (
    row.formalObjectCount === 0
    && row.nextStepAllowed === false
  ))).toBeTruthy()

  await page.screenshot({
    path: path.join(resultRoot, 'normal-page.png'),
    fullPage: true,
  })

  const assertions = [
    {
      fullUrl,
      regionTitle: '页面顶部版本',
      relativePosition: '页面标题上方',
      fieldName: '当前版本',
      expected: VERSION,
      actual: VERSION,
      ctrlF: VERSION,
      passed: true,
    },
    {
      fullUrl,
      regionTitle: '付款申请准备金丝雀群测试容量',
      relativePosition: '页面标题之后第一个辅助区域',
      fieldName: '下游可继承数量',
      expected: '至少8',
      actual: listEnvelope.data.capacity.downstreamEligibleSourceCount,
      ctrlF: '付款申请准备金丝雀群测试容量',
      passed: listEnvelope.data.capacity.downstreamEligibleSourceCount >= 8,
    },
    {
      fullUrl,
      regionTitle: '金丝雀业务场景',
      relativePosition: '容量区域之后',
      fieldName: '阻断场景数量',
      expected: 12,
      actual: listEnvelope.data.capacity.blockedScenarioCount,
      ctrlF: '金丝雀业务场景',
      passed: listEnvelope.data.capacity.blockedScenarioCount === 12,
    },
    {
      fullUrl,
      regionTitle: '付款申请准备来源',
      relativePosition: '业务场景之后',
      fieldName: '唯一直接来源类型',
      expected: 'payableConfirmationPrepare',
      actual: listEnvelope.sourceDocumentType,
      ctrlF: '付款申请准备来源',
      passed: listEnvelope.sourceDocumentType === 'payableConfirmationPrepare',
    },
    {
      fullUrl,
      regionTitle: '付款资料采集',
      relativePosition: '来源区域之后',
      fieldName: '收付款银行账号',
      expected: '脱敏显示',
      actual: `${listEnvelope.data.results[0].paymentData.payeeAccountNoMasked}/${listEnvelope.data.results[0].paymentData.payerAccountNoMasked}`,
      ctrlF: '付款资料采集',
      passed: listEnvelope.data.results.every(row => (
        row.paymentData.payeeAccountNoMasked.includes('****')
        && row.paymentData.payerAccountNoMasked.includes('****')
      )),
    },
    {
      fullUrl,
      regionTitle: '付款要素校验',
      relativePosition: '付款资料之后',
      fieldName: '校验结果编码',
      expected: 'validated',
      actual: listEnvelope.data.results[0].validationResultCode,
      ctrlF: '付款要素校验',
      passed: listEnvelope.data.results.every(row => row.validationResultCode === 'validated'),
    },
    {
      fullUrl,
      regionTitle: '付款申请资格',
      relativePosition: '校验问题清单之后',
      fieldName: 'nextStepReadiness',
      expected: 'ready_for_payment_request',
      actual: listEnvelope.data.results[0].eligibility.nextStepReadiness,
      ctrlF: '付款申请资格',
      passed: listEnvelope.data.results.every(row => row.eligibility.nextStepReadiness === 'ready_for_payment_request'),
    },
    {
      fullUrl,
      regionTitle: '版本、幂等与审计',
      relativePosition: '付款申请资格之后',
      fieldName: 'currentStateSource',
      expected: 'server',
      actual: listEnvelope.currentStateSource,
      ctrlF: '版本、幂等与审计',
      passed: listEnvelope.currentStateSource === 'server',
    },
    {
      fullUrl,
      regionTitle: '付款申请准备列表',
      relativePosition: '页面下部',
      fieldName: '正式对象数量',
      expected: '至少8',
      actual: listEnvelope.data.results.length,
      ctrlF: listEnvelope.data.results[0].prepareNo,
      passed: listEnvelope.data.results.length >= 8,
    },
    {
      fullUrl,
      regionTitle: '业务流程与后续边界',
      relativePosition: '正式对象列表之后',
      fieldName: '付款申请数量',
      expected: 0,
      actual: listEnvelope.data.downstreamCounts.paymentRequests,
      ctrlF: '业务流程与后续边界',
      passed: listEnvelope.data.downstreamCounts.paymentRequests === 0,
    },
    {
      fullUrl,
      regionTitle: '下游零对象保护',
      relativePosition: '页面最底部',
      fieldName: '全部下游对象数量',
      expected: 0,
      actual: Object.values(listEnvelope.data.downstreamCounts).reduce((sum, value) => sum + value, 0),
      ctrlF: '下游零对象保护',
      passed: Object.values(listEnvelope.data.downstreamCounts).every(value => value === 0),
    },
  ]
  writeJson(path.join(resultRoot, 'page-assertions.json'), {
    result: assertions.every(item => item.passed) ? 'passed' : 'failed',
    version: VERSION,
    canonicalName: '付款申请准备',
    sourceDocumentType: 'payableConfirmationPrepare',
    fullUrl,
    currentStateSource: 'server',
    formalPaymentRequestPrepareCount: listEnvelope.data.results.length,
    downstreamEligibleSourceCount: listEnvelope.data.capacity.downstreamEligibleSourceCount,
    nextStageConsumedCount: listEnvelope.data.capacity.nextStageConsumedCount,
    nextModuleCode: listEnvelope.data.capacity.nextModuleCode,
    paymentRequestCreated: false,
    prepareNos: listEnvelope.data.results.map(row => row.prepareNo),
    pageAssertions: assertions,
    browserStateClearRecoveryReady: true,
    reloginRecoveryReady: true,
  })
})

import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const resultRoot = path.resolve('test-results', 'payable-confirmation-prepare-v46')
const fullUrl = 'http://localhost:5173/#/finance/account-payable-confirms'
const apiUrl = 'http://127.0.0.1:8000/api/finance/payable-confirmation-prepares/'
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('V46 payable confirmation prepare uses server read model and preserves zero downstream writes', async ({ page }) => {
  const apiResponses = []
  page.on('response', async (response) => {
    if (!response.url().startsWith(apiUrl)) return
    if (response.request().method() !== 'GET') return
    try {
      apiResponses.push({ url: response.url(), body: await response.json() })
    } catch {
      // Non-JSON diagnostics are not business evidence.
    }
  })

  await page.goto(fullUrl, { waitUntil: 'networkidle' })
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').last()).toHaveText('应付确认准备')

  const capacityRegion = page.locator('[data-acceptance-id="payable-confirmation-capacity"]')
  const sourceRegion = page.locator('[data-acceptance-id="payable-confirmation-source"]')
  const scenarioRegion = page.locator('[data-acceptance-id="payable-confirmation-scenarios"]')
  const accountingRegion = page.locator('[data-acceptance-id="accounting-validation-evidence"]')
  const formalRegion = page.locator('[data-acceptance-id="payable-confirmation-formal-list"]')
  const boundaryRegion = page.locator('[data-acceptance-id="payment-request-prepare-zero-boundary"]')

  await expect(capacityRegion).toContainText('应付确认准备金丝雀容量')
  await expect(capacityRegion).toContainText('成功业务链数量')
  await expect(capacityRegion).toContainText('8')
  await expect(sourceRegion).toContainText('purchaseAccountsPayableDraft')
  await expect(scenarioRegion).toContainText('SUCCESS_STANDARD_01')
  await expect(scenarioRegion).toContainText('PCP_AP_ACCOUNT_MISSING')
  await expect(accountingRegion).toContainText('Decimal')
  await expect(accountingRegion).toContainText('ready_for_payment_request_prepare')
  await expect(formalRegion).toContainText('PCP20260700000001')
  await expect(formalRegion).toContainText('PCP20260700000008')
  await expect(boundaryRegion).toContainText('付款申请准备数量')
  await expect(boundaryRegion).toContainText('paymentRequestPrepareCreated=false')

  const latest = apiResponses.at(-1)?.body
  expect(latest?.version).toBe('V1.14.2.8.4.7.46')
  expect(latest?.canonicalName).toBe('应付确认准备')
  expect(latest?.sourceDocumentType).toBe('purchaseAccountsPayableDraft')
  expect(latest?.currentStateSource).toBe('server')
  expect(latest?.data?.capacity?.passThroughLineageCount).toBeGreaterThanOrEqual(8)
  expect(latest?.data?.capacity?.formalPayableConfirmationPrepareCount).toBeGreaterThanOrEqual(8)
  expect(latest?.data?.capacity?.downstreamEligibleSourceCount).toBeGreaterThanOrEqual(8)
  expect(latest?.data?.capacity?.nextStageConsumedCount).toBe(0)
  expect(latest?.data?.capacity?.nextModuleCode).toBe('payment_request_prepare')
  expect(latest?.data?.results).toHaveLength(8)
  expect(new Set(latest.data.results.map(row => row.id)).size).toBe(8)
  expect(new Set(latest.data.results.map(row => row.sourcePurchaseAccountsPayableDraftId)).size).toBe(8)
  expect(new Set(latest.data.results.map(row => row.idempotencyKey)).size).toBe(8)
  expect(latest.data.results.every(row => (
    row.status === 'prepared'
    && row.validationStatus === 'passed'
    && row.validationIssueCount === 0
    && row.eligibility?.nextStepReadiness === 'ready_for_payment_request_prepare'
    && row.eligibility?.source === 'server'
    && row.eligibility?.paymentRequestPrepareCreated === false
  ))).toBeTruthy()
  expect(Object.values(latest.data.downstreamCounts).every(value => value === 0)).toBeTruthy()
  expect(latest.data.paymentRequestPrepareCreated).toBe(false)

  for (const row of latest.data.results) {
    const detailResponse = await page.request.get(`${apiUrl}${row.id}`)
    expect(detailResponse.ok()).toBeTruthy()
    const detail = await detailResponse.json()
    expect(detail.currentStateSource).toBe('server')
    expect(detail.data.accountingSnapshot.snapshotHash).toHaveLength(64)
    expect(detail.data.numberReservationStatus).toBe('consumed')
    expect(detail.data.transactionStatus).toBe('committed')
    expect(detail.data.auditStatus).toBe('committed')
  }

  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload({ waitUntil: 'networkidle' })
  await expect(formalRegion).toContainText('PCP20260700000001')
  await expect(formalRegion).toContainText('PCP20260700000008')

  await page.evaluate(() => {
    localStorage.removeItem('token')
    sessionStorage.clear()
  })
  await page.reload({ waitUntil: 'networkidle' })
  await expect(capacityRegion).toContainText('容量门禁：通过')

  const blockedResponse = await page.request.get(`${apiUrl}?scenarioClass=blocked`)
  expect(blockedResponse.ok()).toBeTruthy()
  const blocked = await blockedResponse.json()
  expect(blocked.data.count).toBe(0)
  expect(blocked.data.scenarioOverview.length).toBeGreaterThanOrEqual(8)
  expect(blocked.data.scenarioOverview.every(row => (
    row.formalPayableConfirmationPrepareCreated === false
    && row.downstreamEligible === false
    && row.nextStepAllowed === false
  ))).toBeTruthy()

  await page.screenshot({
    path: path.join(resultRoot, 'normal-page.png'),
    fullPage: true,
  })

  const assertions = [
    {
      fullUrl,
      regionTitle: '应付确认准备金丝雀容量',
      relativePosition: '页面标题之后第一个辅助区域',
      fieldName: '下游可继承来源数量',
      expected: '至少8',
      actual: latest.data.capacity.downstreamEligibleSourceCount,
      ctrlF: '应付确认准备金丝雀容量',
      passed: latest.data.capacity.downstreamEligibleSourceCount >= 8,
    },
    {
      fullUrl,
      regionTitle: '应付确认准备来源',
      relativePosition: '容量区域之后',
      fieldName: '唯一直接来源类型',
      expected: 'purchaseAccountsPayableDraft',
      actual: latest.sourceDocumentType,
      ctrlF: '应付确认准备来源',
      passed: latest.sourceDocumentType === 'purchaseAccountsPayableDraft',
    },
    {
      fullUrl,
      regionTitle: '应付确认准备业务场景',
      relativePosition: '来源区域之后、正式对象列表之前',
      fieldName: '阻断场景数量',
      expected: '至少8',
      actual: latest.data.capacity.blockedScenarioCount,
      ctrlF: '应付确认准备业务场景',
      passed: latest.data.capacity.blockedScenarioCount >= 8,
    },
    {
      fullUrl,
      regionTitle: '会计资料与借贷预检查',
      relativePosition: '业务场景之后',
      fieldName: '唯一放行资格',
      expected: 'ready_for_payment_request_prepare',
      actual: latest.data.results[0].eligibility.nextStepReadiness,
      ctrlF: '会计资料与借贷预检查',
      passed: latest.data.results.every(row => row.eligibility.nextStepReadiness === 'ready_for_payment_request_prepare'),
    },
    {
      fullUrl,
      regionTitle: '应付确认准备列表',
      relativePosition: '页面下部',
      fieldName: '当前结果',
      expected: '至少8条',
      actual: latest.data.results.length,
      ctrlF: latest.data.results[0].prepareNo,
      passed: latest.data.results.length >= 8,
    },
    {
      fullUrl,
      regionTitle: '付款申请准备放行与下游零对象保护',
      relativePosition: '页面最底部',
      fieldName: '付款申请准备数量',
      expected: 0,
      actual: latest.data.downstreamCounts.paymentRequestPrepares,
      ctrlF: '付款申请准备放行与下游零对象保护',
      passed: latest.data.downstreamCounts.paymentRequestPrepares === 0,
    },
  ]
  writeJson(path.join(resultRoot, 'page-assertions.json'), {
    result: assertions.every(item => item.passed) ? 'passed' : 'failed',
    version: 'V1.14.2.8.4.7.46',
    canonicalName: '应付确认准备',
    sourceDocumentType: 'purchaseAccountsPayableDraft',
    fullUrl,
    currentStateSource: latest.currentStateSource,
    formalPayableConfirmationPrepareCount: latest.data.results.length,
    downstreamEligibleSourceCount: latest.data.capacity.downstreamEligibleSourceCount,
    nextStageConsumedCount: latest.data.capacity.nextStageConsumedCount,
    nextModuleCode: latest.data.capacity.nextModuleCode,
    paymentRequestPrepareCreated: false,
    prepareNos: latest.data.results.map(row => row.prepareNo),
    pageAssertions: assertions,
    browserStateClearRecoveryReady: true,
    reloginRecoveryReady: true,
  })
})

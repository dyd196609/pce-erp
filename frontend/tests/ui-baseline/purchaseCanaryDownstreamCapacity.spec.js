import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const resultRoot = path.resolve('test-results', 'purchase-canary-downstream-capacity')
const fullUrl = 'http://localhost:5173/#/finance/ap-drafts'
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('V45.3 plain page shows eight formal pass-through lineages and blocked overview', async ({ page }) => {
  const apiResponses = []
  page.on('response', async (response) => {
    if (!response.url().includes('/api/scm/purchase-accounts-payable-drafts/')) return
    if (response.request().method() !== 'GET' || response.url().includes('/by-source/')) return
    try {
      apiResponses.push({ url: response.url(), body: await response.json() })
    } catch {
      // Ignore non-JSON diagnostics.
    }
  })

  await page.goto(fullUrl, { waitUntil: 'networkidle' })
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').last()).toHaveText('采购应付账款草稿')
  const capacity = page.locator('[data-acceptance-id="purchase-canary-capacity"]')
  const overview = page.locator('[data-acceptance-id="purchase-canary-scenario-overview"]')
  const formal = page.locator('[data-acceptance-id="purchase-ap-draft-formal-list"]')
  await expect(capacity).toContainText('金丝雀群测试容量')
  await expect(capacity).toContainText('下游可继承成功链数量')
  await expect(capacity).toContainText('8')
  await expect(overview).toContainText('金丝雀业务场景')
  await expect(overview).toContainText('SUCCESS_STANDARD_01')
  await expect(overview).toContainText('AMOUNT_DIFFERENCE')
  await expect(formal).toContainText('APD20260700000001')
  await expect(formal).toContainText('APD20260700000008')

  const latest = apiResponses.at(-1)?.body?.data
  expect(latest?.capacity?.downstreamEligibleLineageCount).toBeGreaterThanOrEqual(8)
  expect(latest?.capacity?.formalDraftCount).toBeGreaterThanOrEqual(8)
  expect(latest?.capacity?.blockedScenarioCount).toBeGreaterThanOrEqual(6)
  expect(latest?.capacity?.nextStageConsumedCount).toBe(0)
  expect(latest?.results).toHaveLength(8)
  expect(new Set(latest.results.map(row => row.id)).size).toBe(8)
  expect(new Set(latest.results.map(row => row.sourcePurchaseInvoicePrepareId)).size).toBe(8)
  expect(new Set(latest.results.map(row => row.idempotencyKey)).size).toBe(8)
  expect(latest.results.every(row => row.downstreamEligible && !row.nextStageConsumed)).toBeTruthy()
  expect(latest.downstreamCounts.confirmationPrepares).toBe(0)

  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload({ waitUntil: 'networkidle' })
  await expect(formal).toContainText('APD20260700000001')
  await expect(formal).toContainText('APD20260700000008')

  const blockedApi = await page.request.get(
    'http://127.0.0.1:8000/api/scm/purchase-accounts-payable-drafts/?scenarioClass=blocked',
  )
  expect(blockedApi.ok()).toBeTruthy()
  const blockedData = (await blockedApi.json()).data
  expect(blockedData.count).toBe(0)
  expect(blockedData.scenarioOverview.length).toBeGreaterThanOrEqual(6)
  expect(blockedData.scenarioOverview.every(row => !row.formalApDraftCreated && !row.downstreamEligible)).toBeTruthy()

  await page.screenshot({ path: path.join(resultRoot, 'normal-page.png'), fullPage: true })
  const assertions = [
    {
      fullUrl, regionTitle: '金丝雀群测试容量',
      relativePosition: '页面标题之后第一个辅助区域', fieldName: '下游可继承来源数量',
      expected: '至少8', actual: latest.capacity.downstreamEligibleLineageCount,
      ctrlF: '金丝雀群测试容量', passed: latest.capacity.downstreamEligibleLineageCount >= 8,
    },
    {
      fullUrl, regionTitle: '正式采购应付账款草稿列表',
      relativePosition: '页面下部', fieldName: '当前结果',
      expected: '至少8条', actual: latest.results.length,
      ctrlF: 'APD20260700000001', passed: latest.results.length >= 8,
    },
    {
      fullUrl, regionTitle: '金丝雀业务场景',
      relativePosition: '容量区域之后', fieldName: '阻断场景数量',
      expected: '至少6', actual: latest.capacity.blockedScenarioCount,
      ctrlF: '金丝雀业务场景', passed: latest.capacity.blockedScenarioCount >= 6,
    },
    {
      fullUrl, regionTitle: '业务流程与后续边界',
      relativePosition: '页面底部', fieldName: '应付确认准备数量',
      expected: 0, actual: latest.downstreamCounts.confirmationPrepares,
      ctrlF: '后续边界', passed: latest.downstreamCounts.confirmationPrepares === 0,
    },
  ]
  writeJson(path.join(resultRoot, 'page-assertions.json'), {
    result: assertions.every(item => item.passed) ? 'passed' : 'failed',
    version: 'V1.14.2.8.4.7.45.3',
    fullUrl,
    currentStateSource: latest.currentStateSource,
    returnedRowCount: latest.results.length,
    capacity: latest.capacity,
    scenarioOverviewCount: latest.scenarioOverview.length,
    formalDraftNos: latest.results.map(row => row.draftNo),
    apiRequestUrl: apiResponses.at(-1)?.url,
    pageAssertions: assertions,
    browserStateClearRecoveryReady: true,
  })
})

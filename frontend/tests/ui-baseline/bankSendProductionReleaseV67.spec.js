import { expect, test } from '@playwright/test'

const isolationRoute = '/#/finance/bank-send-dual-isolation-checks'
const reviewRoute = '/#/finance/bank-send-production-release-reviews'

async function openIsolation(page) {
  await page.goto(isolationRoute)
  await expect(page.locator('[data-acceptance-id="bank-send-dual-isolation-facts"]')).toContainText('检查数量')
  await expect(page.locator('[data-acceptance-id="bank-send-dual-isolation-results"]')).toContainText('环境隔离')
}

async function openReview(page) {
  await page.goto(reviewRoute)
  await expect(page.locator('[data-acceptance-id="bank-send-production-release-facts"]')).toContainText('评审数量')
  await expect(page.locator('[data-acceptance-id="bank-send-production-release-boundary"]')).toContainText('生产评审通过 ≠ 银行已发送')
}

test('场景1：正常人工生产放行评审锁定', async ({ page }) => {
  await openReview(page)
  const region = page.locator('[data-acceptance-id="bank-send-production-release-list"]')
  await expect(region).toContainText('生产评审已锁定')
  await expect(region).toContainText('v67-business-owner')
  await expect(region).toContainText('v67-fund-owner')
  await expect(region).toContainText('v67-security-owner')
})

test('场景2：隔离失败不能伪装为正常事实', async ({ page }) => {
  await page.route('**/api/finance/bank-send-dual-isolation-checks/', async route => {
    const response = await route.fetch()
    const payload = await response.json()
    payload.data.results[0].interfaceCheck = false
    await route.fulfill({ response, json: payload })
  })
  await page.goto(isolationRoute)
  await expect(page.getByText(/双重隔离事实读取失败/)).toBeVisible()
})

test('场景3：人工评审用户和角色无冲突', async ({ page }) => {
  await openReview(page)
  const decisions = await page.evaluate(async () => {
    const payload = await fetch('/api/finance/bank-send-production-release-reviews/').then(r => r.json())
    return payload.data.results[0].decisions
  })
  expect(new Set(decisions.map(row => row.operator)).size).toBe(3)
  expect(new Set(decisions.map(row => row.role)).size).toBe(3)
})

test('场景4：未授权提交评审意见被服务端阻断', async ({ page }) => {
  await openReview(page)
  const status = await page.evaluate(async () => {
    const response = await fetch('/api/finance/bank-send-production-release-reviews/1/business-review/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'unauthorized' }),
    })
    return response.status
  })
  expect([401, 403, 409]).toContain(status)
})

test('场景5：危险按钮扫描为零', async ({ page }) => {
  for (const route of [isolationRoute, reviewRoute]) {
    await page.goto(route)
    await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of [
      '开启生产接口', '配置生产密钥', '执行银行发送', '调用银行接口',
      '发送银行', '立即发送', '付款执行', '扣款',
    ]) expect(labels.some(label => label.trim() === forbidden)).toBe(false)
  }
})

test('场景6：API Page Diagnostic StrictFacts AcceptanceFacts一致', async ({ page }) => {
  await openIsolation(page)
  const isolation = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-send-dual-isolation-checks/').then(r => r.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return [api.data.isolationFacts.recordCount, runtime.isolationFacts.recordCount, runtime.diagnosticFacts.recordCount, runtime.strictFacts.recordCount, runtime.acceptanceFacts.recordCount]
  })
  expect(isolation).toEqual([1, 1, 1, 1, 1])
  await openReview(page)
  const review = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-send-production-release-reviews/').then(r => r.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return [api.data.reviewFacts.recordCount, runtime.reviewFacts.recordCount, runtime.diagnosticFacts.recordCount, runtime.strictFacts.recordCount, runtime.acceptanceFacts.recordCount]
  })
  expect(review).toEqual([1, 1, 1, 1, 1])
})

test('场景7：页面切换无诊断污染且FAIL UNKNOWN为零', async ({ page }) => {
  await openIsolation(page)
  await openReview(page)
  const acceptance = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  expect(acceptance.pageFactOwner).toBe('FIN_BANK_SEND_PRODUCTION_RELEASE_REVIEW')
  expect(acceptance.acceptanceFacts.acceptanceStatus).toBe('PASS')
  expect(acceptance.acceptanceFacts.unknownReason).toBe('')
  expect(acceptance.dangerActionCount).toBe(0)
})

test('场景8：数据库与执行边界保护计数为零', async ({ page }) => {
  await openReview(page)
  const protection = await page.evaluate(async () => {
    const payload = await fetch('/api/finance/bank-send-production-release-reviews/').then(r => r.json())
    const facts = payload.data.reviewFacts
    return {
      dualIsolationWriteCount: facts.dualIsolationWriteCount,
      releaseReviewWriteCount: facts.releaseReviewWriteCount,
      bankMessageSendWriteCount: facts.bankMessageSendWriteCount,
      paymentExecutionWriteCount: facts.paymentExecutionWriteCount,
      financialImpactWriteCount: facts.financialImpactWriteCount,
      businessProgressWriteCount: facts.businessProgressWriteCount,
    }
  })
  expect(protection).toEqual({
    dualIsolationWriteCount: 1,
    releaseReviewWriteCount: 1,
    bankMessageSendWriteCount: 0,
    paymentExecutionWriteCount: 0,
    financialImpactWriteCount: 0,
    businessProgressWriteCount: 0,
  })
})

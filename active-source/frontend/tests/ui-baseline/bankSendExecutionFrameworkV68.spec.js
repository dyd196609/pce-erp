import { expect, test } from '@playwright/test'

const frameworkRoute = '/#/finance/bank-send-execution-framework-reviews'
const adapterRoute = '/#/finance/bank-connector-adapter-reviews'

async function openFramework(page) {
  await page.goto(frameworkRoute)
  await expect(page.locator('[data-acceptance-id="bank-send-execution-framework-facts"]')).toContainText('加载成功')
}

async function openAdapter(page) {
  await page.goto(adapterRoute)
  await expect(page.locator('[data-acceptance-id="bank-connector-adapter-facts"]')).toContainText('加载成功')
}

test('场景1：执行框架停留安全评审状态', async ({ page }) => {
  await openFramework(page)
  const status = page.locator('[data-acceptance-id="bank-send-execution-framework-status"]')
  await expect(status).toContainText('模拟')
  await expect(status).toContainText('隔离模拟')
  await expect(status).toContainText('关闭')
  await expect(status).toContainText('生产安全评审通过')
})

test('场景2：适配器仅允许本地纯函数模拟', async ({ page }) => {
  await openAdapter(page)
  const list = page.locator('[data-acceptance-id="bank-connector-adapter-list"]')
  await expect(list).toContainText('BankConnectorAdapter')
  await expect(list).toContainText('模拟允许')
  await expect(list).toContainText('本地纯函数模拟')
  await expect(list).toContainText('关闭')
})

test('场景3：签名只使用模拟证书', async ({ page }) => {
  await openAdapter(page)
  const region = page.locator('[data-acceptance-id="bank-connector-signature"]')
  await expect(region).toContainText('SHA256_SIMULATION')
  await expect(region).toContainText('仅模拟')
})

test('场景4：请求和执行版本幂等唯一', async ({ page }) => {
  await openAdapter(page)
  const region = page.locator('[data-acceptance-id="bank-connector-idempotency"]')
  await expect(region).toContainText('执行版本')
  await expect(region).toContainText('1')
  const api = await page.evaluate(() => fetch('/api/finance/bank-connector-adapter-reviews/').then(r => r.json()))
  expect(api.data.adapterFacts.idempotencyCount).toBe(1)
})

test('场景5：失败模型禁止自动重试', async ({ page }) => {
  await openAdapter(page)
  const region = page.locator('[data-acceptance-id="bank-connector-failure"]')
  await expect(region).toContainText('timeout')
  await expect(region).toContainText('允许重试')
  await expect(region).toContainText('否')
  await expect(region).toContainText('模拟失败')
})

test('场景6：模拟回执不冒充真实银行回执', async ({ page }) => {
  await openAdapter(page)
  const region = page.locator('[data-acceptance-id="bank-connector-receipt"]')
  await expect(region).toContainText('模拟')
  await expect(region).toContainText('未发送')
})

test('场景7：危险动作和生产能力为零', async ({ page }) => {
  for (const route of [frameworkRoute, adapterRoute]) {
    await page.goto(route)
    await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of ['执行银行发送', '调用银行接口', '启用生产连接', '上传生产密钥', '发送银行', '付款执行', '扣款']) {
      expect(labels.some(label => label.trim() === forbidden)).toBe(false)
    }
  }
})

test('场景8：API Page Diagnostic StrictFacts AcceptanceFacts一致', async ({ page }) => {
  await openFramework(page)
  const framework = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-send-execution-framework-reviews/').then(r => r.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return [api.data.frameworkFacts.recordCount, runtime.frameworkFacts.recordCount, runtime.diagnosticFacts.recordCount, runtime.strictFacts.recordCount, runtime.acceptanceFacts.recordCount]
  })
  expect(framework).toEqual([1, 1, 1, 1, 1])
  await openAdapter(page)
  const adapter = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-connector-adapter-reviews/').then(r => r.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return [api.data.adapterFacts.recordCount, runtime.adapterFacts.recordCount, runtime.diagnosticFacts.recordCount, runtime.strictFacts.recordCount, runtime.acceptanceFacts.recordCount]
  })
  expect(adapter).toEqual([1, 1, 1, 1, 1])
})

test('场景9：页面切换无诊断污染且写入保护为零', async ({ page }) => {
  await openFramework(page)
  await openAdapter(page)
  const result = await page.evaluate(async () => {
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    const payload = await fetch('/api/finance/bank-connector-adapter-reviews/').then(r => r.json())
    return { runtime, facts: payload.data.adapterFacts }
  })
  expect(result.runtime.pageFactOwner).toBe('FIN_BANK_CONNECTOR_ADAPTER_REVIEW')
  expect(result.runtime.acceptanceFacts.acceptanceStatus).toBe('PASS')
  expect(result.runtime.acceptanceFacts.unknownReason).toBe('')
  expect(result.facts.networkCallCount).toBe(0)
  expect(result.facts.bankMessageSendWriteCount).toBe(0)
  expect(result.facts.paymentExecutionWriteCount).toBe(0)
  expect(result.facts.financialImpactWriteCount).toBe(0)
  expect(result.facts.businessProgressWriteCount).toBe(0)
})

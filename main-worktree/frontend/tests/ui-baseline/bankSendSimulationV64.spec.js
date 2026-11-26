import { expect, test } from '@playwright/test'

const route = '/#/finance/bank-send-simulations'

async function open(page) {
  await page.goto(route)
  await expect(page.getByRole('heading', { name: '银行发送执行模拟', exact: true }).first()).toBeVisible()
  await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
}

test('场景1：正常模拟成功', async ({ page }) => {
  await open(page)
  await expect(page.getByText('模拟成功', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('模拟成功 ≠ 银行已发送', { exact: true })).toBeVisible()
})

test('场景2：模拟失败', async ({ page }) => {
  await open(page)
  await expect(page.getByText('模拟失败', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('模拟检查未通过，未发生任何外部发送或付款执行。')).toBeVisible()
})

test('场景3：失败恢复', async ({ page }) => {
  await open(page)
  const region = page.locator('[data-acceptance-id="bank-send-simulation-recovery"]')
  await expect(region).toContainText('失败恢复')
  await expect(region).toContainText('已恢复')
  await expect(region).toContainText('不自动重试')
})

test('场景4：重复调用幂等', async ({ page }) => {
  await open(page)
  const payload = await page.evaluate(async () => (
    fetch('/api/finance/bank-send-simulations/').then(response => response.json())
  ))
  expect(payload.data.simulationCount).toBe(2)
  const requestNos = payload.data.results.map(row => row.bankSendRequestNo)
  expect(new Set(requestNos).size).toBe(requestNos.length)
  expect(new Set(payload.data.results.map(row => row.executionSimulationIdempotencyKey)).size).toBe(2)
})

test('场景5：危险按钮与技术状态扫描', async ({ page }) => {
  await open(page)
  const buttonLabels = await page.locator('button:visible').allTextContents()
  for (const forbidden of ['发送银行', '提交银行', '执行付款', '扣款']) {
    expect(buttonLabels.some(label => label.trim() === forbidden)).toBe(false)
  }
  const visibleText = await page.locator('body').innerText()
  for (const technical of [
    'simulation_running', 'simulation_success', 'simulation_failed',
    'ready_to_dispatch', 'ready_for_execution',
  ]) {
    expect(visibleText).not.toContain(technical)
  }
})

test('五端服务端事实一致', async ({ page }) => {
  await open(page)
  const result = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-send-simulations/').then(response => response.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return {
      api: api.data.simulationFacts.simulationCount,
      page: runtime.simulationFacts.simulationCount,
      diagnostic: runtime.diagnosticFacts.recordCount,
      strictFacts: runtime.strictFacts.recordCount,
      acceptanceFacts: runtime.acceptanceFacts.recordCount,
      source: runtime.acceptanceFacts.factSource,
    }
  })
  expect(result).toEqual({
    api: 2, page: 2, diagnostic: 2, strictFacts: 2,
    acceptanceFacts: 2, source: 'server',
  })
})


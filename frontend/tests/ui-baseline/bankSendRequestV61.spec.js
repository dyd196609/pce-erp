import { expect, test } from '@playwright/test'

const route = '/#/finance/bank-send-requests'

async function openPage(page) {
  await page.goto(route)
  await expect(page.getByText('银行发送请求列表', { exact: true })).toBeVisible()
  await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
}

test('场景1 正常请求显示发送前待分发', async ({ page }) => {
  await openPage(page)
  await expect(page.locator(
    '[data-acceptance-id="bank-send-requests-main"] tbody tr',
  )).toHaveCount(8)
  await expect(page.getByText('发送前待分发', { exact: true })).toHaveCount(9)
})

test('场景2 八类阻断请求不生成发送请求', async ({ page }) => {
  await openPage(page)
  const capacity = page.locator('[data-acceptance-id="bank-send-request-canary"]')
  await expect(capacity).toContainText('阻断请求池')
  await expect(capacity).toContainText('8')
  await expect(capacity).toContainText('备用请求池')
  await expect(capacity).toContainText('20')
})

test('场景3 二次校验全部通过', async ({ page }) => {
  await openPage(page)
  const validation = page.locator('[data-acceptance-id="pre-dispatch-validation"]')
  await expect(validation).toContainText('授权hash一致')
  await expect(validation).toContainText('收款账户一致')
  await expect(validation.getByText('通过', { exact: true })).toHaveCount(9)
})

test('场景4 API 页面诊断 strictFacts 一致', async ({ page }) => {
  await openPage(page)
  await page.getByRole('button', { name: '复制诊断数据', exact: true }).click()
  const diagnostic = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
  expect(diagnostic.moduleCode).toBe('FIN_BANK_SEND_REQUEST')
  expect(diagnostic.resultCount).toBe(8)
  expect(diagnostic.bankSendRequestFacts.requestCount).toBe(8)
  expect(diagnostic.strictServerFacts.bankSendRequestFacts.requestCount).toBe(8)
  expect(diagnostic.bankSendRequestFacts.readyToDispatchCount).toBe(8)
})

test('场景5 页面不存在任何发送或付款执行动作', async ({ page }) => {
  await openPage(page)
  const buttons = await page.locator('button').allTextContents()
  for (const forbidden of ['发送银行', '立即发送', '执行发送', '提交银行', '执行付款', '扣款']) {
    expect(buttons).not.toContain(forbidden)
  }
  const boundary = page.locator('[data-acceptance-id="bank-send-request-boundary"]')
  await expect(boundary).toContainText('银行报文发送')
  await expect(boundary).toContainText('付款执行')
  await expect(boundary).toContainText('资金扣减')
})

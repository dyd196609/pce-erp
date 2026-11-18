import { expect, test } from '@playwright/test'

const route = '/#/finance/bank-send-execution-gates'

async function openGatePage(page) {
  await page.goto(route)
  await expect(page.getByText('银行发送执行授权列表', { exact: true }))
    .toBeVisible()
  await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
}

test('场景1 正常授权对象显示执行前就绪', async ({ page }) => {
  await openGatePage(page)
  await expect(page.locator(
    '[data-acceptance-id="bank-send-execution-gates-main"] tbody tr',
  )).toHaveCount(8)
  await expect(page.getByText('执行前就绪', { exact: true })).toHaveCount(9)
})

test('场景2 阻断授权池保持六条且不生成授权对象', async ({ page }) => {
  await openGatePage(page)
  const capacity = page.locator(
    '[data-acceptance-id="execution-gate-canary"]',
  )
  await expect(capacity).toContainText('阻断授权池')
  await expect(capacity).toContainText('6')
  await expect(capacity).toContainText('已创建授权')
  await expect(capacity).toContainText('8')
})

test('场景3 API 页面诊断 strictFacts 一致', async ({ page }) => {
  await openGatePage(page)
  await page.getByRole('button', {
    name: '复制诊断数据',
    exact: true,
  }).click()
  const diagnostic = JSON.parse(await page.evaluate(
    () => navigator.clipboard.readText(),
  ))
  expect(diagnostic.moduleCode).toBe('FIN_BANK_SEND_EXECUTION_GATE')
  expect(diagnostic.resultCount).toBe(8)
  expect(diagnostic.bankSendExecutionGateFacts.gateCount).toBe(8)
  expect(
    diagnostic.strictServerFacts.bankSendExecutionGateFacts.gateCount,
  ).toBe(8)
  expect(diagnostic.bankSendExecutionGateFacts.readyForExecutionCount)
    .toBe(8)
})

test('场景4 页面不存在银行发送与付款执行动作', async ({ page }) => {
  await openGatePage(page)
  const buttons = await page.locator('button').allTextContents()
  expect(buttons).not.toContain('发送银行')
  expect(buttons).not.toContain('立即发送')
  expect(buttons).not.toContain('执行发送')
  expect(buttons).not.toContain('提交银行')
  expect(buttons).not.toContain('执行付款')
  const boundary = page.locator(
    '[data-acceptance-id="execution-gate-boundary"]',
  )
  await expect(boundary).toContainText('银行发送')
  await expect(boundary).toContainText('付款执行')
  await expect(boundary).toContainText('银行流水')
})

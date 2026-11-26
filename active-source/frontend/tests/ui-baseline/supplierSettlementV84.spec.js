import { expect, test } from '@playwright/test'

test('V84 供应商付款状态记录页面', async ({ page }) => {
  await page.goto('/#/scm/supplier-payment-status')
  await expect(page.locator('main.page h1')).toHaveText('供应商付款状态记录')
  await expect(page.locator('[data-acceptance-id="supplier-payment-status-list"]')).toBeVisible()
  await expect(page.locator('[data-acceptance-id="supplier-payment-status-list"]')).toContainText(/付款安排中|付款完成|结算完成/)
  await expect(page.locator('body')).not.toContainText('payment_completed')
  const labels = await page.locator('button:visible').allTextContents()
  for (const forbidden of ['执行付款', '银行发送', '资金扣减', '生成银行流水']) {
    expect(labels.map((label) => label.trim())).not.toContain(forbidden)
  }
  const runtime = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  expect(runtime.pageFacts.recordCount).toBe(4)
  expect(runtime.strictFacts.recordCount).toBe(4)
  expect(runtime.factSource).toBe('server')
})

test('V84 供应商结算完成确认页面', async ({ page }) => {
  await page.goto('/#/scm/supplier-settlement-completions')
  await expect(page.locator('main.page h1')).toHaveText('供应商结算完成确认')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-completion-list"]')).toContainText('结算完成')
  await expect(page.locator('[data-acceptance-id="performance-source"]')).toContainText('SupplierSettlementCompletion')
  const runtime = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  expect(runtime.pageFacts.recordCount).toBe(2)
  expect(runtime.diagnosticFacts.recordCount).toBe(2)
  expect(runtime.acceptanceFacts.recordCount).toBe(2)
})

test('V84 业务流程中心包含结算闭环节点', async ({ page }) => {
  await page.goto('/#/process-center')
  const process = page.locator('[data-acceptance-id="scm-purchase-settlement-process"]')
  await expect(process.locator('[data-process-node]')).toHaveCount(16)
  await expect(process.locator('[data-process-node="payment-status-record"]')).toContainText('付款状态记录')
  await expect(process.locator('[data-process-node="supplier-settlement-completion"]')).toContainText('供应商结算完成')
})

import { expect, test } from '@playwright/test'

async function expectPdeSelected(page) {
  await expect(page.locator('[data-process-module="PDE"]')).toHaveClass(/active/)
  await expect(page.locator('[data-acceptance-id="pde-product-engineering-process"]')).toBeVisible()
  await expect(page.locator('[data-acceptance-id="scm-purchase-settlement-process"]')).toHaveCount(0)
}

test('module=PDE恢复PDE流程并展示十个可跳转节点', async ({ page }) => {
  await page.goto('/#/process-center?module=PDE')
  await expectPdeSelected(page)
  const nodes = page.locator('[data-acceptance-id="pde-product-engineering-process"] [data-process-node]')
  await expect(nodes).toHaveCount(10)
  await expect(nodes.locator(':disabled')).toHaveCount(0)
})

test('产品订单需求节点可打开统一治理页面', async ({ page }) => {
  await page.goto('/#/process-center?module=PDE')
  await page.locator('[data-process-node="product-order-demand"]').click()
  await expect(page).toHaveURL(/#\/pde\/product-requirements$/)
  await expect(page.getByRole('heading', { name: '产品订单需求管理', exact: true })).toBeVisible()
  for (const acceptanceId of ['finance-operation-summary', 'module-main-process', 'business-process-navigation', 'pde-server-facts', 'pde-business-boundary-protection']) {
    await expect(page.locator(`[data-acceptance-id="${acceptanceId}"]`)).toBeVisible()
  }
})

test('产品订单需求返回业务流程中心后保持PDE', async ({ page }) => {
  await page.goto('/#/pde/product-requirements')
  await page.locator('[data-acceptance-id="return-process-center-button"]').click()
  await expect(page).toHaveURL(/#\/process-center\?module=PDE$/)
  await expectPdeSelected(page)
})

test('产品设计管理返回业务流程中心后保持PDE', async ({ page }) => {
  await page.goto('/#/process-center?module=PDE')
  await page.locator('[data-process-node="product-design-management"]').click()
  await expect(page).toHaveURL(/#\/pde\/product-definitions$/)
  await page.locator('[data-acceptance-id="return-process-center-button"]').click()
  await expect(page).toHaveURL(/#\/process-center\?module=PDE$/)
  await expectPdeSelected(page)
})

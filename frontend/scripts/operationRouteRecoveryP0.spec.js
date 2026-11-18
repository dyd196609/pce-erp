import { expect, test } from '@playwright/test'

async function openEnterpriseFoundationFromNormalEntry(page) {
  await page.goto('/')
  await page.getByRole('menuitem', { name: '系统配置', exact: true }).click()
  await expect(page).toHaveURL(/#\/admin$/)
  await page.getByRole('button', { name: '进入企业基础资料', exact: true }).click()
  await expect(page).toHaveURL(/#\/foundation$/)
}

test('工序资料真实入口只进入system.Process页面', async ({ page }) => {
  await openEnterpriseFoundationFromNormalEntry(page)
  await page.getByRole('button', { name: '制造资源', exact: true }).click()
  const entry = page.locator('[data-navigation-key="manufacturing-resource.operation"]')
  await expect(entry).toHaveAttribute('href', '#/foundation/master-data/operations')
  await entry.click()

  await expect(page).toHaveURL(/#\/foundation\/master-data\/operations$/)
  await expect(page).toHaveTitle('工序资料')
  const formalPage = page.locator('[data-page-key="foundation-formal-operations"]')
  await expect(formalPage).toHaveAttribute('data-formal-model', 'system.Process')
  await expect(formalPage).toHaveAttribute('data-api-url', '/api/pde/a1-foundation/operations/')
  await expect(page.getByRole('heading', { name: '工艺路线主表', exact: true })).toHaveCount(0)
})

test('工艺资料真实入口不得进入Operation', async ({ page }) => {
  await openEnterpriseFoundationFromNormalEntry(page)
  const entry = page.locator('[data-navigation-key="product-engineering.routing"]')
  await expect(entry).toHaveAttribute('href', '#/foundation/master-data/routings')
  await entry.click()

  await expect(page).toHaveURL(/#\/foundation\/master-data\/routings$/)
  const formalPage = page.locator('[data-page-key="foundation-formal-routings"]')
  await expect(formalPage).toHaveAttribute('data-formal-model', 'pde.Routing')
  await expect(page.getByRole('heading', { name: '工艺路线主表', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '工序', exact: true })).toHaveCount(0)
})

test('路线步骤点击后保持RoutingStep页面身份', async ({ page }) => {
  await openEnterpriseFoundationFromNormalEntry(page)
  await page.locator('[data-navigation-key="product-engineering.routing"]').click()
  await page.getByRole('button', { name: /路线步骤/ }).click()

  await expect(page).toHaveURL(/#\/foundation\/master-data\/routing-steps$/)
  const formalPage = page.locator('[data-page-key="foundation-formal-routing-steps"]')
  await expect(formalPage).toHaveAttribute('data-formal-model', 'pde.RoutingStep')
  await expect(formalPage.getByRole('heading', { name: '路线步骤', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '工序', exact: true })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '工艺路线主表', exact: true })).toHaveCount(0)
})

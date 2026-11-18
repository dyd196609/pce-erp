import { expect, test } from '@playwright/test'

test('工程准备页面显示版本、编码、模块与流程', async ({ page }) => {
  await page.goto('/#/pde/engineering-readiness')
  await expect(page.locator('[data-acceptance-id="page-business-title"]')).toHaveText('PDE工程准备状态')
  await expect(page.getByText('V1.14.2.8.4.10.4', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('pde-engineering-readiness', { exact: true })).toBeVisible()
  await expect(page.getByText('PDE', { exact: true }).first()).toBeVisible()
  await expect(page.locator('[data-acceptance-id="module-main-process"]')).toContainText('CRM客户订单')
  await expect(page.locator('[data-acceptance-id="module-main-process"]')).toContainText('MRP输入准备')
})

test('订单工程准备列表显示全部受治理状态列', async ({ page }) => {
  await page.goto('/#/pde/engineering-readiness')
  for (const name of ['订单号', '产品', '客户交期', '工程状态', 'BOM状态', '工艺状态', '工程资料状态', '制造输出状态', 'MRP准备状态', '交期风险']) {
    await expect(page.getByRole('columnheader', { name: new RegExp(name) })).toBeVisible()
  }
})

test('PDE三段业务导航均为可点击链接并携带pageCode', async ({ page }) => {
  await page.goto('/#/pde/engineering-readiness')
  const navigation = page.locator('[data-acceptance-id="business-process-navigation"]')
  await expect(navigation.locator('[data-pde-navigation-link="previous"]')).toHaveAttribute('data-page-code', 'crm-customer-orders')
  await expect(navigation.locator('[data-pde-navigation-link="current"]')).toHaveAttribute('data-page-code', 'pde-engineering-readiness')
  await expect(navigation.locator('[data-pde-navigation-link="next"]')).toHaveAttribute('data-page-code', 'pde-bom-versions')
})

test('CRM客户订单与PDE工程流程链接进入正确模块', async ({ page }) => {
  await page.goto('/#/pde/workbench')
  const navigation = page.locator('[data-acceptance-id="business-process-navigation"]')
  await navigation.locator('[data-pde-navigation-link="previous"]').click()
  await expect(page).toHaveURL(/#\/process-center\?module=CRM$/)
  await expect(page.locator('[data-process-module="CRM"]')).toHaveClass(/active/)
  await page.goto('/#/pde/workbench')
  await navigation.locator('[data-pde-navigation-link="next"]').click()
  await expect(page).toHaveURL(/#\/process-center\?module=PDE$/)
  await expect(page.locator('[data-process-module="PDE"]')).toHaveClass(/active/)
})

test('下一工程节点可点击且业务边界保持关闭', async ({ page }) => {
  await page.goto('/#/pde/engineering-readiness')
  await page.locator('[data-pde-navigation-link="next"]').click()
  await expect(page).toHaveURL(/#\/pde\/bom-versions$/)
  await page.goto('/#/pde/engineering-readiness')
  const boundary = page.locator('[data-acceptance-id="pde-business-boundary-protection"]')
  await expect(boundary).toContainText('采购执行')
  await expect(boundary).toContainText('付款')
  await expect(boundary).toContainText('财务影响')
  await expect(boundary.getByText('否', { exact: true })).toHaveCount(3)
})

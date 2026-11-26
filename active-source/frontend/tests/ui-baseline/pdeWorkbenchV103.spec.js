import { expect, test } from '@playwright/test'

test('流程中心只保留PDE工作台一级入口', async ({ page }) => {
  await page.goto('/#/process-center?module=PDE')
  await expect(page.locator('[data-process-module="PDE"]')).toHaveClass(/active/)
  const process = page.locator('[data-acceptance-id="pde-product-engineering-process"]')
  await expect(process.getByRole('button', { name: /PDE产品工程工作台/ })).toHaveCount(1)
  await expect(process.locator('[data-entry-mode="workbench-context-only"] [data-process-node]')).toHaveCount(12)
  await expect(process.locator('[data-entry-mode="workbench-context-only"] button')).toHaveCount(0)
  await expect(process.getByText('客户订单需求输入', { exact: true })).toBeVisible()
})

test('PDE工作台展示十个既有工程入口', async ({ page }) => {
  await page.goto('/#/pde/workbench')
  await expect(page.locator('[data-acceptance-id="page-business-title"]')).toHaveText('PDE产品工程工作台')
  const entries = page.locator('[data-acceptance-id="pde-workbench-entry-grid"] [data-workbench-entry]')
  await expect(entries).toHaveCount(10)
  await expect(entries.getByText('客户订单需求输入', { exact: true })).toBeVisible()
  await expect(entries.getByText('产品需求评审', { exact: true })).toBeVisible()
  await expect(entries.getByText('MRP输入准备', { exact: true })).toBeVisible()
})

test('工作台明确CRM来源与制造关系链', async ({ page }) => {
  await page.goto('/#/pde/workbench')
  const chain = page.locator('[data-acceptance-id="pde-order-driven-chain"]')
  await expect(chain).toContainText('来源：CRM')
  for (const name of ['CRM客户订单', 'PDE', 'EMD物料', 'BOM', '工艺路线', 'MRP输入', 'SCM采购依据']) {
    await expect(chain.getByText(name, { exact: true })).toBeVisible()
  }
})

test('工作台边界禁止复杂研发与采购执行', async ({ page }) => {
  await page.goto('/#/pde/workbench')
  const boundary = page.locator('[data-acceptance-id="pde-workbench-boundary-protection"]')
  await expect(boundary).toContainText('CAD / 三维设计')
  await expect(boundary).toContainText('PLM / PDM')
  await expect(boundary).toContainText('采购订单生成')
  await expect(boundary).toContainText('否')
  await expect(boundary).toContainText('SCM采购依据')
  await expect(boundary).toContainText('只读')
})

test('返回流程中心后保持PDE模块', async ({ page }) => {
  await page.goto('/#/pde/workbench')
  await page.locator('[data-acceptance-id="return-process-center-button"]').click()
  await expect(page).toHaveURL(/#\/process-center\?module=PDE$/)
  await expect(page.locator('[data-process-module="PDE"]')).toHaveClass(/active/)
})

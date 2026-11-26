import { expect, test } from '@playwright/test'

async function openPdeProcess(page) {
  await page.goto('/#/process-center')
  await page.locator('[data-process-module="PDE"]').click()
  return page.locator('[data-acceptance-id="pde-product-engineering-process"]')
}

test('PDE V1.2展示十节点版本治理流程', async ({ page }) => {
  const process = await openPdeProcess(page)
  await expect(process.getByRole('heading', { name: 'PDE产品研发工程流程 V1.2' })).toBeVisible()
  await expect(process.locator('[data-process-node]')).toHaveCount(10)
  for (const nodeName of ['产品版本管理', 'BOM版本管理', '工艺路线版本管理', '工程变更ECN']) {
    await expect(process.getByText(nodeName, { exact: true })).toBeVisible()
  }
})

test('产品版本页面显示版本号和生效区间', async ({ page }) => {
  const process = await openPdeProcess(page)
  await process.locator('[data-process-node="product-version-management"]').click()
  await expect(page).toHaveURL(/#\/pde\/product-versions$/)
  await expect(page.getByRole('heading', { name: '产品版本管理', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '版本号' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '生效日期' })).toBeVisible()
})

test('BOM版本页面存在产品版本号和BOM版本号', async ({ page }) => {
  await page.goto('/#/pde/bom-versions')
  await expect(page.getByRole('heading', { name: 'BOM版本管理', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '产品版本号' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'BOM版本号' })).toBeVisible()
  await expect(page.locator('[data-acceptance-id="pde-emd-source-facts"]')).toContainText('失效BOM不得作为MRP输入')
})

test('工艺版本页面存在工艺版本号', async ({ page }) => {
  await page.goto('/#/pde/routing-versions')
  await expect(page.getByRole('heading', { name: '工艺版本管理', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '工艺版本号' })).toBeVisible()
  await expect(page.locator('[data-acceptance-id="pde-emd-source-facts"]')).toContainText('失效工艺版本不得作为MES输入')
})

test('ECN页面显示变更前版本和变更后版本', async ({ page }) => {
  await page.goto('/#/pde/engineering-changes')
  await expect(page.getByRole('heading', { name: '工程变更管理', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '变更前版本' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '变更后版本' })).toBeVisible()
  await expect(page.locator('[data-acceptance-id="finance-operation-summary"]')).toContainText('复杂审批流')
})


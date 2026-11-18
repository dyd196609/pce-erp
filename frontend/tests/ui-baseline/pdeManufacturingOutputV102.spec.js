import { expect, test } from '@playwright/test'

test('PDE V1.3显示制造输出确认和MRP输入准备', async ({ page }) => {
  await page.goto('/#/process-center?module=PDE')
  await expect(page.locator('[data-process-module="PDE"]')).toHaveClass(/active/)
  const process = page.locator('[data-acceptance-id="pde-product-engineering-process"]')
  await expect(process.getByRole('heading', { name: 'PDE产品研发工程流程 V1.3' })).toBeVisible()
  await expect(process.locator('[data-process-node]')).toHaveCount(12)
  await expect(process.getByText('制造输出确认', { exact: true })).toBeVisible()
  await expect(process.getByText('MRP输入准备', { exact: true })).toBeVisible()
})

test('制造输出确认节点进入统一治理页面', async ({ page }) => {
  await page.goto('/#/process-center?module=PDE')
  await page.locator('[data-process-node="manufacturing-output-confirmation"]').click()
  await expect(page).toHaveURL(/#\/pde\/manufacturing-outputs$/)
  await expect(page.getByRole('heading', { name: 'PDE制造输出确认', exact: true })).toBeVisible()
  await expect(page.locator('[data-acceptance-id="finance-operation-summary"]')).toContainText('满足制造输入条件')
})

test('制造输出页面显示BOM工艺和EMD物料引用', async ({ page }) => {
  await page.goto('/#/pde/manufacturing-outputs')
  await expect(page.getByRole('columnheader', { name: 'BOM版本' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '工艺版本' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '物料来源' })).toBeVisible()
  const relationship = page.locator('[data-acceptance-id="pde-emd-source-facts"]')
  await expect(relationship.getByRole('heading', { name: '制造输入关系' })).toBeVisible()
  await expect(relationship).toContainText('PDE BOM → EMD物料 → 工艺路线 → 制造输入')
})

test('业务边界明确禁止采购付款财务执行', async ({ page }) => {
  await page.goto('/#/pde/manufacturing-outputs')
  const boundary = page.locator('[data-acceptance-id="pde-business-boundary-protection"]')
  await expect(boundary).toContainText('采购执行')
  await expect(boundary).toContainText('付款')
  await expect(boundary).toContainText('财务')
  await expect(boundary.getByText('否', { exact: true })).toHaveCount(3)
})

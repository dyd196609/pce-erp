import { expect, test } from '@playwright/test'

test('V852业务流程中心保留PDE、EMD、SCM流程入口', async ({ page }) => {
  await page.goto('/#/process-center')
  const center = page.locator('[data-acceptance-id="pce-business-process-center"]')
  await expect(center).toBeVisible()
  for (const moduleCode of ['PDE', 'EMD', 'SCM']) {
    await expect(center.locator(`[data-process-module="${moduleCode}"]`)).toHaveCount(1)
  }
  await expect(center).toHaveAttribute('data-master-data-maintenance', 'false')
})

test('V852数据引用中心保持只读', async ({ page }) => {
  await page.goto('/#/reference')
  const center = page.locator('[data-acceptance-id="enterprise-data-reference-center"]')
  await expect(center.getByRole('heading', { name: '数据引用中心', exact: true })).toBeVisible()
  for (const action of ['新增', '编辑', '删除']) {
    await expect(center.getByRole('button', { name: action, exact: true })).toHaveCount(0)
  }
  await expect(center).toHaveAttribute('data-edit-action-count', '0')
})

test('V852基础资料兼容入口使用企业基础资料名称', async ({ page }) => {
  await page.goto('/#/foundation')
  const foundation = page.locator('[data-acceptance-id="enterprise-foundation-data"]')
  await expect(foundation.locator('h1')).toHaveText('企业基础资料')
  await expect(foundation).toHaveAttribute('data-maintenance-owner', 'EMD')
})

test('V852制造数字化能力地图只展示十三项能力', async ({ page }) => {
  await page.goto('/#/manufacturing/modules')
  const map = page.locator('[data-acceptance-id="pce-manufacturing-capability-map"]')
  await expect(map.getByRole('heading', { name: 'PCE制造数字化能力地图', exact: true }).first()).toBeVisible()
  const capabilities = await map.locator('.module-card > header > span').evaluateAll(elements => (
    elements.map(element => element.textContent?.trim())
  ))
  expect(capabilities).toEqual([
    'ERP', 'CRM', 'SCM', 'WMS', 'MRP', 'MPS', 'APS',
    'MES', 'QMS', 'BI', 'FDM', 'KPI', 'PFM',
  ])
  await expect(map).toHaveAttribute('data-operation-entry', 'false')
  await expect(map).toHaveAttribute('data-business-execution-button-count', '0')
})

test('V852旧业务伙伴和制造模块入口保留兼容迁移', async ({ page }) => {
  await page.goto('/#/foundation/business-partners')
  await expect(page).toHaveURL(/#\/master-data\/suppliers$/)
  await expect(page.locator('[data-acceptance-id="enterprise-master-data-center"]')).toContainText('企业主数据中心')
  await page.goto('/#/manufacturing')
  await expect(page).toHaveURL(/#\/manufacturing\/modules$/)
  await expect(page.getByRole('heading', { name: 'PCE制造数字化能力地图', exact: true }).first()).toBeVisible()
})

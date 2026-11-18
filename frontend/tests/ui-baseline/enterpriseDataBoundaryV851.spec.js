import { expect, test } from '@playwright/test'

test('V851业务流程中心按治理顺序展示业务模块', async ({ page }) => {
  await page.goto('/#/process-center')
  const catalog = page.locator('[data-acceptance-id="business-process-center-v1"]')
  await expect(catalog).toBeVisible()
  const modules = await catalog.locator('[data-process-module]').evaluateAll(elements => (
    elements.map(element => element.getAttribute('data-process-module'))
  ))
  expect(modules).toEqual([
    'CRM', 'PDE', 'EMD', 'SCM', 'PLAN', 'MRP', 'MPS', 'APS',
    'WMS', 'MES', 'QMS', 'BI/FDM', 'KPI', 'ProfitOS',
  ])
  expect(modules.indexOf('PDE')).toBeLessThan(modules.indexOf('EMD'))
  expect(modules.indexOf('EMD')).toBeLessThan(modules.indexOf('SCM'))
})

test('V851数据引用中心只展示引用关系', async ({ page }) => {
  await page.goto('/#/reference')
  const center = page.locator('[data-acceptance-id="enterprise-data-reference-center"]')
  await expect(center.getByRole('heading', { name: '数据引用中心', exact: true })).toBeVisible()
  await expect(center.getByText('数据维护：')).toBeVisible()
  await expect(center.getByText('请进入企业主数据中心。')).toBeVisible()
  await expect(center.getByText('数据引用：')).toBeVisible()
  await expect(center.getByText('本页面只展示引用关系。')).toBeVisible()
  for (const action of ['新增', '编辑', '删除']) {
    await expect(center.getByRole('button', { name: action, exact: true })).toHaveCount(0)
  }
})

test('V851企业主数据页面显示统一中心名称', async ({ page }) => {
  await page.goto('/#/master-data/organizations')
  const center = page.locator('[data-acceptance-id="enterprise-master-data-center"]')
  await expect(center.getByRole('heading', { name: '企业主数据中心', exact: true })).toBeVisible()
  await expect(center.getByText('Enterprise Master Data Center（EMD）', { exact: true })).toBeVisible()
})

test('V851制造数字化能力地图只展示产品能力架构', async ({ page }) => {
  await page.goto('/#/manufacturing/modules')
  const map = page.locator('[data-acceptance-id="pce-manufacturing-capability-map"]')
  await expect(map.getByRole('heading', { name: 'PCE制造数字化能力地图', exact: true }).first()).toBeVisible()
  await expect(map.getByText('展示PCE覆盖的制造数字化能力，不是业务操作入口。', { exact: true })).toBeVisible()
  const names = await map.locator('.module-card > header > span').evaluateAll(elements => (
    elements.map(element => element.textContent?.trim())
  ))
  expect(names).toEqual([
    'PDE', 'CRM', 'EMD', 'SCM', 'PLAN', 'MRP', 'MPS',
    'APS', 'WMS', 'MES', 'QMS', 'BI/FDM', 'KPI',
  ])
  await expect(map.getByText('ERP', { exact: true })).toHaveCount(0)
})

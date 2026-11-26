import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/#/process-center')
  await page.evaluate(() => {
    localStorage.removeItem('pce-business-process-registry-v85')
  })
  await page.reload()
})

test('V85业务流程中心显示EMD并位于PDE与SCM之间', async ({ page }) => {
  const catalog = page.locator('[data-acceptance-id="business-process-center-v1"]')
  await expect(catalog).toBeVisible()
  const modules = await catalog.locator('[data-process-module]').evaluateAll(elements => (
    elements.map(element => element.getAttribute('data-process-module'))
  ))
  expect(modules).toEqual(['CRM', 'PDE', 'EMD', 'SCM', 'PLAN', 'WMS', 'MES', 'QMS', 'BI', 'ProfitOS'])
  await catalog.locator('[data-process-module="EMD"]').click()
  const emdProcess = page.locator('[data-acceptance-id="emd-master-data-maintenance-process"]')
  await expect(emdProcess.getByText('EMD企业主数据中心', { exact: true })).toBeVisible()
  await expect(emdProcess.locator('[data-process-node]')).toHaveCount(7)
})

test('V85供应商主数据使用企业级列表和服务端事实', async ({ page }) => {
  await page.goto('/#/master-data/suppliers')
  await expect(page.getByText('供应商主数据', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('供应商列表', { exact: true })).toBeVisible()
  await expect(page.locator('[data-pce-enterprise-list-runtime="V1.1"]')).toBeVisible()
  await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
  await expect(page.getByText('SUP-1001', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '高级筛选' })).toBeVisible()
  await expect(page.getByRole('button', { name: '导出当前结果' })).toBeVisible()
  await page.getByRole('button', { name: '查看详情' }).first().click()
  await expect(page.locator('[data-acceptance-id="pce-business-detail-card"]')).toBeVisible()
  await expect(page.locator('pre')).toHaveCount(0)
})

test('V85物料主数据字段、类型和五端事实一致', async ({ page }) => {
  await page.goto('/#/master-data/materials')
  await expect(page.getByText('物料主数据列表', { exact: true })).toBeVisible()
  for (const label of ['物料编码', '物料名称', '规格', '单位']) {
    await expect(page.getByRole('columnheader', { name: new RegExp(`^${label}`) })).toBeVisible()
  }
  const table = page.locator('[data-acceptance-id="master-data-materials-table"]')
  for (const type of ['原材料', '半成品', '成品', '辅料']) {
    await expect(table.getByText(type, { exact: true })).toBeVisible()
  }
  const acceptance = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  expect(acceptance.factSource).toBe('server')
  expect(acceptance.apiFacts).toEqual(acceptance.pageFacts)
  expect(acceptance.pageFacts).toEqual(acceptance.diagnosticFacts)
  expect(acceptance.diagnosticFacts).toEqual(acceptance.strictFacts)
  expect(acceptance.strictFacts).toEqual(acceptance.acceptanceFacts)
  expect(acceptance.resultCount).toBe(4)
})

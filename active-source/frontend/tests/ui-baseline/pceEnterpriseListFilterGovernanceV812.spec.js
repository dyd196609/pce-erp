import { expect, test } from '@playwright/test'

const pages = [
  {
    key: 'supplier-reconciliation',
    kind: 'reconciliation',
    title: '供应商对账',
    route: '/#/scm/supplier-reconciliations',
    selectField: 'statusCode',
    selectLabel: '对账状态',
    dateField: 'period',
    dateLabel: '对账期间',
    expectedFields: ['reconciliationNo', 'supplierName', 'period', 'statusCode'],
  },
  {
    key: 'supplier-performance',
    kind: 'supplier',
    title: '供应商绩效',
    route: '/#/scm/supplier-performance',
    selectField: 'supplierName',
    selectLabel: '供应商',
    dateField: 'period',
    dateLabel: '周期',
    expectedFields: ['supplierName', 'period'],
  },
  {
    key: 'buyer-performance',
    kind: 'buyer',
    title: '采购员绩效',
    route: '/#/scm/buyer-performance',
    selectField: 'buyerName',
    selectLabel: '采购员',
    dateField: 'period',
    dateLabel: '周期',
    expectedFields: ['buyerName', 'period'],
  },
]

async function openAdvancedFilter(page, definition) {
  await page.goto(definition.route)
  await expect(page.locator('[data-acceptance-id="page-identity-region"]')).toContainText(definition.title)
  const list = page.locator(`[data-acceptance-id="${definition.kind}-list"]`)
  await list.getByRole('button', { name: '展开高级筛选', exact: true }).click()
  const panel = page.locator(`[data-acceptance-id="v81-${definition.kind}-advanced-filter"]`)
  await expect(panel).toBeVisible()
  return { list, panel }
}

for (const definition of pages) {
  test(`${definition.title}-01 高级筛选可展开`, async ({ page }) => {
    const { panel } = await openAdvancedFilter(page, definition)
    await expect(panel).toHaveAttribute('data-pce-enterprise-filter-version', 'V1.1')
  })

  test(`${definition.title}-02 Schema字段与控件类型正确`, async ({ page }) => {
    const { panel } = await openAdvancedFilter(page, definition)
    for (const field of definition.expectedFields) {
      await expect(panel.locator(`[data-filter-field="${field}"]`)).toHaveCount(1)
    }
    await expect(panel.locator(`[data-filter-field="${definition.selectField}"]`))
      .toHaveAttribute('data-filter-type', 'select')
    await expect(panel.locator(`[data-filter-field="${definition.selectField}"] [data-pce-rendered-control-type="select"]`))
      .toBeVisible()
    await expect(panel.locator(`[data-filter-field="${definition.dateField}"]`))
      .toHaveAttribute('data-filter-type', 'daterange')
    await expect(panel.locator(`[data-filter-field="${definition.dateField}"] [data-pce-rendered-control-type="daterange"]`))
      .toBeVisible()
  })

  test(`${definition.title}-03 下拉选择改变查询结果`, async ({ page }) => {
    const { list, panel } = await openAdvancedFilter(page, definition)
    const before = await list.locator('.el-table__body-wrapper tbody tr').count()
    await panel.locator(`[data-filter-field="${definition.selectField}"] .el-select`).click()
    const option = page.locator('.el-select-dropdown:visible .el-select-dropdown__item').first()
    const optionText = (await option.textContent())?.trim()
    await option.click()
    await expect.poll(() => list.locator('.el-table__body-wrapper tbody tr').count()).toBeLessThanOrEqual(before)
    await expect(panel.locator(`[data-filter-field="${definition.selectField}"]`)).toContainText(optionText)
  })

  test(`${definition.title}-04 筛选参数传递API正确`, async ({ page }) => {
    const { panel } = await openAdvancedFilter(page, definition)
    await panel.locator(`[data-filter-field="${definition.selectField}"] .el-select`).click()
    const option = page.locator('.el-select-dropdown:visible .el-select-dropdown__item').first()
    const requestPromise = page.waitForRequest(request => (
      request.url().includes('/api/scm/') && new URL(request.url()).searchParams.has(definition.selectField)
    ))
    await option.click()
    const request = await requestPromise
    const actual = new URL(request.url()).searchParams.get(definition.selectField)
    expect(actual).toBeTruthy()
    await expect.poll(() => page.evaluate(field => (
      window.__PCE_BUSINESS_PAGE_ACCEPTANCE__?.filterApiParams?.[field]
    ), definition.selectField)).toBe(actual)
  })

  test(`${definition.title}-05 清空筛选恢复结果`, async ({ page }) => {
    const { list, panel } = await openAdvancedFilter(page, definition)
    const original = await list.locator('.el-table__body-wrapper tbody tr').count()
    await panel.locator(`[data-filter-field="${definition.selectField}"] .el-select`).click()
    await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').first().click()
    await list.getByRole('button', { name: '清空筛选', exact: true }).click()
    await expect.poll(() => list.locator('.el-table__body-wrapper tbody tr').count()).toBe(original)
  })

  test(`${definition.title}-06 导出当前结果可用`, async ({ page }) => {
    const { list } = await openAdvancedFilter(page, definition)
    const downloadPromise = page.waitForEvent('download')
    await list.getByRole('button', { name: '导出当前结果', exact: true }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toContain(`v81-${definition.kind}`)
  })
}

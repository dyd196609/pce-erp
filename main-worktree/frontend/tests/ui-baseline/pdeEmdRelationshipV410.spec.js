import { expect, test } from '@playwright/test'

async function openPdeProcess(page) {
  await page.goto('/#/process-center')
  await page.locator('[data-process-module="PDE"]').click()
  return page.locator('[data-acceptance-id="pde-product-engineering-process"]')
}

test('PDE流程展示产品设计、BOM、工艺路线和工程资料页面', async ({ page }) => {
  const process = await openPdeProcess(page)
  for (const nodeName of ['产品设计管理', 'BOM管理', '工艺路线管理', '工程资料管理']) {
    await expect(process.getByText(nodeName, { exact: true })).toBeVisible()
  }
  await expect(process.locator('[data-process-node]')).toHaveCount(8)
  await expect(process.locator('[data-process-node="engineering-data-release"]'))
    .toHaveAttribute('data-page-url', '/pde/engineering-documents')
})

test('BOM管理明确物料来源为EMD', async ({ page }) => {
  const process = await openPdeProcess(page)
  await process.locator('[data-process-node="bom-management"]').click()
  await expect(page).toHaveURL(/#\/pde\/product-boms$/)
  await expect(page.getByRole('heading', { name: 'BOM管理', exact: true })).toBeVisible()
  const relationships = page.locator('[data-acceptance-id="pde-emd-source-facts"]')
  await expect(relationships).toContainText('物料来源：EMD企业主数据中心')
  await expect(relationships).toContainText('禁止PDE创建或分配第二套物料编码')
})

test('工艺路线管理明确工作中心来源为EMD', async ({ page }) => {
  const process = await openPdeProcess(page)
  await process.locator('[data-process-node="routing-management"]').click()
  await expect(page).toHaveURL(/#\/pde\/routings$/)
  await expect(page.getByRole('heading', { name: '工艺路线管理', exact: true })).toBeVisible()
  await expect(page.locator('[data-acceptance-id="pde-emd-source-facts"]'))
    .toContainText('工作中心来源：EMD企业主数据中心')
})

test('工程资料管理接入统一页面治理且不提供CAD能力', async ({ page }) => {
  const process = await openPdeProcess(page)
  await process.locator('[data-process-node="engineering-data-release"]').click()
  await expect(page).toHaveURL(/#\/pde\/engineering-documents$/)
  await expect(page.getByRole('heading', { name: '工程资料管理', exact: true })).toBeVisible()
  await expect(page.locator('[data-pce-shell-type="PceListPageShell"]')).toBeVisible()
  await expect(page.locator('[data-acceptance-id="finance-operation-summary"]')).toContainText('禁止')
  await expect(page.locator('[data-acceptance-id="finance-operation-summary"]')).toContainText('上传CAD文件')
  await expect(page.locator('[data-acceptance-id="pde-server-facts"]')).toContainText('server')
  await expect(page.locator('[data-acceptance-id="pde-emd-source-facts"]'))
    .toContainText('产品设计、BOM、工艺路线')
})


import { expect, test } from '@playwright/test'

const expectedNodes = [
  '产品订单需求',
  '产品需求评审',
  '产品设计管理',
  'BOM管理',
  '工艺路线管理',
  '工程资料发布',
  '试制验证',
  '量产导入',
]

test('流程中心展示PDE V1.1八节点并可进入产品需求管理', async ({ page }) => {
  await page.goto('/#/process-center')
  await page.locator('[data-process-module="PDE"]').click()
  const process = page.locator('[data-acceptance-id="pde-product-engineering-process"]')
  await expect(process.getByRole('heading', { name: 'PDE产品研发工程流程 V1.1' })).toBeVisible()
  const nodes = process.locator('[data-process-node]')
  await expect(nodes).toHaveCount(8)
  expect(await nodes.locator('strong').allTextContents()).toEqual(expectedNodes)
  await process.locator('[data-process-node="product-requirement-review"]').click()
  await expect(page).toHaveURL(/#\/pde\/product-requirements$/)
})

test('产品需求管理具备统一治理区域并返回PDE模块', async ({ page }) => {
  await page.goto('/#/pde/product-requirements')
  await expect(page.getByRole('heading', { name: '产品需求管理', exact: true })).toBeVisible()
  for (const title of ['当前业务动作说明', '模块主流程', '业务流程导航', '业务边界保护']) {
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
  }
  await expect(page.locator('[data-pce-shell-type="PceListPageShell"]')).toBeVisible()
  await expect(page.locator('[data-acceptance-id="business-process-navigation"]')).toContainText('下一步：产品设计管理')
  await page.locator('[data-acceptance-id="return-process-center-button"]').click()
  await expect(page).toHaveURL(/#\/process-center\?module=PDE$/)
  await expect(page.locator('[data-process-module="PDE"]')).toHaveClass(/active/)
  await expect(page.locator('[data-acceptance-id="pde-product-engineering-process"]')).toBeVisible()
})

test('产品设计页面名称为产品设计管理', async ({ page }) => {
  await page.goto('/#/pde/product-definitions')
  await expect(page.getByRole('heading', { name: '产品设计管理', exact: true })).toBeVisible()
  await expect(page.locator('[data-acceptance-id="finance-operation-summary"]')).toContainText('面向订单交付')
})

test('BOM管理引用EMD物料并输出MRP依据', async ({ page }) => {
  await page.goto('/#/pde/product-boms')
  await expect(page.getByRole('heading', { name: 'BOM管理', exact: true })).toBeVisible()
  const boundary = page.locator('[data-acceptance-id="pde-business-boundary-protection"]')
  await expect(boundary).toContainText('EMD物料')
  await expect(boundary).toContainText('MRP输入依据')
})

test('工艺路线页面名称为工艺路线管理', async ({ page }) => {
  await page.goto('/#/pde/routings')
  await expect(page.getByRole('heading', { name: '工艺路线管理', exact: true })).toBeVisible()
  await expect(page.locator('[data-acceptance-id="finance-operation-summary"]')).toContainText('EMD工作中心')
  await expect(page.locator('[data-acceptance-id="pde-product-boms-page"]')).toHaveCount(0)
})


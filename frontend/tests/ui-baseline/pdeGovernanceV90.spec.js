import { expect, test } from '@playwright/test'

const expectedNodes = [
  ['product-requirement', '产品需求'],
  ['product-initiation', '产品立项'],
  ['product-design', '产品设计'],
  ['bom-establishment', 'BOM建立'],
  ['routing-design', '工艺路线设计'],
  ['engineering-data-release', '工程资料发布'],
  ['mass-production-introduction', '量产导入'],
]

test('PDE模块与产品研发工程流程按七节点顺序注册', async ({ page }) => {
  await page.goto('/#/process-center')
  const pdeModule = page.locator('[data-process-module="PDE"]')
  await expect(pdeModule).toContainText('PDE')
  await expect(pdeModule).toContainText('产品研发与工程管理中心')
  await pdeModule.click()

  const process = page.locator('[data-acceptance-id="pde-product-engineering-process"]')
  await expect(process.getByText('产品研发与工程流程', { exact: true })).toBeVisible()
  const nodes = process.locator('[data-process-node]')
  await expect(nodes).toHaveCount(7)
  const actual = await nodes.evaluateAll(elements => elements.map(element => [
    element.getAttribute('data-process-node'),
    element.querySelector('strong')?.textContent?.trim(),
  ]))
  expect(actual).toEqual(expectedNodes)
})

test('PDE BOM页面复用企业列表契约与服务端事实', async ({ page }) => {
  await page.goto('/#/pde/product-boms')
  const pageRoot = page.locator('[data-acceptance-id="pde-product-boms-page"]')
  await expect(pageRoot.getByRole('heading', { name: 'BOM管理', exact: true })).toBeVisible()
  await expect(pageRoot).toHaveAttribute(
    'data-enterprise-list-contract',
    'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
  )
  await expect(pageRoot).toHaveAttribute('data-fact-source', 'server')
  await expect(page.locator('[data-pce-enterprise-list-contract="PCE-ENTERPRISE-LIST-CONTRACT-V1.1"]')).toBeVisible()
  await expect(page.locator('[data-acceptance-id="pde-server-facts"]')).toContainText('server')
  const acceptance = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  expect(acceptance.factSource).toBe('server')
  expect(acceptance.strictFacts).toEqual(acceptance.acceptanceFacts)
})


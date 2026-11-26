import { expect, test } from '@playwright/test'

const scmNodeOrder = [
  '采购申请', '询价', '核价', '采购订单', '收货', '质量检验', '入库',
  '供应商对账', '差异分析', '供应商确认', '应付确认', '付款申请',
  '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效',
]

test.beforeEach(async ({ page }) => {
  await page.goto('/#/process-designer')
  await page.evaluate(() => {
    localStorage.removeItem('pce-business-process-registry-v842')
  })
  await page.reload()
})

test('V842流程中心与设计中心共用七条正式流程', async ({ page }) => {
  await page.goto('/#/process-center')
  const catalog = page.locator('[data-acceptance-id="business-process-center-v1"]')
  await expect(catalog).toBeVisible()
  await expect(catalog).toHaveAttribute('data-process-count', '7')
  const moduleCodes = await catalog.locator('[data-process-module]').evaluateAll(elements => (
    elements.map(element => element.getAttribute('data-process-module'))
  ))
  expect(moduleCodes.indexOf('PDE')).toBeLessThan(moduleCodes.indexOf('SCM'))

  await page.goto('/#/process-designer')
  const designer = page.locator('[data-acceptance-id="process-designer-page"]')
  await expect(designer).toHaveAttribute('data-process-source', 'businessProcessRegistry')
  await expect(page.locator('[data-process-code]')).toHaveCount(7)
  await expect(page.getByText('SCM采购与供应商结算流程', { exact: true })).toBeVisible()
  await expect(page.getByText('计划流程', { exact: true })).toHaveCount(0)
  await expect(page.getByText('发货流程', { exact: true })).toHaveCount(0)
  await expect(page.getByText('测试流程副本', { exact: true })).toHaveCount(0)
})

test('V842 SCM节点顺序和页面版本来自统一注册表', async ({ page }) => {
  await page.goto('/#/process-designer/process/SCM_PURCHASE_SETTLEMENT')
  const nodeList = page.locator('[data-acceptance-id="process-designer-node-list"]')
  await expect(nodeList).toBeVisible()
  await expect(nodeList.locator('[data-node-code]')).toHaveCount(16)
  const actualNodes = await nodeList.locator('[data-node-code] strong').allTextContents()
  expect(actualNodes.map(value => value.trim())).toEqual(scmNodeOrder)
  await expect(nodeList).toContainText('V1.14.2.8.4.8.3.1.1')
  await expect(page.getByText('businessProcessRegistry', { exact: true })).toBeVisible()
})

test('V842流程版本修改与启停回写统一注册表', async ({ page }) => {
  await page.goto('/#/process-designer/process/SCM_PURCHASE_SETTLEMENT/edit')
  await page.getByLabel('流程版本').fill('V1.1')
  await page.getByRole('button', { name: '保存流程', exact: true }).click()
  await expect(page).toHaveURL(/#\/process-designer$/)
  const scmCard = page.locator('[data-process-code="SCM_PURCHASE_SETTLEMENT"]')
  await expect(scmCard).toContainText('流程版本：V1.1')
  await scmCard.getByRole('button', { name: '停用', exact: true }).click()
  await expect(scmCard).toContainText('设计状态：已停用')
  await page.reload()
  await expect(page.locator('[data-process-code="SCM_PURCHASE_SETTLEMENT"]')).toContainText('流程版本：V1.1')
  await expect(page.locator('[data-process-code="SCM_PURCHASE_SETTLEMENT"]')).toContainText('设计状态：已停用')
})

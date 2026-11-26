import { expect, test } from '@playwright/test'

test('V841 PDE模块位于SCM之前且保持SCM采购流程', async ({ page }) => {
  await page.goto('/#/process-center')
  const catalog = page.locator('[data-acceptance-id="business-process-center-v1"]')
  await expect(catalog).toBeVisible()

  const moduleButtons = catalog.locator('[data-process-module]')
  await expect(moduleButtons).toHaveCount(9)
  const moduleCodes = await moduleButtons.evaluateAll(elements => (
    elements.map(element => element.getAttribute('data-process-module'))
  ))
  expect(moduleCodes).toEqual(['CRM', 'PDE', 'SCM', 'PLAN', 'WMS', 'MES', 'QMS', 'BI', 'ProfitOS'])
  expect(moduleCodes.indexOf('PDE')).toBeLessThan(moduleCodes.indexOf('SCM'))
  await expect(catalog).toContainText('CRM营销业务中心')
  await expect(catalog).toContainText('PDE产品研发与工程管理中心')
  await expect(catalog).toContainText('SCM供应链管理中心')

  const scmProcess = page.locator('[data-acceptance-id="scm-purchase-settlement-process"]')
  const expectedScmOrder = [
    '采购申请', '询价', '核价', '采购订单', '收货', '质量检验', '入库',
    '供应商对账', '差异分析', '供应商确认', '应付确认', '付款申请',
    '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效',
  ]
  expect((await scmProcess.locator('[data-process-node] strong').allTextContents()).map(value => value.trim()))
    .toEqual(expectedScmOrder)
})

test('V841 PDE规划流程不伪造业务页面', async ({ page }) => {
  await page.goto('/#/process-center')
  await page.locator('[data-process-module="PDE"]').click()
  const pdeProcess = page.locator('[data-acceptance-id="pde-product-engineering-process"]')
  await expect(pdeProcess).toBeVisible()
  await expect(pdeProcess.locator('[data-process-node]')).toHaveCount(6)
  await expect(pdeProcess.locator('[data-page-status="planned"]')).toHaveCount(6)
  await expect(pdeProcess.locator('[data-acceptance-status="not_started"]')).toHaveCount(6)
  await expect(pdeProcess).toContainText('产品需求')
  await expect(pdeProcess).toContainText('产品设计')
  await expect(pdeProcess).toContainText('工程评审')
  await expect(pdeProcess).toContainText('BOM建立')
  await expect(pdeProcess).toContainText('工艺路线')
  await expect(pdeProcess).toContainText('工程资料发布')
  await expect(pdeProcess).toContainText('工程资料驱动采购')
  await expect(pdeProcess.locator('[data-page-url]')).toHaveCount(0)
})


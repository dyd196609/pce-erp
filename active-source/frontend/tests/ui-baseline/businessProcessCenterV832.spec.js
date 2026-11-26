import { expect, test } from '@playwright/test'

test('V832 业务流程中心展示模块目录与 SCM 采购结算流程', async ({ page }) => {
  await page.goto('/#/process-center')

  const catalog = page.locator('[data-acceptance-id="business-process-center-v1"]')
  await expect(catalog).toBeVisible()
  await expect(catalog).toContainText('企业业务流程目录')

  const moduleNavigation = page.locator('[data-acceptance-id="business-module-navigation"]')
  for (const moduleCode of ['CRM', 'SCM', 'WMS', 'Plan', 'MES', 'QMS', 'BI', 'ProfitOS']) {
    await expect(moduleNavigation.locator(`[data-process-module="${moduleCode}"]`)).toBeVisible()
  }

  const scmProcess = page.locator('[data-acceptance-id="scm-purchase-settlement-process"]')
  await expect(scmProcess).toBeVisible()
  await expect(scmProcess.locator('[data-process-node]')).toHaveCount(15)
  await expect(scmProcess).toContainText('采购申请')
  await expect(scmProcess).toContainText('供应商对账')
  await expect(scmProcess).toContainText('付款申请')
  await expect(scmProcess).toContainText('采购员绩效')
})

test('V832 SCM 付款申请流程节点导航到已注册页面', async ({ page }) => {
  await page.goto('/#/process-center')
  const node = page.locator('[data-process-node="supplier-payment-request"]')
  await expect(node).toContainText('付款申请')
  await expect(node).toHaveAttribute('data-page-url', '/scm/supplier-payment-requests')
  await node.click()
  await expect(page).toHaveURL(/#\/scm\/supplier-payment-requests$/)
})

test('V832 流程页面版本与验收状态可观测', async ({ page }) => {
  await page.goto('/#/process-center')
  const boundNodes = page.locator('[data-acceptance-id="scm-purchase-settlement-process"] .process-node.bound')
  await expect(boundNodes).toHaveCount(7)
  for (let index = 0; index < 7; index += 1) {
    await expect(boundNodes.nth(index)).toContainText('页面已挂接 · PASS')
    await expect(boundNodes.nth(index).locator('small')).toContainText(/^V1\.14\./)
  }
})


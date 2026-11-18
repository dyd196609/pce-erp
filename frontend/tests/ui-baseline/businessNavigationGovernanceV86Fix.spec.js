import { expect, test } from '@playwright/test'

test('V86业务流程中心只保留模块到流程节点的唯一导航链', async ({ page }) => {
  await page.goto('/#/process-center')

  const center = page.locator('[data-acceptance-id="pce-business-process-center"]')
  const catalog = center.locator('[data-acceptance-id="business-process-center-v1"]')
  await expect(center).toHaveAttribute('data-isolated-business-shortcut-count', '0')
  await expect(center).toHaveAttribute('data-navigation-hierarchy', 'module-process-node-page')
  await expect(center.locator('[data-pce-business-module-zone="top"]')).toHaveCount(0)

  await expect(catalog.getByText('SCM供应链管理中心', { exact: true })).toBeVisible()
  await expect(catalog.getByText('SCM采购与供应商结算流程', { exact: true })).toBeVisible()

  for (const shortcutName of ['采购申请', '付款申请', '供应商绩效']) {
    await expect(page.locator('header.page-header').getByRole('link', { name: shortcutName, exact: true })).toHaveCount(0)
  }

  const paymentRequestNode = catalog.locator('[data-process-node="supplier-payment-request"]')
  await expect(paymentRequestNode).toContainText('付款申请')
  await expect(paymentRequestNode).toHaveAttribute('data-page-url', '/scm/supplier-payment-requests')
  await paymentRequestNode.click()
  await expect(page).toHaveURL(/#\/scm\/supplier-payment-requests$/)
})

import { test, expect } from '@playwright/test'

const pages = [
  '/finance/payable-prepares',
  '/finance/payable-checks',
  '/scm/supplier-settlements',
  '/finance/purchase-invoice-prepares',
  '/finance/ap-drafts',
  '/finance/account-payable-confirms',
  '/finance/payment-applications',
  '/finance/payment-order-prepares',
  '/finance/payment-prepares',
  '/finance/payment-order-drafts',
  '/finance/payment-risk-reviews',
  '/finance/payment-execution-prepares',
  '/finance/payment-executions',
  '/finance/payment-voucher-drafts',
  '/finance/payment-voucher-reviews',
  '/finance/payment-record-reviews',
  '/finance/formal-payment-vouchers',
]

test.describe('V1.14.1 采购应付至正式付款凭证统一操作布局', () => {
  for (const routePath of pages) {
    test(`${routePath} 接入统一业务操作外壳`, async ({ page }) => {
      await page.goto(`/#${routePath}`)
      await expect(page.locator('[data-acceptance-id="business-operation-page-shell"]')).toBeVisible()
      await expect(page.locator('[data-acceptance-id="page-business-title"]')).toBeVisible()
      await expect(page.locator('[data-acceptance-id="business-process-navigation"]')).toBeVisible()
      await expect(page.locator('[data-acceptance-id="page-operation-guide"]')).toContainText('本页操作说明')
      await expect(page.locator('[data-acceptance-id="current-business-operation"]')).toBeVisible()
      await expect(page.locator('[data-acceptance-id="operation-result-next-step"]')).toContainText('操作结果与下一步')
      await expect(page.locator('[data-acceptance-id="technical-diagnostics-toggle"]')).toContainText('技术诊断与开发验证')
      await expect(page.locator('[data-acceptance-id="technical-diagnostics-content"]')).toHaveCount(0)
    })
  }
})

import { expect, test } from '@playwright/test'

test.describe('V1.13.68.1 payment voucher prepare acceptance', () => {
  test('normal PEP shows acceptance summary and precheck counts', async ({ page }) => {
    await page.goto('/#/finance/payment-voucher-prepare-preview/PEP2026071311191257')
    await expect(page.getByText('V1.13.68.1 关键验收摘要')).toBeVisible()
    await expect(page.getByText('页面运行时自动验收结果')).toBeVisible()
    await expect(page.locator('[data-acceptance-id="precheck-passed-count"]')).toContainText('11')
    await expect(page.locator('[data-acceptance-id="precheck-blocked-count"]')).toContainText('20')
    await expect(page.locator('[data-acceptance-id="precheck-warning-count"]')).toContainText('0')
    await expect(page.locator('[data-acceptance-id="precheck-not-applicable-count"]')).toContainText('1')
    await expect(page.locator('[data-acceptance-id="allowed-pure-preview-effect-count"]')).toContainText('18')
    await expect(page.locator('[data-acceptance-id="forbidden-by-policy-effect-count"]')).toContainText('22')
  })

  test('UNKNOWN-PEP remains stable and blocked', async ({ page }) => {
    await page.goto('/#/finance/payment-voucher-prepare-preview/UNKNOWN-PEP')
    await expect(page.getByText('V1.13.68.1 关键验收摘要')).toBeVisible()
    await expect(page.getByText('付款执行准备不存在')).toBeVisible()
    await expect(page.locator('[data-acceptance-id="precheck-passed-count"]')).toContainText('6')
    await expect(page.locator('[data-acceptance-id="precheck-blocked-count"]')).toContainText('25')
    await expect(page.locator('[data-acceptance-id="precheck-warning-count"]')).toContainText('0')
    await expect(page.locator('[data-acceptance-id="precheck-not-applicable-count"]')).toContainText('1')
    await expect(page.locator('[data-acceptance-id="business-data-written-count"]')).toContainText('0')
  })
})

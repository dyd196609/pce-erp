import { test, expect } from '@playwright/test'

test('process center opens SCM nodes in independent tabs without business writes', async ({ page, context }) => {
  const mutationRequests = []
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) {
      mutationRequests.push(`${request.method()} ${request.url()}`)
    }
  })

  await page.goto('/#/process-center', { waitUntil: 'domcontentloaded' })
  const center = page.locator('[data-acceptance-id="pce-business-process-center"]')
  await expect(center).toBeVisible()
  await expect(center.locator('[data-process-node]')).toHaveCount(16)

  const purchaseRequest = center.locator('[data-process-node="purchase-request"]')
  await purchaseRequest.locator('.process-node-summary').click()
  await expect(page).toHaveURL(/#\/process-center/)
  await expect(center.locator('[data-acceptance-id="process-node-inspector"]')).toContainText('采购申请')

  const purchaseRequestPopupPromise = context.waitForEvent('page')
  await purchaseRequest.locator('[data-process-node-action="new-tab"]').click()
  const purchaseRequestPopup = await purchaseRequestPopupPromise
  await purchaseRequestPopup.waitForLoadState('domcontentloaded')
  await expect(purchaseRequestPopup).toHaveURL(/#\/scm\/purchase-request$/)
  await expect(page).toHaveURL(/#\/process-center/)

  const inquiry = center.locator('[data-process-node="request-for-quotation"]')
  const inquiryPopupPromise = context.waitForEvent('page')
  await inquiry.locator('[data-process-node-action="new-tab"]').click()
  const inquiryPopup = await inquiryPopupPromise
  await inquiryPopup.waitForLoadState('domcontentloaded')
  await expect(inquiryPopup).toHaveURL(/#\/scm\/purchase-inquiry$/)

  expect(context.pages()).toHaveLength(3)
  expect(mutationRequests).toEqual([])
})

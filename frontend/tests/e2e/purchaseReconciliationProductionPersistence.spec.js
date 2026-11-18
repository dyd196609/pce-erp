import { test, expect } from '@playwright/test'

test('production persistence readiness renders nine server-evidence regions without production writes', async ({ page }) => {
  const writeRequests = []
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method()) && request.url().includes('/api/')) writeRequests.push(request.url())
  })
  await page.addInitScript((acceptance) => { window.__PCE_PRODUCTION_PERSISTENCE_ACCEPTANCE__ = acceptance }, {
    environment: 'isolated-test-database', tenantId: 'tenant-v41', transactionState: 'committed',
    targetId: '1', reconciliationNo: 'PRC202607TEST', sourceKey: 'supplier-settlement:tenant-v41:PCE-REG-concurrent',
    transactionId: 'PRCTX-test', canaryBatchId: process.env.PCE_CANARY_BATCH_ID || 'v41-canary', failureInjectionCount: 15,
  })
  const url = '/#/scm/purchase-reconciliations?designMode=production_persistence_readiness&scenarioCode=CANARY_A&testTenantId=tenant-v41&sourceSupplierSettlementNo=PCE-REG-concurrent&reviewId=review-concurrent&idempotencyKey=idem-concurrent&transactionId=PRCTX-test'
  await page.goto(url)
  await expect(page.getByRole('heading', { name: '采购对账生产持久化能力验收' })).toBeVisible()
  const headings = ['生产持久化能力总览', '服务端业务动作门禁', '服务端事务能力门禁', '正式采购对账持久化结果', '硬唯一约束验证', '服务端授权与灰度边界', '事务、回滚与提交恢复', '金丝雀群与并发结果', '生产灰度与下游保护']
  for (const heading of headings) await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  await expect(page.getByText('生产灰度开关：关闭').first()).toBeVisible()
  await expect(page.getByText('用户正式租户对象数量：0')).toBeVisible()
  await expect(page.getByText('付款对象数量：0')).toBeVisible()
  await expect(page.locator('[data-acceptance-id="persistence-readonly-actions"] button')).toHaveCount(4)
  expect(writeRequests).toEqual([])
  if (process.env.PCE_CANARY_STAGING_DIR) {
    await page.screenshot({ path: `${process.env.PCE_CANARY_STAGING_DIR}/checkpoint-screenshot.png`, fullPage: true })
  }
})

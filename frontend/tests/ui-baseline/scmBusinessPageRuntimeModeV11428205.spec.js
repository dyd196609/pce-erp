import { test, expect } from '@playwright/test'

async function authenticate(page) {
  const response = await page.request.post('/api/auth/login/', { data: { username: 'admin', password: 'admin123' } })
  expect(response.ok()).toBeTruthy()
  const payload = await response.json()
  await page.addInitScript(token => localStorage.setItem('token', token), payload.token)
}

test.beforeEach(async ({ page }) => authenticate(page))

test('同一页面组件在production模式读取正式事实', async ({ page }) => {
  const requests = []
  page.on('request', request => requests.push(request.url()))
  await page.goto('/#/scm/purchase-request', { waitUntil: 'domcontentloaded' })
  const root = page.locator('[data-acceptance-id="purchase-request-business-page"]')
  await expect(root).toHaveAttribute('data-page-code', 'purchase-request')
  await expect(page.locator('[data-acceptance-id="scm-business-data-mode"]')).toHaveText('production')
  await expect(page.locator('[data-acceptance-id="purchase-request-enterprise-list-runtime"]')).toHaveAttribute('data-source-mode', 'production')
  await expect.poll(() => page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').count()).toBeGreaterThan(1)
  expect(requests.filter(url => url.includes('/api/procurement/scm-page-facts/purchase-request/')).length).toBeGreaterThan(0)
  expect(requests.filter(url => url.includes('/api/pce/purchase-canary/context'))).toHaveLength(0)
})

test('同一页面组件在canary模式使用统一列表和只读详情', async ({ page }) => {
  const requests = []
  const writes = []
  page.on('request', request => {
    requests.push(request.url())
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) writes.push(`${request.method()} ${request.url()}`)
  })
  await page.goto('/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=HAPPY_PATH', { waitUntil: 'domcontentloaded' })
  const root = page.locator('[data-acceptance-id="purchase-request-business-page"]')
  await expect(root).toHaveAttribute('data-page-code', 'purchase-request')
  await expect(page.locator('[data-acceptance-id="scm-business-data-mode"]')).toHaveText('canary_acceptance')
  const row = page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').first()
  await expect(row).toContainText('PRQ-CAN-001')
  await row.getByRole('button', { name: '查看' }).click()
  await expect(page.getByRole('dialog', { name: '采购申请只读详情' })).toBeVisible()
  await expect(page.locator('[data-acceptance-id="pce-business-detail-card"]')).toContainText('PRQ-CAN-001')
  await expect(page.locator('[data-acceptance-id="pce-business-detail-card"]')).toContainText('HAPPY_PATH')
  expect(requests.filter(url => url.includes('/api/procurement/scm-page-facts/purchase-request/'))).toHaveLength(0)
  expect(requests.filter(url => url.includes('/api/pce/purchase-canary/context')).length).toBeGreaterThan(0)
  expect(writes).toHaveLength(0)
})

test('QUALITY_FAIL切换与刷新保持业务编号', async ({ page }) => {
  await page.goto('/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=QUALITY_FAIL', { waitUntil: 'domcontentloaded' })
  const row = page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').first()
  await expect(row).toContainText('PRQ-CAN-003')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(row).toContainText('PRQ-CAN-003')
  await expect(page.locator('[data-acceptance-id="canary-list-scenario-code"]')).toHaveText('QUALITY_FAIL')
})

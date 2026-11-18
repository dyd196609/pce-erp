import { test, expect } from '@playwright/test'

async function authenticate(page) {
  const response = await page.request.post('/api/auth/login/', { data: { username: 'admin', password: 'admin123' } })
  expect(response.ok()).toBeTruthy()
  const payload = await response.json()
  await page.addInitScript(token => localStorage.setItem('token', token), payload.token)
}

test.beforeEach(async ({ page }) => authenticate(page))

test('金丝雀URL只读取Canary Provider且列表只有当前场景对象', async ({ page }) => {
  const requests = []
  page.on('request', request => requests.push(request.url()))
  await page.goto('/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=HAPPY_PATH', { waitUntil: 'domcontentloaded' })
  const tableRuntime = page.locator('[data-acceptance-id="purchase-request-enterprise-list-runtime"]')
  const rows = page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr')
  await expect(tableRuntime).toHaveAttribute('data-source-mode', 'canary_acceptance')
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText('PRQ-CAN-001')
  await expect(page.locator('body')).not.toContainText('PR202608020008')
  await expect(page.locator('[data-acceptance-id="canary-list-data-source"]')).toHaveText('canary_acceptance')
  await expect(page.locator('[data-acceptance-id="canary-list-business-read"]')).toHaveText('否')
  await expect(page.locator('[data-acceptance-id="canary-list-object-count"]')).toHaveText('8')
  expect(requests.filter(url => url.includes('/api/procurement/purchase-requests/'))).toHaveLength(0)
  expect(requests.filter(url => url.includes('/api/procurement/scm-page-facts/purchase-request/'))).toHaveLength(0)
  expect(requests.filter(url => url.includes('/api/pce/purchase-canary/context'))).toHaveLength(1)
})

test('普通URL继续使用业务数据源', async ({ page }) => {
  await page.goto('/#/scm/purchase-request', { waitUntil: 'domcontentloaded' })
  const tableRuntime = page.locator('[data-acceptance-id="purchase-request-enterprise-list-runtime"]')
  const table = page.locator('[data-acceptance-id="purchase-request-table"]')
  await expect(tableRuntime).toHaveAttribute('data-source-mode', 'production')
  await expect(page.locator('[data-acceptance-id="enterprise-list-canary-mode"]')).toHaveCount(0)
  await expect.poll(() => table.locator('.el-table__body tbody tr').count()).toBeGreaterThan(1)
})

test('场景切换和刷新保持，正式列表不能回写', async ({ page }) => {
  await page.goto('/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=HAPPY_PATH', { waitUntil: 'domcontentloaded' })
  const row = page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').first()
  await expect(row).toContainText('PRQ-CAN-001')
  await expect(page.locator('body')).not.toContainText('PR202608020008')

  await page.goto('/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=PRICE_EXCEPTION', { waitUntil: 'domcontentloaded' })
  await expect(row).toContainText('PRQ-CAN-007')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(row).toContainText('PRQ-CAN-007')
  await expect(page.locator('[data-acceptance-id="canary-list-scenario-code"]')).toHaveText('PRICE_EXCEPTION')
})

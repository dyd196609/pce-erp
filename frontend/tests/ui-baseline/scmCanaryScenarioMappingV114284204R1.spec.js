import { test, expect } from '@playwright/test'

const expected = Object.freeze({
  HAPPY_PATH: 'PRQ-CAN-001',
  PRICE_EXCEPTION: 'PRQ-CAN-007',
  QUALITY_FAIL: 'PRQ-CAN-003',
  QUANTITY_DIFFERENCE: 'PRQ-CAN-004',
  SOURCE_MISSING: 'PRQ-CAN-005',
  INVOICE_VALIDATION_FAILED: 'PRQ-CAN-006',
  DUPLICATE_INVOICE: 'PRQ-CAN-002',
  SOURCE_STALE: 'PRQ-CAN-008',
})

test('八场景对象唯一映射，正式API零调用，刷新保持', async ({ page }) => {
  const authentication = await page.request.post('/api/auth/login/', { data: { username: 'admin', password: 'admin123' } })
  expect(authentication.ok()).toBeTruthy()
  const authenticationPayload = await authentication.json()
  await page.addInitScript(token => localStorage.setItem('token', token), authenticationPayload.token)
  const requests = []
  page.on('request', request => requests.push(request.url()))

  for (const [scenarioCode, businessNo] of Object.entries(expected)) {
    await page.goto(`/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=${scenarioCode}`, { waitUntil: 'domcontentloaded' })
    const rows = page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr')
    await expect(rows).toHaveCount(1)
    await expect(rows.first()).toContainText(businessNo)
    await expect(page.locator('[data-acceptance-id="canary-list-scenario-code"]')).toHaveText(scenarioCode)
    await expect(page.locator('[data-acceptance-id="canary-list-data-mode"]')).toHaveText('canary_acceptance')
    await expect(page.locator('body')).not.toContainText('PRQ-DEMO-')
  }

  await page.goto('/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=PRICE_EXCEPTION', { waitUntil: 'domcontentloaded' })
  const before = await page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').first().innerText()
  await page.reload({ waitUntil: 'domcontentloaded' })
  const after = await page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').first().innerText()
  expect(after).toBe(before)
  expect(after).toContain('PRQ-CAN-007')
  expect(requests.filter(url => url.includes('/api/procurement/purchase-requests/'))).toHaveLength(0)
  expect(requests.filter(url => url.includes('/api/procurement/scm-page-facts/purchase-request/'))).toHaveLength(0)
})

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const canaryDatabase = path.resolve(frontendRoot, '../backend/canary-data/scm-canary-flow-v1.sqlite3')
const formalDatabase = path.resolve(frontendRoot, '../backend/db.sqlite3')
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')

test('SCM金丝雀群：场景切换、通用页面壳与刷新保持', async ({ page }) => {
  const authentication = await page.request.post('/api/auth/login/', {
    data: { username: 'admin', password: 'admin123' },
  })
  expect(authentication.ok()).toBeTruthy()
  const authenticationPayload = await authentication.json()
  await page.addInitScript(token => localStorage.setItem('token', token), authenticationPayload.token)

  const requests = []
  const businessWrites = []
  page.on('request', request => {
    requests.push({ method: request.method(), url: request.url() })
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())
      && !request.url().endsWith('/api/auth/login/')) businessWrites.push(`${request.method()} ${request.url()}`)
  })
  const canaryHashBefore = digest(canaryDatabase)
  const formalHashBefore = digest(formalDatabase)
  const expected = [
    ['HAPPY_PATH', 'PRQ-CAN-001'],
    ['PRICE_EXCEPTION', 'PRQ-CAN-007'],
    ['QUALITY_FAIL', 'PRQ-CAN-003'],
  ]

  for (const [scenario, requestNo] of expected) {
    requests.length = 0
    await page.goto(`/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=${scenario}`, { waitUntil: 'domcontentloaded' })
    const pageRoot = page.locator('[data-acceptance-id="purchase-request-business-page"]')
    const card = page.locator('[data-acceptance-id="enterprise-list-canary-mode"]')
    const row = page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').first()
    await expect(pageRoot).toHaveAttribute('data-canary-mode', 'true')
    await expect(card.locator('[data-acceptance-id="canary-list-data-mode"]')).toHaveText('canary_acceptance')
    await expect(card.locator('[data-acceptance-id="canary-list-batch-id"]')).toHaveText('SCM-CANARY-FLOW-V1')
    await expect(card.locator('[data-acceptance-id="canary-list-scenario-code"]')).toHaveText(scenario)
    await expect(card.locator('[data-acceptance-id="canary-list-object-no"]')).toHaveText(requestNo)
    await expect(row).toContainText(requestNo)
    expect(requests.filter(item => item.url.includes('/api/procurement/scm-page-facts/purchase-request/'))).toEqual([])
    expect(requests.filter(item => item.url.includes('/api/pce/purchase-canary/context')).length).toBeGreaterThan(0)
  }

  const refreshUrl = page.url()
  const refreshRow = await page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').first().innerText()
  await page.reload({ waitUntil: 'domcontentloaded' })
  expect(page.url()).toBe(refreshUrl)
  await expect(page.locator('[data-acceptance-id="canary-list-scenario-code"]')).toHaveText('QUALITY_FAIL')
  expect(await page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').first().innerText()).toBe(refreshRow)

  requests.length = 0
  await page.goto('/#/scm/supplier-reconciliations?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=HAPPY_PATH', { waitUntil: 'domcontentloaded' })
  const generic = page.locator('[data-acceptance-id="enterprise-canary-list-view"]')
  await expect(generic).toBeVisible()
  await expect(generic).toHaveAttribute('data-list-data-mode', 'canary_acceptance')
  await expect(page.locator('[data-acceptance-id="supplier-reconciliation-canary-table"] .el-table__body tbody tr').first()).toContainText('REC-CAN-001')
  expect(requests.filter(item => item.url.includes('/api/procurement/scm-page-facts/supplier-reconciliation/'))).toEqual([])
  expect(requests.filter(item => item.url.includes('/api/pce/purchase-canary/context')).length).toBeGreaterThan(0)

  expect(digest(canaryDatabase)).toBe(canaryHashBefore)
  expect(digest(formalDatabase)).toBe(formalHashBefore)
  expect(businessWrites).toEqual([])
})

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const canaryDatabase = path.resolve(frontendRoot, '../backend/canary-data/purchase-flow-demo.sqlite3')
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')

test('采购申请一页一验收：Query切换金丝雀Provider且刷新保持', async ({ page }) => {
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
      && !request.url().endsWith('/api/auth/login/')) {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })

  await page.goto('/#/scm/purchase-request', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('[data-acceptance-id="purchase-request-business-page"]')).toHaveAttribute('data-canary-mode', 'false')
  await expect(page.locator('[data-acceptance-id="enterprise-list-canary-mode"]')).toHaveCount(0)
  await expect.poll(() => page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').count()).toBeGreaterThan(1)

  requests.length = 0
  const databaseHashBefore = digest(canaryDatabase)
  const canaryUrl = '/#/scm/purchase-request?canaryBatchId=PURCHASE-FLOW-DEMO-V1&scenarioCode=HAPPY_PATH'
  await page.goto(canaryUrl, { waitUntil: 'domcontentloaded' })

  const pageRoot = page.locator('[data-acceptance-id="purchase-request-business-page"]')
  const card = page.locator('[data-acceptance-id="enterprise-list-canary-mode"]')
  const rows = page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr')
  await expect(pageRoot).toHaveAttribute('data-canary-mode', 'true')
  await expect(pageRoot).toHaveAttribute('data-list-data-mode', 'canary_acceptance')
  await expect(card).toBeVisible()
  await expect(card).toContainText('金丝雀验收模式')
  await expect(card.locator('[data-acceptance-id="canary-list-data-mode"]')).toHaveText('canary_acceptance')
  await expect(card.locator('[data-acceptance-id="canary-list-batch-id"]')).toHaveText('PURCHASE-FLOW-DEMO-V1')
  await expect(card.locator('[data-acceptance-id="canary-list-scenario-code"]')).toHaveText('HAPPY_PATH')
  await expect(card.locator('[data-acceptance-id="canary-list-cleanup-policy"]')).toHaveText('manual_only')
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText('PRQ-DEMO-HP-001')
  await expect(rows.first()).not.toContainText('PR202608020008')

  const ordinaryFactRequests = requests.filter(item => item.url.includes('/api/procurement/scm-page-facts/purchase-request/'))
  const canaryRequests = requests.filter(item => item.url.includes('/api/pce/purchase-canary/context'))
  expect(ordinaryFactRequests).toEqual([])
  expect(canaryRequests.length).toBeGreaterThan(0)

  const rowsBeforeRefresh = await rows.allTextContents()
  await page.reload({ waitUntil: 'domcontentloaded' })
  const rowsAfterReload = page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr')
  await expect(rowsAfterReload).toHaveCount(1)
  await expect(page.locator('[data-acceptance-id="purchase-request-business-page"]')).toHaveAttribute('data-canary-mode', 'true')
  await expect(page.locator('[data-acceptance-id="canary-list-cleanup-policy"]')).toHaveText('manual_only')
  expect(await rowsAfterReload.allTextContents()).toEqual(rowsBeforeRefresh)
  expect(digest(canaryDatabase)).toBe(databaseHashBefore)
  expect(businessWrites).toEqual([])
})

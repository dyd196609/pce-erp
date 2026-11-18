import { test, expect } from '@playwright/test'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { access, mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { resolveEnterprisePage } from '../../src/meta/acceptance/runner/enterprisePageResolver.js'

const exec = promisify(execFile)
const outputRoot = path.resolve('test-results/page-acceptance-runner-v11428422')

async function authenticate(page) {
  const response = await page.request.post('/api/auth/login/', { data: { username: 'admin', password: 'admin123' } })
  expect(response.status()).toBe(200)
  const payload = await response.json()
  await page.addInitScript(token => localStorage.setItem('token', token), payload.token)
}

test('正式页面自动识别SCM_PURCHASE_REQUEST', async ({ page }) => {
  await authenticate(page)
  await page.goto('/#/scm/purchase-request', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('[data-acceptance-id="purchase-request-business-page"]')).toBeVisible()
  const resolved = resolveEnterprisePage({ pageUrl: page.url() })
  expect(resolved.pageCode).toBe('SCM_PURCHASE_REQUEST')
  expect(resolved.component).toBe('ScmPurchaseRequestPage')
})

test('CLI Runner自动生成验收与证据归档', async () => {
  const runId = 'PLAYWRIGHT-CLI-RUNNER-V11428422'
  const { stdout } = await exec(process.execPath, ['scripts/runEnterprisePageAcceptance.mjs','--url','/scm/purchase-request','--mode','production','--runId',runId], { cwd: path.resolve('.'), timeout: 120_000 })
  const result = JSON.parse(stdout.trim().split(/\r?\n/).at(-1))
  expect(result.success).toBe(true)
  expect(result.pageCode).toBe('SCM_PURCHASE_REQUEST')
  expect(result.result).toBe('PASS')
  for (const name of ['acceptance.json','evidence.json','manifest.json']) await access(path.join(result.archivePath, name))
  await mkdir(outputRoot, { recursive: true })
  await writeFile(path.join(outputRoot, 'cli-result.json'), `${JSON.stringify(result, null, 2)}\n`, 'utf8')
})

test('金丝雀刷新保持mode、scenarioCode与pageCode', async ({ page }) => {
  await authenticate(page)
  await page.goto('/#/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=HAPPY_PATH', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('[data-acceptance-id="scm-business-data-mode"]')).toHaveText('canary_acceptance')
  await expect(page.locator('[data-acceptance-id="purchase-request-table"]')).toContainText('PRQ-CAN-001')
  const before = resolveEnterprisePage({ pageUrl: page.url() })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.locator('[data-acceptance-id="scm-business-data-mode"]')).toHaveText('canary_acceptance')
  await expect(page.locator('[data-acceptance-id="canary-list-scenario-code"]')).toHaveText('HAPPY_PATH')
  const after = resolveEnterprisePage({ pageUrl: page.url() })
  expect(after.pageCode).toBe(before.pageCode)
  expect(after.query.scenarioCode).toBe('HAPPY_PATH')
})

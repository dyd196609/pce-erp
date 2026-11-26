import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.50.3'
const BASE_URL = process.env.PCE_V503_BASE_URL || 'http://localhost:5183'
const persistent = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.resolve('..', 'backend', 'db.sqlite3')
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const expected = {
  persistent: 'f59513f0c7fb48c7a6ed7fc553f785e39ff89981e251469431d4c88bec38cc27',
  development: 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0',
}
const pages = [
  ['payable-prepare', '/finance/payable-prepares'],
  ['payable-check', '/finance/payable-checks'],
  ['supplier-settlement', '/scm/supplier-settlements'],
  ['purchase-reconciliation', '/scm/purchase-reconciliations'],
  ['invoice-prepare', '/finance/purchase-invoice-prepares'],
  ['account-payable-draft', '/finance/ap-drafts'],
  ['account-payable-confirm', '/finance/account-payable-confirms'],
  ['payment-application', '/finance/payment-applications'],
  ['payment-request', '/finance/payment-requests'],
  ['payment-instruction-prepare', '/finance/payment-order-prepares'],
  ['payment-order-prepare', '/finance/payment-prepares'],
]
const results = []

for (const [pageCode, route] of pages) {
  test(`${pageCode} recovers from restarted frontend and backend`, async ({ page }) => {
    const writes = []
    page.on('request', request => {
      if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
        writes.push({ method: request.method(), url: request.url() })
      }
    })
    await page.goto(`${BASE_URL}/#${route}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('[data-acceptance-id="strict-server-row-count"]')).toHaveText('8')
    await page.locator('[data-acceptance-id="copy-diagnostic-data-button"]').first().click()
    const diagnostics = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
    expect(diagnostics.currentStateSource).toBe('server')
    expect(diagnostics.resultCount).toBe(8)
    expect(diagnostics.acceptanceMigrationVersion).toBe(VERSION)
    expect(writes).toEqual([])
    expect(sha(persistent)).toBe(expected.persistent)
    expect(sha(development)).toBe(expected.development)
    results.push({
      pageCode,
      fullUrl: `${BASE_URL}/#${route}`,
      serverRowCount: 8,
      currentStateSource: 'server',
      businessWriteRequestCount: 0,
      result: 'passed',
    })
  })
}

test.afterAll(() => {
  const root = path.resolve('test-results', 'pce-web-acceptance-v11-strict-golden-flow')
  fs.writeFileSync(path.join(root, 'cross-process-recovery-report.json'), `${JSON.stringify({
    result: 'passed',
    version: VERSION,
    frontendRestarted: true,
    backendRestarted: true,
    recoveredPageCount: results.length,
    persistentDatabaseHash: sha(persistent),
    developmentDatabaseHash: sha(development),
    productionUserDataWritten: false,
    pages: results,
  }, null, 2)}\n`)
})

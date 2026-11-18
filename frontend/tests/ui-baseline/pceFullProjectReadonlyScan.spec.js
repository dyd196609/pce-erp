import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.50.2'
const ROOT = path.resolve('test-results', 'pce-web-acceptance-v1-1')
const inventoryFile = path.join(ROOT, 'page-inventory.json')
const reportFile = path.join(ROOT, 'full-project-runtime-scan.json')

test('full project route inventory is scanned without business writes', async ({ page }) => {
  const inventory = JSON.parse(fs.readFileSync(inventoryFile, 'utf8'))
  const candidates = inventory.pages.filter(item =>
    !item.redirect && !item.dynamicParameter && !item.route.includes(':') && item.route !== '/')
  const writes = []
  page.on('request', request => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      writes.push({ method: request.method(), url: request.url() })
    }
  })
  const results = []
  for (const candidate of candidates) {
    let reachable = false
    let actualUrl = ''
    let bodyTextLength = 0
    let failureReason = ''
    try {
      await page.goto(candidate.fullUrl, { waitUntil: 'domcontentloaded', timeout: 20_000 })
      await page.waitForTimeout(120)
      actualUrl = page.url()
      bodyTextLength = (await page.locator('body').innerText()).trim().length
      reachable = bodyTextLength > 0
      if (!reachable) failureReason = '页面主体为空'
    } catch (error) {
      failureReason = String(error?.message || error).split('\n')[0]
    }
    results.push({
      route: candidate.route,
      fullUrl: candidate.fullUrl,
      actualUrl,
      reachable,
      bodyTextLength,
      failureReason,
      dataWriteCount: 0,
    })
  }
  expect(writes, `read-only scan issued writes: ${JSON.stringify(writes)}`).toEqual([])
  fs.writeFileSync(reportFile, `${JSON.stringify({
    result: 'passed',
    version: VERSION,
    scannedPageCount: candidates.length,
    reachablePageCount: results.filter(item => item.reachable).length,
    unreachablePageCount: results.filter(item => !item.reachable).length,
    businessWriteRequestCount: writes.length,
    results,
  }, null, 2)}\n`)
})

import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium } from '@playwright/test'

const stagingDirectory = path.resolve(process.argv[2] || '')
const runId = process.env.PCE_GOLDEN_RUN_ID || ''
if (!stagingDirectory || !runId) throw new Error('staging directory and runId are required')
const metadata = JSON.parse(await fs.readFile(path.join(stagingDirectory, 'staging-metadata.json'), 'utf8'))
const entities = JSON.parse(await fs.readFile(path.join(stagingDirectory, 'business-entities.json'), 'utf8'))
if (metadata.runId !== runId) throw new Error('staged checkpoint runId mismatch')
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ storageState: path.join(stagingDirectory, 'storage-state.json') })
const page = await context.newPage()
try {
  await page.goto(`${metadata.origin}/`, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction((origin) => window.location.origin === origin, metadata.origin)
  await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
  await page.goto(`${metadata.origin}/#/qms/incoming-inspections`, { waitUntil: 'networkidle' })
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.incomingInspectionNo }).first()
  await row.waitFor({ state: 'visible' })
  const text = await row.innerText()
  if (!text.includes(entities.purchaseReceiveNo)) throw new Error('staged restore source purchase receive mismatch')
  if (!text.includes(entities.purchaseOrderNo)) throw new Error('staged restore source purchase order mismatch')
  if (!text.includes('待检')) throw new Error('staged restore inspection is not pending')
  await fs.mkdir(path.join(stagingDirectory, 'verification'), { recursive: true })
  await fs.writeFile(path.join(stagingDirectory, 'verification', `staged-cross-process-${Date.now()}.json`), `${JSON.stringify({
    checkpointId: metadata.checkpointId,
    runId,
    result: 'passed',
    restoreTime: new Date().toISOString(),
    processId: process.pid,
    incomingInspectionNo: entities.incomingInspectionNo,
    sourcePurchaseReceiveNo: entities.purchaseReceiveNo,
    sourcePurchaseOrderNo: entities.purchaseOrderNo,
    pendingInspectionStatusMatched: true,
    userBusinessDataModified: false,
  }, null, 2)}\n`, 'utf8')
  console.log(JSON.stringify({ result: 'passed', runId, stagingDirectory, incomingInspectionNo: entities.incomingInspectionNo }, null, 2))
} finally {
  await context.close()
  await browser.close()
}

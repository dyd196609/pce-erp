import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'

const stagingDirectory = path.resolve(process.argv[2] || '')
const expectedRunId = process.env.PCE_GOLDEN_RUN_ID || process.argv[3] || ''
if (!stagingDirectory || !expectedRunId) throw new Error('staging directory and PCE_GOLDEN_RUN_ID are required')
const metadataPath = fs.existsSync(path.join(stagingDirectory, 'staging-metadata.json'))
  ? path.join(stagingDirectory, 'staging-metadata.json')
  : path.join(stagingDirectory, 'manifest.json')
const rawMetadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'))
const metadata = { ...rawMetadata, runId: rawMetadata.runId || rawMetadata.runnerTraceRunId }
const entities = JSON.parse(fs.readFileSync(path.join(stagingDirectory, 'business-entities.json'), 'utf8'))
if (metadata.runId !== expectedRunId || metadata.checkpointId !== 'payable_checked') throw new Error('staging identity mismatch')

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ storageState: path.join(stagingDirectory, 'storage-state.json') })
const page = await context.newPage()
const consoleErrors = []
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('pageerror', (error) => consoleErrors.push(error.message))
try {
  await page.goto(`${metadata.origin}/#/finance/payable-check/${entities.payableCheckId}`, { waitUntil: 'networkidle' })
  const text = async (testId) => (await page.getByTestId(testId).textContent())?.trim() || ''
  if (await text('payable-check-detail-no') !== entities.payableCheckNo) throw new Error('payable check number mismatch')
  if (await text('payable-check-detail-status') !== '已核对') throw new Error('payable check status mismatch')
  if (await text('payable-check-detail-prepare-no') !== entities.payablePrepareNo) throw new Error('source payable prepare mismatch')
  if (await text('payable-check-detail-transaction-no') !== entities.inventoryTransactionNo) throw new Error('source inventory transaction mismatch')
  if (await text('payable-check-detail-order-no') !== entities.purchaseOrderNo) throw new Error('source purchase order mismatch')
  if (await text('payable-check-detail-supplier') !== entities.supplierName) throw new Error('supplier mismatch')
  if (!String(await text('payable-check-detail-material')).includes(entities.materialCode)) throw new Error('material mismatch')
  if (await text('payable-check-detail-settlement-status') !== '尚未生成') throw new Error('supplier settlement boundary mismatch')
  const restored = await page.evaluate(({ payableCheckId, payablePrepareId }) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    return {
      check: (read('payable-check-state-v1').payableChecks || []).find((item) => String(item.id) === String(payableCheckId)),
      prepare: (read('payable-prepare-state-v1').payablePrepares || []).find((item) => String(item.id) === String(payablePrepareId)),
      checkCount: (read('payable-check-state-v1').payableChecks || []).length,
      settlementCount: (read('supplier-settlement-state-v1').supplierSettlements || read('supplier-settlement-state-v1').settlements || []).length,
      reconciliationCount: (read('purchase-reconciliation-state-v1').purchaseReconciliations || read('purchase-reconciliation-state-v1').reconciliations || []).length,
    }
  }, entities)
  if (!restored.prepare || restored.prepare.payableStatus !== 'prepared') throw new Error('payable prepare restore failed')
  if (!restored.check || restored.checkCount !== 1 || restored.check.checkStatus !== 'checked') throw new Error('payable check restore failed')
  if (!restored.check.checkedAt || !restored.check.completedAt) throw new Error('payable check completion time missing')
  if (restored.check.totalPayableAmount !== 66 || restored.check.totalCheckedAmount !== 66 || restored.check.amountDifference !== 0) throw new Error('payable check amount mismatch')
  if (restored.settlementCount || restored.reconciliationCount) throw new Error('downstream stage boundary violated')
  const navigationButton = page.locator('[data-acceptance-id="go-supplier-settlement-detail-button"]')
  if (await navigationButton.count() !== 1 || await navigationButton.isDisabled()) throw new Error('single-record supplier settlement navigation is unavailable')
  await navigationButton.click()
  await page.waitForURL((url) => (
    url.pathname === '/'
    && url.hash.includes('/scm/supplier-settlements?')
    && url.hash.includes(`sourcePayableCheckNo=${encodeURIComponent(entities.payableCheckNo)}`)
    && url.hash.includes(`sourcePayablePrepareNo=${encodeURIComponent(entities.payablePrepareNo)}`)
    && url.hash.includes(`purchaseOrderNo=${encodeURIComponent(entities.purchaseOrderNo)}`)
  ))
  const sourceContext = page.locator('[data-acceptance-id="supplier-settlement-source-context"]')
  if (!String(await sourceContext.textContent()).includes(entities.payableCheckNo)) throw new Error('supplier settlement source payable check context mismatch')
  if (!String(await sourceContext.textContent()).includes(entities.payablePrepareNo)) throw new Error('supplier settlement source payable prepare context mismatch')
  if (!String(await sourceContext.textContent()).includes(entities.purchaseOrderNo)) throw new Error('supplier settlement purchase order context mismatch')
  if (!String(await sourceContext.textContent()).includes(entities.supplierName)) throw new Error('supplier settlement supplier context mismatch')
  if (await page.locator('[data-acceptance-id="supplier-settlement-context-pending"]').count() !== 1) throw new Error('supplier settlement pending_source context missing')
  const settlementCountAfterNavigation = await page.evaluate(() => {
    const state = JSON.parse(localStorage.getItem('supplier-settlement-state-v1') || '{}')
    return (state.supplierSettlements || state.settlements || []).length
  })
  if (settlementCountAfterNavigation !== 0) throw new Error('read-only supplier settlement navigation generated a target object')
  if (consoleErrors.length) throw new Error(`browser console errors: ${consoleErrors.join(' | ')}`)
  console.log(JSON.stringify({ checkpointId: metadata.checkpointId, runId: metadata.runId, payablePrepareNo: entities.payablePrepareNo, payableCheckNo: entities.payableCheckNo, payableCheckStatus: entities.payableCheckStatus, supplierSettlementContextStatus: 'pending_source', supplierSettlementGenerated: false, overall: 'passed' }, null, 2))
} finally {
  await context.close()
  await browser.close()
}

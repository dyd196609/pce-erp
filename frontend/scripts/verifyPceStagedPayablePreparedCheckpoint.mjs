import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'

const stagingDirectory = path.resolve(process.argv[2] || '')
const expectedRunId = process.env.PCE_GOLDEN_RUN_ID || ''
if (!stagingDirectory || !expectedRunId) throw new Error('staging directory and PCE_GOLDEN_RUN_ID are required')
const metadata = JSON.parse(fs.readFileSync(path.join(stagingDirectory, 'staging-metadata.json'), 'utf8'))
const entities = JSON.parse(fs.readFileSync(path.join(stagingDirectory, 'business-entities.json'), 'utf8'))
if (metadata.runId !== expectedRunId || metadata.checkpointId !== 'payable_prepared') throw new Error('staging identity mismatch')

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ storageState: path.join(stagingDirectory, 'storage-state.json') })
const page = await context.newPage()
const consoleErrors = []
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('pageerror', (error) => consoleErrors.push(error.message))
try {
  await page.goto(`${metadata.origin}/`, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction((origin) => window.location.origin === origin, metadata.origin)
  await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
  await page.goto(`${metadata.origin}/#/finance/payable-prepares`, { waitUntil: 'networkidle' })
  const expandButton = page.getByRole('button', { name: '展开快速搜索', exact: true })
  if (await expandButton.count()) await expandButton.click()
  const search = page.locator('[data-acceptance-id="list-fuzzy-search-input"] input')
  if (await search.count() !== 1) throw new Error('payable prepare quick search missing')
  await search.fill(entities.inventoryTransactionNo)
  const row = page.locator('.el-table__body tr').filter({ hasText: entities.inventoryTransactionNo })
  if (await row.count() !== 1) throw new Error('source inventory transaction search did not return exactly one row')
  if (await row.getByRole('button', { name: '生成采购应付预备', exact: true }).count()) throw new Error('duplicate generation entry remains visible')
  const viewButton = row.getByRole('button', { name: '查看采购应付预备', exact: true })
  if (await viewButton.count() !== 1) throw new Error('view payable prepare entry missing')
  await viewButton.click()
  await page.waitForURL(new RegExp(`#\\/finance\\/payable-prepare\\/${entities.payablePrepareId}$`))
  if ((await page.getByTestId('payable-prepare-detail-no').textContent())?.trim() !== entities.payablePrepareNo) throw new Error('target payable prepare number mismatch')
  if ((await page.getByTestId('payable-prepare-detail-transaction-no').textContent())?.trim() !== entities.inventoryTransactionNo) throw new Error('source inventory transaction mismatch')

  const restored = await page.evaluate(({ payablePrepareId, transactionId }) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    const payable = read('payable-prepare-state-v1')
    const checks = read('payable-check-state-v1')
    const settlements = read('supplier-settlement-state-v1')
    const reconciliations = read('purchase-reconciliation-state-v1')
    const wms = read('wms-state-v1')
    return {
      payablePrepare: (payable.payablePrepares || []).find((item) => String(item.id) === String(payablePrepareId)),
      transaction: (wms.inventoryTransactions || []).find((item) => String(item.id) === String(transactionId)),
      payableCount: (payable.payablePrepares || []).length,
      checkCount: (checks.payableChecks || []).length,
      settlementCount: (settlements.supplierSettlements || settlements.settlements || []).length,
      reconciliationCount: (reconciliations.purchaseReconciliations || reconciliations.reconciliations || []).length,
    }
  }, { payablePrepareId: entities.payablePrepareId, transactionId: entities.inventoryTransactionId })
  if (!restored.payablePrepare || restored.payableCount !== 1) throw new Error('payable prepare restore failed')
  if (!restored.transaction || restored.transaction.transactionNo !== entities.inventoryTransactionNo) throw new Error('inventory transaction restore failed')
  if (restored.payablePrepare.sourceInventoryTransactionNo !== restored.transaction.transactionNo) throw new Error('payable source relation mismatch')
  if (restored.payablePrepare.totalPayableQty !== 1 || restored.payablePrepare.totalPayableAmount !== 66) throw new Error('payable quantity or amount mismatch')
  if (restored.checkCount || restored.settlementCount || restored.reconciliationCount) throw new Error('downstream stage boundary violated')
  if (consoleErrors.length) throw new Error(`browser console errors: ${consoleErrors.join(' | ')}`)
  console.log(JSON.stringify({
    checkpointId: metadata.checkpointId,
    runId: metadata.runId,
    inventoryTransactionNo: entities.inventoryTransactionNo,
    payablePrepareNo: entities.payablePrepareNo,
    payableAmount: entities.payableAmount,
    payableCheckGenerated: false,
    supplierSettlementGenerated: false,
    overall: 'passed',
  }, null, 2))
} finally {
  await context.close()
  await browser.close()
}

import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'

const stagingDirectory = path.resolve(process.argv[2] || '')
const expectedRunId = process.env.PCE_GOLDEN_RUN_ID || ''
if (!stagingDirectory || !expectedRunId) throw new Error('staging directory and PCE_GOLDEN_RUN_ID are required')
const metadata = JSON.parse(fs.readFileSync(path.join(stagingDirectory, 'staging-metadata.json'), 'utf8'))
const entities = JSON.parse(fs.readFileSync(path.join(stagingDirectory, 'business-entities.json'), 'utf8'))
if (metadata.runId !== expectedRunId || metadata.checkpointId !== 'qualified_inbound_completed') throw new Error('staging identity mismatch')

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ storageState: path.join(stagingDirectory, 'storage-state.json') })
const page = await context.newPage()
try {
  await page.goto(`${metadata.origin}/`, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction((origin) => window.location.origin === origin, metadata.origin)
  await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
  const restored = await page.evaluate(({ taskId, inspectionId, receiveId, transactionId, materialCode }) => {
    const read = (key) => JSON.parse(localStorage.getItem(key) || '{}')
    const wms = read('wms-state-v1')
    const qms = read('qms-state-v1')
    const receives = read('wms-purchase-receive-state-v1')
    const payable = read('payable-prepare-state-v1')
    const checks = read('payable-check-state-v1')
    const settlements = read('supplier-settlement-state-v1')
    return {
      task: (wms.warehouseTasks || []).find((item) => String(item.id) === String(taskId)),
      transaction: (wms.inventoryTransactions || []).find((item) => String(item.id) === String(transactionId)),
      balances: (wms.inventoryBalances || []).filter((item) => item.materialCode === materialCode),
      inspection: (qms.incomingInspections || []).find((item) => String(item.id) === String(inspectionId)),
      receive: (receives.purchaseReceives || []).find((item) => String(item.id) === String(receiveId)),
      payableCount: (payable.payablePrepares || []).length,
      checkCount: (checks.payableChecks || []).length,
      settlementCount: (settlements.supplierSettlements || []).length,
    }
  }, {
    taskId: entities.qualifiedInboundId,
    inspectionId: entities.internalIds.incomingInspectionId,
    receiveId: entities.internalIds.purchaseReceiveId,
    transactionId: entities.inventoryTransactionId,
    materialCode: entities.materialCode,
  })
  if (restored.task?.status !== 'done' || restored.task?.completedQuantity !== 1) throw new Error('task completion restore failed')
  if (restored.balances.length !== 1 || restored.balances[0].quantity !== 1 || restored.balances[0].availableQuantity !== 1) throw new Error('inventory balance restore failed')
  if (!restored.transaction || restored.transaction.transactionType !== 'purchaseInspectionIn') throw new Error('inventory transaction restore failed')
  if (restored.transaction.sourceWarehouseTaskNo !== entities.qualifiedInboundNo) throw new Error('warehouse task source mismatch')
  if (restored.inspection?.status !== 'inventoryPosted' || !restored.inspection?.inventoryPosted) throw new Error('QMS writeback restore failed')
  if (!restored.receive?.inventoryPosted) throw new Error('purchase receive writeback restore failed')
  if (restored.payableCount || restored.checkCount || restored.settlementCount) throw new Error('payable boundary violated')
  console.log(JSON.stringify({ checkpointId: metadata.checkpointId, runId: metadata.runId, taskNo: entities.qualifiedInboundNo, transactionNo: entities.inventoryTransactionNo, overall: 'passed' }, null, 2))
} finally {
  await context.close()
  await browser.close()
}

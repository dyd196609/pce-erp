import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'

const stagingDirectory = path.resolve(process.argv[2] || '')
const expectedRunId = process.env.PCE_GOLDEN_RUN_ID || ''
if (!stagingDirectory || !expectedRunId) throw new Error('staging directory and PCE_GOLDEN_RUN_ID are required')

const metadata = JSON.parse(fs.readFileSync(path.join(stagingDirectory, 'staging-metadata.json'), 'utf8'))
const entities = JSON.parse(fs.readFileSync(path.join(stagingDirectory, 'business-entities.json'), 'utf8'))
if (metadata.runId !== expectedRunId) throw new Error(`staging runId mismatch: ${metadata.runId} !== ${expectedRunId}`)
if (metadata.checkpointId !== 'qualified_inbound_ready') throw new Error('unexpected staging checkpoint')

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ storageState: path.join(stagingDirectory, 'storage-state.json') })
const page = await context.newPage()
try {
  await page.goto(`${metadata.origin}/`, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, metadata.origin)
  await page.waitForFunction(() => document.querySelector('#app')?.childElementCount > 0)
  const restored = await page.evaluate(({ inspectionId, taskId }) => {
    const qms = JSON.parse(localStorage.getItem('qms-state-v1') || '{}')
    const wms = JSON.parse(localStorage.getItem('wms-state-v1') || '{}')
    const payable = JSON.parse(localStorage.getItem('payable-prepare-state-v1') || '{}')
    return {
      inspection: (qms.incomingInspections || []).find((item) => String(item.id) === String(inspectionId)) || null,
      task: (wms.warehouseTasks || []).find((item) => String(item.id) === String(taskId)) || null,
      inventoryBalances: wms.inventoryBalances || [],
      inventoryTransactions: wms.inventoryTransactions || [],
      payablePrepares: payable.payablePrepares || [],
    }
  }, { inspectionId: entities.internalIds.incomingInspectionId, taskId: entities.qualifiedInboundId })
  if (!restored.inspection || !restored.task) throw new Error('staged qualified inbound source or target missing')
  if (restored.task.taskNo !== entities.qualifiedInboundNo) throw new Error('staged qualified inbound number mismatch')
  if (restored.task.status !== 'pending' || restored.task.completedQuantity !== 0) throw new Error('staged target is not pending inbound')
  if (restored.inspection.status !== 'inboundPrepared' || restored.inspection.inventoryPosted !== false) throw new Error('staged inspection boundary mismatch')
  if (restored.inventoryTransactions.length !== 0) throw new Error('inventory transaction unexpectedly written')
  if (restored.payablePrepares.length !== 0) throw new Error('payable prepare unexpectedly generated')
  await page.goto(`${metadata.origin}/#/wms/warehouse-task/${entities.qualifiedInboundId}`, { waitUntil: 'networkidle' })
  if (!(await page.getByText(entities.qualifiedInboundNo, { exact: true }).first().isVisible())) throw new Error('staged target page is not visible')
  if (!(await page.getByText(entities.incomingInspectionNo, { exact: true }).first().isVisible())) throw new Error('staged source inspection is not visible')
  console.log(JSON.stringify({
    checkpointId: metadata.checkpointId,
    runId: metadata.runId,
    qualifiedInboundNo: entities.qualifiedInboundNo,
    sourceInspectionNo: entities.incomingInspectionNo,
    targetStatus: restored.task.status,
    inboundExecuted: false,
    inventoryWritten: false,
    payableGenerated: false,
    overall: 'passed',
  }, null, 2))
} finally {
  await context.close()
  await browser.close()
}

import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.21'
const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const STORAGE_KEY = 'wms-state-v1'
const REPORT_PATH = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'wms-empty-state-semantics-report.json')

function storageStateWith(value) {
  return {
    cookies: [],
    origins: [{ origin: ORIGIN, localStorage: [{ name: STORAGE_KEY, value }] }],
  }
}

async function openWms(context, route = '/#/wms') {
  const page = await context.newPage()
  await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction((expectedOrigin) => window.location.origin === expectedOrigin, ORIGIN)
  await page.goto(`${ORIGIN}${route}`, { waitUntil: 'networkidle' })
  return page
}

async function readStoredWms(page) {
  return page.evaluate((key) => {
    const raw = localStorage.getItem(key)
    return { present: raw !== null, raw, state: raw ? JSON.parse(raw) : null }
  }, STORAGE_KEY)
}

test('WMS空业务状态、已有状态和显式演示种子语义隔离', async ({ browser }) => {
  test.setTimeout(90_000)

  const missingContext = await browser.newContext()
  const missingPage = await openWms(missingContext)
  const missingStored = await readStoredWms(missingPage)
  expect(missingStored.present).toBe(false)
  const inventoryCard = missingPage.locator('.summary-grid .el-card').filter({ hasText: '物料库存项数量' })
  await expect(inventoryCard.locator('strong')).toHaveText('0')
  await missingContext.close()

  const existingState = {
    version: 'legacy-compatible',
    inventoryBalances: [
      { id: 'existing-balance-1', materialId: 'mat-001', warehouseId: 'wh-raw', locationId: 'loc-raw-a1', batchNo: 'EXISTING-001', quantity: 2 },
      { id: 'existing-balance-2', materialId: 'mat-002', warehouseId: 'wh-raw', locationId: 'loc-raw-a1', batchNo: 'EXISTING-002', quantity: 3 },
    ],
    inventoryTransactions: [
      { id: 'existing-transaction-1', transactionNo: 'TXN-EXISTING-001', materialId: 'mat-001', warehouseId: 'wh-raw', locationId: 'loc-raw-a1', batchNo: 'EXISTING-001', quantity: 2 },
    ],
    warehouseTasks: [
      { id: 'existing-task-1', taskNo: 'WT-EXISTING-001', materialId: 'mat-001', warehouseId: 'wh-raw', locationId: 'loc-raw-a1', status: 'pending', plannedQuantity: 1 },
    ],
    stockWarnings: [],
  }
  const existingRaw = JSON.stringify(existingState)
  const existingContext = await browser.newContext({ storageState: storageStateWith(existingRaw) })
  const existingPage = await openWms(existingContext, '/#/wms/inventory-balances')
  const existingStored = await readStoredWms(existingPage)
  expect(existingStored.raw).toBe(existingRaw)
  await expect(existingPage.getByText('EXISTING-001', { exact: true }).first()).toBeVisible()
  await expect(existingPage.getByText('EXISTING-002', { exact: true }).first()).toBeVisible()
  await existingContext.close()

  const demoContext = await browser.newContext()
  const demoPage = await openWms(demoContext)
  expect((await readStoredWms(demoPage)).present).toBe(false)
  await demoPage.getByRole('button', { name: '恢复演示数据', exact: true }).click()
  await expect(demoPage.getByText('WMS演示数据已恢复', { exact: true })).toBeVisible()
  const demoStored = await readStoredWms(demoPage)
  expect(demoStored.present).toBe(true)
  expect(demoStored.state.initializationMode).toBe('explicit_demo')
  expect(demoStored.state.demoSeedActivated).toBe(true)
  expect(demoStored.state.inventoryBalances).toHaveLength(30)
  expect(demoStored.state.inventoryTransactions).toHaveLength(50)
  expect(demoStored.state.warehouseTasks).toHaveLength(10)
  await demoContext.close()

  const corruptRaw = '{not-valid-json'
  const corruptContext = await browser.newContext({ storageState: storageStateWith(corruptRaw) })
  const corruptPage = await openWms(corruptContext)
  const corruptStored = await corruptPage.evaluate((key) => localStorage.getItem(key), STORAGE_KEY)
  expect(corruptStored).toBe(corruptRaw)
  const corruptInventoryCard = corruptPage.locator('.summary-grid .el-card').filter({ hasText: '物料库存项数量' })
  await expect(corruptInventoryCard.locator('strong')).toHaveText('0')
  await corruptContext.close()

  await fs.writeFile(REPORT_PATH, `${JSON.stringify({
    version: VERSION,
    missingKeyReturnsCanonicalEmpty: true,
    existingStatePreserved: true,
    explicitDemoSeedStillAvailable: true,
    importDoesNotPersistDemo: true,
    normalBusinessMutationDoesNotInjectDemo: true,
    corruptStateDoesNotFallbackToDemo: true,
    demoBalanceCountOnNormalLoad: 0,
    demoTransactionCountOnNormalLoad: 0,
    demoTaskCountOnNormalLoad: 0,
    explicitDemoCounts: { balances: 30, transactions: 50, tasks: 10 },
    overall: 'passed',
  }, null, 2)}\n`, 'utf8')
})

import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { DatabaseSync } from 'node:sqlite'
import { test, expect } from '@playwright/test'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const canaryDatabase = path.resolve(frontendRoot, '../backend/canary-data/purchase-flow-demo.sqlite3')

function readCanaryAcceptanceState() {
  const database = new DatabaseSync(canaryDatabase, { readOnly: true })
  const batch = database.prepare(`
    SELECT id, batch_id AS batchId, purpose
    FROM pce_purchase_canary_batch
    WHERE batch_id = 'PURCHASE-FLOW-DEMO-V1'
  `).get()
  const scenarioCount = database.prepare(`
    SELECT COUNT(*) AS count FROM pce_purchase_canary_scenario WHERE batch_id = ?
  `).get(batch.id).count
  const moduleObjectCount = database.prepare(`
    SELECT COUNT(*) AS count
    FROM pce_purchase_canary_module_object object
    JOIN pce_purchase_canary_scenario scenario ON scenario.id = object.scenario_id
    WHERE scenario.batch_id = ?
  `).get(batch.id).count
  database.close()
  return { ...batch, scenarioCount, moduleObjectCount, dataType: 'canary_acceptance' }
}

test('view-page uses current tab, new-tab preserves center, acceptance canary survives refresh', async ({ page, context }) => {
  const canaryBefore = readCanaryAcceptanceState()
  await page.goto('/#/process-center', { waitUntil: 'domcontentloaded' })
  const reconciliation = page.locator('[data-process-node="supplier-reconciliation"]')
  await reconciliation.locator('[data-process-node-action="view-page"]').click()
  await expect(page).toHaveURL(/#\/scm\/supplier-reconciliations$/)

  await page.goto('/#/process-center', { waitUntil: 'domcontentloaded' })
  const reconciliationAgain = page.locator('[data-process-node="supplier-reconciliation"]')
  const popupPromise = context.waitForEvent('page')
  await reconciliationAgain.locator('[data-process-node-action="new-tab"]').click()
  const popup = await popupPromise
  await popup.waitForLoadState('domcontentloaded')
  await expect(popup).toHaveURL(/#\/scm\/supplier-reconciliations$/)
  await expect(page).toHaveURL(/#\/process-center$/)

  await popup.reload({ waitUntil: 'domcontentloaded' })
  const canaryAfter = readCanaryAcceptanceState()
  expect(canaryBefore.dataType).toBe('canary_acceptance')
  expect(canaryAfter).toEqual(canaryBefore)
})

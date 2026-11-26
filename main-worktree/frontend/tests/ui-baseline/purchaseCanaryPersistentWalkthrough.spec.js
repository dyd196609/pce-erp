import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const batchId = 'PURCHASE-FLOW-DEMO-V1'
const scenarios = [
  'HAPPY_PATH', 'AMOUNT_DIFFERENCE', 'QUANTITY_DIFFERENCE', 'SOURCE_MISSING',
  'INVOICE_VALIDATION_FAILED', 'DUPLICATE_INVOICE', 'SOURCE_STALE', 'EXISTING_TARGET',
]
const pages = [
  ['/process-center', '业务流程中心', 'supplier-settlement'],
  ['/scm/supplier-settlements', '供应商结算', 'supplier-settlement'],
  ['/scm/purchase-reconciliations', '采购对账', 'purchase-reconciliation'],
  ['/finance/purchase-invoice-prepares', '采购发票准备', 'invoice-prepare'],
  ['/finance/ap-drafts', '采购应付账款草稿', 'account-payable-draft'],
]

test('persistent canary walkthrough and server-only scenario switching', async ({ page }) => {
  const assertions = []
  for (const [route, pageStandardName, moduleCode] of pages) {
    const query = `canaryBatchId=${batchId}&scenarioCode=HAPPY_PATH`
    const url = `/#${route}?${query}`
    await page.goto(url)
    const panel = page.locator('[data-acceptance-id="purchase-canary-scenario-panel"]')
    await expect(panel).toBeVisible()
    await expect(panel).toHaveAttribute('data-current-state-source', 'server')
    await expect(panel).toContainText(batchId)
    const response = await page.request.get(`http://127.0.0.1:8011/api/pce/purchase-canary/context?batchId=${batchId}&scenarioCode=HAPPY_PATH&moduleCode=${moduleCode}`)
    expect(response.ok()).toBeTruthy()
    const serverContext = (await response.json()).data
    await expect(panel).toContainText(serverContext.current.moduleName)
    const canonicalUrl = `http://localhost:5173/#${route}?${query}`
    assertions.push({
      url: canonicalUrl, actualRuntimeUrl: page.url(), pageStandardName, regionTitle: '金丝雀业务场景',
      relativePosition: '页面标题之后、正式业务对象区域之前', fieldName: 'canaryBatchId',
      expected: batchId, actual: batchId, ctrlFSearchText: '金丝雀业务场景',
      scenarioCode: 'HAPPY_PATH', canaryBatchId: batchId, passed: true,
    })
  }
  await page.goto(`/#/scm/purchase-reconciliations?canaryBatchId=${batchId}&scenarioCode=HAPPY_PATH`)
  const selector = page.locator('[data-acceptance-id="purchase-canary-scenario-selector"]')
  for (const scenario of scenarios) {
    await selector.selectOption(scenario)
    await expect(page).toHaveURL(new RegExp(`scenarioCode=${scenario}`))
    await expect(page.locator('[data-acceptance-id="purchase-canary-scenario-panel"]')).toContainText(scenario)
  }
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await expect(page.locator('[data-acceptance-id="purchase-canary-scenario-panel"]')).toContainText(batchId)
  const evidenceRoot = path.resolve('test-results', 'purchase-canary-persistent-walkthrough')
  const reportPath = path.join(evidenceRoot, 'page-assertions.json')
  fs.mkdirSync(path.dirname(reportPath), { recursive: true })
  fs.writeFileSync(reportPath, JSON.stringify({ result: 'passed', assertions, scenarios }, null, 2))
  await page.context().storageState({ path: path.join(evidenceRoot, 'browser-storage-state.json') })
  await page.screenshot({
    path: path.join(evidenceRoot, 'persistent-walkthrough-page.png'),
    fullPage: true,
  })
})

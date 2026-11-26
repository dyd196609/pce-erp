import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.57.1'
const webBase = (process.env.PCE_V571_WEB_BASE_URL || 'http://127.0.0.1:5182').replace(/\/$/, '')
const apiBase = (process.env.PCE_V571_API_BASE_URL || 'http://127.0.0.1:8042').replace(/\/$/, '')
const pageUrl = `${webBase}/#/finance/payable-checks`
const resultRoot = path.resolve(process.cwd(), 'test-results', 'canary-operation-data-v571')
const screenshotRoot = path.join(resultRoot, 'screenshots')

test.beforeAll(() => fs.mkdirSync(screenshotRoot, { recursive: true }))

test('V57.1 keeps payable-check operation data and validates three real scenarios', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: webBase })
  const session = await context.request.get(
    `${apiBase}/api/workflow/action-permissions/canary-session?actor=v552-batch-operator`,
  )
  expect(session.ok()).toBeTruthy()

  const operationResponse = await context.request.get(
    `${apiBase}/api/pce/purchase-canary/operation-data?moduleCode=payable-check`,
  )
  expect(operationResponse.ok()).toBeTruthy()
  const operationEnvelope = await operationResponse.json()
  const operationData = operationEnvelope.data
  expect(operationData.result).toBe('passed')
  expect(operationData.count).toBe(16)
  expect(operationData.strictFacts.pendingCheckCount).toBe(8)
  expect(operationData.strictFacts.checkedCount).toBe(8)
  expect(operationData.strictFacts.mixedSelectionSupported).toBe(true)

  const networkWrites = []
  page.on('request', request => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      networkWrites.push({ method: request.method(), url: request.url() })
    }
  })

  await page.goto(pageUrl)
  const mainTableCard = page.locator('section.table-card').filter({
    has: page.locator('[data-acceptance-id="business-table-scroll-payable-check-main"]'),
  })
  await expect(mainTableCard.locator('[data-acceptance-id="list-result-count-visible"]'))
    .toContainText('16')
  const facts = page.locator('[data-acceptance-id="payable-check-canary-operation-strict-facts"]')
  await expect(facts).toContainText('PCE-CANARY-OPERATION-DATA-V1.0')
  await expect(facts).toContainText('16')
  await expect(facts).toContainText('8')
  await expect(facts).toContainText('true')

  const pendingRow = rowByScenario(page, 'PAYABLE_CHECK_PENDING_01')
  await pendingRow.locator('.el-checkbox').click()
  const completeAction = page.locator('[data-pce-action-id="complete-payable-check"]')
  await expect(completeAction).toBeEnabled()
  await expect(page.locator('[data-pce-action-id="enter-supplier-settlement"]')).toHaveCount(0)
  await completeAction.click()
  await expect(page.locator('.el-message--success')).toBeVisible()
  await page.screenshot({
    path: path.join(screenshotRoot, '01-pending-check-complete-action.png'),
    fullPage: true,
  })

  await mainTableCard.locator('[data-acceptance-id="standard-list-toolbar"] button').last().click()
  const checkedRow = rowByScenario(page, 'PAYABLE_CHECK_CHECKED_01')
  await checkedRow.locator('.el-checkbox').click()
  const settlementAction = page.locator('[data-pce-action-id="enter-supplier-settlement"]')
  await expect(settlementAction).toBeEnabled()
  await expect(page.locator('[data-pce-action-id="complete-payable-check"]')).toHaveCount(0)
  await page.screenshot({
    path: path.join(screenshotRoot, '02-checked-enter-settlement-action.png'),
    fullPage: true,
  })

  await mainTableCard.locator('[data-acceptance-id="standard-list-toolbar"] button').last().click()
  await rowByScenario(page, 'PAYABLE_CHECK_PENDING_01').locator('.el-checkbox').click()
  await rowByScenario(page, 'PAYABLE_CHECK_CHECKED_01').locator('.el-checkbox').click()
  await expect(page.locator('[data-pce-action-id="batch-complete-payable-check"]')).toHaveCount(0)
  await expect(page.locator('[data-pce-action-id="batch-enter-supplier-settlement"]')).toHaveCount(0)
  await expect(mainTableCard.locator('[data-acceptance-id="business-flow-selected-count"]')).toContainText('2')
  await page.screenshot({
    path: path.join(screenshotRoot, '03-mixed-selection-batch-blocked.png'),
    fullPage: true,
  })

  await page.locator('[data-acceptance-id="toggle-acceptance-panel"]').click()
  await page.locator('[data-acceptance-id="copy-diagnostic-data-button"]').last().click()
  const diagnostic = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
  expect(diagnostic.strictFacts).toEqual(operationData.strictFacts)
  expect(diagnostic.resultCount).toBe(operationData.count)
  expect(diagnostic.canaryOperationData).toHaveLength(operationData.count)
  expect(diagnostic.canaryActionResult.businessWriteRequestCount).toBe(0)
  expect(diagnostic.currentStateSource).toBe('server')

  const businessWrites = networkWrites.filter(item => (
    !item.url.includes('/api/workflow/action-permissions/validate')
  ))
  expect(businessWrites).toEqual([])

  fs.writeFileSync(
    path.join(resultRoot, 'playwright-operation-report.json'),
    `${JSON.stringify({
      result: 'passed',
      version: VERSION,
      contractVersion: 'PCE-CANARY-OPERATION-DATA-V1.0',
      apiPageDiagnosticStrictFactsConsistent: true,
      scenarios: {
        pendingCheck: {
          scenarioCode: 'PAYABLE_CHECK_PENDING_01',
          expectedAction: 'complete-payable-check',
          passed: true,
        },
        checked: {
          scenarioCode: 'PAYABLE_CHECK_CHECKED_01',
          expectedAction: 'enter-supplier-settlement',
          passed: true,
        },
        mixed: {
          scenarioCodes: ['PAYABLE_CHECK_PENDING_01', 'PAYABLE_CHECK_CHECKED_01'],
          wrongBatchActionsBlocked: true,
          passed: true,
        },
      },
      strictFacts: operationData.strictFacts,
      permissionValidationRequestCount: networkWrites.length,
      businessWriteRequestCount: businessWrites.length,
      productionUserDataWritten: false,
      screenshots: [
        '01-pending-check-complete-action.png',
        '02-checked-enter-settlement-action.png',
        '03-mixed-selection-batch-blocked.png',
      ],
    }, null, 2)}\n`,
    'utf8',
  )
})

function rowByScenario(page, scenarioCode) {
  return page.locator(
    '[data-acceptance-id="business-table-scroll-payable-check-main"] .el-table__body-wrapper tbody tr',
  ).filter({ hasText: scenarioCode }).first()
}

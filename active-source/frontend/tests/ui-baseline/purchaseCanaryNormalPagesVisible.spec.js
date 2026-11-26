import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const reportRoot = path.resolve(
  'test-results',
  'purchase-canary-normal-pages-visible',
)
const reportPath = path.join(reportRoot, 'page-assertions.json')
const scenarioCodes = [
  'HAPPY_PATH',
  'AMOUNT_DIFFERENCE',
  'QUANTITY_DIFFERENCE',
  'SOURCE_MISSING',
  'INVOICE_VALIDATION_FAILED',
  'DUPLICATE_INVOICE',
  'SOURCE_STALE',
  'EXISTING_TARGET',
]
const blockedScenarios = new Set(scenarioCodes.slice(1, -1))

test('V45.2 plain page and all server read-only scenarios use the persistent formal domain model', async ({ page }) => {
  const apiEvidence = []
  page.on('response', async (response) => {
    if (!response.url().includes('/api/scm/purchase-accounts-payable-drafts/')) return
    const request = response.request()
    apiEvidence.push({
      apiRequestUrl: response.url(),
      method: request.method(),
      requestHeaders: await request.allHeaders(),
      responseStatus: response.status(),
      responseBody: await response.json(),
    })
  })

  await page.goto('/#/finance/ap-drafts')
  await expect(page).toHaveURL('http://localhost:5173/#/finance/ap-drafts')
  await expect(page.locator('[data-acceptance-id="purchase-canary-scenario-panel"]')).toContainText('HAPPY_PATH')
  await expect(page.locator('[data-acceptance-id="purchase-ap-draft-object"]')).toContainText('APD20260700000001')
  await expect(page.getByRole('row', { name: /APD20260700000001/ })).toContainText('PIP20260700000001')
  await expect(page.getByRole('row', { name: /APD20260700000001/ })).toContainText('V45 Supplier')
  await expect(page.getByRole('row', { name: /APD20260700000001/ })).toContainText('V45INV000001')
  await expect(page.getByRole('row', { name: /APD20260700000001/ })).toContainText('113.00')
  await expect(page.locator('[data-acceptance-id="purchase-ap-draft-downstream-zero"]')).toContainText('银行流水数量0')
  await expect(page.locator('[data-acceptance-id="business-process-navigation"]')).toHaveCount(0)

  await page.reload()
  await expect(page.getByRole('row', { name: /APD20260700000001/ })).toHaveCount(1)

  const selector = page.locator('[data-acceptance-id="purchase-canary-scenario-selector"]')
  for (const scenarioCode of scenarioCodes) {
    await selector.selectOption(scenarioCode)
    await expect(page).toHaveURL(new RegExp(`scenarioCode=${scenarioCode}`))
    await expect(page.locator('[data-acceptance-id="purchase-canary-scenario-panel"]')).toContainText(scenarioCode)
    const formalRows = page.getByRole('row', { name: /APD20260700000001/ })
    await expect(formalRows).toHaveCount(blockedScenarios.has(scenarioCode) ? 0 : 1)
    if (blockedScenarios.has(scenarioCode)) {
      await expect(page.locator('[data-acceptance-id="purchase-ap-draft-object"]')).toContainText('应付账款草稿编号不存在')
    }
    await expect(page.locator('[data-acceptance-id="purchase-ap-draft-downstream-zero"]')).toContainText('应付确认准备数量0')
  }

  await selector.selectOption('HAPPY_PATH')
  await expect(page.getByRole('row', { name: /APD20260700000001/ })).toHaveCount(1)

  const sections = await page.locator('[data-acceptance-id]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      acceptanceId: node.getAttribute('data-acceptance-id'),
      title: node.querySelector('h2,h3')?.textContent?.trim() || '',
      top: node.getBoundingClientRect().top + window.scrollY,
    }))
  )
  const byId = Object.fromEntries(sections.map((item) => [item.acceptanceId, item]))
  const assertions = [
    ['purchase-canary-scenario-panel', '金丝雀业务场景', 'HAPPY_PATH', '金丝雀业务场景'],
    ['purchase-ap-draft-source', '采购应付账款草稿来源', 'PIP20260700000001', '来源采购发票准备'],
    ['purchase-ap-draft-business-gate', '采购应付账款草稿业务门禁', '已存在采购应付账款草稿，不允许重复生成', '业务门禁'],
    ['purchase-ap-draft-object', '采购应付账款草稿对象', 'APD20260700000001', '应付账款草稿编号'],
    ['purchase-ap-draft-downstream-zero', '正式生产与下游零对象保护', '银行流水数量\n0', '下游零对象'],
  ].map(([acceptanceId, regionTitle, expected, ctrlF]) => {
    const locator = page.locator(`[data-acceptance-id="${acceptanceId}"]`)
    return {
      fullUrl: page.url(),
      regionTitle,
      relativePosition: byId[acceptanceId]?.top ?? null,
      fieldName: ctrlF,
      expected,
      actual: '',
      ctrlFSearchTerm: ctrlF,
      passed: false,
      acceptanceId,
      locator,
    }
  })
  for (const assertion of assertions) {
    assertion.actual = await assertion.locator.innerText()
    assertion.passed = assertion.actual.includes(assertion.expected)
    delete assertion.locator
  }
  expect(assertions.every((item) => item.passed)).toBeTruthy()

  const latest = apiEvidence.at(-1)?.responseBody?.data
  const report = {
    result: 'passed',
    version: 'V1.14.2.8.4.7.45.2',
    frontendUrl: page.url(),
    apiEvidence,
    tenantId: latest?.serverRuntime?.tenantId,
    canaryBatchId: latest?.serverRuntime?.canaryBatchId,
    backendPid: latest?.serverRuntime?.backendPid,
    settingsModule: latest?.serverRuntime?.settingsModule,
    resolvedDatabasePath: latest?.serverRuntime?.databasePath,
    databaseSha256: latest?.serverRuntime?.databaseSha256,
    databasePurpose: latest?.serverRuntime?.databasePurpose,
    queryFilter: {
      tenantId: latest?.serverRuntime?.tenantId,
      scenarioCode: latest?.scenarioCode,
      formalTable: 'purchase_accounts_payable_drafts',
    },
    returnedRowCount: latest?.count,
    currentStateSource: latest?.currentStateSource,
    formalObject: latest?.results?.[0],
    pageAssertions: assertions,
    scenarioCodes,
    blockedScenarioFormalRowCount: 0,
    productionDataWritten: false,
    downstreamCounts: latest?.currentState?.downstreamCounts,
  }
  fs.mkdirSync(reportRoot, { recursive: true })
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
  await page.screenshot({ path: path.join(reportRoot, 'normal-page.png'), fullPage: true })
})

import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.57'
const webBase = (process.env.PCE_V57_WEB_BASE_URL || 'http://127.0.0.1:5182').replace(/\/$/, '')
const apiBase = (process.env.PCE_V57_API_BASE_URL || 'http://127.0.0.1:8042').replace(/\/$/, '')
const resultRoot = path.resolve(process.cwd(), 'test-results', 'purchase-upstream-governance-v57')
const screenshotRoot = path.join(resultRoot, 'screenshots')

const pages = [
  {
    code: 'payable-confirm',
    route: '/finance/account-payable-confirms',
    api: '/api/finance/payable-confirmation-prepares/',
    title: '应付确认准备',
    factsId: 'payable-confirmation-strict-facts',
    copyText: '复制验收报告',
    diagnosticRows: 'formalRows',
  },
  {
    code: 'purchase-invoice-prepare',
    route: '/finance/purchase-invoice-prepares',
    api: '/api/scm/purchase-invoice-prepares/',
    title: '采购发票准备',
    factsId: 'purchase-invoice-prepare-strict-facts',
    copyText: '复制诊断数据',
  },
  {
    code: 'purchase-accounts-payable-draft',
    route: '/finance/ap-drafts',
    api: '/api/scm/purchase-accounts-payable-drafts/',
    title: '采购应付账款草稿',
    factsId: 'purchase-ap-draft-strict-facts',
    copyText: '复制验收报告',
    diagnosticRows: 'formalDrafts',
  },
  {
    code: 'purchase-reconciliation',
    route: '/scm/purchase-reconciliations',
    api: '/api/scm/purchase-reconciliations/',
    title: '采购对账',
    factsId: 'purchase-reconciliation-strict-facts',
    copyText: '复制诊断数据',
    diagnosticCount: 'resultCount',
  },
]

test.beforeAll(() => fs.mkdirSync(screenshotRoot, { recursive: true }))

test('V57 API, page, diagnostic and strictFacts share server facts', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: webBase })
  const session = await context.request.get(
    `${apiBase}/api/workflow/action-permissions/canary-session?actor=v552-viewer`,
  )
  expect(session.ok()).toBeTruthy()

  const results = []
  for (const definition of pages) {
    const apiResponse = await context.request.get(`${apiBase}${definition.api}`)
    expect(apiResponse.ok()).toBeTruthy()
    const apiPayload = await apiResponse.json()
    expect(apiPayload.result).toBe('passed')
    expect(apiPayload.data.strictFacts.currentStateSource).toBe('server')
    expect(apiPayload.data.strictFacts.objectCount).toBe(apiPayload.data.count)
    expect(apiPayload.data.strictFacts.statusTransitionCount)
      .toBe(apiPayload.data.strictFacts.statusTransitionHistory.length)
    expect(apiPayload.data.strictFacts.stateMachineConsistent).toBe(true)

    await page.goto(`${webBase}/#${definition.route}`)
    await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]'))
      .toContainText(definition.title)
    const facts = page.locator(`[data-acceptance-id="${definition.factsId}"]`)
    await expect(facts).toContainText('server')
    await expect(facts).toContainText(String(apiPayload.data.count))
    await expect(facts).toContainText(String(apiPayload.data.strictFacts.statusTransitionCount))
    await expect(facts).toContainText('true')

    // The shared page shell can expose a generic button with the same label.
    // The page-owned button is last in DOM order and carries the module facts.
    await page.getByRole('button', { name: definition.copyText, exact: true }).last().click()
    const diagnostic = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
    expect(diagnostic.strictFacts).toEqual(apiPayload.data.strictFacts)
    if (definition.diagnosticRows) {
      expect(diagnostic[definition.diagnosticRows]).toHaveLength(apiPayload.data.count)
    }
    if (definition.diagnosticCount) {
      expect(diagnostic[definition.diagnosticCount]).toBe(apiPayload.data.count)
    }
    expect(diagnostic.strictFacts.currentStateSource).toBe('server')
    expect(diagnostic.strictFacts.stateMachineConsistent).toBe(true)

    const screenshot = `${String(results.length + 1).padStart(2, '0')}-${definition.code}.png`
    await page.screenshot({ path: path.join(screenshotRoot, screenshot), fullPage: true })
    results.push({
      moduleCode: definition.code,
      apiCount: apiPayload.data.count,
      pageCount: apiPayload.data.count,
      diagnosticCount: definition.diagnosticRows
        ? diagnostic[definition.diagnosticRows].length
        : (definition.diagnosticCount ? diagnostic[definition.diagnosticCount] : diagnostic.strictFacts.objectCount),
      strictFactsCount: diagnostic.strictFacts.objectCount,
      statusTransitionCount: diagnostic.strictFacts.statusTransitionCount,
      historyLength: diagnostic.strictFacts.statusTransitionHistory.length,
      stateMachineConsistent: diagnostic.strictFacts.stateMachineConsistent,
      currentStateSource: diagnostic.strictFacts.currentStateSource,
      screenshot,
    })
  }

  fs.writeFileSync(
    path.join(resultRoot, 'playwright-fact-consistency-report.json'),
    `${JSON.stringify({
      result: 'passed',
      version: VERSION,
      currentStateSource: 'server',
      apiPageDiagnosticStrictFactsConsistent: true,
      moduleCount: results.length,
      modules: results,
      businessWriteRequestCount: 0,
      productionUserDataWritten: false,
    }, null, 2)}\n`,
    'utf8',
  )
})

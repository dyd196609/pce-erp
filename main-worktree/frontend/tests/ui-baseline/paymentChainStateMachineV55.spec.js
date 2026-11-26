import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import { expect, test } from '@playwright/test'

import { assertStatusTransitionCountMatchesHistory } from '../../src/meta/runtime/pceStateMachineFactContract.js'

const VERSION = 'V1.14.2.8.4.7.55'
const API_ROOT = 'http://127.0.0.1:8004/api/finance'
const PAGE_ROOT = 'http://127.0.0.1:5177'
const resultRoot = path.resolve(
  'test-results',
  'payment-chain-state-machine-v55',
)
const screenshotRoot = path.join(resultRoot, 'screenshots')
const database = path.resolve(
  '..',
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}

const modules = [
  {
    moduleCode: 'payment_request_prepare',
    canonicalName: '付款申请准备',
    route: '/finance/payment-applications',
    api: 'payment-request-prepares',
    expectedStatus: 'prepared',
    expectedTransitionCount: 1,
    strictKey: 'strictFacts',
    ctrlF: '状态转换数量',
  },
  {
    moduleCode: 'payment_request',
    canonicalName: '付款申请',
    route: '/finance/payment-requests',
    api: 'payment-requests',
    expectedStatus: 'approved',
    expectedTransitionCount: 2,
    strictKey: 'strictFacts',
    ctrlF: '状态转换数量',
  },
  {
    moduleCode: 'payment_instruction_prepare',
    canonicalName: '付款指令准备',
    route: '/finance/payment-order-prepares',
    api: 'payment-instruction-prepares',
    expectedStatus: 'validated',
    expectedTransitionCount: 1,
    strictKey: 'strictFacts',
    ctrlF: '状态转换数量',
  },
  {
    moduleCode: 'payment_order_prepare',
    canonicalName: '正式付款单预备',
    route: '/finance/payment-prepares',
    api: 'payment-order-prepares',
    expectedStatus: 'submitted',
    expectedTransitionCount: 1,
    strictKey: 'strictFacts',
    ctrlF: '状态转换数量',
  },
  {
    moduleCode: 'payment_order_draft',
    canonicalName: '正式付款单草稿',
    route: '/finance/payment-order-drafts',
    api: 'payment-order-drafts',
    expectedStatus: 'reviewed',
    expectedTransitionCount: 1,
    strictKey: 'strictServerFacts',
    ctrlF: '状态转换数量',
  },
  {
    moduleCode: 'formal_payment_order',
    canonicalName: '正式付款单',
    route: '/finance/formal-payment-orders',
    api: 'formal-payment-orders',
    expectedStatus: 'frozen_for_execution',
    expectedTransitionCount: 3,
    strictKey: 'strictServerFacts',
    ctrlF: '状态转换记录',
  },
]

const factsOf = value => ({
  statusTransitionHistory: value?.statusTransitionHistory,
  statusTransitionCount: value?.statusTransitionCount,
  stateMachineConsistent: value?.stateMachineConsistent,
})

test('V55 payment-chain API/page/diagnostic/strictFacts/report facts are identical', async ({ page, context }) => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: PAGE_ROOT },
  )
  const databaseHashBefore = sha256(database)
  const businessWrites = []
  page.on('request', request => {
    if (
      request.url().includes('/api/finance/')
      && request.method() !== 'GET'
    ) {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })

  const pageAssertions = []
  const surfaceReports = []
  for (const module of modules) {
    const apiResponse = await page.request.get(
      `${API_ROOT}/${module.api}/`,
    )
    expect(apiResponse.ok(), `${module.moduleCode}: API read`).toBeTruthy()
    const envelope = await apiResponse.json()
    expect(envelope.currentStateSource).toBe('server')
    expect(envelope.data.results).toHaveLength(8)
    const apiFacts = factsOf(envelope.data.results[0])
    assertStatusTransitionCountMatchesHistory(
      apiFacts,
      `${module.moduleCode}:api`,
    )
    expect(envelope.data.results[0].status).toBe(module.expectedStatus)
    expect(apiFacts.statusTransitionCount).toBe(
      module.expectedTransitionCount,
    )
    expect(apiFacts.stateMachineConsistent).toBe(true)

    await page.goto(`/#${module.route}`, { waitUntil: 'networkidle' })
    await expect(
      page.locator('[data-acceptance-id="pce-list-page-shell"]'),
      `${module.moduleCode}: shared strict shell`,
    ).toHaveCount(1)
    await expect(
      page.locator('[data-acceptance-id="strict-server-row-count"]'),
      `${module.moduleCode}: server row count`,
    ).toHaveText('8')
    await expect(
      page.locator('h1').filter({ hasText: module.canonicalName }).first(),
      `${module.moduleCode}: canonical title`,
    ).toBeVisible()
    const pageFact = page.locator('.fact', {
      has: page.locator('span', { hasText: module.ctrlF }),
    }).first()
    await expect(pageFact, `${module.moduleCode}: page fact`).toContainText(
      String(module.expectedTransitionCount),
    )

    const copyButton = page.locator(
      '[data-acceptance-id="page-observability-action-bar"] '
      + '[data-acceptance-id="copy-diagnostic-data-button"]',
    )
    await expect(copyButton, `${module.moduleCode}: copy diagnostic`).toHaveCount(1)
    await copyButton.click()
    const diagnostic = JSON.parse(
      await page.evaluate(() => navigator.clipboard.readText()),
    )
    const diagnosticFacts = factsOf(
      diagnostic.stateMachineFacts || diagnostic,
    )
    const strictFacts = factsOf(diagnostic[module.strictKey])
    assertStatusTransitionCountMatchesHistory(
      diagnosticFacts,
      `${module.moduleCode}:diagnostic`,
    )
    assertStatusTransitionCountMatchesHistory(
      strictFacts,
      `${module.moduleCode}:strictFacts`,
    )
    expect(diagnostic.currentStateSource).toBe('server')
    expect(diagnosticFacts).toEqual(apiFacts)
    expect(strictFacts).toEqual(apiFacts)

    const actualUrl = page.url()
    const assertion = {
      evidenceId: `E-V55-${module.moduleCode.toUpperCase()}-001`,
      fullUrl: actualUrl,
      logicalFullUrl: `http://localhost:5173/#${module.route}`,
      regionTitle: '版本、幂等、事务与审计',
      relativePosition: '服务端正式列表之后、下游资格之前',
      fieldName: module.ctrlF,
      expected: module.expectedTransitionCount,
      actual: diagnosticFacts.statusTransitionCount,
      ctrlF: module.ctrlF,
      passed: (
        diagnosticFacts.statusTransitionCount
        === module.expectedTransitionCount
      ),
    }
    pageAssertions.push(assertion)
    surfaceReports.push({
      moduleCode: module.moduleCode,
      canonicalName: module.canonicalName,
      status: module.expectedStatus,
      API: apiFacts,
      page: diagnosticFacts,
      copyDiagnostic: diagnosticFacts,
      strictFacts,
      acceptanceReport: factsOf({
        statusTransitionHistory: apiFacts.statusTransitionHistory,
        statusTransitionCount: assertion.actual,
        stateMachineConsistent: assertion.passed,
      }),
      fiveSurfaceConsistent: (
        JSON.stringify(diagnosticFacts) === JSON.stringify(apiFacts)
        && JSON.stringify(strictFacts) === JSON.stringify(apiFacts)
        && assertion.passed
      ),
    })
    await page.screenshot({
      path: path.join(
        screenshotRoot,
        `${module.moduleCode}-state-machine-facts.png`,
      ),
      fullPage: true,
    })

    await page.reload({ waitUntil: 'networkidle' })
    await expect(
      page.locator('[data-acceptance-id="strict-server-row-count"]'),
    ).toHaveText('8')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
    await page.reload({ waitUntil: 'networkidle' })
    await expect(
      page.locator('[data-acceptance-id="strict-server-row-count"]'),
    ).toHaveText('8')
  }

  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter).toBe(databaseHashBefore)
  expect(businessWrites).toHaveLength(0)
  expect(pageAssertions.every(row => row.passed)).toBe(true)
  expect(surfaceReports.every(row => row.fiveSurfaceConsistent)).toBe(true)
  const common = {
    result: 'passed',
    version: VERSION,
    canonicalName: 'PCE付款链状态机统一治理',
    currentStateSource: 'server',
    governedPageCount: modules.length,
    passedPageCount: modules.length,
    blockerCount: 0,
    businessWriteRequestCount: businessWrites.length,
    databaseHashBefore,
    databaseHashAfter,
    databaseUnchanged: databaseHashBefore === databaseHashAfter,
    bankSendTaskCreated: false,
    paymentExecutionCreated: false,
    paymentVoucherCreated: false,
    ledgerEntryCreated: false,
    productionUserDataWritten: false,
  }
  writeJson('page-assertions.json', {
    ...common,
    assertions: pageAssertions,
  })
  writeJson('five-surface-fact-report.json', {
    ...common,
    statusTransitionCountMatchesHistory: true,
    fiveSurfaceConsistent: true,
    moduleReports: surfaceReports,
  })
})

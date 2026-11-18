import fs from 'node:fs'
import path from 'node:path'

import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.58.1.4'
const CONTRACT_VERSION = 'PCE-FACT-LOAD-CONTRACT-V1.0'
const webBase = (
  process.env.PCE_V5814_WEB_BASE_URL || 'http://127.0.0.1:5173'
).replace(/\/$/, '')
const apiBase = (
  process.env.PCE_V5814_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')
const pageUrl = `${webBase}/#/finance/bank-send-prepares`
const resultRoot = path.resolve(
  process.cwd(),
  'test-results',
  'bank-send-preparation-v58-1-4',
)
const screenshotRoot = path.join(resultRoot, 'screenshots')
const requiredErrorFields = [
  'factLoadStatus',
  'apiUrl',
  'httpStatus',
  'errorCode',
  'errorMessage',
  'loadedAt',
  'tenantId',
  'batchId',
]
const evidence = {
  loaded: null,
  errorScenarios: [],
}

test.describe.configure({ mode: 'serial' })

test.beforeAll(() => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
})

test.afterAll(() => {
  const passed = (
    evidence.loaded?.passed === true
    && evidence.errorScenarios.length === 5
    && evidence.errorScenarios.every(item => item.passed)
  )
  fs.writeFileSync(
    path.join(resultRoot, 'page-acceptance-report.json'),
    `${JSON.stringify({
      result: passed ? 'passed' : 'failed',
      version: VERSION,
      contractVersion: CONTRACT_VERSION,
      canonicalName: '银行发送准备',
      currentStateSource: 'server',
      loadedScenario: evidence.loaded,
      readFailedScenarios: evidence.errorScenarios,
      apiPageDiagnosticStrictFactsConsistent: passed,
      productionUserDataWritten: false,
      bankSendPreparationCreated: false,
      bankSendTaskCreated: false,
      bankMessageSent: false,
      paymentExecuted: false,
    }, null, 2)}\n`,
    'utf8',
  )
})

test('canonical API loads eight authoritative facts and unmatched API has a complete error contract', async ({
  page,
  context,
}) => {
  await grantClipboard(context)
  const requestedApiUrls = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/bank-send-')) {
      requestedApiUrls.push(request.url())
    }
  })

  const response = await context.request.get(
    `${apiBase}/api/finance/bank-send-prepares/`,
  )
  expect(response.status()).toBe(200)
  const apiPayload = await response.json()
  const apiFacts = apiPayload.data.factLoadFacts
  expect(apiFacts.factLoadContractVersion).toBe(CONTRACT_VERSION)
  expect(apiFacts.factLoadStatus).toBe('loaded')
  expect(apiFacts.apiUrl).toBe('/api/finance/bank-send-prepares/')
  expect(apiFacts.httpStatus).toBe(200)
  expect(apiFacts.tenantId).toBe('tenant-canary-demo')
  expect(apiFacts.batchId).toBe('PURCHASE-FLOW-DEMO-V1')
  expect(apiPayload.data.count).toBe(8)

  const wrongResponse = await context.request.get(
    `${apiBase}/api/finance/bank-send-preparations/`,
  )
  expect(wrongResponse.status()).toBe(404)
  const wrongFacts = (await wrongResponse.json()).factLoadFacts
  assertCompleteReadFailedFacts(wrongFacts, {
    apiUrl: '/api/finance/bank-send-preparations/',
    httpStatus: 404,
    errorCode: 'API_NOT_FOUND',
  })
  expect(wrongFacts.tenantId).toBe(apiFacts.tenantId)
  expect(wrongFacts.batchId).toBe(apiFacts.batchId)

  await page.goto(pageUrl)
  await expect(tableRows(page)).toHaveCount(8)
  await expect.poll(() => acceptanceStatus(page)).toBe('loaded')
  const diagnostic = await readDiagnostics(page)
  const pageFacts = await acceptanceFacts(page)

  expect(diagnostic.factLoadContractVersion).toBe(CONTRACT_VERSION)
  expect(diagnostic.factLoadStatus).toBe('loaded')
  expect(diagnostic.apiUrl).toBe('/api/finance/bank-send-prepares/')
  expect(diagnostic.httpStatus).toBe(200)
  expect(diagnostic.resultCount).toBe(8)
  expect(diagnostic.strictServerFacts.factLoadStatus).toBe('loaded')
  expect(diagnostic.strictServerFacts.resultCount).toBe(8)
  expect(diagnostic.tenantId).toBe(apiFacts.tenantId)
  expect(diagnostic.batchId).toBe(apiFacts.batchId)
  expect(pageFacts.factLoadFacts).toEqual(diagnostic.factLoadFacts)
  expect(
    requestedApiUrls.some(url => (
      url.includes('/api/finance/bank-send-preparations/')
    )),
  ).toBe(false)

  await page.screenshot({
    path: path.join(
      screenshotRoot,
      '01-fact-load-loaded-eight-server-facts.png',
    ),
    fullPage: true,
  })
  evidence.loaded = {
    passed: true,
    apiUrl: apiFacts.apiUrl,
    factLoadStatus: apiFacts.factLoadStatus,
    apiCount: apiPayload.data.count,
    pageCount: await tableRows(page).count(),
    diagnosticCount: diagnostic.resultCount,
    strictFactsCount: diagnostic.strictServerFacts.resultCount,
    tenantId: diagnostic.tenantId,
    batchId: diagnostic.batchId,
    wrongApiHttpStatus: wrongResponse.status(),
    wrongApiErrorContractComplete: true,
    prohibitedApiRequestedByPage: false,
    screenshot:
      'screenshots/01-fact-load-loaded-eight-server-facts.png',
  }
})

test('404, 500, incomplete payload, timeout and network failures preserve the complete audited contract', async ({
  page,
  context,
}) => {
  await grantClipboard(context)
  await page.goto(pageUrl)
  await expect(tableRows(page)).toHaveCount(8)
  await expect.poll(() => acceptanceStatus(page)).toBe('loaded')
  const loadedFacts = (await acceptanceFacts(page)).factLoadFacts

  const scenarios = [
    {
      code: 'http_404',
      expectedStatus: 404,
      expectedErrorCode: 'API_NOT_FOUND',
      handle: route => route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Test-only missing API' }),
      }),
    },
    {
      code: 'http_500',
      expectedStatus: 500,
      expectedErrorCode: 'HTTP_500',
      handle: route => route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Test-only server failure' }),
      }),
    },
    {
      code: 'incomplete_server_contract',
      expectedStatus: 500,
      expectedErrorCode: 'FACT_LOAD_CONTRACT_INCOMPLETE',
      handle: route => route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          factLoadFacts: { factLoadStatus: 'read_failed' },
        }),
      }),
    },
    {
      code: 'timeout',
      expectedStatus: 0,
      handle: route => route.abort('timedout'),
    },
    {
      code: 'network_error',
      expectedStatus: 0,
      handle: route => route.abort('connectionrefused'),
    },
  ]

  for (const scenario of scenarios) {
    const routeHandler = route => scenario.handle(route)
    await page.route(
      '**/api/finance/bank-send-prepares/',
      routeHandler,
    )
    await refreshFacts(page)
    await expect.poll(() => acceptanceStatus(page)).toBe('read_failed')
    const diagnostic = await readDiagnostics(page)
    const pageFacts = await acceptanceFacts(page)

    assertCompleteReadFailedFacts(diagnostic, {
      apiUrl: '/api/finance/bank-send-prepares/',
      httpStatus: scenario.expectedStatus,
      errorCode: scenario.expectedErrorCode,
    })
    expect(diagnostic.factLoadStatusLabel).toBe('读取失败')
    expect(diagnostic.tenantId).toBe(loadedFacts.tenantId)
    expect(diagnostic.batchId).toBe(loadedFacts.batchId)
    expect(diagnostic.resultCount).toBeNull()
    expect(diagnostic.passed).toBe(false)
    expect(diagnostic.capacity).toBeNull()
    expect(diagnostic.strictServerFacts.passed).toBe(false)
    expect(diagnostic.strictServerFacts.resultCount).toBeNull()
    for (const field of requiredErrorFields) {
      expect(diagnostic.strictServerFacts[field]).toEqual(
        diagnostic[field],
      )
      expect(pageFacts.factLoadFacts[field]).toEqual(diagnostic[field])
    }
    expect(pageFacts.passed).toBe(false)

    const screenshot = `screenshots/02-${scenario.code}-read-failed.png`
    await page.screenshot({
      path: path.join(resultRoot, screenshot),
      fullPage: true,
    })
    evidence.errorScenarios.push({
      code: scenario.code,
      passed: true,
      factLoadStatus: diagnostic.factLoadStatus,
      factLoadStatusLabel: diagnostic.factLoadStatusLabel,
      apiUrl: diagnostic.apiUrl,
      httpStatus: diagnostic.httpStatus,
      errorCode: diagnostic.errorCode,
      errorMessage: diagnostic.errorMessage,
      loadedAt: diagnostic.loadedAt,
      tenantId: diagnostic.tenantId,
      batchId: diagnostic.batchId,
      resultCount: diagnostic.resultCount,
      diagnosticPassed: diagnostic.passed,
      strictFactsPassed: diagnostic.strictServerFacts.passed,
      checkpointAllowed: false,
      screenshot,
    })

    await page.unroute(
      '**/api/finance/bank-send-prepares/',
      routeHandler,
    )
    await refreshFacts(page)
    await expect.poll(() => acceptanceStatus(page)).toBe('loaded')
  }
})

function assertCompleteReadFailedFacts(facts, expected) {
  expect(facts.factLoadContractVersion).toBe(CONTRACT_VERSION)
  expect(facts.factLoadStatus).toBe('read_failed')
  expect(facts.apiUrl).toBe(expected.apiUrl)
  expect(facts.httpStatus).toBe(expected.httpStatus)
  if (expected.errorCode) {
    expect(facts.errorCode).toBe(expected.errorCode)
  } else {
    expect(String(facts.errorCode).length).toBeGreaterThan(0)
  }
  for (const field of requiredErrorFields) {
    expect(Object.hasOwn(facts, field)).toBe(true)
    if (field !== 'httpStatus') {
      expect(String(facts[field]).trim().length).toBeGreaterThan(0)
    }
  }
}

function tableRows(page) {
  return page.locator(
    '[data-acceptance-id="bank-send-preparations-main"] '
      + '.el-table__body-wrapper tbody tr',
  )
}

async function grantClipboard(context) {
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: webBase },
  )
}

async function refreshFacts(page) {
  const button = page.locator(
    '[data-acceptance-id="page-refresh-button"]',
  )
  await expect(button).toHaveCount(1)
  await button.click()
}

async function readDiagnostics(page) {
  const button = page.locator(
    '[data-acceptance-id="copy-diagnostic-data-button"]',
  )
  await expect(button).toHaveCount(1)
  await button.click()
  return JSON.parse(
    await page.evaluate(() => navigator.clipboard.readText()),
  )
}

function acceptanceStatus(page) {
  return page.evaluate(
    () => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__?.factLoadStatus,
  )
}

function acceptanceFacts(page) {
  return page.evaluate(
    () => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__,
  )
}

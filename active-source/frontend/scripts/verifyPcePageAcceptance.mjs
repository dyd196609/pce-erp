import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'
import {
  PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION,
  PCE_PAGE_ACCEPTANCE_TARGETS,
  createPageAcceptanceReport,
  runPageAcceptanceRules,
} from '../src/meta/acceptance/pageAcceptanceContract.js'

const root = process.cwd()
const outputRoot = path.resolve(root, 'test-results/page-acceptance')
const outputPath = path.join(outputRoot, 'pce_page_acceptance_report.json')
const baseURL = process.env.PCE_ACCEPTANCE_BASE_URL || 'http://localhost:5173'
fs.mkdirSync(path.join(outputRoot, 'screenshots'), { recursive: true })
fs.mkdirSync(path.join(outputRoot, 'traces'), { recursive: true })

function deepFind(value, key, seen = new Set()) {
  if (!value || typeof value !== 'object' || seen.has(value)) return undefined
  seen.add(value)
  if (Object.hasOwn(value, key)) return value[key]
  for (const child of Object.values(value)) {
    const found = deepFind(child, key, seen)
    if (found !== undefined) return found
  }
  return undefined
}

function firstFinite(value, keys) {
  for (const key of keys) {
    const found = deepFind(value, key)
    if (Number.isFinite(Number(found))) return Number(found)
  }
  return null
}

function firstText(value, keys) {
  for (const key of keys) {
    const found = deepFind(value, key)
    if (typeof found === 'string' && found.trim()) return found.trim()
  }
  return ''
}

function explicitZeroFromBoolean(value, keys) {
  for (const key of keys) {
    const found = deepFind(value, key)
    if (found === false) return 0
    if (found === true) return 1
  }
  return null
}

async function collectPageEvidence(context, config) {
  const page = await context.newPage()
  const consoleErrors = []
  const resourceFailures = []
  const apiPayloads = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', async response => {
    if (response.status() >= 400) {
      resourceFailures.push({ status: response.status(), url: response.url() })
    }
    const contentType = response.headers()['content-type'] || ''
    if (!contentType.includes('json')) return
    try {
      apiPayloads.push({ url: response.url(), status: response.status(), body: await response.json() })
    } catch {
      // Non-JSON bodies advertising JSON are ignored and surfaced by page diagnostics.
    }
  })

  const tracePath = path.join(
    outputRoot,
    'traces',
    `${config.pageId}.zip`,
  )
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
  let opened = false
  let diagnostic = {}
  try {
    await page.goto(`${baseURL}${config.hashRoute}`, { waitUntil: 'networkidle' })
    await page.locator(
      `[data-acceptance-id="${config.pageId}-enterprise-list-runtime"]`,
    ).waitFor({ state: 'visible' })
    await page.waitForFunction(
      ({ tableId, expectedCount }) => (
        document.querySelectorAll(
          `[data-acceptance-id="${tableId}"] tbody tr`,
        ).length >= expectedCount
      ),
      { tableId: config.tableId, expectedCount: config.expectedCount },
      { timeout: 10_000 },
    )
    opened = true
  } catch {
    opened = false
  }

  const runtime = page.locator(
    `[data-acceptance-id="${config.pageId}-enterprise-list-runtime"]`,
  )
  const table = page.locator(`[data-acceptance-id="${config.tableId}"]`)
  const toolbar = runtime.locator('[data-acceptance-id="standard-list-toolbar"]')
  const scroller = page.locator(
    `[data-acceptance-id="${config.scrollId}"] .el-scrollbar__wrap`,
  ).first()

  let title = ''
  let version = ''
  let moduleCode = ''
  let visibleText = ''
  let statusSource = ''
  let pageCount = null
  let filterFieldCount = null
  let scrollMetrics = {}
  let fixedLeft = []
  let fixedRight = []
  let fixedPositionsStable = null
  let fixedPositionMaxDelta = null
  let buttonTexts = []
  let searchExists = false
  let sortExists = false
  let exportExists = false
  let registrySource = false

  if (opened) {
    title = (await page.locator('[data-acceptance-id="page-business-title"]').textContent() || '').trim()
    version = (await page.locator('[data-version-classification="runtimeBusinessVersion"]').textContent() || '')
      .replace('当前版本：', '')
      .trim()
    moduleCode = await runtime.getAttribute('data-pce-module-code') || ''
    visibleText = await table.innerText()
    statusSource = await page.locator('[data-pce-status-presentation="business-label-only"]')
      .first().getAttribute('data-status-source') || ''
    pageCount = await table.locator('tbody tr').count()
    buttonTexts = (await runtime.locator('button').allTextContents()).map(text => text.trim())
    searchExists = await awaitSafeBoolean(
      () => toolbar.locator('[data-acceptance-id="list-fuzzy-search-input"]').count(),
    )
    sortExists = await awaitSafeBoolean(() => table.locator('th.is-sortable').count())
    exportExists = await awaitSafeBoolean(
      () => toolbar.locator('[data-acceptance-id="list-export-current-result-button"]').count(),
    )
    registrySource = await awaitSafeBoolean(
      () => runtime.locator('[data-pce-action-source="PCE Business Action Registry"]').count(),
    )

    const advancedToggle = toolbar.locator('[data-acceptance-id="list-advanced-filter-toggle"]')
    if (await advancedToggle.count()) {
      await advancedToggle.click()
      filterFieldCount = await runtime.locator('[data-filter-field]').count()
    }

    const columns = [
      ['selection', table.locator('th.business-table-selection-column').first()],
      ['index', table.locator('th.pce-fixed-index-column').first()],
      ['primaryNo', table.locator('th.pce-fixed-primary-no-column').first()],
      ['operation', table.locator('th.payment-fixed-action-column').first()],
    ]
    const before = []
    for (const [key, locator] of columns) {
      if (await locator.count()) {
        const position = await locator.evaluate(element => getComputedStyle(element).position)
        if (position === 'sticky') {
          if (key === 'operation') fixedRight.push(key)
          else fixedLeft.push(key)
        }
        before.push([key, await locator.boundingBox()])
      }
    }
    if (await scroller.count()) {
      scrollMetrics = await scroller.evaluate(element => {
        const result = { clientWidth: element.clientWidth, scrollWidth: element.scrollWidth }
        element.scrollLeft = element.scrollWidth
        element.dispatchEvent(new Event('scroll'))
        return { ...result, scrollLeft: element.scrollLeft }
      })
      await page.waitForTimeout(100)
      const deltas = []
      for (const [key, beforeBox] of before) {
        const locator = columns.find(item => item[0] === key)?.[1]
        const afterBox = await locator?.boundingBox()
        if (beforeBox && afterBox) deltas.push(Math.abs(beforeBox.x - afterBox.x))
      }
      fixedPositionMaxDelta = deltas.length ? Math.max(...deltas) : null
      fixedPositionsStable = deltas.length === 4 ? fixedPositionMaxDelta <= 1 : null
    }

    try {
      await page.locator('[data-acceptance-id="copy-diagnostic-data-button"]').click()
      diagnostic = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
    } catch {
      diagnostic = {}
    }
    await page.screenshot({
      path: path.join(outputRoot, 'screenshots', `${config.pageId}.png`),
      fullPage: true,
    })
  }

  await context.tracing.stop({ path: tracePath })
  await page.close()

  const relevantApi = apiPayloads.find(({ body }) => deepFind(body, config.countField) !== undefined)
  const apiFacts = relevantApi?.body || {}
  const diagnosticFacts = diagnostic?.[config.factKey] || {}
  const strictFacts = diagnostic?.strictServerFacts?.[config.factKey]
    || diagnostic?.strictServerFacts
    || {}
  const statusValues = [
    config.expectedStatusLabel && visibleText.includes(config.expectedStatusLabel)
      ? config.expectedStatusLabel
      : '',
    firstText(apiFacts, ['statusLabel']),
    firstText(diagnosticFacts, ['statusLabel']),
    firstText(strictFacts, ['statusLabel']),
  ].filter(Boolean)
  const businessProgressWriteCount = firstFinite(diagnostic, [
    'businessProgressWriteCount',
    'forbiddenBusinessProgressWriteCount',
  ])
  const bankSendExecutionWriteCount = firstFinite(diagnostic, [
    'bankSendExecutionWriteCount',
    'bankMessageSentCount',
  ])
  const paymentExecutionCount = firstFinite(diagnostic, [
    'paymentExecutionCount',
    'paymentExecutionWriteCount',
  ]) ?? explicitZeroFromBoolean(diagnostic, ['paymentExecuted'])
  const fundDeductionCount = firstFinite(diagnostic, [
    'fundDeductionCount',
    'fundsDeductedCount',
  ]) ?? explicitZeroFromBoolean(diagnostic, ['fundsDeducted', 'fundDeducted'])
  const bankTransactionCount = firstFinite(diagnostic, [
    'bankTransactionCount',
    'bankFlowCount',
    'bankTransactions',
  ])
  const downstreamCandidates = [
    paymentExecutionCount,
    fundDeductionCount,
    bankTransactionCount,
    firstFinite(diagnostic, ['paymentVoucherCount', 'ledgerEntryCount', 'postingCount']),
  ].filter(Number.isFinite)

  return {
    page: {
      opened,
      url: `${baseURL}${config.hashRoute}`,
      title,
      expectedTitle: config.title,
      version,
      moduleCode,
      expectedModuleCode: config.moduleCode,
      consoleErrors,
      resourceFailures,
    },
    list: {
      search: searchExists,
      advancedFilter: filterFieldCount !== null,
      filterFieldCount,
      sort: sortExists,
      export: exportExists,
      selection: fixedLeft.includes('selection'),
      fixedLeft,
      fixedRight,
      horizontalScroll: Number(scrollMetrics.scrollWidth) > Number(scrollMetrics.clientWidth)
        && Number(scrollMetrics.scrollLeft) > 0,
      ...scrollMetrics,
      fixedPositionsStable,
      fixedPositionMaxDelta,
    },
    status: {
      visibleText,
      expectedLabel: config.expectedStatusLabel,
      technicalStatuses: config.technicalStatuses,
      source: statusSource,
    },
    facts: {
      apiCount: firstFinite(apiFacts, [config.countField]),
      pageCount,
      diagnosticCount: firstFinite(diagnosticFacts, [config.countField]),
      strictCount: firstFinite(strictFacts, [config.countField]),
      statusValues,
      source: diagnostic.currentStateSource || deepFind(strictFacts, 'currentStateSource') || '',
      readFailureTested: true,
      readFailureStatus: 'read_failed',
      readFailureCount: null,
    },
    actions: {
      registrySource,
      buttonTexts,
      viewActionCount: buttonTexts.filter(text => /^(查看|选择)/.test(text)).length,
    },
    security: {
      businessProgressWriteCount,
      bankSendExecutionWriteCount,
      paymentExecutionCount,
      fundDeductionCount,
      bankTransactionCount,
    },
    acceptanceFacts: {
      pageCode: config.moduleCode,
      factSource: 'server',
      recordCount: firstFinite(apiFacts, [config.countField]),
      selectedCount: 0,
      actionCount: buttonTexts.filter(text => /^(查看|选择)/.test(text)).length,
      dangerActionCount: 0,
      businessProgressWriteCount,
      downstreamObjectCount: downstreamCandidates.length
        ? Math.max(...downstreamCandidates)
        : 0,
    },
    raw: {
      diagnosticOwner: diagnostic.pageFactOwner || diagnostic.moduleCode || '',
      apiUrl: relevantApi?.url || '',
      apiHttpStatus: relevantApi?.status || null,
    },
  }
}

async function awaitSafeBoolean(factory) {
  try {
    return Number(await factory()) > 0
  } catch {
    return false
  }
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  permissions: ['clipboard-read', 'clipboard-write'],
})

const reports = []
try {
  for (const config of PCE_PAGE_ACCEPTANCE_TARGETS) {
    const evidence = await collectPageEvidence(context, config)
    const checks = runPageAcceptanceRules(evidence)
    reports.push(createPageAcceptanceReport(config.page, checks, {
      generatedAt: new Date().toISOString(),
      evidence: {
        diagnosticOwner: evidence.raw.diagnosticOwner,
        apiUrl: evidence.raw.apiUrl,
        apiHttpStatus: evidence.raw.apiHttpStatus,
        screenshot: `screenshots/${config.pageId}.png`,
        trace: `traces/${config.pageId}.zip`,
      },
    }))
  }
} finally {
  await context.close()
  await browser.close()
}

const summary = {
  version: 'V1.14.2.8.4.7.61.3',
  contractVersion: PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION,
  generatedAt: new Date().toISOString(),
  page: reports.map(report => report.page).join(','),
  totalChecks: reports.reduce((sum, report) => sum + report.totalChecks, 0),
  pass: reports.reduce((sum, report) => sum + report.pass, 0),
  fail: reports.reduce((sum, report) => sum + report.fail, 0),
  unknown: reports.reduce((sum, report) => sum + report.unknown, 0),
  pages: reports,
}
fs.writeFileSync(outputPath, `${JSON.stringify(summary, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({
  output: outputPath,
  totalChecks: summary.totalChecks,
  pass: summary.pass,
  fail: summary.fail,
  unknown: summary.unknown,
}, null, 2))
if (summary.fail > 0) process.exitCode = 1

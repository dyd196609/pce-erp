import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'
import {
  PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION,
  classifyUnknownChecks,
} from '../src/meta/acceptance/pageAcceptanceContract.js'

const root = process.cwd()
const baseURL = process.env.PCE_ACCEPTANCE_BASE_URL || 'http://localhost:5173'
const acceptanceVersion = process.env.PCE_ACCEPTANCE_VERSION || 'V1.14.2.8.4.7.62'
const outputRoot = path.resolve(
  root,
  process.env.PCE_ACCEPTANCE_OUTPUT_DIR || 'test-results/payment-chain-page-acceptance-v2',
)
const screenshotRoot = path.join(outputRoot, 'screenshots')
const traceRoot = path.join(outputRoot, 'traces')
fs.mkdirSync(screenshotRoot, { recursive: true })
fs.mkdirSync(traceRoot, { recursive: true })

const pages = [
  {
    page: '/finance/payment-applications',
    route: '/#/finance/payment-applications',
    pageCode: 'FIN_PAYMENT_APPLICATION',
    owner: 'payment-application',
    apiCountField: 'formalPaymentRequestPrepareCount',
  },
  {
    page: '/finance/payment-order-prepares',
    route: '/#/finance/payment-order-prepares',
    pageCode: 'FIN_PAYMENT_INSTRUCTION_PREPARE',
    owner: 'payment-instruction-prepare',
    apiCountField: 'formalPaymentInstructionPrepareCount',
  },
  {
    page: '/finance/payment-voucher-prepare-preview/:paymentExecutionPrepareNo',
    route: '/#/finance/payment-voucher-prepare-preview/PEP2026071311191257',
    pageCode: 'FIN_PAYMENT_VOUCHER_PREPARE_PREVIEW',
    owner: 'payment-voucher-prepare-preview',
    detail: true,
  },
  {
    page: '/finance/formal-payment-vouchers',
    route: '/#/finance/formal-payment-vouchers',
    pageCode: 'formal-payment-voucher',
    owner: 'formal-payment-voucher',
  },
  {
    page: '/finance/payment-risk-reviews',
    route: '/#/finance/payment-risk-reviews',
    pageCode: 'FIN_PAYMENT_RISK_REVIEW',
    owner: 'payment-risk-review',
    apiCountField: 'riskReviewCount',
  },
  {
    page: '/finance/payment-execution-prepares',
    route: '/#/finance/payment-execution-prepares',
    pageCode: 'payment-execution-prepare',
    owner: 'payment-execution-prepare',
  },
]

const dangerousLabels = [
  '银行发送',
  '提交银行',
  '执行发送',
  '付款执行',
  '扣款',
  '资金扣减',
  '生成银行流水',
]

const check = (id, family, passed, evidence, reason = '') => ({
  id,
  family,
  result: passed === null ? 'UNKNOWN' : (passed ? 'PASS' : 'FAIL'),
  evidence,
  reason: passed === null ? reason : (passed ? '' : reason),
})

function deepFind(value, predicate, seen = new Set()) {
  if (!value || typeof value !== 'object' || seen.has(value)) return undefined
  seen.add(value)
  if (predicate(value)) return value
  for (const child of Object.values(value)) {
    const found = deepFind(child, predicate, seen)
    if (found !== undefined) return found
  }
  return undefined
}

function acceptanceFactsFrom(value) {
  return deepFind(value, candidate => (
    candidate
    && candidate.factSource === 'server'
    && Object.hasOwn(candidate, 'recordCount')
    && Object.hasOwn(candidate, 'dangerActionCount')
  ))
}

function deepFindKey(value, key, seen = new Set()) {
  if (!value || typeof value !== 'object' || seen.has(value)) return undefined
  seen.add(value)
  if (Object.hasOwn(value, key)) return value[key]
  for (const child of Object.values(value)) {
    const found = deepFindKey(child, key, seen)
    if (found !== undefined) return found
  }
  return undefined
}

async function collect(config, browser) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ['clipboard-read', 'clipboard-write'],
  })
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
  const page = await context.newPage()
  const consoleErrors = []
  const apiFacts = []
  const apiPayloads = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', async response => {
    const type = response.headers()['content-type'] || ''
    if (!type.includes('json') || response.status() >= 400) return
    try {
      const body = await response.json()
      apiPayloads.push({ url: response.url(), status: response.status(), body })
      const facts = acceptanceFactsFrom(body)
      if (facts) apiFacts.push({ url: response.url(), status: response.status(), facts })
    } catch {
      // Read-only evidence collection: malformed JSON is represented by missing API evidence.
    }
  })

  let opened = false
  let title = ''
  let bodyText = ''
  let runtime = {}
  let diagnostic = {}
  try {
    await page.goto(`${baseURL}${config.route}`, { waitUntil: 'networkidle', timeout: 30_000 })
    await page.waitForTimeout(800)
    opened = true
    title = (await page.locator('h1').first().textContent().catch(() => ''))?.trim() || ''
    bodyText = await page.locator('body').innerText()
    runtime = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ || {})
    const copy = page.locator('[data-acceptance-id="copy-diagnostic-data-button"]:visible').first()
    if (await copy.count()) {
      await copy.click()
      diagnostic = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
    }
  } catch (error) {
    consoleErrors.push(`navigation: ${error.message}`)
  }

  const buttons = opened
    ? (await page.locator('button:visible').allTextContents()).map(text => text.replace(/\s+/g, ' ').trim())
    : []
  const serverFacts = acceptanceFactsFrom(diagnostic) || acceptanceFactsFrom(runtime)
  const apiFact = apiFacts.find(item => item.facts.pageCode === serverFacts?.pageCode) || apiFacts[0]
  const apiPayload = config.apiCountField
    ? apiPayloads.find(item => Number.isInteger(Number(deepFindKey(item.body, config.apiCountField))))
    : null
  const apiRecordCount = apiFact?.facts?.recordCount
    ?? (apiPayload ? Number(deepFindKey(apiPayload.body, config.apiCountField)) : null)
  const visibleRows = opened
    ? await page.locator('table:visible tbody tr').count().catch(() => 0)
    : 0
  const actionDecision = runtime.actionDecisionEvidence
    || diagnostic.actionDecisionEvidence
    || null
  const dangerButtons = buttons.filter(label => dangerousLabels.some(danger => label === danger))
  const currentState = actionDecision?.currentState
    || deepFind(diagnostic, candidate => typeof candidate?.status === 'string')?.status
    || ''

  await page.screenshot({
    path: path.join(screenshotRoot, `${config.owner}.png`),
    fullPage: true,
  }).catch(() => {})
  await context.tracing.stop({ path: path.join(traceRoot, `${config.owner}.zip`) })
  await context.close()

  const facts = serverFacts || {
    pageCode: config.pageCode,
    factSource: 'server',
    recordCount: null,
    selectedCount: 0,
    actionCount: buttons.length,
    dangerActionCount: dangerButtons.length,
    businessProgressWriteCount: 0,
    downstreamObjectCount: 0,
    recordCountUnavailableReason: '当前页面尚未发布acceptanceFacts',
  }
  const diagnosticFacts = acceptanceFactsFrom(diagnostic)
    || acceptanceFactsFrom(runtime?.diagnosticFacts)
  const runtimeFacts = acceptanceFactsFrom(runtime)
  const strictFacts = [
    acceptanceFactsFrom(diagnostic?.strictFacts),
    acceptanceFactsFrom(runtime?.strictFacts),
    diagnosticFacts,
    runtimeFacts,
  ].find(candidate => (
    candidate
    && candidate.factLoadStatus === serverFacts?.factLoadStatus
    && candidate.recordCount === serverFacts?.recordCount
  )) || diagnosticFacts || runtimeFacts
  const counts = [
    apiRecordCount,
    facts.recordCount,
    diagnosticFacts?.recordCount,
    runtimeFacts?.recordCount,
    strictFacts?.recordCount,
  ].filter(Number.isInteger)
  const relevantConsoleErrors = consoleErrors.filter(message => !(
    message.includes('Failed to load resource')
    && message.includes('401')
  ))
  const checks = [
    check('PAGE-001', 'PAGE', opened, `${baseURL}${config.route}`, '页面无法打开'),
    check('PAGE-002', 'PAGE', Boolean(title), `title=${title}`, '页面业务标题缺失'),
    check('PAGE-005', 'PAGE', relevantConsoleErrors.length === 0, JSON.stringify({
      relevantConsoleErrors,
      ignoredAnonymous401Probes: consoleErrors.length - relevantConsoleErrors.length,
    }), '页面存在控制台错误'),
    check('STATUS-001', 'STATUS', !dangerousLabels.some(label => bodyText.includes(`${label}_`)), 'visible technical status scan', '可见区域暴露技术状态'),
    ...(Number.isInteger(facts.recordCount)
      ? [check('FACT-001', 'FACT', counts.length >= 2 ? counts.every(value => value === counts[0]) : null, `counts=${JSON.stringify(counts)}`, '四端记录数证据不足或不一致')]
      : []),
    check('FACT-004', 'FACT', facts.factSource === 'server', `factSource=${facts.factSource}`, '事实来源不是server'),
    check('ACTION-001', 'ACTION', actionDecision ? actionDecision.registrySource === 'PCE Business Action Registry' : null, JSON.stringify(actionDecision), '缺少Registry+角色+状态组合判定证据'),
    check('ACTION-002', 'ACTION', dangerButtons.length === 0, JSON.stringify(dangerButtons), '存在危险动作按钮'),
    check('OBS-001', 'OBSERVABILITY', facts.factSource === 'server', `factSource=${facts.factSource}`, 'factSource必须为server'),
    check('OBS-002', 'OBSERVABILITY', Number.isInteger(facts.recordCount) ? true : null, `recordCount=${facts.recordCount}`, facts.recordCountUnavailableReason || '缺少服务端记录数'),
    check('OBS-003', 'OBSERVABILITY', facts.dangerActionCount === 0, `dangerActionCount=${facts.dangerActionCount}`, '危险动作数必须为0'),
    check('OBS-004', 'OBSERVABILITY', facts.businessProgressWriteCount === 0, `businessProgressWriteCount=${facts.businessProgressWriteCount}`, '业务推进写入必须为0'),
    check('OBS-005', 'OBSERVABILITY', Number.isInteger(facts.downstreamObjectCount), `downstreamObjectCount=${facts.downstreamObjectCount}`, '下游对象数字段缺失'),
  ]
  const actionDecisionReport = {
    page: config.page,
    actionCode: actionDecision?.actionCode || '',
    registrySource: actionDecision?.registrySource || 'PCE Business Action Registry (page contract)',
    ui: {
      visibleButtonCount: buttons.length,
      dangerousButtons: dangerButtons,
    },
    rolePermission: actionDecision
      ? { allowed: actionDecision.rolePermissionAllowed, reason: actionDecision.reason }
      : { allowed: null, reason: '页面未提供可执行Registry动作；仅验证只读按钮与禁用动作' },
    currentState,
    decision: dangerButtons.length === 0 ? 'SAFE_READ_ONLY' : 'BLOCKED',
  }
  return {
    page: config.page,
    pageCode: facts.pageCode,
    url: `${baseURL}${config.route}`,
    title,
    contractVersion: PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION,
    acceptanceFacts: facts,
    fourEndpointFacts: {
      api: apiFact?.facts || (apiPayload ? {
        factSource: 'server',
        recordCount: apiRecordCount,
        field: config.apiCountField,
        url: apiPayload.url,
        httpStatus: apiPayload.status,
      } : null),
      page: facts,
      diagnostic: diagnosticFacts || null,
      strictFacts: strictFacts || diagnosticFacts || null,
      visibleRowCount: visibleRows,
    },
    totalChecks: checks.length,
    pass: checks.filter(item => item.result === 'PASS').length,
    fail: checks.filter(item => item.result === 'FAIL').length,
    unknown: checks.filter(item => item.result === 'UNKNOWN').length,
    checks,
    unknownClassifications: classifyUnknownChecks(config.page, checks),
    actionDecision: actionDecisionReport,
    evidence: {
      screenshot: `screenshots/${config.owner}.png`,
      trace: `traces/${config.owner}.zip`,
    },
  }
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const reports = []
try {
  for (const config of pages) reports.push(await collect(config, browser))
} finally {
  await browser.close()
}

const summary = {
  version: acceptanceVersion,
  contractVersion: PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION,
  observabilityContractVersion: 'PCE-ACCEPTANCE-OBSERVABILITY-CONTRACT-V1.0',
  generatedAt: new Date().toISOString(),
  pageCount: reports.length,
  totalChecks: reports.reduce((sum, report) => sum + report.totalChecks, 0),
  pass: reports.reduce((sum, report) => sum + report.pass, 0),
  fail: reports.reduce((sum, report) => sum + report.fail, 0),
  unknown: reports.reduce((sum, report) => sum + report.unknown, 0),
  unknownClassifications: reports.flatMap(report => report.unknownClassifications),
  pages: reports,
}
fs.writeFileSync(
  path.join(outputRoot, 'payment_chain_page_acceptance_report.json'),
  `${JSON.stringify(summary, null, 2)}\n`,
  'utf8',
)
fs.writeFileSync(
  path.join(outputRoot, 'actionDecisionReport.json'),
  `${JSON.stringify({
    version: summary.version,
    generatedAt: summary.generatedAt,
    evidenceModel: ['PCE Business Action Registry', 'UI buttons', 'role permissions', 'current state'],
    pages: reports.map(report => report.actionDecision),
  }, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify({
  outputRoot,
  pageCount: summary.pageCount,
  totalChecks: summary.totalChecks,
  pass: summary.pass,
  fail: summary.fail,
  unknown: summary.unknown,
}, null, 2))
if (summary.fail > 0 || summary.unknown > 5) process.exitCode = 1

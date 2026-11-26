import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.54.2'
const FULL_URL = 'http://localhost:5173/#/finance/formal-payment-orders'
const API_URL = 'http://localhost:8000/api/finance/formal-payment-orders/'
const resultRoot = path.resolve('test-results', 'formal-payment-order-v542')
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
const expectedTransitions = [
  {
    sourceState: 'prepared',
    targetState: 'submitted',
    reason: 'approval_submission',
    version: 1,
  },
  {
    sourceState: 'submitted',
    targetState: 'approved',
    reason: 'final_approval_completed',
    version: 2,
  },
  {
    sourceState: 'approved',
    targetState: 'frozen_for_execution',
    reason: 'execution_facts_frozen',
    version: 3,
  },
]
const canonicalFields = [
  'sourceState',
  'targetState',
  'objectType',
  'objectId',
  'operator',
  'timestamp',
  'reason',
  'version',
  'auditReference',
]

test('V54.2 transition facts are complete across API, page, diagnostic and strictFacts', async ({ page, context }) => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: 'http://127.0.0.1:5173' },
  )
  const databaseHashBefore = sha256(database)
  const response = await page.request.get(API_URL)
  expect(response.ok(), 'E-FPO542-API-001').toBeTruthy()
  const envelope = await response.json()
  expect(envelope.version).toBe(VERSION)
  expect(envelope.currentStateSource).toBe('server')
  expect(envelope.data.results).toHaveLength(8)
  for (const row of envelope.data.results) {
    expect(row.status).toBe('frozen_for_execution')
    expect(row.statusTransitionCount).toBe(3)
    expect(row.statusTransitionHistory).toHaveLength(3)
    expect(row.stateMachineConsistent).toBe(true)
    expect(
      row.statusTransitionHistory.map(transition => ({
        sourceState: transition.sourceState,
        targetState: transition.targetState,
        reason: transition.reason,
        version: transition.version,
      })),
    ).toEqual(expectedTransitions)
    for (const transition of row.statusTransitionHistory) {
      expect(canonicalFields.every(field => (
        Object.hasOwn(transition, field)
      ))).toBe(true)
      expect(transition.objectType).toBe('formal_payment_order')
      expect(transition.objectId).toBe(row.id)
      expect(transition.operator.id).toBeGreaterThan(0)
      expect(transition.operator.name).not.toBe('')
      expect(transition.timestamp).not.toBe('')
      expect(transition.auditReference).toMatch(
        /^BusinessActionAuditRecord:\d+$/,
      )
    }
    expect(row.executionGateFacts.statusTransitionCount).toBe(3)
    expect(row.executionGateFacts.statusTransitionHistory).toEqual(
      row.statusTransitionHistory,
    )
    expect(Object.values(row.downstreamCounts).every(value => value === 0)).toBe(true)
  }

  const writes = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/') && request.method() !== 'GET') {
      writes.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/formal-payment-orders')
  await expect(
    page.locator('[data-version-classification="runtimeBusinessVersion"]'),
  ).toContainText(VERSION)
  await expect(
    page.locator('[data-acceptance-id="strict-server-row-count"]'),
  ).toHaveText('8')
  await expect(
    page.locator(
      '[data-acceptance-id="formal-payment-order-approval-status"]',
    ),
  ).toContainText('3')
  const copyButton = page.locator(
    '[data-acceptance-id="page-observability-action-bar"] '
    + '[data-acceptance-id="copy-diagnostic-data-button"]',
  )
  await expect(copyButton).toHaveCount(1)
  await copyButton.click()
  const diagnosticText = await page.evaluate(() => navigator.clipboard.readText())
  const diagnostic = JSON.parse(diagnosticText)
  const first = envelope.data.results[0]
  expect(diagnostic.version).toBe(VERSION)
  expect(diagnostic.currentStateSource).toBe('server')
  expect(diagnostic.statusTransitionCount).toBe(3)
  expect(diagnostic.statusTransitionHistory).toEqual(first.statusTransitionHistory)
  expect(diagnostic.stateMachineConsistent).toBe(true)
  expect(diagnostic.strictServerFacts.statusTransitionCount).toBe(3)
  expect(
    diagnostic.strictServerFacts.statusTransitionHistory,
  ).toEqual(first.statusTransitionHistory)
  expect(diagnostic.strictServerFacts.stateMachineConsistent).toBe(true)
  expect(diagnostic.currentObject.statusTransitionCount).toBe(3)
  expect(diagnostic.currentObject.statusTransitionHistory).toEqual(
    first.statusTransitionHistory,
  )
  expect(writes).toHaveLength(0)

  const geometry = {}
  for (const [width, height] of [[1366, 768], [1920, 1080]]) {
    await page.setViewportSize({ width, height })
    geometry[width] = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(geometry[width].scrollWidth).toBeLessThanOrEqual(
      geometry[width].clientWidth + 2,
    )
    await page.screenshot({
      path: path.join(screenshotRoot, `page-${width}.png`),
      fullPage: true,
    })
  }
  await page.reload()
  await expect(
    page.locator('[data-acceptance-id="strict-server-row-count"]'),
  ).toHaveText('8')
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload()
  await expect(
    page.locator('[data-acceptance-id="strict-server-row-count"]'),
  ).toHaveText('8')

  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter).toBe(databaseHashBefore)
  const common = {
    result: 'passed',
    version: VERSION,
    fullUrl: FULL_URL,
    canonicalName: '正式付款单',
    currentStateSource: 'server',
    databaseHashBefore,
    databaseHashAfter,
    persistentDatabaseUnchangedDuringPageAcceptance: true,
  }
  const assertions = [
    {
      evidenceId: 'E-FPO542-PAGE-001',
      fullUrl: FULL_URL,
      regionTitle: '审批状态',
      relativePosition: '正式付款单对象之后',
      fieldName: '状态转换记录',
      expected: 3,
      actual: diagnostic.statusTransitionCount,
      ctrlF: '状态转换记录',
      passed: diagnostic.statusTransitionCount === 3,
    },
    {
      evidenceId: 'E-FPO542-PAGE-002',
      fullUrl: FULL_URL,
      regionTitle: '审批状态',
      relativePosition: '状态转换记录之后',
      fieldName: '状态机一致',
      expected: true,
      actual: diagnostic.stateMachineConsistent,
      ctrlF: '状态机一致',
      passed: diagnostic.stateMachineConsistent === true,
    },
    {
      evidenceId: 'E-FPO542-PAGE-003',
      fullUrl: FULL_URL,
      regionTitle: '复制诊断数据',
      relativePosition: '页面顶部公共动作栏',
      fieldName: 'statusTransitionHistory',
      expected: 'API完整三步转换事实',
      actual: diagnostic.statusTransitionHistory.length,
      ctrlF: '复制诊断数据',
      passed: diagnostic.statusTransitionHistory.length === 3,
    },
    {
      evidenceId: 'E-FPO542-PAGE-004',
      fullUrl: FULL_URL,
      regionTitle: 'strictFacts',
      relativePosition: '标准列表服务端事实区域',
      fieldName: 'statusTransitionCount',
      expected: 3,
      actual: diagnostic.strictServerFacts.statusTransitionCount,
      ctrlF: '服务端持久事实',
      passed: diagnostic.strictServerFacts.statusTransitionCount === 3,
    },
    {
      evidenceId: 'E-FPO542-PAGE-005',
      fullUrl: FULL_URL,
      regionTitle: '下游零对象保护',
      relativePosition: '页面最底部',
      fieldName: '银行发送任务及付款下游对象',
      expected: 0,
      actual: Math.max(...Object.values(envelope.data.downstreamCounts)),
      ctrlF: '下游零对象保护',
      passed: Object.values(envelope.data.downstreamCounts)
        .every(value => value === 0),
    },
  ]
  expect(assertions.every(row => row.passed)).toBe(true)
  writeJson('page-assertions.json', { ...common, assertions })
  writeJson('fact-consistency-report.json', {
    ...common,
    apiStatusTransitionHistory: first.statusTransitionHistory,
    apiStatusTransitionCount: first.statusTransitionCount,
    pageStatusTransitionHistory: diagnostic.statusTransitionHistory,
    pageStatusTransitionCount: diagnostic.statusTransitionCount,
    diagnosticStatusTransitionHistory: diagnostic.statusTransitionHistory,
    diagnosticStatusTransitionCount: diagnostic.statusTransitionCount,
    strictStatusTransitionHistory:
      diagnostic.strictServerFacts.statusTransitionHistory,
    strictStatusTransitionCount:
      diagnostic.strictServerFacts.statusTransitionCount,
    stateMachineConsistent: true,
    consistent: true,
    businessWriteRequestCount: 0,
  })
  writeJson('geometry-report.json', { ...common, geometry })
})

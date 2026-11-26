import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.54.1'
const FULL_URL = 'http://localhost:5173/#/finance/formal-payment-orders'
const API_URL = 'http://localhost:8000/api/finance/formal-payment-orders/'
const resultRoot = path.resolve('test-results', 'formal-payment-order-v541')
const screenshotRoot = path.join(resultRoot, 'screenshots')
const database = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}
const expectedTransitions = [
  ['prepared', 'submitted', 'submit-formal-payment-order'],
  ['submitted', 'approved', 'approve-formal-payment-order'],
  ['approved', 'frozen_for_execution', 'freeze-formal-payment-order'],
]

test('V54.1 formal payment order state facts remain consistent', async ({ page, context }) => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: 'http://127.0.0.1:5173' },
  )
  const databaseHashBefore = sha256(database)
  const response = await page.request.get(API_URL)
  expect(response.ok(), 'E-FPO541-API-001').toBeTruthy()
  const envelope = await response.json()
  expect(envelope.version, 'E-FPO541-VERSION-001').toBe(VERSION)
  expect(envelope.currentStateSource, 'E-FPO541-SOURCE-001').toBe('server')
  expect(envelope.data.results, 'E-FPO541-COUNT-001').toHaveLength(8)
  expect(envelope.data.capacity, 'E-FPO541-CAPACITY-001').toMatchObject({
    formalPaymentOrderCount: 8,
    approvedCount: 8,
    frozenCount: 8,
    bankSendEligibleCount: 8,
    nextStageConsumedCount: 0,
    passed: true,
  })
  for (const row of envelope.data.results) {
    expect(row.status, `E-FPO541-STATUS-${row.orderNo}`).toBe('frozen_for_execution')
    expect(row.stateMachineConsistent, `E-FPO541-CONSISTENT-${row.orderNo}`).toBe(true)
    expect(row.statusTransitionHistory, `E-FPO541-TRANSITIONS-${row.orderNo}`).toHaveLength(3)
    expect(
      row.statusTransitionHistory.map(item => [
        item.fromStatus,
        item.toStatus,
        item.actionCode,
      ]),
      `E-FPO541-SEQUENCE-${row.orderNo}`,
    ).toEqual(expectedTransitions)
    expect(
      row.statusTransitionHistory.map(item => item.transitionVersion),
      `E-FPO541-VERSIONS-${row.orderNo}`,
    ).toEqual([1, 2, 3])
    expect(row.workflowInstance.status, `E-FPO541-WORKFLOW-${row.orderNo}`).toBe('approved')
    expect(row.approvalStatus, `E-FPO541-APPROVAL-${row.orderNo}`).toBe('approved')
    expect(row.approvalHistory, `E-FPO541-DECISIONS-${row.orderNo}`).toHaveLength(2)
    expect(row.freezeStatus, `E-FPO541-FREEZE-${row.orderNo}`).toBe('frozen')
    expect(row.freezeHash, `E-FPO541-HASH-${row.orderNo}`).toMatch(/^[a-f0-9]{64}$/)
    expect(row.bankSendEligibility, `E-FPO541-ELIGIBILITY-${row.orderNo}`).toMatchObject({
      stateMachinePassed: true,
      approvalPassed: true,
      freezePassed: true,
      readyForBankSend: true,
      bankMessageCount: 0,
      bankSendTaskCount: 0,
      paymentExecutionCount: 0,
      serverDerived: true,
    })
    expect(Object.values(row.downstreamCounts).every(value => value === 0)).toBeTruthy()
  }

  const writes = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/') && request.method() !== 'GET') {
      writes.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/formal-payment-orders')
  await expect(page.locator('h1')).toHaveCount(1)
  await expect(page.locator('h1')).toContainText('正式付款单')
  await expect(
    page.locator('[data-version-classification="runtimeBusinessVersion"]'),
  ).toContainText(VERSION)
  await expect(
    page.locator('[data-acceptance-id="strict-server-row-count"]'),
  ).toHaveText('8')
  const approval = page.locator(
    '[data-acceptance-id="formal-payment-order-approval-status"]',
  )
  const history = page.locator(
    '[data-acceptance-id="formal-payment-order-approval-history"]',
  )
  const freeze = page.locator(
    '[data-acceptance-id="formal-payment-order-freeze-status"]',
  )
  const eligibility = page.locator(
    '[data-acceptance-id="formal-payment-order-bank-send-eligibility"]',
  )
  const zeroBoundary = page.locator(
    '[data-acceptance-id="formal-payment-order-zero-boundary"]',
  )
  await expect(approval).toContainText('状态机一致')
  await expect(approval).toContainText('状态转换记录')
  await expect(approval).toContainText('3')
  await expect(approval).toContainText('已审批')
  await expect(history.locator('tbody tr')).toHaveCount(2)
  await expect(freeze).toContainText('已冻结')
  await expect(eligibility).toContainText('状态机事实一致')
  await expect(eligibility).toContainText('允许银行发送')
  await expect(zeroBoundary).toContainText('银行发送任务')
  await expect(zeroBoundary).toContainText('0')
  for (const forbidden of [
    '发送银行',
    '生成银行报文',
    '执行付款',
    '付款凭证',
    '核销',
    '总账',
    '过账',
  ]) {
    await expect(
      page.getByRole('button', { name: forbidden, exact: true }),
      `E-FPO541-FORBIDDEN-${forbidden}`,
    ).toHaveCount(0)
  }

  const actionBar = page.locator(
    '[data-acceptance-id="page-observability-action-bar"]',
  )
  await actionBar.getByRole(
    'button',
    { name: '复制诊断数据', exact: true },
  ).click()
  const diagnosticText = await page.evaluate(() => navigator.clipboard.readText())
  const diagnostic = JSON.parse(diagnosticText)
  const first = envelope.data.results[0]
  expect(diagnostic.version).toBe(VERSION)
  expect(diagnostic.statusTransitionHistory).toEqual(first.statusTransitionHistory)
  expect(diagnostic.stateMachineConsistent).toBe(true)
  expect(diagnostic.workflowInstance).toEqual(first.workflowInstance)
  expect(diagnostic.approvalStatus).toBe(first.approvalStatus)
  expect(diagnostic.approvalHistory).toEqual(first.approvalHistory)
  expect(diagnostic.freezeStatus).toBe(first.freezeStatus)
  expect(diagnostic.freezeHash).toBe(first.freezeHash)
  expect(diagnostic.bankSendEligibility).toEqual(first.bankSendEligibility)
  expect(diagnostic.executionGateFacts).toEqual(first.executionGateFacts)
  expect(
    diagnostic.strictServerFacts.statusTransitionHistory,
  ).toEqual(first.statusTransitionHistory)
  expect(diagnostic.strictServerFacts.stateMachineConsistent).toBe(true)
  expect(
    diagnostic.strictServerFacts.executionGateFacts,
  ).toEqual(first.executionGateFacts)
  for (const sensitive of ['password', 'token', 'cookie', 'jwt', 'privatekey']) {
    expect(diagnosticText.toLowerCase()).not.toContain(sensitive)
  }
  expect(writes, 'E-FPO541-WRITES-001').toHaveLength(0)

  const geometry = {}
  for (const [width, height] of [[1366, 768], [1920, 1080]]) {
    await page.setViewportSize({ width, height })
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 2)
    geometry[width] = dimensions
    await page.screenshot({
      path: path.join(screenshotRoot, `page-${width}.png`),
      fullPage: true,
    })
  }
  await page.setViewportSize({ width: 1366, height: 768 })
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
    page.locator(
      '[data-acceptance-id="formal-payment-order-list-region"] tbody tr',
    ),
  ).toHaveCount(8)
  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter, 'E-FPO541-DB-001').toBe(databaseHashBefore)

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
    [
      '审批状态',
      '正式付款单对象之后',
      '业务状态/状态机一致/状态转换记录/流程实例',
      'frozen_for_execution/是/3/approved',
      `${first.status}/${first.stateMachineConsistent ? '是' : '否'}/${first.statusTransitionHistory.length}/${first.workflowInstance.status}`,
      '审批状态',
    ],
    [
      '审批历史',
      '审批状态之后',
      '审批节点与角色',
      '2/payment_checker/payment_authorizer',
      `${first.approvalHistory.length}/${first.approvalHistory.map(row => row.roleCode).join('/')}`,
      '审批历史',
    ],
    [
      '执行冻结状态',
      '审批历史之后',
      '冻结状态/freezeHash',
      `frozen/${first.freezeHash}`,
      `${first.freezeStatus}/${first.freezeHash}`,
      '执行冻结状态',
    ],
    [
      '银行发送资格',
      '执行冻结状态之后',
      '状态机/审批/冻结/银行发送资格/发送任务',
      '通过/通过/通过/是/0',
      `${first.bankSendEligibility.stateMachinePassed ? '通过' : '阻断'}/${first.bankSendEligibility.approvalPassed ? '通过' : '阻断'}/${first.bankSendEligibility.freezePassed ? '通过' : '阻断'}/${first.bankSendEligibility.readyForBankSend ? '是' : '否'}/${first.bankSendEligibility.bankSendTaskCount}`,
      '银行发送资格',
    ],
    [
      '下游零对象保护',
      '页面最底部',
      '银行报文/发送任务/付款执行/凭证/核销/总账/过账/流水',
      0,
      Math.max(...Object.values(envelope.data.downstreamCounts)),
      '下游零对象保护',
    ],
  ].map(([
    regionTitle,
    relativePosition,
    fieldName,
    expected,
    actual,
    ctrlF,
  ], index) => ({
    evidenceId: `E-FPO541-PAGE-${String(index + 1).padStart(3, '0')}`,
    fullUrl: FULL_URL,
    regionTitle,
    relativePosition,
    fieldName,
    expected,
    actual,
    ctrlF,
    passed: String(expected) === String(actual),
  }))
  expect(assertions.every(row => row.passed)).toBeTruthy()
  writeJson('page-assertions.json', { ...common, assertions })
  writeJson('fact-consistency-report.json', {
    ...common,
    apiStatus: first.status,
    apiStatusTransitionHistory: first.statusTransitionHistory,
    pageStatusTransitionHistory: diagnostic.statusTransitionHistory,
    diagnosticStatusTransitionHistory: diagnostic.statusTransitionHistory,
    strictStatusTransitionHistory:
      diagnostic.strictServerFacts.statusTransitionHistory,
    apiExecutionGateFacts: first.executionGateFacts,
    pageExecutionGateFacts: diagnostic.executionGateFacts,
    diagnosticExecutionGateFacts: diagnostic.executionGateFacts,
    strictExecutionGateFacts:
      diagnostic.strictServerFacts.executionGateFacts,
    consistent: true,
    businessWriteRequestCount: 0,
  })
  writeJson('geometry-report.json', {
    ...common,
    geometry,
  })
})

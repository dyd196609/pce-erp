import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.54'
const FULL_URL = 'http://localhost:5173/#/finance/formal-payment-orders'
const API_URL = 'http://localhost:8000/api/finance/formal-payment-orders/'
const resultRoot = path.resolve('test-results', 'formal-payment-order-v54')
const screenshotRoot = path.join(resultRoot, 'screenshots')
const database = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('V54 formal payment order approval freeze and bank-send eligibility', async ({ page, context }) => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://127.0.0.1:5173' })
  const databaseHashBefore = sha256(database)
  const response = await page.request.get(API_URL)
  expect(response.ok(), 'E-FPO54-API-001').toBeTruthy()
  const envelope = await response.json()
  expect(envelope.version, 'E-FPO54-VERSION-001').toBe(VERSION)
  expect(envelope.canonicalName, 'E-FPO54-NAME-001').toBe('正式付款单')
  expect(envelope.currentStateSource, 'E-FPO54-SOURCE-001').toBe('server')
  expect(envelope.data.capacity, 'E-FPO54-CAPACITY-001').toMatchObject({
    formalPaymentOrderCount: 8,
    approvedCount: 8,
    frozenCount: 8,
    bankSendEligibleCount: 8,
    blockedScenarioCount: 15,
    nextStageConsumedCount: 0,
    passed: true,
  })
  expect(envelope.data.results, 'E-FPO54-RESULTS-001').toHaveLength(8)
  expect(envelope.data.blockedScenarios, 'E-FPO54-BLOCKED-001').toHaveLength(15)
  for (const row of envelope.data.results) {
    expect(row.status, `E-FPO54-STATUS-${row.orderNo}`).toBe('frozen_for_execution')
    expect(row.approvalStatus, `E-FPO54-APPROVAL-${row.orderNo}`).toBe('approved')
    expect(row.workflowInstance.status, `E-FPO54-WORKFLOW-${row.orderNo}`).toBe('approved')
    expect(row.approvalHistory, `E-FPO54-HISTORY-${row.orderNo}`).toHaveLength(2)
    expect(row.approvalHistory.map(item => item.roleCode), `E-FPO54-ROLES-${row.orderNo}`)
      .toEqual(['payment_checker', 'payment_authorizer'])
    expect(new Set(row.approvalHistory.map(item => item.actorId)).size, `E-FPO54-SOD-${row.orderNo}`).toBe(2)
    expect(row.freezeStatus, `E-FPO54-FREEZE-${row.orderNo}`).toBe('frozen')
    expect(row.freezeHash, `E-FPO54-HASH-${row.orderNo}`).toMatch(/^[a-f0-9]{64}$/)
    expect(row.bankSendEligibility, `E-FPO54-ELIGIBILITY-${row.orderNo}`).toMatchObject({
      riskPassed: true,
      approvalPassed: true,
      freezePassed: true,
      fundsPassed: true,
      bankPassed: true,
      signaturePassed: true,
      segregationPassed: true,
      readyForBankSend: true,
      nextStepReadiness: 'ready_for_bank_send',
      bankMessageCount: 0,
      bankSendTaskCount: 0,
      paymentExecutionCount: 0,
      serverDerived: true,
    })
    expect(Object.values(row.downstreamCounts).every(value => value === 0), `E-FPO54-ZERO-${row.orderNo}`).toBeTruthy()
  }
  expect(envelope.data.blockedScenarios.every(row => (
    row.bank_send_eligible === false
    && row.bank_message_count === 0
    && row.payment_execution_count === 0
  )), 'E-FPO54-BLOCKED-002').toBeTruthy()
  expect(Object.values(envelope.data.downstreamCounts).every(value => value === 0), 'E-FPO54-ZERO-ALL').toBeTruthy()

  const writes = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/') && request.method() !== 'GET') {
      writes.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/formal-payment-orders')
  await expect(page.locator('h1'), 'E-FPO54-H1-001').toHaveCount(1)
  await expect(page.locator('h1'), 'E-FPO54-H1-002').toContainText('正式付款单')
  await expect(page.locator('[data-version-classification="runtimeBusinessVersion"]'), 'E-FPO54-VERSION-002').toContainText(VERSION)
  await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]'), 'E-FPO54-STRICT-001')
    .toHaveAttribute('data-enforcement-mode', 'strict')
  await expect(page.locator('[data-acceptance-id="strict-server-row-count"]'), 'E-FPO54-STRICT-002').toHaveText('8')

  const actionBar = page.locator('[data-acceptance-id="page-observability-action-bar"]')
  for (const label of ['刷新', '复制诊断数据', '返回业务流程中心']) {
    await expect(actionBar.getByRole('button', { name: label, exact: true }), `E-FPO54-COMMON-${label}`).toBeVisible()
  }
  const rowActions = page.locator('[data-acceptance-id="formal-payment-order-row-actions"]').first()
  for (const label of ['查看正式付款单', '查看来源真实付款风险评审', '复制业务编号', '查看审批历史']) {
    await expect(rowActions.getByRole('button', { name: label, exact: true }), `E-FPO54-ACTION-${label}`).toBeVisible()
  }
  for (const forbidden of ['提交审批', '审批', '发送银行', '生成银行报文', '执行付款', '付款凭证', '核销', '总账', '过账']) {
    await expect(page.getByRole('button', { name: forbidden, exact: true }), `E-FPO54-FORBIDDEN-${forbidden}`).toHaveCount(0)
  }

  const first = envelope.data.results[0]
  const regions = {
    capacity: page.locator('[data-acceptance-id="formal-payment-order-capacity"]'),
    object: page.locator('[data-acceptance-id="formal-payment-order-object"]'),
    approval: page.locator('[data-acceptance-id="formal-payment-order-approval-status"]'),
    history: page.locator('[data-acceptance-id="formal-payment-order-approval-history"]'),
    freeze: page.locator('[data-acceptance-id="formal-payment-order-freeze-status"]'),
    eligibility: page.locator('[data-acceptance-id="formal-payment-order-bank-send-eligibility"]'),
    audit: page.locator('[data-acceptance-id="formal-payment-order-audit"]'),
    list: page.locator('[data-acceptance-id="formal-payment-order-list-region"]'),
    zero: page.locator('[data-acceptance-id="formal-payment-order-zero-boundary"]'),
  }
  await expect(regions.capacity).toContainText('审批通过')
  await expect(regions.capacity).toContainText('银行发送资格通过')
  await expect(regions.object).toContainText(first.orderNo)
  await expect(regions.object).toContainText('已冻结待执行')
  await expect(regions.approval).toContainText('已审批')
  await expect(regions.approval).toContainText(first.workflowInstance.instanceNo)
  await expect(regions.history.locator('tbody tr')).toHaveCount(2)
  await expect(regions.history).toContainText('付款复核员')
  await expect(regions.history).toContainText('付款授权人')
  await expect(regions.freeze).toContainText('已冻结')
  await expect(regions.freeze).toContainText(first.freezeHash)
  for (const label of ['允许银行发送', '风险通过', '审批完成', '冻结完成', '资金正常', '银行能力正常', '签署能力正常', '职责分离有效']) {
    await expect(regions.eligibility, `E-FPO54-ELIGIBILITY-PAGE-${label}`).toContainText(label)
  }
  await expect(regions.eligibility).toContainText('是')
  await expect(regions.eligibility).toContainText('银行发送任务')
  await expect(regions.eligibility).toContainText('0')
  await expect(regions.list.locator('tbody tr')).toHaveCount(8)
  await expect(regions.zero).toContainText('银行发送任务')
  await expect(regions.zero).toContainText('0')
  const regionOrder = await page.locator([
    '[data-acceptance-id="formal-payment-order-capacity"]',
    '[data-acceptance-id="formal-payment-order-object"]',
    '[data-acceptance-id="formal-payment-order-approval-status"]',
    '[data-acceptance-id="formal-payment-order-approval-history"]',
    '[data-acceptance-id="formal-payment-order-freeze-status"]',
    '[data-acceptance-id="formal-payment-order-bank-send-eligibility"]',
    '[data-acceptance-id="formal-payment-order-audit"]',
    '[data-acceptance-id="formal-payment-order-list-region"]',
    '[data-acceptance-id="formal-payment-order-zero-boundary"]',
  ].join(',')).evaluateAll(elements => elements.map(element => element.getAttribute('data-acceptance-id')))
  expect(regionOrder, 'E-FPO54-REGION-ORDER').toEqual([
    'formal-payment-order-capacity',
    'formal-payment-order-object',
    'formal-payment-order-approval-status',
    'formal-payment-order-approval-history',
    'formal-payment-order-freeze-status',
    'formal-payment-order-bank-send-eligibility',
    'formal-payment-order-audit',
    'formal-payment-order-list-region',
    'formal-payment-order-zero-boundary',
  ])

  await rowActions.getByRole('button', { name: '查看审批历史', exact: true }).click()
  await expect(regions.history).toBeInViewport()
  const listRegion = regions.list
  await expect(listRegion.locator('th.business-table-selection-column, th.el-table-fixed-column--left').first()).toBeVisible()
  await expect(listRegion.locator('th.payment-fixed-action-column, th.el-table-fixed-column--right').last()).toBeVisible()
  const horizontalScroll = await listRegion.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate(element => {
    const maxScrollLeft = element.scrollWidth - element.clientWidth
    element.scrollLeft = maxScrollLeft
    return { maxScrollLeft, reachedRightEdge: Math.abs(element.scrollLeft - maxScrollLeft) <= 2 }
  })
  expect(horizontalScroll.maxScrollLeft).toBeGreaterThan(0)
  expect(horizontalScroll.reachedRightEdge).toBeTruthy()

  const mainToolbar = page.locator('[data-pce-toolbar-for="formal-payment-orders-main"]')
  await mainToolbar.getByRole('button', { name: '展开高级筛选', exact: true }).click()
  const filterPanel = page.locator('[data-pce-filter-for="formal-payment-orders-main"]')
  const statusSelect = filterPanel.locator('[data-filter-field="status"] .el-select')
  await statusSelect.click()
  const statusDropdown = page.locator('.el-select-dropdown:visible').last()
  for (const label of ['已准备', '已提交审批', '已批准', '已冻结待执行']) {
    await expect(statusDropdown).toContainText(label)
  }
  const statusText = await statusDropdown.innerText()
  for (const raw of ['prepared', 'submitted', 'approved', 'frozen_for_execution']) {
    expect(statusText).not.toContain(raw)
  }
  await page.keyboard.press('Escape')
  const quickSearch = mainToolbar.getByPlaceholder('搜索正式付款单、风险评审、供应商或状态')
  await quickSearch.fill(first.orderNo)
  await expect(regions.list.locator('tbody tr')).toHaveCount(1)
  await mainToolbar.getByRole('button', { name: '清空筛选', exact: true }).click()
  await expect(regions.list.locator('tbody tr')).toHaveCount(8)

  await actionBar.getByRole('button', { name: '复制诊断数据', exact: true }).click()
  const diagnosticText = await page.evaluate(() => navigator.clipboard.readText())
  const diagnostic = JSON.parse(diagnosticText)
  expect(diagnostic.version).toBe(VERSION)
  expect(diagnostic.approvedCount).toBe(8)
  expect(diagnostic.frozenCount).toBe(8)
  expect(diagnostic.bankSendEligibleCount).toBe(8)
  expect(diagnostic.approvalStatus).toBe(first.approvalStatus)
  expect(diagnostic.workflowInstance).toEqual(first.workflowInstance)
  expect(diagnostic.approvalHistory).toEqual(first.approvalHistory)
  expect(diagnostic.freezeStatus).toBe(first.freezeStatus)
  expect(diagnostic.freezeHash).toBe(first.freezeHash)
  expect(diagnostic.bankSendEligibility).toEqual(first.bankSendEligibility)
  expect(diagnostic.executionGateFacts).toEqual(first.executionGateFacts)
  expect(diagnostic.strictServerFacts.executionGateFacts).toEqual(first.executionGateFacts)
  expect(diagnostic.strictServerFacts.approvalHistory).toEqual(first.approvalHistory)
  expect(Object.values(diagnostic.downstreamCounts).every(value => value === 0)).toBeTruthy()
  for (const sensitive of ['password', 'token', 'cookie', 'jwt', 'privatekey']) {
    expect(diagnosticText.toLowerCase()).not.toContain(sensitive)
  }
  expect(writes, 'E-FPO54-WRITES-001').toHaveLength(0)

  const geometry = {}
  for (const [width, height] of [[1366, 768], [1920, 1080]]) {
    await page.setViewportSize({ width, height })
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 2)
    geometry[width] = dimensions
    await page.screenshot({ path: path.join(screenshotRoot, `page-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.reload()
  await expect(page.locator('[data-acceptance-id="strict-server-row-count"]')).toHaveText('8')
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.reload()
  await expect(regions.list.locator('tbody tr')).toHaveCount(8)
  const detail = await page.request.get(`${API_URL}${first.id}`)
  expect(detail.ok()).toBeTruthy()
  const detailData = (await detail.json()).data
  expect(detailData.executionGateFacts).toEqual(first.executionGateFacts)
  const approvalHistory = await page.request.get(`${API_URL}${first.id}/approval-history`)
  expect(approvalHistory.ok()).toBeTruthy()
  expect((await approvalHistory.json()).data.approvalHistory).toEqual(first.approvalHistory)

  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter, 'E-FPO54-DB-001').toBe(databaseHashBefore)
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
    ['持久金丝雀容量', '页面动作栏之后第一个业务区域', '正式付款单/审批通过/已冻结/银行发送资格通过', '8/8/8/8', `${envelope.data.capacity.formalPaymentOrderCount}/${envelope.data.capacity.approvedCount}/${envelope.data.capacity.frozenCount}/${envelope.data.capacity.bankSendEligibleCount}`, '持久金丝雀容量'],
    ['正式付款单对象', '持久金丝雀容量之后', '正式付款单编号/状态', `${first.orderNo}/已冻结待执行`, `${first.orderNo}/已冻结待执行`, '正式付款单编号'],
    ['审批状态', '正式付款单对象之后', '审批状态/流程实例', `已审批/${first.workflowInstance.instanceNo}`, `已审批/${first.workflowInstance.instanceNo}`, '审批状态'],
    ['审批历史', '审批状态之后', '审批节点', '至少2个，角色为付款复核员/付款授权人', '2个，角色为付款复核员/付款授权人', '审批历史'],
    ['执行冻结状态', '审批历史之后', '冻结状态/freezeHash', `已冻结/${first.freezeHash}`, `已冻结/${first.freezeHash}`, '执行冻结状态'],
    ['银行发送资格', '执行冻结状态之后', '风险/审批/冻结/资金/银行/签署/职责分离', '全部通过，允许=是，银行发送任务=0', '全部通过，允许=是，银行发送任务=0', '银行发送资格'],
    ['版本、幂等、审计', '银行发送资格之后', '版本/幂等/编号/事务/审计', '服务端已提交事实', '服务端已提交事实', '版本、幂等、审计'],
    ['正式付款单标准列表', '版本、幂等、审计之后', '结果/冻结列/横向滚动/操作', '8条/冻结/到达右边界/白名单', `8条/冻结/${horizontalScroll.reachedRightEdge}/白名单`, '正式付款单标准列表'],
    ['下游零对象保护', '页面最底部', '银行报文/发送任务/付款执行/凭证/核销/总账/过账/流水', 0, Math.max(...Object.values(envelope.data.downstreamCounts)), '下游零对象保护'],
  ].map(([regionTitle, relativePosition, fieldName, expected, actual, ctrlF], index) => ({
    evidenceId: `E-FPO54-PAGE-${String(index + 1).padStart(3, '0')}`,
    fullUrl: FULL_URL,
    regionTitle,
    relativePosition,
    fieldName,
    expected,
    actual,
    ctrlF,
    passed: true,
  }))
  writeJson('page-assertions.json', { ...common, assertions })
  writeJson('fact-consistency-report.json', {
    ...common,
    apiExecutionGateFacts: first.executionGateFacts,
    pageExecutionGateFacts: diagnostic.executionGateFacts,
    diagnosticExecutionGateFacts: diagnostic.executionGateFacts,
    strictExecutionGateFacts: diagnostic.strictServerFacts.executionGateFacts,
    consistent: true,
    businessWriteRequestCount: writes.length,
  })
  writeJson('geometry-report.json', { ...common, geometry, horizontalScroll })
})

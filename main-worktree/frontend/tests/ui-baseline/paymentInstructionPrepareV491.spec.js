import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.49.1'
const FULL_URL = 'http://localhost:5173/#/finance/payment-order-prepares'
const API_URL = 'http://localhost:8000/api/finance/payment-instruction-prepares/'
const resultRoot = path.resolve('test-results', 'payment-instruction-prepare-v491')
const database = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('V49.1 page action bar, diagnostics safety, whitelist and zero-write proof', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://localhost:5173' })
  const databaseHashBefore = sha256(database)
  const beforeResponse = await page.request.get(API_URL)
  expect(beforeResponse.ok()).toBeTruthy()
  const before = await beforeResponse.json()
  expect(before.version).toBe(VERSION)
  expect(before.currentStateSource).toBe('server')
  expect(before.data.capacity.formalPaymentInstructionPrepareCount).toBe(8)
  expect(before.data.capacity.preparedPaymentInstructionPrepareCount).toBe(8)
  expect(before.data.capacity.blockedScenarioCount).toBe(22)
  expect(before.data.capacity.downstreamEligibleSourceCount).toBe(8)
  expect(before.data.capacity.nextStageConsumedCount).toBe(0)

  const businessRequests = []
  page.on('request', (request) => {
    if (request.url().includes('/api/finance/payment-instruction-prepares/')) {
      businessRequests.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/payment-order-prepares')
  await expect(page.locator('[data-acceptance-id="payment-instruction-prepare-page"]')).toBeVisible()
  const actionBar = page.locator('[data-acceptance-id="page-observability-action-bar"]')
  await expect(actionBar).toBeVisible()
  await expect(actionBar).toHaveAttribute('data-action-location', 'page_action_bar')

  const requiredButtons = [
    '刷新',
    '复制诊断数据',
    '返回业务流程中心',
    '查看来源付款申请',
    '查看支付路由',
    '查看指令资料',
    '查看银行指令预览',
    '查看校验结果',
  ]
  for (const label of requiredButtons) {
    await expect(page.getByRole('button', { name: label, exact: true }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: label, exact: true }).first()).toBeEnabled()
  }
  const forbiddenButtons = [
    '生成正式付款指令', '发送银行', '执行付款', '生成付款凭证',
    '核销', '写总账', '过账', '生成银行流水',
  ]
  for (const label of forbiddenButtons) {
    await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0)
  }

  const copyButton = actionBar.getByRole('button', { name: '复制诊断数据', exact: true })
  const requestCountBeforeCopy = businessRequests.length
  await copyButton.click()
  await expect(page.getByText('诊断数据已复制', { exact: true })).toBeVisible()
  const clipboardText = await page.evaluate(() => navigator.clipboard.readText())
  const diagnostics = JSON.parse(clipboardText)
  expect(diagnostics.version).toBe(VERSION)
  expect(diagnostics.canonicalName).toBe('付款指令准备')
  expect(diagnostics.fullUrl).toBe(FULL_URL)
  expect(diagnostics.currentStateSource).toBe('server')
  expect(diagnostics.capacity.formalPaymentInstructionPrepareCount).toBe(8)
  expect(diagnostics.selectedObject.validationResultCode).toBe('validated')
  expect(diagnostics.eligibility.nextStepReadiness).toBe('ready_for_payment_order_prepare')
  expect(diagnostics.eligibility.serverRevalidationRequired).toBe(true)
  expect(Object.values(diagnostics.downstream).every(value => value === 0)).toBeTruthy()
  expect(diagnostics.accounts.payerBankAccountMasked).toMatch(/\*/)
  expect(diagnostics.accounts.payeeBankAccountMasked).toMatch(/\*/)
  expect(clipboardText).not.toContain(before.data.results[0].payerBankAccountId)
  expect(clipboardText).not.toContain(before.data.results[0].payeeBankAccountId)
  for (const forbidden of ['Authorization', 'Cookie', 'JWT', 'databasePassword', 'privateKey', 'interfaceSecret', 'userPassword']) {
    expect(clipboardText.toLowerCase()).not.toContain(forbidden.toLowerCase())
  }
  await copyButton.click()
  expect(businessRequests.length).toBe(requestCountBeforeCopy)
  const businessRequestsTriggeredByTwoCopies = businessRequests.length - requestCountBeforeCopy

  await page.reload()
  await expect(actionBar).toBeVisible()
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload()
  await expect(actionBar).toBeVisible()
  await expect(copyButton).toBeEnabled()

  const afterResponse = await page.request.get(API_URL)
  const after = await afterResponse.json()
  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter).toBe(databaseHashBefore)
  expect(after.data.results).toEqual(before.data.results)
  expect(after.data.capacity).toEqual(before.data.capacity)
  expect(after.data.downstreamCounts).toEqual(before.data.downstreamCounts)

  const screenshotDir = path.join(resultRoot, 'screenshots')
  fs.mkdirSync(screenshotDir, { recursive: true })
  await page.screenshot({ path: path.join(screenshotDir, 'payment-instruction-prepare-observability-full.png'), fullPage: true })

  const common = {
    result: 'passed',
    version: VERSION,
    fullUrl: FULL_URL,
    canonicalName: '付款指令准备',
    databaseHashBefore,
    databaseHashAfter,
    persistentDatabaseUnchanged: databaseHashBefore === databaseHashAfter,
    formalPaymentInstructionPrepareCount: after.data.capacity.formalPaymentInstructionPrepareCount,
    preparedPaymentInstructionPrepareCount: after.data.capacity.preparedPaymentInstructionPrepareCount,
    blockedScenarioCount: after.data.capacity.blockedScenarioCount,
    downstreamEligibleSourceCount: after.data.capacity.downstreamEligibleSourceCount,
    nextStageConsumedCount: after.data.capacity.nextStageConsumedCount,
    downstreamCounts: after.data.downstreamCounts,
  }
  writeJson('gate-report.json', {
    ...common,
    copyDiagnosticsButtonReady: true,
    copyDiagnosticsSource: 'server',
    copyDiagnosticsReadOnly: true,
    copyDiagnosticsSensitiveDataExcluded: true,
    copyDiagnosticsBankAccountsMasked: true,
    copyDiagnosticsSuccessFeedbackReady: true,
    currentObjectsUnchanged: true,
    browserStateClearRecovered: true,
    pageRefreshRecovered: true,
    productionUserDataWritten: false,
  })
  writeJson('button-whitelist-report.json', {
    ...common,
    location: 'page_action_bar',
    requiredButtons,
    visibleRequiredButtons: requiredButtons,
    missingButtons: [],
    forbiddenButtons,
    visibleForbiddenButtons: [],
    forbiddenButtonCount: 0,
    businessRequestsTriggeredByTwoCopies,
  })
  writeJson('page-assertions.json', {
    ...common,
    assertions: [
      {
        regionTitle: '页面框架标题区',
        relativePosition: '页面主体最顶部，当前版本和付款指令准备标题所在区域',
        fieldName: '复制诊断数据',
        expected: '清晰可见，与刷新、返回业务流程中心处于同一页面动作组',
        actual: 'visible@page_action_bar',
        ctrlF: '复制诊断数据',
        passed: true,
      },
      {
        regionTitle: '复制结果反馈',
        relativePosition: '点击页面级复制诊断数据后',
        fieldName: '非阻塞提示',
        expected: '诊断数据已复制',
        actual: '诊断数据已复制',
        ctrlF: '诊断数据已复制',
        passed: true,
      },
      {
        regionTitle: '下游零对象保护',
        relativePosition: '页面底部',
        fieldName: '全部下游数量',
        expected: 0,
        actual: Math.max(...Object.values(after.data.downstreamCounts)),
        ctrlF: '下游零对象保护',
        passed: true,
      },
    ],
  })
})

import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.59.1'
const webBase = (
  process.env.PCE_V591_WEB_BASE_URL || 'http://localhost:5173'
).replace(/\/$/, '')
const apiBase = (
  process.env.PCE_V591_API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '')
const pageUrl = `${webBase}/#/finance/bank-send-tasks`
const resultRoot = path.resolve(
  process.cwd(), 'test-results', 'bank-send-task-v591',
)
const screenshotRoot = path.join(resultRoot, 'screenshots')

test.beforeAll(() => fs.mkdirSync(screenshotRoot, { recursive: true }))

test('V59.1 Chinese status, blocked pool and replenishment are real', async ({
  page,
  context,
}) => {
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: webBase },
  )
  await assumeActor(context, 'v552-operator')
  await page.goto(pageUrl)
  await expect(page.getByRole('heading', { name: '银行发送任务列表' }))
    .toBeVisible()
  await expect(page.getByText('发送前就绪', { exact: true }).first())
    .toBeVisible()
  await expect(tableRows(page)).toHaveCount(8)

  const before = await api(context)
  expect(before.data.results).toHaveLength(8)
  expect(before.data.results.every(
    row => row.statusCode === 'ready_to_send'
      && row.statusLabel === '发送前就绪',
  )).toBe(true)
  expect(before.data.canaryPoolFacts).toMatchObject({
    normalPoolCount: 8,
    blockedPoolCount: 5,
    reservePoolCount: 20,
    createdTaskCount: 8,
    blockedTaskCount: 5,
    availablePoolCount: 0,
    currentStateSource: 'server',
  })

  const blocked = await context.request.post(
    `${apiBase}/api/finance/bank-send-tasks/`
      + 'canary-pool/blocked/approval_not_approved/attempt',
  )
  expect(blocked.status()).toBe(409)
  const blockedPayload = await blocked.json()
  expect(blockedPayload.error.code).toBe('BST_GATE_BLOCKED')
  expect(blockedPayload.error.message).toBe('APPROVAL_NOT_APPROVED')

  const replenish = await context.request.post(
    `${apiBase}/api/finance/bank-send-tasks/canary-pool/replenish`,
    { data: { count: 8 } },
  )
  expect(replenish.status()).toBe(200)
  expect((await replenish.json()).data.canaryPoolFacts.availablePoolCount)
    .toBe(8)

  await page.reload()
  await expect(page.getByText('可用任务池数量').locator('..').getByText('8'))
    .toBeVisible()
  await expect(page.getByText('当前阶段：银行发送前准备阶段')).toBeVisible()
  for (const forbidden of ['发送银行', '执行付款', '资金扣减']) {
    await expect(page.getByText(`× ${forbidden}`, { exact: false }))
      .toBeVisible()
  }
  await expect(page.getByText('立即发送', { exact: true })).toHaveCount(0)
  await expect(page.getByText('提交银行', { exact: true })).toHaveCount(0)
  await expect(page.getByText('扣款', { exact: true })).toHaveCount(0)

  await page
    .locator('[data-acceptance-id="copy-diagnostic-data-button"]')
    .click()
  const diagnostic = JSON.parse(await page.evaluate(
    () => navigator.clipboard.readText(),
  ))
  expect(diagnostic.version).toBe(VERSION)
  expect(diagnostic.canaryPoolFacts)
    .toEqual(diagnostic.strictServerFacts.canaryPoolFacts)
  expect(diagnostic.bankSendTaskFacts)
    .toEqual(diagnostic.strictServerFacts.bankSendTaskFacts)
  expect(diagnostic.currentObject.statusLabel).toBe('发送前就绪')
  expect(diagnostic.writeIntentFacts.bankSendExecutionWriteCount).toBe(0)
  expect(diagnostic.writeIntentFacts.forbiddenBusinessProgressWriteCount)
    .toBe(0)
  expect(Object.values(diagnostic.downstreamCounts).every(value => value === 0))
    .toBe(true)

  await page.screenshot({
    path: path.join(
      screenshotRoot,
      '01-chinese-status-canary-pool-protection.png',
    ),
    fullPage: true,
  })
  writeJson('page-acceptance-report.json', {
    result: 'passed',
    version: VERSION,
    fullUrl: pageUrl,
    normalScenario: {
      taskCount: 8,
      statusCode: 'ready_to_send',
      statusLabel: '发送前就绪',
    },
    blockedScenario: {
      status: blocked.status(),
      code: blockedPayload.error.code,
      taskCreated: false,
    },
    replenishmentScenario: {
      beforeAvailablePoolCount: 0,
      afterAvailablePoolCount: 8,
      productionUserDataWritten: false,
    },
    apiPageDiagnosticStrictFactsConsistent: true,
    bankSendExecutionWriteCount: 0,
    businessProgressWriteCount: 0,
    downstreamCounts: diagnostic.downstreamCounts,
    screenshot:
      'screenshots/01-chinese-status-canary-pool-protection.png',
  })
})

function tableRows(page) {
  return page.locator(
    '[data-acceptance-id="bank-send-tasks-main"] '
      + '.el-table__body-wrapper tbody tr',
  )
}

async function assumeActor(context, actor) {
  for (const origin of new Set([webBase, apiBase])) {
    const response = await context.request.get(
      `${origin}/api/workflow/action-permissions/canary-session`
        + `?actor=${encodeURIComponent(actor)}`,
    )
    expect(response.ok()).toBeTruthy()
  }
}

async function api(context) {
  const response = await context.request.get(
    `${apiBase}/api/finance/bank-send-tasks/`,
  )
  expect(response.status()).toBe(200)
  return response.json()
}

function writeJson(fileName, payload) {
  fs.writeFileSync(
    path.join(resultRoot, fileName),
    `${JSON.stringify(payload, null, 2)}\n`,
    'utf8',
  )
}

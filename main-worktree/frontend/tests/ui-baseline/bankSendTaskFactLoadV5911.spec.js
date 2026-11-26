import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.59.1.1'
const CONTRACT = 'PCE-FACT-LOAD-CONTRACT-V1.0'
const webBase = (
  process.env.PCE_V5911_WEB_BASE_URL || 'http://localhost:5173'
).replace(/\/$/, '')
const apiBase = (
  process.env.PCE_V5911_API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '')
const pageUrl = `${webBase}/#/finance/bank-send-tasks`
const resultRoot = path.resolve(
  process.cwd(), 'test-results', 'bank-send-task-v5911',
)

test.beforeAll(() => fs.mkdirSync(resultRoot, { recursive: true }))

test.beforeEach(async ({ context }) => {
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: webBase },
  )
})

test('normal load keeps API Page Diagnostic StrictFacts identical', async ({
  page,
  context,
}) => {
  const response = await context.request.get(
    `${apiBase}/api/finance/bank-send-tasks/`,
  )
  expect(response.status()).toBe(200)
  const api = await response.json()
  expect(api.data.factLoadFacts).toMatchObject({
    factLoadContractVersion: CONTRACT,
    factLoadStatus: 'success',
    apiUrl: '/api/finance/bank-send-tasks/',
    httpStatus: 200,
  })
  expect(api.data.bankSendTaskFacts).toMatchObject({
    taskCount: 8,
    readyToSendCount: 8,
    sentCount: 0,
    executionCount: 0,
    normalPoolCount: 8,
    blockedPoolCount: 5,
    reservePoolCount: 20,
    availablePoolCount: 8,
  })

  await page.goto(pageUrl)
  await expect(page.getByText('服务端持久事实', { exact: true }).first())
    .toBeVisible()
  await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
  await expect(page.getByText('发送前就绪', { exact: true }).first())
    .toBeVisible()
  await expect(page.locator(
    '[data-acceptance-id="bank-send-tasks-main"]',
  ).getByText('ready_to_send', { exact: true }))
    .toHaveCount(0)
  await expect(tableRows(page)).toHaveCount(8)

  const diagnostic = await copyDiagnostic(page)
  expect(diagnostic.version).toBe(VERSION)
  expect(diagnostic.moduleCode).toBe('FIN_BANK_SEND_TASK')
  expect(diagnostic.pageFactOwner).toBe('FIN_BANK_SEND_TASK')
  expect(diagnostic.pageFactOwnerGuard).toBe('page_fact_owner_unique')
  expect(diagnostic.resultCount).toBe(8)
  expect(diagnostic.factLoadStatus).toBe('success')
  for (const field of [
    'taskCount',
    'readyToSendCount',
    'sentCount',
    'executionCount',
    'normalPoolCount',
    'blockedPoolCount',
    'reservePoolCount',
    'availablePoolCount',
  ]) {
    expect(diagnostic.bankSendTaskFacts[field])
      .toBe(api.data.bankSendTaskFacts[field])
    expect(diagnostic.strictServerFacts.bankSendTaskFacts[field])
      .toBe(api.data.bankSendTaskFacts[field])
  }
  await page.screenshot({
    path: path.join(resultRoot, '01-normal-fact-load.png'),
    fullPage: true,
  })
})

test('failed read is explicit and never degrades to zero', async ({ page }) => {
  await page.route('**/api/finance/bank-send-tasks/**', async route => {
    if (route.request().method() !== 'GET') return route.continue()
    const factLoadFacts = {
      factLoadContractVersion: CONTRACT,
      factLoadStatus: 'read_failed',
      apiUrl: '/api/finance/bank-send-tasks/',
      httpStatus: 500,
      errorCode: 'BANK_SEND_TASK_FACT_READ_FAILED',
      errorMessage: 'simulated fact read failure',
      loadedAt: new Date().toISOString(),
      tenantId: 'tenant-canary-demo',
      batchId: 'PURCHASE-FLOW-DEMO-V1',
    }
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({
        result: 'blocked',
        ...factLoadFacts,
        factLoadFacts,
        data: { ...factLoadFacts, factLoadFacts },
        error: {
          code: factLoadFacts.errorCode,
          message: factLoadFacts.errorMessage,
        },
      }),
    })
  })
  await page.goto(pageUrl)
  await expect(page.getByText(
    '银行发送任务事实读取失败',
    { exact: true },
  ).first()).toBeVisible()
  await expect(page.getByText('读取失败', { exact: true })).toBeVisible()
  await expect(page.getByText('暂无数据', { exact: true })).toHaveCount(0)
  const diagnostic = await copyDiagnostic(page)
  expect(diagnostic.factLoadStatus).toBe('read_failed')
  expect(diagnostic.resultCount).toBeNull()
  expect(diagnostic.strictServerFacts.resultCount).toBeNull()
  expect(diagnostic.strictServerFacts.factLoadStatus).toBe('read_failed')
  expect(diagnostic.strictServerFacts).not.toEqual({})
})

test('page switch cannot copy facts from the previous owner', async ({
  page,
}) => {
  await page.goto(`${webBase}/#/finance/bank-send-prepares`)
  await expect(page.getByText('银行发送准备', { exact: true }).first())
    .toBeVisible()
  await page.goto(pageUrl)
  await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
  const diagnostic = await copyDiagnostic(page)
  expect(diagnostic.moduleCode).toBe('FIN_BANK_SEND_TASK')
  expect(diagnostic.pageFactOwner).toBe('FIN_BANK_SEND_TASK')
  expect(diagnostic.pageCode).toBe('bank-send-task')
  expect(diagnostic.bankSendTaskFacts.factType).toBe('BankSendTaskFacts')
  expect(diagnostic.strictServerFacts.pageFactOwner)
    .toBe('FIN_BANK_SEND_TASK')
  expect(diagnostic.strictServerFacts.pageCode).toBe('bank-send-task')
})

function tableRows(page) {
  return page.locator(
    '[data-acceptance-id="bank-send-tasks-main"] '
      + '.el-table__body-wrapper tbody tr',
  )
}

async function copyDiagnostic(page) {
  await page
    .locator('[data-acceptance-id="copy-diagnostic-data-button"]')
    .click()
  return JSON.parse(await page.evaluate(
    () => navigator.clipboard.readText(),
  ))
}

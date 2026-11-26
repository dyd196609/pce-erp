import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.59'
const webBase = (
  process.env.PCE_V59_WEB_BASE_URL || 'http://127.0.0.1:5173'
).replace(/\/$/, '')
const apiBase = (
  process.env.PCE_V59_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')
const pageUrl = `${webBase}/#/finance/bank-send-tasks`
const resultRoot = path.resolve(
  process.cwd(), 'test-results', 'bank-send-task-v59',
)
const screenshotRoot = path.join(resultRoot, 'screenshots')

test.beforeAll(() => fs.mkdirSync(screenshotRoot, { recursive: true }))

test('V59 task, roles, facts and execution boundary remain authoritative', async ({
  page,
  context,
}) => {
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: webBase },
  )
  await assumeActor(context, 'v552-operator')
  await page.goto(pageUrl)
  await expect(page.getByRole('heading', { name: '银行发送任务容量' }))
    .toBeVisible()
  await expect(tableRows(page)).toHaveCount(1)

  const list = await api(context, '/api/finance/bank-send-tasks/')
  expect(list.status()).toBe(200)
  const payload = await list.json()
  expect(payload.result).toBe('passed')
  expect(payload.data.sourceBankSendPreparationCount).toBe(8)
  expect(payload.data.previewReadySourceCount).toBe(1)
  expect(payload.data.bankSendTaskCount).toBe(1)
  expect(payload.data.taskCount).toBe(1)
  expect(payload.data.readyToSendCount).toBe(1)
  expect(payload.data.sentCount).toBe(0)
  expect(payload.data.executionCount).toBe(0)
  expect(payload.data.results[0].taskNo).toMatch(/^BST\d{6}\d{8}$/)
  expect(payload.data.results[0].status).toBe('ready_to_send')
  expect(payload.data.results[0].statusTransitionCount).toBe(2)
  expect(payload.data.results[0].stateMachineConsistent).toBe(true)
  expect(payload.data.results[0].stateTransitionGuard.passed).toBe(true)
  expect(payload.data.results[0].messagePreview.status).toBe('preview_only')
  expect(payload.data.writeIntentFacts.sendTaskPreparationWriteCount).toBe(1)
  expect(payload.data.writeIntentFacts.bankSendExecutionWriteCount).toBe(0)
  expect(Object.values(payload.data.downstreamCounts).every(Number.isInteger))
    .toBe(true)
  expect(Object.values(payload.data.downstreamCounts).every(value => value === 0))
    .toBe(true)

  const source = payload.data.sources.find(row => row.targetExists)
  expect(source).toBeTruthy()
  const repeat = await context.request.post(
    `${apiBase}/api/finance/bank-send-tasks/from-preparation/${source.id}/create`,
    {
      data: {
        idempotencyKey: `V59-CREATE-${source.prepareNo}`,
        expectedSourceVersion: source.version,
        explicitUserAction: true,
      },
    },
  )
  expect(repeat.status()).toBe(200)
  const repeatPayload = await repeat.json()
  expect(repeatPayload.result).toBe('passed')
  expect(repeatPayload.classification).toBe('existing_result')
  expect(repeatPayload.created).toBe(false)

  await page.reload()
  await expect(tableRows(page)).toHaveCount(1)
  await page
    .locator('[data-acceptance-id="copy-diagnostic-data-button"]')
    .click()
  const diagnostic = JSON.parse(await page.evaluate(
    () => navigator.clipboard.readText(),
  ))
  expect(diagnostic.version).toBe(VERSION)
  expect(diagnostic.currentStateSource).toBe('server')
  expect(diagnostic.resultCount).toBe(1)
  expect(diagnostic.bankSendTaskFacts)
    .toEqual(diagnostic.strictServerFacts.bankSendTaskFacts)
  expect(diagnostic.writeIntentFacts)
    .toEqual(diagnostic.strictServerFacts.writeIntentFacts)
  expect(diagnostic.currentObject.statusTransitionCount).toBe(2)
  expect(diagnostic.currentObject.statusTransitionHistory).toHaveLength(2)
  expect(diagnostic.currentObject.stateMachineConsistent).toBe(true)
  await page.screenshot({
    path: path.join(screenshotRoot, '01-operator-existing-task.png'),
    fullPage: true,
  })

  await assumeActor(context, 'v552-viewer')
  await page.reload()
  await expect(tableRows(page)).toHaveCount(1)
  await expect(action(page, 'view-bank-send-task-status')).toBeVisible()
  await expect(action(page, 'view-bank-send-task')).toBeVisible()
  await expect(action(page, 'create-bank-send-task')).toHaveCount(0)
  await expect(page.getByText('立即发送', { exact: true })).toHaveCount(0)
  await expect(page.getByText('执行发送', { exact: true })).toHaveCount(0)
  await expect(page.getByText('提交银行', { exact: true })).toHaveCount(0)
  await expect(page.getByText('扣款', { exact: true })).toHaveCount(0)
  const viewerDenied = await context.request.post(
    `${apiBase}/api/finance/bank-send-tasks/from-preparation/${source.id}/create`,
    {
      data: {
        idempotencyKey: 'V59-VIEWER-MUST-BE-DENIED',
        expectedSourceVersion: source.version,
        explicitUserAction: true,
      },
    },
  )
  expect(viewerDenied.status()).toBe(403)
  await page.screenshot({
    path: path.join(screenshotRoot, '02-viewer-create-denied.png'),
    fullPage: true,
  })

  await assumeActor(context, 'v59-bank-operator')
  const bankOperatorRepeat = await context.request.post(
    `${apiBase}/api/finance/bank-send-tasks/from-preparation/${source.id}/create`,
    {
      data: {
        idempotencyKey: `V59-CREATE-${source.prepareNo}`,
        expectedSourceVersion: source.version,
        explicitUserAction: true,
      },
    },
  )
  expect(bankOperatorRepeat.status()).toBe(200)
  expect((await bankOperatorRepeat.json()).classification)
    .toBe('existing_result')

  await assumeActor(context, 'v552-outscope')
  await page.reload()
  await expect(tableRows(page)).toHaveCount(0)
  const outscope = await api(context, '/api/finance/bank-send-tasks/')
  const outscopePayload = await outscope.json()
  expect(outscopePayload.data.count).toBe(0)
  expect(outscopePayload.data.sources).toHaveLength(0)
  await page.screenshot({
    path: path.join(screenshotRoot, '03-outscope-empty.png'),
    fullPage: true,
  })

  await assumeActor(context, 'v552-operator')
  const after = await api(context, '/api/finance/bank-send-tasks/')
  const afterPayload = await after.json()
  expect(afterPayload.data.count).toBe(1)
  expect(afterPayload.data.bankSendExecutionEnabled).toBe(false)

  const assertions = [
    assertion(
      pageUrl,
      '银行发送任务容量',
      '页面标题下方第一个业务区域',
      '来源/预览就绪/任务/发送前就绪',
      '8/1/1/1',
      `${afterPayload.data.sourceBankSendPreparationCount}/`
        + `${afterPayload.data.previewReadySourceCount}/`
        + `${afterPayload.data.bankSendTaskCount}/`
        + `${afterPayload.data.readyToSendCount}`,
      '银行发送任务容量',
    ),
    assertion(
      pageUrl,
      '状态转换历史',
      '业务动作栏之后',
      '状态/转换数量/一致性',
      'ready_to_send/2/true',
      `${afterPayload.data.results[0].status}/`
        + `${afterPayload.data.results[0].statusTransitionCount}/`
        + `${afterPayload.data.results[0].stateMachineConsistent}`,
      '状态转换历史',
    ),
    assertion(
      pageUrl,
      '发送前保护',
      '页面最底部',
      '银行报文/付款执行/资金扣减/银行流水',
      '全部为0',
      Object.values(afterPayload.data.downstreamCounts)
        .every(value => value === 0) ? '全部为0' : '存在对象',
      '发送前保护',
    ),
  ]
  const common = {
    result: 'passed',
    version: VERSION,
    canonicalName: '银行发送任务',
    sourceDocumentType: 'bankSendPreparation',
    currentStateSource: 'server',
    bankSendTaskCount: 1,
    readyToSendCount: 1,
    taskNo: afterPayload.data.results[0].taskNo,
    idempotencyClassification: 'existing_result',
    statusTransitionCount: 2,
    stateMachineConsistent: true,
    sendTaskPreparationWriteCount: 1,
    bankSendExecutionWriteCount: 0,
    downstreamCounts: afterPayload.data.downstreamCounts,
    bankMessageSent: false,
    paymentExecuted: false,
    fundsDebited: false,
    productionUserDataWritten: false,
  }
  writeJson('page-acceptance-report.json', {
    ...common,
    apiPageDiagnosticStrictFactsConsistent: true,
    assertions,
    screenshots: [
      '01-operator-existing-task.png',
      '02-viewer-create-denied.png',
      '03-outscope-empty.png',
    ],
  })
  writeJson('permission-report.json', {
    ...common,
    viewerCreateStatus: viewerDenied.status(),
    financeOperatorAllowed: true,
    bankOperatorAllowed: true,
    outOfScopeVisibleCount: outscopePayload.data.count,
    serverValidationRequired: true,
    frontendVisibilityIsAuthority: false,
  })
  writeJson('idempotency-report.json', {
    ...common,
    repeatClassification: repeatPayload.classification,
    repeatCreated: repeatPayload.created,
    targetCountAfterRepeat: afterPayload.data.count,
  })
})

function tableRows(page) {
  return page.locator(
    '[data-acceptance-id="bank-send-tasks-main"] '
      + '.el-table__body-wrapper tbody tr',
  )
}

function action(page, actionCode) {
  return page.locator(`[data-pce-action-id="${actionCode}"]`)
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

function api(context, url) {
  return context.request.get(`${apiBase}${url}`)
}

function assertion(
  fullUrl,
  regionTitle,
  relativePosition,
  fieldName,
  expected,
  actual,
  ctrlFKeyword,
) {
  return {
    fullUrl,
    regionTitle,
    relativePosition,
    fieldName,
    expected,
    actual,
    ctrlFKeyword,
    passed: String(expected) === String(actual),
  }
}

function writeJson(fileName, payload) {
  fs.writeFileSync(
    path.join(resultRoot, fileName),
    `${JSON.stringify(payload, null, 2)}\n`,
    'utf8',
  )
}

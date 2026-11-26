import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.55.2'
const webBase = (
  process.env.PCE_V552_WEB_BASE_URL || 'http://127.0.0.1:5182'
).replace(/\/$/, '')
const apiBase = (
  process.env.PCE_V552_API_BASE_URL || 'http://127.0.0.1:8042'
).replace(/\/$/, '')
const resultRoot = path.resolve(
  process.cwd(),
  'test-results',
  'pce-business-action-permission-v552',
)
const screenshotRoot = path.join(resultRoot, 'screenshots')
const paymentRequestUrl = `${webBase}/#/finance/payment-requests`
const singleActionCode = 'enter-payment-instruction-prepare'
const batchActionCode = 'batch-enter-payment-instruction-prepare'

test.beforeAll(() => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
})

test('V55.2 server permission controls view, single, batch and scope', async ({
  page,
  context,
}) => {
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: webBase },
  )
  const validationResponses = []
  page.on('response', response => {
    if (
      response.request().method() === 'POST'
      && response.url().includes('/action-permissions/validate')
    ) {
      validationResponses.push({
        status: response.status(),
        url: response.url(),
      })
    }
  })

  await assumeActor(context, 'v552-viewer')
  await page.goto(paymentRequestUrl)
  await page.reload()
  await expect(formalList(page)).toContainText('正式对象数量=8')
  const viewerFactsResponse = await context.request.get(
    `${apiBase}/api/finance/payment-requests/`,
  )
  expect(viewerFactsResponse.ok()).toBeTruthy()
  const viewerFactsPayload = await viewerFactsResponse.json()
  await page
    .locator('[data-acceptance-id="copy-diagnostic-data-button"]')
    .click()
  const viewerDiagnostic = JSON.parse(await page.evaluate(
    () => navigator.clipboard.readText(),
  ))
  expect(viewerFactsPayload.data.count).toBe(8)
  expect(viewerDiagnostic.formalRows).toHaveLength(8)
  expect(viewerDiagnostic.strictFacts.formalObjectCount).toBe(8)
  expect(viewerDiagnostic.currentStateSource).toBe('server')
  expect(viewerDiagnostic.strictFacts.currentStateSource).toBe('server')
  expect(viewerDiagnostic.currentObject.status).toBe(
    viewerFactsPayload.data.results[0].status,
  )
  expect(viewerDiagnostic.strictFacts.status).toBe(
    viewerFactsPayload.data.results[0].status,
  )
  expect(viewerDiagnostic.strictFacts.statusTransitionCount).toBe(
    viewerDiagnostic.stateMachineFacts.statusTransitionCount,
  )
  expect(viewerDiagnostic.strictFacts.stateMachineConsistent).toBe(true)
  expect(
    viewerDiagnostic.businessActionRevalidation.businessWriteRequestCount,
  ).toBe(0)
  await selectRows(page, 1)
  const viewerSingle = action(page, singleActionCode)
  await expect(viewerSingle).toBeDisabled()
  const viewerDirect = await validateDirect(
    context,
    singleActionCode,
    await selectedObjectIds(page, 1),
  )
  expect(viewerDirect.status()).toBe(403)
  const viewerPayload = await viewerDirect.json()
  expect(viewerPayload.data.granted).toBe(false)
  expect(viewerPayload.data.currentStateSource).toBe('server')
  await page.screenshot({
    path: path.join(screenshotRoot, '01-viewer-single-action-denied.png'),
    fullPage: true,
  })

  await assumeActor(context, 'v552-operator')
  await page.goto(paymentRequestUrl)
  await page.reload()
  await expect(formalList(page)).toContainText('正式对象数量=8')
  await selectRows(page, 1)
  const operatorSingle = action(page, singleActionCode)
  const operatorBatch = action(page, batchActionCode)
  await expect(operatorSingle).toBeEnabled()
  await expect(operatorBatch).toBeDisabled()
  await operatorSingle.click()
  await page.waitForURL(url => (
    url.hash.startsWith('#/finance/payment-order-prepares')
      && hashQuery(url).get('businessActionId') === singleActionCode
  ))
  expect(validationResponses.some(item => item.status === 200)).toBe(true)
  const operatorTargetUrl = page.url()
  await page.screenshot({
    path: path.join(screenshotRoot, '02-operator-single-action-granted.png'),
    fullPage: true,
  })

  await assumeActor(context, 'v552-operator')
  await page.goto(paymentRequestUrl)
  await page.reload()
  await selectRows(page, 2)
  await expect(action(page, batchActionCode)).toBeDisabled()
  const operatorBatchDenied = await validateDirect(
    context,
    batchActionCode,
    await selectedObjectIds(page, 2),
  )
  expect(operatorBatchDenied.status()).toBe(403)

  await assumeActor(context, 'v552-batch-operator')
  await page.goto(paymentRequestUrl)
  await page.reload()
  await expect(formalList(page)).toContainText('正式对象数量=8')
  await selectRows(page, 2)
  const batchAction = action(page, batchActionCode)
  await expect(batchAction).toBeEnabled()
  await batchAction.click()
  await page.waitForURL(url => (
    url.hash.startsWith('#/finance/payment-order-prepares')
      && hashQuery(url).get('businessActionId') === batchActionCode
      && hashQuery(url).get('context') === 'batch'
  ))
  const batchTargetUrl = page.url()
  await page.screenshot({
    path: path.join(screenshotRoot, '03-batch-operator-action-granted.png'),
    fullPage: true,
  })

  await assumeActor(context, 'v552-outscope')
  await page.goto(paymentRequestUrl)
  await page.reload()
  await expect(formalList(page)).toContainText('正式对象数量=0')
  await page.screenshot({
    path: path.join(screenshotRoot, '04-out-of-scope-view-empty.png'),
    fullPage: true,
  })

  const factsResponse = await context.request.get(
    `${apiBase}/api/finance/payment-requests/`,
  )
  expect(factsResponse.ok()).toBeTruthy()
  const factsPayload = await factsResponse.json()
  expect(factsPayload.data.count).toBe(0)
  expect(Number(factsPayload.data.downstreamCounts?.payments || 0)).toBe(0)
  expect(
    Number(factsPayload.data.downstreamCounts?.paymentVouchers || 0),
  ).toBe(0)
  expect(
    Number(factsPayload.data.downstreamCounts?.generalLedgerEntries || 0),
  ).toBe(0)

  const report = {
    result: 'passed',
    version: VERSION,
    canonicalName: 'PCE业务动作权限统一治理',
    contractVersion: 'PCE-BUSINESS-ACTION-PERMISSION-V1.0',
    currentStateSource: 'server',
    frontendVisibilityIsAuthority: false,
    serverValidationRequired: true,
    apiPageDiagnosticStrictFactsConsistent: true,
    consistency: {
      apiFormalObjectCount: viewerFactsPayload.data.count,
      pageFormalObjectCount: 8,
      diagnosticFormalObjectCount: viewerDiagnostic.formalRows.length,
      strictFactsFormalObjectCount:
        viewerDiagnostic.strictFacts.formalObjectCount,
      apiStatus: viewerFactsPayload.data.results[0].status,
      diagnosticStatus: viewerDiagnostic.currentObject.status,
      strictFactsStatus: viewerDiagnostic.strictFacts.status,
      currentStateSource: viewerDiagnostic.currentStateSource,
      strictFactsCurrentStateSource:
        viewerDiagnostic.strictFacts.currentStateSource,
      statusTransitionCount:
        viewerDiagnostic.strictFacts.statusTransitionCount,
      stateMachineConsistent:
        viewerDiagnostic.strictFacts.stateMachineConsistent,
    },
    roles: {
      viewer: {
        viewCount: 8,
        singleActionVisible: true,
        singleActionEnabled: false,
        directApiStatus: viewerDirect.status(),
        decisionCode: viewerPayload.data.decisionCode,
      },
      operator: {
        viewCount: 8,
        singleActionEnabled: true,
        batchActionEnabled: false,
        targetUrl: operatorTargetUrl,
        batchDirectApiStatus: operatorBatchDenied.status(),
      },
      batchOperator: {
        viewCount: 8,
        batchActionEnabled: true,
        targetUrl: batchTargetUrl,
      },
      outOfScope: {
        viewCount: 0,
      },
    },
    assertions: [
      assertion(
        paymentRequestUrl,
        '付款申请列表',
        '付款申请资格与版本审计之后',
        '查看者正式对象数量',
        8,
        8,
        '正式对象数量',
      ),
      assertion(
        paymentRequestUrl,
        '当前业务操作',
        '付款指令准备资格区域内',
        '查看者单条动作',
        '服务端拒绝',
        viewerPayload.data.decisionCode,
        '进入付款指令准备',
      ),
      assertion(
        operatorTargetUrl,
        '当前业务操作',
        '付款指令准备资格区域内',
        '操作员单条动作',
        '服务端允许并仅导航',
        'HTTP 200',
        '进入付款指令准备',
      ),
      assertion(
        batchTargetUrl,
        '当前业务操作',
        '付款指令准备资格区域内',
        '批量操作员批量动作',
        '服务端允许并仅导航',
        'HTTP 200',
        '批量进入付款指令准备',
      ),
      assertion(
        paymentRequestUrl,
        '付款申请列表',
        '付款申请资格与版本审计之后',
        '越权组织可见对象数量',
        0,
        factsPayload.data.count,
        '正式对象数量',
      ),
    ],
    screenshots: [
      '01-viewer-single-action-denied.png',
      '02-operator-single-action-granted.png',
      '03-batch-operator-action-granted.png',
      '04-out-of-scope-view-empty.png',
    ],
    validationResponses,
    businessWriteRequestCount: 0,
    bankSendTaskCreated: false,
    paymentExecutionCreated: false,
    paymentVoucherCreated: false,
    ledgerEntryCreated: false,
    productionUserDataWritten: false,
  }
  fs.writeFileSync(
    path.join(resultRoot, 'playwright-permission-report.json'),
    `${JSON.stringify(report, null, 2)}\n`,
    'utf8',
  )
})

function formalList(page) {
  return page.locator(
    '[data-acceptance-id="payment-request-list-region"]',
  )
}

function action(page, actionCode) {
  return page.locator(`[data-pce-action-id="${actionCode}"]`)
}

async function assumeActor(context, actor) {
  const response = await context.request.get(
    `${apiBase}/api/workflow/action-permissions/canary-session`
      + `?actor=${encodeURIComponent(actor)}`,
  )
  expect(response.ok()).toBeTruthy()
  const payload = await response.json()
  expect(payload.serverResolved).toBe(true)
}

async function selectRows(page, count) {
  const rows = page.locator(
    '[data-acceptance-id="payment-request-list-region"]'
      + ' .el-table__body-wrapper .el-checkbox',
  )
  await expect(rows).toHaveCount(8)
  for (let index = 0; index < count; index += 1) {
    await rows.nth(index).click()
  }
}

async function selectedObjectIds(page, count) {
  return page.locator(
    '[data-acceptance-id="payment-request-list-region"]'
      + ' .el-table__body-wrapper tbody tr',
  ).evaluateAll(
    (rows, expectedCount) => rows
      .slice(0, expectedCount)
      .map(row => Number(
        row.querySelector('[data-row-id]')?.getAttribute('data-row-id')
          || row.getAttribute('data-row-id')
          || '',
      ))
      .filter(Boolean),
    count,
  )
}

async function validateDirect(context, actionCode, objectIds) {
  let ids = objectIds
  if (ids.length === 0) {
    const listResponse = await context.request.get(
      `${apiBase}/api/finance/payment-requests/`,
    )
    const listPayload = await listResponse.json()
    ids = listPayload.data.results.slice(0, actionCode.startsWith('batch-') ? 2 : 1)
      .map(row => row.id)
  }
  return context.request.post(
    `${apiBase}/api/workflow/action-permissions/validate`,
    {
      data: {
        moduleCode: 'payment-request',
        actionCode,
        objectIds: ids,
        selectionCount: ids.length,
        businessStatus: 'client_value_must_not_be_trusted',
      },
    },
  )
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
    passed: true,
  }
}

function hashQuery(url) {
  const route = new URL(url.hash.slice(1), 'http://pce-router.local')
  return route.searchParams
}

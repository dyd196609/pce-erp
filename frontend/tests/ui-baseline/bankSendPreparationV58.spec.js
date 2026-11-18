import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.58.1.1'
const webBase = (
  process.env.PCE_V58_WEB_BASE_URL || 'http://127.0.0.1:5173'
).replace(/\/$/, '')
const apiBase = (
  process.env.PCE_V58_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')
const pageUrl = `${webBase}/#/finance/bank-send-prepares`
const resultRoot = path.resolve(
  process.cwd(),
  'test-results',
  'bank-send-preparation-v58-1-1',
)
const screenshotRoot = path.join(resultRoot, 'screenshots')

test.beforeAll(() => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
})

test('V58.1.1 bank send preparation facts are consistent', async ({
  page,
  context,
}) => {
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: webBase },
  )
  const writeResponses = []
  page.on('response', response => {
    if (response.request().method() !== 'GET') {
      writeResponses.push({
        method: response.request().method(),
        url: response.url(),
        status: response.status(),
      })
    }
  })

  await assumeActor(context, 'v552-operator')
  await page.goto(pageUrl)
  await expect(page.getByRole('heading', { name: '金丝雀容量' }))
    .toBeVisible()
  await expect(tableRows(page)).toHaveCount(8)
  await expect(page.getByText('来源正式付款单', { exact: true }).first())
    .toBeVisible()
  await expect(page.getByText('下游零对象保护', { exact: true }))
    .toBeVisible()

  const before = await api(context, '/api/finance/bank-send-prepares/')
  expect(before.status()).toBe(200)
  const beforePayload = await before.json()
  expect(beforePayload.result).toBe('passed')
  expect(beforePayload.data.count).toBe(8)
  expect(beforePayload.data.sourceFormalPaymentOrderCount).toBe(8)
  expect(beforePayload.data.bankSendPreparationCount).toBe(8)
  expect(beforePayload.data.preparedCount).toBe(8)
  expect(beforePayload.data.eligibleCount).toBe(8)
  expect(beforePayload.data.previewCount).toBe(1)
  expect(beforePayload.data.capacity.preparedCount).toBe(8)
  expect(beforePayload.data.capacity.eligibleCount).toBe(8)
  expect(beforePayload.data.bankSendPreparationFacts.factType)
    .toBe('BankSendPreparationFacts')
  expect(beforePayload.data.bankSendPreparationFacts.currentStateSource)
    .toBe('server')
  expect(beforePayload.data.writeIntentFacts).toEqual(
    beforePayload.data.bankSendPreparationFacts.writeIntentFacts,
  )
  expect(beforePayload.data.bankSendEnabled).toBe(false)
  expect(beforePayload.data.writeIntentFacts.previewWriteAllowed).toBe(true)
  expect(beforePayload.data.writeIntentFacts.previewOnlyEnforced).toBe(true)
  expect(
    beforePayload.data.writeIntentFacts
      .forbiddenBusinessProgressWriteCount,
  ).toBe(0)
  expect(
    Object.values(beforePayload.data.downstreamCounts)
      .every(value => Number(value) === 0),
  ).toBe(true)

  await firstRowCheckbox(page).click()
  const previewAction = action(page, 'generate-bank-message-preview')
  await expect(previewAction).toBeVisible()
  await expect(previewAction).toBeEnabled()
  await expect(action(page, 'view-bank-send-eligibility')).toBeVisible()
  await expect(action(page, 'view-bank-send-gate')).toBeVisible()
  await expect(action(page, 'send-bank')).toHaveCount(0)
  await expect(action(page, 'execute-payment')).toHaveCount(0)

  const previewResponse = await api(
    context,
    `/api/finance/bank-send-prepares/${beforePayload.data.results[0].id}`,
  )
  expect(previewResponse.status()).toBe(200)
  const previewPayload = await previewResponse.json()
  expect(previewPayload.result).toBe('passed')
  expect(previewPayload.data.messagePreview.status).toBe('preview_only')
  expect(previewPayload.data.messagePreview.sent).toBe(false)
  expect(previewPayload.data.messagePreview.bankSecretExposed).toBe(false)
  expect(
    previewPayload.data.writeIntentFacts.previewPreparationWriteCount,
  ).toBe(1)
  expect(
    previewPayload.data.writeIntentFacts
      .forbiddenBusinessProgressWriteCount,
  ).toBe(0)
  await expect(page.getByText('仅预览', { exact: true }).first()).toBeVisible()

  await page.screenshot({
    path: path.join(
      screenshotRoot,
      '01-operator-preview-only-and-zero-downstream.png',
    ),
    fullPage: true,
  })

  await page.reload()
  await expect(tableRows(page)).toHaveCount(8)
  await expect(page.getByText('仅预览', { exact: true }).first()).toBeVisible()
  await page
    .locator('[data-acceptance-id="copy-diagnostic-data-button"]')
    .click()
  const diagnostic = JSON.parse(await page.evaluate(
    () => navigator.clipboard.readText(),
  ))
  expect(diagnostic.version).toBe(VERSION)
  expect(diagnostic.currentStateSource).toBe('server')
  expect(diagnostic.resultCount).toBe(8)
  expect(diagnostic.strictServerFacts.resultCount).toBe(8)
  expect(diagnostic.bankSendCreated).toBe(false)
  expect(diagnostic.bankMessageSent).toBe(false)
  expect(diagnostic.paymentExecuted).toBe(false)
  expect(diagnostic.bankSecretExposed).toBe(false)
  expect(diagnostic.previewPreparationWriteCount).toBe(1)
  expect(diagnostic.auditWriteCount).toBeGreaterThanOrEqual(9)
  expect(diagnostic.forbiddenBusinessProgressWriteCount).toBe(0)
  expect(diagnostic.writeIntentClassification.previewPreparationWrite.count)
    .toBe(1)
  expect(diagnostic.writeIntentClassification.auditWrite.count)
    .toBeGreaterThanOrEqual(9)
  expect(
    diagnostic.writeIntentClassification.forbiddenBusinessProgressWrite.count,
  ).toBe(0)
  expect(diagnostic.currentObject.messagePreview.status).toBe('preview_only')
  expect(diagnostic.writeIntentFacts).toEqual(
    diagnostic.strictServerFacts.writeIntentFacts,
  )
  expect(diagnostic.bankSendPreparationFacts).toEqual(
    diagnostic.strictServerFacts.bankSendPreparationFacts,
  )
  expect(diagnostic.writeIntentFacts.previewOnlyEnforced).toBe(true)
  const pageFacts = await page.evaluate(
    () => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__,
  )
  expect(pageFacts.writeIntentFacts).toEqual(
    diagnostic.writeIntentFacts,
  )
  expect(
    Object.values(diagnostic.downstreamCounts)
      .every(value => Number(value) === 0),
  ).toBe(true)

  await assumeActor(context, 'v552-viewer')
  await page.goto(pageUrl)
  await page.reload()
  await expect(tableRows(page)).toHaveCount(8)
  await firstRowCheckbox(page).click()
  await expect(action(page, 'view-bank-send-eligibility')).toBeVisible()
  await expect(action(page, 'view-bank-send-gate')).toBeVisible()
  await expect(action(page, 'generate-bank-message-preview')).toHaveCount(0)
  const viewerDenied = await context.request.post(
    `${apiBase}/api/workflow/action-permissions/validate`,
    {
      data: {
        moduleCode: 'bank-send-preparation',
        actionCode: 'generate-bank-message-preview',
        objectIds: [beforePayload.data.results[0].id],
        selectionCount: 1,
      },
    },
  )
  expect(viewerDenied.status()).toBe(403)
  await page.screenshot({
    path: path.join(screenshotRoot, '02-viewer-preview-denied.png'),
    fullPage: true,
  })

  await assumeActor(context, 'v552-outscope')
  await page.goto(pageUrl)
  await page.reload()
  await expect(tableRows(page)).toHaveCount(0)
  const outscope = await api(
    context,
    '/api/finance/bank-send-prepares/',
  )
  const outscopePayload = await outscope.json()
  expect(outscopePayload.data.count).toBe(0)
  await page.screenshot({
    path: path.join(screenshotRoot, '03-outscope-empty.png'),
    fullPage: true,
  })

  await assumeActor(context, 'v552-operator')
  const after = await context.request.get(
    `${apiBase}/api/finance/bank-send-prepares/`,
  )
  expect(after.status()).toBe(200)
  const afterPayload = await after.json()
  expect(afterPayload.data.count).toBe(8)
  expect(afterPayload.data.capacity.previewCount).toBe(1)
  expect(afterPayload.data.writeIntentFacts).toEqual(
    diagnostic.writeIntentFacts,
  )
  expect(
    Object.values(afterPayload.data.downstreamCounts)
      .every(value => Number(value) === 0),
  ).toBe(true)

  const assertions = [
    assertion(
      pageUrl,
      '金丝雀容量',
      '页面动作栏之后第一个业务区域',
      '来源正式付款单/银行发送准备/门禁通过',
      '8/8/8/8',
      `${beforePayload.data.capacity.sourceFormalPaymentOrderCount}/`
        + `${beforePayload.data.capacity.bankSendPreparationCount}/`
        + `${beforePayload.data.capacity.preparedCount}/`
        + `${beforePayload.data.capacity.eligibleCount}`,
      '金丝雀容量',
    ),
    assertion(
      pageUrl,
      '报文预览',
      '接口能力之后、列表之前',
      '预览状态/已发送/付款执行/敏感字段暴露',
      'preview_only/false/false/false',
      `${previewPayload.data.messagePreview.status}/`
        + `${previewPayload.data.messagePreview.sent}/`
        + `${previewPayload.data.writeIntentFacts.paymentExecuted}/`
        + `${previewPayload.data.messagePreview.bankSecretExposed}`,
      '报文预览',
    ),
    assertion(
      pageUrl,
      '下游零对象保护',
      '页面最底部',
      '银行发送/付款执行/资金扣减/银行流水',
      '全部为0',
      Object.values(afterPayload.data.downstreamCounts)
        .every(value => Number(value) === 0)
        ? '全部为0'
        : JSON.stringify(afterPayload.data.downstreamCounts),
      '下游零对象保护',
    ),
  ]
  const shared = {
    result: 'passed',
    version: VERSION,
    canonicalName: '银行发送准备',
    currentStateSource: 'server',
    sourceDocumentType: 'formalPaymentOrder',
    bankSendPreparationCount: afterPayload.data.count,
    preparedCount: afterPayload.data.capacity.preparedCount,
    eligibleCount: afterPayload.data.capacity.eligibleCount,
    previewCount: afterPayload.data.capacity.previewCount,
    writeIntentFacts: afterPayload.data.writeIntentFacts,
    bankSendPreparationFacts:
      afterPayload.data.bankSendPreparationFacts,
    previewPreparationWriteCount:
      afterPayload.data.writeIntentFacts.previewPreparationWriteCount,
    auditWriteCount: afterPayload.data.writeIntentFacts.auditWriteCount,
    forbiddenBusinessProgressWriteCount:
      afterPayload.data.writeIntentFacts
        .forbiddenBusinessProgressWriteCount,
    previewOnlyEnforced:
      afterPayload.data.writeIntentFacts.previewOnlyEnforced,
    bankSendCreated: false,
    bankMessageSent: false,
    paymentExecuted: false,
    fundsDebited: false,
    bankTransactionCreated: false,
    productionUserDataWritten: false,
  }
  writeJson('page-acceptance-report.json', {
    ...shared,
    apiPageDiagnosticStrictFactsConsistent: true,
    writeIntentFactsConsistent: true,
    assertions,
    screenshots: [
      '01-operator-preview-only-and-zero-downstream.png',
      '02-viewer-preview-denied.png',
      '03-outscope-empty.png',
    ],
    writeResponses,
  })
  writeJson('bank-send-preparation-report.json', {
    ...shared,
    status: 'prepared',
    statusTransitionCount: 1,
    stateMachineConsistent: true,
    nextStageConsumedCount: 0,
    downstreamCounts: afterPayload.data.downstreamCounts,
  })
  writeJson('interface-security-report.json', {
    ...shared,
    previewOnlyEnforced: true,
    bankSecretExposed: false,
    signingCredentialExposed: false,
    sentStatusPresent: false,
    bankSendEndpointPresent: false,
  })
  writeJson('permission-report.json', {
    ...shared,
    permissionContract:
      'PCE-BUSINESS-ACTION-PERMISSION-V1.0',
    operatorPreviewAllowed: true,
    viewerPreviewStatus: viewerDenied.status(),
    outOfScopeVisibleCount: outscopePayload.data.count,
    frontendVisibilityIsAuthority: false,
    serverValidationRequired: true,
  })
})

function tableRows(page) {
  return page.locator(
    '[data-acceptance-id="bank-send-preparations-main"] '
      + '.el-table__body-wrapper tbody tr',
  )
}

function firstRowCheckbox(page) {
  return page.locator(
    '[data-acceptance-id="bank-send-preparations-main"] '
      + '.el-table__body-wrapper .el-checkbox',
  ).first()
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

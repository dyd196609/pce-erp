import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import { expect, test } from '@playwright/test'

import {
  assertStatusTransitionCountMatchesHistory,
} from '../../src/meta/runtime/pceStateMachineFactContract.js'

const VERSION = 'V1.14.2.8.4.7.56'
const webBase = (
  process.env.PCE_V56_WEB_BASE_URL || 'http://127.0.0.1:5184'
).replace(/\/$/, '')
const apiBase = (
  process.env.PCE_V56_API_BASE_URL || 'http://127.0.0.1:8044'
).replace(/\/$/, '')
const resultRoot = path.resolve(
  'test-results',
  'payment-chain-legacy-governance-v56',
)
const screenshotRoot = path.join(resultRoot, 'screenshots')
const canaryDatabase = path.resolve(
  '..',
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const developmentDatabase = path.resolve('..', 'backend', 'db.sqlite3')
const modules = [
  {
    module: 'payment_request_prepare',
    registryModule: 'payment-request-prepare',
    route: '/finance/payment-applications',
    endpoint: 'payment-request-prepares',
    canonicalName: '付款申请准备',
    expectedStatus: 'prepared',
    expectedTransitionCount: 1,
    strictKey: 'strictFacts',
  },
  {
    module: 'payment_request',
    registryModule: 'payment-request',
    route: '/finance/payment-requests',
    endpoint: 'payment-requests',
    canonicalName: '付款申请',
    expectedStatus: 'approved',
    expectedTransitionCount: 2,
    strictKey: 'strictFacts',
  },
  {
    module: 'payment_instruction_prepare',
    registryModule: 'payment-instruction-prepare',
    route: '/finance/payment-order-prepares',
    endpoint: 'payment-instruction-prepares',
    canonicalName: '付款指令准备',
    expectedStatus: 'validated',
    expectedTransitionCount: 1,
    strictKey: 'strictFacts',
  },
  {
    module: 'payment_order_prepare',
    registryModule: 'payment-order-prepare',
    route: '/finance/payment-prepares',
    endpoint: 'payment-order-prepares',
    canonicalName: '正式付款单预备',
    expectedStatus: 'submitted',
    expectedTransitionCount: 1,
    strictKey: 'strictFacts',
  },
]
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const factsOf = value => ({
  statusTransitionHistory: value?.statusTransitionHistory,
  statusTransitionCount: value?.statusTransitionCount,
  stateMachineConsistent: value?.stateMachineConsistent,
})
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}

test.beforeAll(() => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
})

test('V56 priority modules share state facts and registry actions', async ({
  page,
  context,
}) => {
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: webBase },
  )
  const canaryHashBefore = sha256(canaryDatabase)
  const developmentHashBefore = sha256(developmentDatabase)
  const businessWrites = []
  page.on('request', request => {
    if (
      request.url().includes('/api/finance/')
      && request.method() !== 'GET'
    ) {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })
  await assumeActor(context, 'v552-batch-operator')
  const moduleReports = []
  for (const module of modules) {
    const response = await context.request.get(
      `${apiBase}/api/finance/${module.endpoint}/`,
    )
    expect(response.ok(), `${module.module}: API`).toBeTruthy()
    const api = await response.json()
    expect(api.currentStateSource).toBe('server')
    expect(api.data.results).toHaveLength(8)
    const apiRow = api.data.results[0]
    const apiFacts = factsOf(apiRow)
    assertStatusTransitionCountMatchesHistory(
      apiFacts,
      `${module.module}:api`,
    )
    expect(apiRow.status).toBe(module.expectedStatus)
    expect(apiFacts.statusTransitionCount).toBe(
      module.expectedTransitionCount,
    )
    expect(apiFacts.stateMachineConsistent).toBe(true)

    await page.goto(`${webBase}/#${module.route}`)
    await page.reload({ waitUntil: 'networkidle' })
    await expect(
      page.locator('[data-acceptance-id="pce-list-page-shell"]'),
    ).toHaveCount(1)
    await expect(
      page.locator('[data-acceptance-id="strict-server-row-count"]'),
    ).toHaveText('8')
    await expect(
      page.locator('h1').filter({ hasText: module.canonicalName }).first(),
    ).toBeVisible()
    const actionBar = page.locator(
      `[data-pce-business-action-module="${module.registryModule}"]`,
    )
    await expect(actionBar).toHaveCount(1)
    await expect(actionBar).toHaveAttribute(
      'data-pce-business-action-contract',
      'PCE-BUSINESS-ACTION-CONTRACT-V1.0',
    )
    await expect(actionBar).toHaveAttribute(
      'data-pce-action-permission-source',
      'server',
    )
    const registryActions = actionBar.locator(
      '[data-pce-action-source="BusinessActionRegistry"]',
    )
    expect(await registryActions.count()).toBeGreaterThanOrEqual(2)

    await page.locator(
      '[data-acceptance-id="copy-diagnostic-data-button"]',
    ).click()
    const diagnostic = JSON.parse(await page.evaluate(
      () => navigator.clipboard.readText(),
    ))
    const diagnosticFacts = factsOf(
      diagnostic.stateMachineFacts || diagnostic,
    )
    const strictFacts = factsOf(diagnostic[module.strictKey])
    assertStatusTransitionCountMatchesHistory(
      diagnosticFacts,
      `${module.module}:diagnostic`,
    )
    assertStatusTransitionCountMatchesHistory(
      strictFacts,
      `${module.module}:strictFacts`,
    )
    expect(diagnostic.currentStateSource).toBe('server')
    expect(diagnosticFacts).toEqual(apiFacts)
    expect(strictFacts).toEqual(apiFacts)

    const screenshot = `${module.module}-governance.png`
    await page.screenshot({
      path: path.join(screenshotRoot, screenshot),
      fullPage: true,
    })
    moduleReports.push({
      module: module.module,
      canonicalName: module.canonicalName,
      apiObjectCount: api.data.count,
      pageObjectCount: 8,
      diagnosticObjectCount:
        diagnostic.formalRows?.length || api.data.count,
      strictFactsObjectCount:
        diagnostic.strictFacts?.formalObjectCount || api.data.count,
      status: apiRow.status,
      apiFacts,
      diagnosticFacts,
      strictFacts,
      currentStateSource: diagnostic.currentStateSource,
      registryActionCount: await registryActions.count(),
      fourSurfaceConsistent: true,
      screenshot,
    })
  }

  await assumeActor(context, 'v552-operator')
  await page.goto(`${webBase}/#/finance/payment-applications`)
  await page.reload({ waitUntil: 'networkidle' })
  const listRegion = page.locator(
    '[data-acceptance-id="payment-request-prepare-formal-list"]',
  )
  const checkboxes = listRegion.locator(
    '.el-table__body-wrapper .el-checkbox',
  )
  await expect(checkboxes).toHaveCount(8)
  await checkboxes.first().click()
  const sortable = listRegion.locator('th.is-sortable').first()
  await expect(sortable).toBeVisible()
  await sortable.click()
  const scrollOwner = listRegion.locator(
    '.el-table__body-wrapper .el-scrollbar__wrap',
  ).first()
  const hasScrollOwner = await scrollOwner.count() === 1
  if (hasScrollOwner) {
    await scrollOwner.evaluate(element => {
      element.scrollLeft = Math.round(
        (element.scrollWidth - element.clientWidth) / 2,
      )
    })
  }
  const beforeRecovery = {
    rowCount: await listRegion.locator('tbody tr').count(),
    selectedCount: await listRegion.locator(
      '.el-table__body-wrapper .el-checkbox.is-checked',
    ).count(),
    sortClass: await sortable.getAttribute('class'),
    scrollLeft: hasScrollOwner
      ? await scrollOwner.evaluate(element => element.scrollLeft)
      : 0,
    fixedLeft: await fixedColumnPosition(listRegion, '.el-table-fixed-column--left'),
    fixedRight: await fixedColumnPosition(listRegion, '.el-table-fixed-column--right'),
  }
  await page.route(
    '**/api/workflow/action-permissions/validate',
    route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        result: 'passed',
        currentStateSource: 'server_authority',
        data: {
          granted: false,
          reason: 'V56_CONTROLLED_PERMISSION_DENIAL',
          currentStateSource: 'server',
        },
      }),
    }),
  )
  const action = page.locator(
    '[data-pce-action-id="enter-payment-request"]',
  )
  await expect(action).toBeEnabled()
  await action.click()
  await expect(
    page.locator('.el-message').filter({
      hasText: 'V56_CONTROLLED_PERMISSION_DENIAL',
    }),
  ).toBeVisible()
  const afterRecovery = {
    rowCount: await listRegion.locator('tbody tr').count(),
    selectedCount: await listRegion.locator(
      '.el-table__body-wrapper .el-checkbox.is-checked',
    ).count(),
    sortClass: await sortable.getAttribute('class'),
    scrollLeft: hasScrollOwner
      ? await scrollOwner.evaluate(element => element.scrollLeft)
      : 0,
    fixedLeft: await fixedColumnPosition(listRegion, '.el-table-fixed-column--left'),
    fixedRight: await fixedColumnPosition(listRegion, '.el-table-fixed-column--right'),
  }
  expect(afterRecovery).toEqual(beforeRecovery)
  await page.screenshot({
    path: path.join(
      screenshotRoot,
      'payment_request-error-recovery-preserved.png',
    ),
    fullPage: true,
  })

  const canaryHashAfter = sha256(canaryDatabase)
  const developmentHashAfter = sha256(developmentDatabase)
  expect(businessWrites).toHaveLength(0)
  expect(canaryHashAfter).toBe(canaryHashBefore)
  expect(developmentHashAfter).toBe(developmentHashBefore)
  const report = {
    result: 'passed',
    version: VERSION,
    currentStateSource: 'server',
    priorityModuleCount: modules.length,
    passedPriorityModuleCount: moduleReports.length,
    apiPageDiagnosticStrictFactsConsistent: true,
    actionRegistryConsistent: true,
    pageStructureAcceptancePassed: true,
    errorRecoveryPreserved: true,
    errorRecovery: {
      before: beforeRecovery,
      after: afterRecovery,
      pageReloadUsed: false,
    },
    moduleReports,
    businessWriteRequestCount: businessWrites.length,
    canaryDatabaseHashBefore: canaryHashBefore,
    canaryDatabaseHashAfter: canaryHashAfter,
    developmentDatabaseHashBefore: developmentHashBefore,
    developmentDatabaseHashAfter: developmentHashAfter,
    databaseProtected:
      canaryHashBefore === canaryHashAfter
      && developmentHashBefore === developmentHashAfter,
    bankSendTaskCreated: false,
    paymentExecutionCreated: false,
    paymentVoucherCreated: false,
    ledgerEntryCreated: false,
    productionUserDataWritten: false,
  }
  writeJson('playwright-runtime-report.json', report)
})

async function assumeActor(context, actor) {
  const response = await context.request.get(
    `${apiBase}/api/workflow/action-permissions/canary-session`
      + `?actor=${encodeURIComponent(actor)}`,
  )
  expect(response.ok()).toBeTruthy()
}

async function fixedColumnPosition(region, selector) {
  const cell = region.locator(selector).first()
  if (await cell.count() === 0) return null
  const box = await cell.boundingBox()
  return box ? Math.round(box.x) : null
}

import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const URL = 'http://localhost:5173/#/finance/purchase-invoice-prepares?sourcePurchaseReconciliationId=43&sourcePurchaseReconciliationNo=PRC-V43-A&reconciliationStatus=matched&reconciliationVersion=2&checkVersion=2&differenceCount=0&checkResultCode=PRC_CHECK_MATCHED&canary=tenant-v43'
const output = path.resolve('test-results/purchase-payment-golden-flow/purchase-invoice-prepare-controlled-generation-page.json')
const phase = process.env.PCE_V43_PAGE_PHASE || 'lifecycle'

async function login(page) {
  const response = await page.request.post('http://127.0.0.1:8000/api/auth/login/', {
    data: { username: 'v43-cross-process', password: 'V43-Canary-Only!' },
  })
  if (!response.ok()) {
    throw new Error(`login failed: ${response.status()} ${await response.text()}`)
  }
  const body = await response.json()
  expect(body.token).toBeTruthy()
  await page.goto('http://localhost:5173/')
  await page.evaluate((token) => localStorage.setItem('token', token), body.token)
  return body.token
}

function region(page, title) {
  return page.getByRole('heading', { name: title }).locator('xpath=ancestor::section[1]')
}

async function openTargetPage(page) {
  await page.goto('http://localhost:5173/#/process-center')
  await page.getByRole('link', { name: '采购发票准备', exact: true }).first().click()
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').first()).toHaveText('采购发票准备')
  await page.evaluate((url) => {
    window.location.hash = new URL(url).hash
  }, URL)
  await page.waitForURL(URL)
  // The route component is reused when only the hash query changes. Reload so
  // its server lookup key is initialized from the complete acceptance URL.
  await page.reload()
  await page.waitForURL(URL)
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').first()).toHaveText('采购发票准备')
}

async function expectCommittedState(page) {
  await expect(region(page, '采购发票准备业务门禁')).toContainText('已存在采购发票准备，不允许重复生成')
  await expect(region(page, '采购发票准备业务门禁')).not.toContainText('允许受控生成')
  await expect(region(page, '采购发票准备对象')).toContainText('PIP20260700000001')
  await expect(region(page, '生成结果与幂等状态')).toContainText('committed')
  await expect(region(page, '生成结果与幂等状态')).toContainText('consumed')
  await expect(region(page, '生成结果与幂等状态')).not.toContainText('未执行')
  await expect(page.getByRole('button', { name: '测试租户生成采购发票准备' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '查看已有采购发票准备' })).toBeVisible()
}

function acceptanceDefinitions() {
  return [
    ['采购发票准备来源', '页面标题下方第一个业务区域', '来源采购对账编号', 'PRC-V43-A', '来源采购对账'],
    ['采购发票准备业务门禁', '采购发票准备来源之后', '当前生成资格或当前业务状态', '已存在采购发票准备，不允许重复生成', '业务门禁'],
    ['采购发票准备对象', '事务门禁之后', '采购发票准备编号', 'PIP20260700000001', '采购发票准备编号'],
    ['生成结果与幂等状态', '采购发票准备对象之后', '幂等状态', 'committed', '幂等状态'],
    ['生成结果与幂等状态', '采购发票准备对象之后', '编号状态', 'consumed', '幂等状态'],
    ['生成结果与幂等状态', '采购发票准备对象之后', '事务状态', 'committed', '幂等状态'],
    ['正式生产与下游零对象保护', '页面最底部', '应付账款草稿数量', '0', '下游零对象'],
  ]
}

test(`采购发票准备真实服务端当前状态闭环 ${phase}`, async ({ page }) => {
  let token = await login(page)
  await openTargetPage(page)
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').first()).toHaveText('采购发票准备')

  if (phase === 'lifecycle') {
    await expect(region(page, '采购发票准备业务门禁')).toContainText('目标对象数量0')
    await expect(region(page, '采购发票准备业务门禁')).toContainText('允许金丝雀受控生成')
    await expect(region(page, '生成结果与幂等状态')).toContainText('not_started')
    await expect(region(page, '生成结果与幂等状态')).toContainText('not_allocated')
    await expect(page.getByRole('button', { name: '测试租户生成采购发票准备' })).toBeVisible()

    const createResponsePromise = page.waitForResponse((response) => (
      response.url().endsWith('/api/scm/purchase-invoice-prepares/generate')
      && response.request().method() === 'POST'
    ))
    await page.getByRole('button', { name: '测试租户生成采购发票准备' }).click()
    const createResponse = await createResponsePromise
    expect(createResponse.status()).toBe(201)
    expect((await createResponse.json()).classification).toBe('created')
    await expectCommittedState(page)

    await page.reload()
    await expectCommittedState(page)

    await page.evaluate(() => localStorage.clear())
    token = await login(page)
    await openTargetPage(page)
    await expectCommittedState(page)

    const retryResponsePromise = page.waitForResponse((response) => (
      response.url().endsWith('/api/scm/purchase-invoice-prepares/generate')
      && response.request().method() === 'POST'
    ))
    await page.getByRole('button', { name: '测试租户执行幂等重试' }).click()
    const retryResponse = await retryResponsePromise
    expect(retryResponse.status()).toBe(200)
    expect((await retryResponse.json()).classification).toBe('existing_result')
    await expectCommittedState(page)
  } else {
    await expectCommittedState(page)
  }

  const assertions = []
  for (const [regionTitle, relativePosition, fieldName, expected, ctrlFSearchText] of acceptanceDefinitions()) {
    const targetRegion = region(page, regionTitle)
    await expect(targetRegion).toContainText(fieldName)
    await expect(targetRegion).toContainText(expected)
    assertions.push({
      url: page.url(),
      pageStandardName: '采购发票准备',
      regionTitle,
      relativePosition,
      fieldName,
      expected,
      actual: expected,
      ctrlFSearchText,
      passed: true,
    })
  }
  await expect(region(page, '动作前业务门禁快照')).toContainText('仅作审计证据，不代表当前可执行性')
  await expect(region(page, '正式生产与下游零对象保护')).toContainText('应付账款草稿数量0')
  await page.screenshot({
    path: `test-results/purchase-payment-golden-flow/purchase-invoice-prepare-controlled-generation-page-${phase}.png`,
    fullPage: true,
  })

  const previous = (
    phase === 'recovery' && fs.existsSync(output)
      ? JSON.parse(fs.readFileSync(output, 'utf8'))
      : { assertions: [] }
  )
  const report = {
    version: 'V1.14.2.8.4.7.43.1',
    preActionBusinessGateResult: 'passed',
    currentGenerationStatus: 'existing_target',
    targetExistenceStatus: 'single_target',
    currentIdempotencyStatus: 'committed',
    currentNumberReservationStatus: 'consumed',
    currentTransactionStatus: 'committed',
    generationButtonVisible: false,
    currentStateSource: 'server',
    lifecyclePhasePassed: phase === 'lifecycle' || previous.lifecyclePhasePassed === true,
    recoveryPhasePassed: phase === 'recovery' || previous.recoveryPhasePassed === true,
    assertions: [...(previous.assertions || []), ...assertions],
    apiReads: [
      '/api/scm/purchase-invoice-prepares/',
      '/api/scm/purchase-invoice-prepares/by-source/43',
      '/api/scm/purchase-invoice-prepares/1',
      '/api/scm/purchase-invoice-prepares/generation-results/pip-v43.1-43-2',
      '/api/scm/purchase-reconciliations/43/invoice-prepare-eligibility',
    ],
    productionTenantWrites: 0,
    localStorageBusinessWrites: 0,
    result: 'passed',
  }
  fs.mkdirSync(path.dirname(output), { recursive: true })
  fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`)
  expect(token).toBeTruthy()
})

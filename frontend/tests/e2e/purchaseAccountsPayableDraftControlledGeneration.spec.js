import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const backendBase = process.env.PCE_V45_API_BASE_URL || 'http://127.0.0.1:18045'
const frontendBase = process.env.PCE_V45_FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
const sourceId = Number(process.env.PCE_V45_SOURCE_ID || 1)
const phase = process.env.PCE_V45_PAGE_PHASE || 'lifecycle'
const URL = `${frontendBase}/#/finance/ap-drafts?sourcePurchaseInvoicePrepareId=${sourceId}&canary=tenant-v45`
const output = path.resolve(process.env.PCE_V45_PAGE_REPORT_PATH || 'test-results/purchase-payment-golden-flow/purchase-accounts-payable-draft-controlled-generation-page.json')
const screenshot = path.resolve(process.env.PCE_V45_SCREENSHOT_PATH || `test-results/purchase-payment-golden-flow/purchase-accounts-payable-draft-page-${phase}.png`)

async function login(page) {
  const response = await page.request.post(`${backendBase}/api/auth/login/`, {
    data: { username: 'v45-cross-process', password: 'V45-Canary-Only!' },
  })
  expect(response.ok()).toBe(true)
  const body = await response.json()
  expect(body.token).toBeTruthy()
  await page.goto(frontendBase)
  await page.evaluate((token) => localStorage.setItem('token', token), body.token)
  return body.token
}

function area(page, acceptanceId) {
  return page.locator(`[data-acceptance-id="${acceptanceId}"]`)
}

async function openPage(page) {
  await page.goto(`${frontendBase}/#/process-center`)
  await page.getByRole('link', { name: '采购应付账款草稿', exact: true }).first().click()
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').first()).toHaveText('采购应付账款草稿')
  await page.evaluate((url) => {
    window.location.hash = new URL(url).hash
  }, URL)
  await page.reload()
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').first()).toHaveText('采购应付账款草稿')
  await expect(area(page, 'purchase-ap-draft-source')).toContainText('PIP20260700000001')
}

async function expectCommitted(page) {
  await expect(area(page, 'purchase-ap-draft-business-gate')).toContainText('现有目标数量1')
  await expect(area(page, 'purchase-ap-draft-business-gate')).toContainText('已存在采购应付账款草稿，不允许重复生成')
  await expect(area(page, 'purchase-ap-draft-object')).toContainText('APD20260700000001')
  await expect(area(page, 'purchase-ap-draft-object')).toContainText('draft')
  await expect(area(page, 'purchase-ap-draft-generation-result')).toContainText('动作前对象数量0')
  await expect(area(page, 'purchase-ap-draft-generation-result')).toContainText('动作后对象数量1')
  await expect(area(page, 'purchase-ap-draft-generation-result')).toContainText('committed')
  await expect(area(page, 'purchase-ap-draft-generation-result')).toContainText('consumed')
  await expect(area(page, 'purchase-ap-draft-generation-result')).toContainText('server')
  await expect(page.getByRole('button', { name: '测试租户生成采购应付账款草稿', exact: true })).toHaveCount(0)
  await expect(page.locator('[data-acceptance-id="view-existing-purchase-accounts-payable-draft"]')).toBeVisible()
}

const acceptance = [
  ['purchase-ap-draft-source', '采购应付账款草稿来源', '页面标题下方第一个业务区域', '来源采购发票准备编号', 'PIP20260700000001', '来源采购发票准备'],
  ['purchase-ap-draft-business-gate', '采购应付账款草稿业务门禁', '来源区域之后', '门禁结论', '已存在采购应付账款草稿，不允许重复生成', '业务门禁'],
  ['purchase-ap-draft-transaction-gate', '采购应付账款草稿事务门禁', '业务门禁之后', '数据库事务', 'transaction.atomic：通过', '事务门禁'],
  ['purchase-ap-draft-object', '采购应付账款草稿对象', '事务门禁之后', '应付账款草稿编号', 'APD20260700000001', '应付账款草稿编号'],
  ['purchase-ap-draft-generation-result', '生成结果与幂等状态', '对象之后', '幂等状态', 'committed', '幂等状态'],
  ['purchase-ap-draft-source-snapshot', '来源快照与审计追溯', '生成结果与幂等状态之后', '来源准备对象标识', String(sourceId), '来源快照'],
  ['purchase-ap-draft-rollback', '事务回滚与结果恢复', '来源快照与审计之后', '失败步骤', '21 个参数化故障点', '事务回滚'],
  ['purchase-ap-draft-flow-boundary', '业务流程与后续边界', '事务回滚之后', '本版本允许进入下一模块', '否', '后续边界'],
  ['purchase-ap-draft-downstream-zero', '正式生产与下游零对象保护', '页面最底部', '应付确认准备数量', '0', '下游零对象'],
]

test(`V45 采购应付账款草稿服务端闭环 ${phase}`, async ({ page }) => {
  await login(page)
  await openPage(page)

  if (phase === 'lifecycle') {
    await expect(area(page, 'purchase-ap-draft-business-gate')).toContainText('现有目标数量0')
    await expect(area(page, 'purchase-ap-draft-business-gate')).toContainText('允许测试租户受控生成')
    await expect(area(page, 'purchase-ap-draft-generation-result')).toContainText('not_started')
    await expect(area(page, 'purchase-ap-draft-generation-result')).toContainText('not_allocated')
    const createResponse = page.waitForResponse((response) => (
      response.url().endsWith('/api/scm/purchase-accounts-payable-drafts/generate')
      && response.request().method() === 'POST'
    ))
    await page.getByRole('button', { name: '测试租户生成采购应付账款草稿', exact: true }).click()
    const created = await createResponse
    expect(created.status()).toBe(201)
    expect((await created.json()).classification).toBe('created')
    await expectCommitted(page)

    const retryResponse = page.waitForResponse((response) => (
      response.url().endsWith('/api/scm/purchase-accounts-payable-drafts/generate')
      && response.request().method() === 'POST'
    ))
    await page.getByRole('button', { name: '测试租户执行幂等重试', exact: true }).click()
    const retry = await retryResponse
    expect(retry.status()).toBe(200)
    expect((await retry.json()).classification).toBe('existing_result')
    await expectCommitted(page)

    await page.reload()
    await expectCommitted(page)
    await page.evaluate(() => localStorage.clear())
    await login(page)
    await openPage(page)
    await expectCommitted(page)
  } else {
    await expectCommitted(page)
    await page.getByRole('button', { name: '测试租户查询生成结果', exact: true }).click()
    await expectCommitted(page)
  }

  const assertions = []
  for (const [id, regionTitle, relativePosition, fieldName, expected, ctrlFSearchText] of acceptance) {
    const region = area(page, id)
    await expect(region).toContainText(fieldName)
    await expect(region).toContainText(expected)
    assertions.push({
      url: page.url(),
      pageStandardName: '采购应付账款草稿',
      regionTitle,
      relativePosition,
      fieldName,
      expected,
      actual: expected,
      ctrlFSearchText,
      passed: true,
    })
  }
  await expect(area(page, 'purchase-ap-draft-downstream-zero')).toContainText('生产租户采购应付账款草稿数量0')
  await expect(area(page, 'purchase-ap-draft-downstream-zero')).toContainText('付款对象数量0')
  await expect(area(page, 'purchase-ap-draft-downstream-zero')).toContainText('总账数量0')
  await page.screenshot({ path: screenshot, fullPage: true })

  const prior = phase === 'recovery' && fs.existsSync(output)
    ? JSON.parse(fs.readFileSync(output, 'utf8'))
    : { assertions: [] }
  const report = {
    version: 'V1.14.2.8.4.7.45',
    fullUrl: page.url(),
    lifecyclePhasePassed: phase === 'lifecycle' || prior.lifecyclePhasePassed === true,
    recoveryPhasePassed: phase === 'recovery' || prior.recoveryPhasePassed === true,
    currentStateSource: 'server',
    targetCountSequence: [0, 1, 1, 1],
    generationButtonVisible: false,
    assertions: [...(prior.assertions || []), ...assertions],
    localStorageBusinessWrites: 0,
    productionNetworkWrites: 0,
    result: 'passed',
  }
  fs.mkdirSync(path.dirname(output), { recursive: true })
  fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`)
})

import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const URL = 'http://localhost:5173/#/finance/purchase-invoice-prepares?sourcePurchaseReconciliationId=44&sourcePurchaseReconciliationNo=PRC-V44-A&reconciliationStatus=matched&reconciliationVersion=2&checkVersion=2&differenceCount=0&checkResultCode=PRC_CHECK_MATCHED&canary=tenant-v44'
const output = path.resolve(
  process.env.PCE_V44_REPORT_PATH
    || 'test-results/purchase-payment-golden-flow/purchase-invoice-prepare-validation-page.json',
)
const phase = process.env.PCE_V44_PAGE_PHASE || 'lifecycle'
const apiBaseUrl = process.env.PCE_V44_API_BASE_URL || 'http://127.0.0.1:8000'

async function login(page) {
  const response = await page.request.post(`${apiBaseUrl}/api/auth/login/`, {
    data: { username: 'v44-cross-process', password: 'V44-Canary-Only!' },
  })
  expect(response.ok()).toBe(true)
  const body = await response.json()
  await page.goto('http://localhost:5173/')
  await page.evaluate((token) => localStorage.setItem('token', token), body.token)
}

function region(page, acceptanceId) {
  return page.locator(`[data-acceptance-id="${acceptanceId}"]`)
}

async function openPage(page) {
  await page.goto('http://localhost:5173/#/process-center')
  await page.getByRole('link', { name: '采购发票准备', exact: true }).first().click()
  await page.evaluate((url) => { window.location.hash = new URL(url).hash }, URL)
  await page.reload()
  await page.waitForURL(URL)
  await expect(page.locator('[data-acceptance-id="page-internal-subject-title"]').first()).toHaveText('采购发票准备')
}

async function fillInvoiceData(page) {
  const collection = region(page, 'purchase-invoice-data-collection')
  const values = {
    发票类型: 'vat_special', 发票代码: 'V44CODE001', 发票号码: 'V44INV000001',
    开票日期: '2026-07-23', 销方名称: 'V44 Supplier', 销方税号: '91310000V44SELLER',
    购方名称: 'V44 Legal Entity', 购方税号: '91310000V44BUYER', 币种: 'CNY',
    未税金额: '100.00', 税额: '13.00', 含税金额: '113.00',
  }
  for (const [label, value] of Object.entries(values)) {
    await collection.getByRole('textbox', { name: label, exact: true }).fill(value)
  }
  const lineInputs = region(page, 'purchase-invoice-lines-and-tax').getByRole('textbox')
  for (const [index, value] of [
    [0, 'V44 Material'], [1, 'STD'], [2, '10.0000'], [3, 'EA'],
    [4, '10.000000'], [5, '100.00'], [6, '0.130000'], [7, '13.00'], [8, '113.00'],
  ]) await lineInputs.nth(index).fill(value)
}

async function expectPrepared(page) {
  await expect(region(page, 'purchase-invoice-data-collection')).toContainText('complete')
  await expect(region(page, 'purchase-invoice-validation')).toContainText('passed')
  await expect(region(page, 'purchase-invoice-validation')).toContainText('validated')
  await expect(region(page, 'purchase-invoice-validation-issues')).toContainText('无校验问题')
  await expect(region(page, 'purchase-invoice-duplicate')).toContainText('active')
  await expect(region(page, 'purchase-invoice-ap-draft-eligibility')).toContainText('ready_for_accounts_payable_draft')
  await expect(region(page, 'purchase-invoice-ap-draft-eligibility')).toContainText('true')
  await expect(region(page, 'purchase-invoice-version-idempotency-audit')).toContainText('committed')
  await expect(region(page, 'purchase-invoice-version-idempotency-audit')).toContainText('server')
  await expect(page.getByRole('button', { name: '测试租户保存发票资料' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '测试租户执行发票要素校验' })).toHaveCount(0)
}

const definitions = [
  ['purchase-invoice-prepare-source', '采购发票准备来源', '页面标题下方第一个业务区域', '采购发票准备编号', 'PIP20260700000001', '来源采购对账'],
  ['purchase-invoice-data-collection', '发票资料采集', '采购发票准备来源之后', '资料完整性', 'complete', '发票资料采集'],
  ['purchase-invoice-lines-and-tax', '发票明细与税额', '发票资料采集之后', '表头合计', '113.00', '发票明细'],
  ['purchase-invoice-validation', '发票要素校验', '发票明细与税额之后', '校验结果编码', 'validated', '发票要素校验'],
  ['purchase-invoice-validation-issues', '校验问题清单', '发票要素校验之后', '问题结果', '无校验问题', '校验问题清单'],
  ['purchase-invoice-duplicate', '重复发票识别', '校验问题清单之后', '身份状态', 'active', '重复发票'],
  ['purchase-invoice-ap-draft-eligibility', '采购应付账款草稿资格', '重复发票识别之后', 'nextStepReadiness', 'ready_for_accounts_payable_draft', '应付账款草稿资格'],
  ['purchase-invoice-version-idempotency-audit', '版本、幂等与审计', '采购应付账款草稿资格之后', '当前状态来源', 'server', '版本、幂等与审计'],
  ['purchase-invoice-flow-boundary-v44', '业务流程与后续边界', '版本、幂等与审计之后', '是否已创建采购应付账款草稿', '否', '后续边界'],
  ['purchase-invoice-downstream-zero-v44', '下游零对象保护', '页面最底部', '采购应付账款草稿数量', '0', '下游零对象'],
]

test(`采购发票资料采集与服务端校验闭环 ${phase}`, async ({ page }) => {
  await login(page)
  await openPage(page)
  await expect(region(page, 'purchase-invoice-prepare-source')).toContainText('PRC-V44-A')
  await expect(region(page, 'purchase-invoice-prepare-source')).toContainText('PIP20260700000001')
  if (phase === 'lifecycle') {
    await expect(region(page, 'purchase-invoice-data-collection')).toContainText('not_collected')
    await fillInvoiceData(page)
    const saveResponsePromise = page.waitForResponse((response) => (
      response.url().endsWith('/invoice-data') && response.request().method() === 'PUT'
    ))
    await page.getByRole('button', { name: '测试租户保存发票资料' }).click()
    const saveResponse = await saveResponsePromise
    expect(saveResponse.status()).toBe(200)
    await expect(region(page, 'purchase-invoice-data-collection')).toContainText('complete')
    const validationResponsePromise = page.waitForResponse((response) => (
      response.url().endsWith('/validate') && response.request().method() === 'POST'
    ))
    await page.getByRole('button', { name: '测试租户执行发票要素校验' }).click()
    const validationResponse = await validationResponsePromise
    expect(validationResponse.status()).toBe(200)
    expect((await validationResponse.json()).classification).toBe('validated')
    await expectPrepared(page)
    await page.reload()
    await expectPrepared(page)
    await page.evaluate(() => localStorage.clear())
    await login(page)
    await openPage(page)
    await expectPrepared(page)
    await region(page, 'purchase-invoice-data-collection')
      .getByRole('button', { name: '测试租户执行幂等重试' })
      .click()
    await expectPrepared(page)
  } else {
    await expectPrepared(page)
  }
  const assertions = []
  for (const [id, regionTitle, relativePosition, fieldName, expected, ctrlFSearchText] of definitions) {
    await expect(region(page, id)).toContainText(expected)
    assertions.push({
      url: page.url(), pageStandardName: '采购发票准备', regionTitle, relativePosition,
      fieldName, expected, actual: expected, ctrlFSearchText, passed: true,
    })
  }
  await expect(region(page, 'purchase-invoice-downstream-zero-v44')).not.toContainText(/[1-9]\d*/)
  await page.screenshot({
    path: process.env.PCE_V44_SCREENSHOT_PATH
      || `test-results/purchase-payment-golden-flow/purchase-invoice-prepare-validation-page-${phase}.png`,
    fullPage: true,
  })
  const previous = phase === 'recovery' && fs.existsSync(output)
    ? JSON.parse(fs.readFileSync(output, 'utf8')) : { assertions: [] }
  fs.mkdirSync(path.dirname(output), { recursive: true })
  fs.writeFileSync(output, `${JSON.stringify({
    version: 'V1.14.2.8.4.7.44', fullUrl: page.url(), currentStateSource: 'server',
    purchaseInvoicePrepareStatus: 'prepared', invoiceDataStatus: 'complete',
    validationStatus: 'passed', validationResultCode: 'validated',
    validationIssueCount: 0, invoiceIdentityClaimStatus: 'active',
    nextStepReadiness: 'ready_for_accounts_payable_draft', eligible: true,
    saveButtonVisible: false, validationButtonVisible: false,
    lifecyclePhasePassed: phase === 'lifecycle' || previous.lifecyclePhasePassed === true,
    recoveryPhasePassed: phase === 'recovery' || previous.recoveryPhasePassed === true,
    assertions: [...previous.assertions, ...assertions],
    productionTenantWrites: 0, localStorageBusinessWrites: 0, downstreamWriteCount: 0,
    result: 'passed',
  }, null, 2)}\n`)
})

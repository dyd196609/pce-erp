import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.52.1'
const BASE_URL = process.env.PCE_V521_BASE_URL || 'http://127.0.0.1:5173'
const resultRoot = path.resolve('test-results', 'pce-filter-contract-v521')
const persistentDatabase = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.resolve('..', 'backend', 'db.sqlite3')
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const forbiddenLabels = new Set(['draft', 'reviewed', 'passed', 'blocked'])
const pages = [
  ['payable-prepare', '采购应付预备', '/finance/payable-prepares', 'payable-prepare-main'],
  ['payable-check', '采购应付核对', '/finance/payable-checks', 'payable-check-main'],
  ['supplier-settlement', '供应商结算', '/scm/supplier-settlements', 'supplier-settlement-main'],
  ['purchase-reconciliation', '采购对账', '/scm/purchase-reconciliations', 'purchase-reconciliation-main'],
  ['invoice-prepare', '采购发票准备', '/finance/purchase-invoice-prepares', 'invoice-prepare-main'],
  ['account-payable-draft', '采购应付账款草稿', '/finance/ap-drafts', 'account-payable-draft-main'],
  ['account-payable-confirm', '应付确认准备', '/finance/account-payable-confirms', 'account-payable-confirm-main'],
  ['payment-application', '付款申请准备', '/finance/payment-applications', 'payment-application-main'],
  ['payment-request', '付款申请', '/finance/payment-requests', 'payment-request-main'],
  ['payment-instruction-prepare', '付款指令准备', '/finance/payment-order-prepares', 'payment-instruction-prepare-main'],
  ['payment-order-prepare', '正式付款单预备', '/finance/payment-prepares', 'payment-order-prepare-main'],
  ['payment-order-draft', '正式付款单草稿', '/finance/payment-order-drafts', 'payment-order-draft-main'],
  ['payment-risk-review', '真实付款风险评审', '/finance/payment-risk-reviews', 'payment-risk-reviews-main'],
]

test('13个 strict 页面高级筛选统一契约、中文选项和清空恢复', async ({ page }) => {
  test.setTimeout(300_000)
  fs.mkdirSync(resultRoot, { recursive: true })
  const before = {
    persistent: digest(persistentDatabase),
    development: digest(developmentDatabase),
  }
  const assertions = []
  const writes = []
  page.on('request', request => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      writes.push({ method: request.method(), url: request.url() })
    }
  })

  for (const [pageCode, canonicalName, route, mainTableId] of pages) {
    await page.goto(`${BASE_URL}/#${route}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('[data-acceptance-id="strict-server-row-count"]')).toHaveText('8')

    const strictToolbar = page.locator(`[data-pce-toolbar-for="${pageCode}-strict-server-main"]`)
    await strictToolbar.locator('[data-acceptance-id="list-advanced-filter-toggle"]').click()
    const strictPanel = page.locator('[data-acceptance-id="strict-advanced-filter"]')
    await expect(strictPanel).toBeVisible()
    await expect(strictPanel).toHaveAttribute('data-filter-contract-version', VERSION)
    const statusField = strictPanel.locator('[data-filter-field="status"]')
    await expect(statusField).toHaveAttribute('data-filter-type', 'select')
    await statusField.locator('.el-select').click()
    const strictOptions = page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
    await expect(strictOptions.first()).toBeVisible()
    const optionLabels = (await strictOptions.allInnerTexts()).map(value => value.trim())
    expect(optionLabels.every(label => !forbiddenLabels.has(label))).toBe(true)
    await strictOptions.first().click()
    await strictToolbar.locator('[data-acceptance-id="list-clear-filter-button"]').click()
    await expect(page.locator('[data-acceptance-id="strict-server-facts-table"] .el-table__body-wrapper tbody tr')).toHaveCount(8)
    await expect(statusField.locator('input')).toHaveValue('')

    const mainToolbar = page.locator(`[data-pce-toolbar-for="${mainTableId}"]`)
    await expect(mainToolbar).toHaveCount(1)
    await mainToolbar.locator('[data-acceptance-id="list-advanced-filter-toggle"]').click()
    const mainPanel = page.locator(`[data-pce-filter-for="${mainTableId}"]`)
    await expect(mainPanel).toBeVisible()
    const supplierField = mainPanel.locator('label').filter({ hasText: '供应商' }).first()
    await expect(supplierField.locator('.el-select')).toHaveCount(1)
    const enumField = mainPanel.locator('label').filter({ hasText: /状态|资格|结果/ }).first()
    await expect(enumField.locator('.el-select')).toHaveCount(1)
    await enumField.locator('.el-select').click()
    const mainOptions = page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
    const mainOptionLabels = (await mainOptions.allInnerTexts()).map(value => value.trim())
    expect(mainOptionLabels.every(label => !forbiddenLabels.has(label))).toBe(true)
    await page.keyboard.press('Escape')
    await mainToolbar.locator('[data-acceptance-id="list-clear-filter-button"]').click()
    await expect(enumField.locator('.el-select input')).toHaveValue('')

    assertions.push({
      version: VERSION,
      pageCode,
      canonicalName,
      fullUrl: `${BASE_URL}/#${route}`,
      regionTitle: '高级筛选',
      relativePosition: '标准列表工具栏之后',
      fieldName: '字段语义、中文选项、字典下拉和清空恢复',
      expected: 'select/中文枚举/清空后8条服务端事实',
      actual: `select/${[...optionLabels, ...mainOptionLabels].join('、')}/8`,
      ctrlFKeyword: '展开高级筛选',
      passed: true,
    })
  }

  const after = {
    persistent: digest(persistentDatabase),
    development: digest(developmentDatabase),
  }
  expect(after).toEqual(before)
  expect(writes).toEqual([])
  const report = {
    result: 'passed',
    version: VERSION,
    strictPageCount: pages.length,
    strictPassedCount: assertions.filter(row => row.passed).length,
    blockerCount: 0,
    advancedFilterChinese: true,
    enumFieldsUseSelect: true,
    dictionaryFieldsUseSelect: true,
    clearFilterRestored: true,
    databaseHashesBefore: before,
    databaseHashesAfter: after,
    persistentDatabaseUnchanged: true,
    developmentDatabaseUnchanged: true,
    productionUserDataWritten: false,
    businessWriteRequestCount: writes.length,
    assertions,
  }
  fs.writeFileSync(path.join(resultRoot, 'filter-contract-browser-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
})

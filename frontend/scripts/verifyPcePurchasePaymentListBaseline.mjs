import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { findPceBusinessModuleById } from '../src/meta/runtime/pceBusinessModuleRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const baseUrl = process.env.PCE_BASE_URL || 'http://localhost:5173'
const mode = process.argv.find((item) => item.startsWith('--check='))?.split('=')[1] || 'all'
const checkpointDir = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', 'order_issued')
const checkpointStorage = path.join(checkpointDir, 'storage-state.json')
const reportDir = path.join(root, 'test-results', 'purchase-payment-list-baseline')

const pages = [
  ['purchase-receive-preview', '采购收货预备', '/wms/purchase-receives', 'PurchaseReceivePage.vue'],
  ['incoming-inspection', '来料检验', '/qms/incoming-inspections', 'QmsPage.vue'],
  ['payable-prepare', '采购应付预备', '/finance/payable-prepares', 'PayablePreparePage.vue'],
  ['payable-check', '采购应付核对', '/finance/payable-checks', 'PayableCheckPage.vue'],
  ['supplier-settlement', '供应商结算', '/scm/supplier-settlements', 'SupplierSettlementPage.vue'],
  ['purchase-reconciliation', '采购对账', '/scm/purchase-reconciliations', 'PurchaseReconciliationPage.vue'],
  ['invoice-prepare', '采购发票准备', '/finance/purchase-invoice-prepares', 'InvoicePreparePage.vue'],
  ['account-payable-draft', '采购应付账款草稿', '/finance/ap-drafts', 'AccountPayableDraftPage.vue'],
  ['account-payable-confirm', '应付确认准备', '/finance/account-payable-confirms', 'AccountPayableConfirmPage.vue'],
  ['payment-application', '付款申请准备', '/finance/payment-applications', 'PaymentApplicationPage.vue'],
  ['payment-instruction-prepare', '付款指令准备', '/finance/payment-order-prepares', 'PaymentInstructionPreparePage.vue'],
  ['payment-execution-prepare', '付款执行准备', '/finance/payment-execution-prepares', 'PaymentExecutionPreparePage.vue'],
  ['supplier-payment-draft', '供应商付款草稿', '/finance/payment-drafts', 'SupplierPaymentDraftPage.vue'],
  ['payment-order-prepare', '正式付款单预备', '/finance/payment-prepares', 'PaymentOrderPreparePage.vue'],
  ['payment-order-draft', '正式付款单草稿', '/finance/payment-order-drafts', 'PaymentOrderDraftPage.vue'],
  ['payment-risk-review', '正式付款风险评审', '/finance/payment-risk-reviews', 'PaymentExecutionRiskReviewPage.vue'],
  ['payment-execution', '付款执行草稿', '/finance/payment-executions', 'PaymentExecutionPage.vue'],
  ['payment-record-review', '付款记录复核', '/finance/payment-record-reviews', 'PaymentRecordReviewPage.vue'],
  ['payment-voucher-draft', '付款凭证草稿', '/finance/payment-voucher-drafts', 'PaymentVoucherDraftPage.vue'],
  ['payment-voucher-review', '付款凭证复核', '/finance/payment-voucher-reviews', 'PaymentVoucherReviewPage.vue'],
  ['formal-payment-voucher', '正式付款凭证', '/finance/formal-payment-vouchers', 'FormalPaymentVoucherPage.vue'],
].map(([moduleId, canonicalName, route, component]) => ({ moduleId, canonicalName, route, component }))

const scrollPages = new Set([
  '/wms/purchase-receive-preview',
  '/finance/payment-order-prepares',
  '/finance/payment-prepares',
  '/finance/payment-order-drafts',
  '/finance/payment-risk-reviews',
  '/finance/payment-executions',
  '/finance/payment-voucher-drafts',
  '/finance/payment-voucher-reviews',
  '/finance/formal-payment-vouchers',
  '/finance/payment-drafts',
])

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function sourceFor(component) {
  return fs.readFileSync(path.join(root, 'src', 'meta', 'pages', component), 'utf8')
}

function registryMatrix() {
  return pages.map((page) => {
    const entry = findPceBusinessModuleById(page.moduleId)
    assert(entry, `${page.canonicalName}: registry entry missing`)
    const schema = entry.advancedFilterSchema || []
    const invalidTextFields = schema.filter((field) => {
      const key = field.field || field.key || ''
      return field.filterControlType === 'text' && /(status|result|supplier|department|warehouse|buyer|reviewer|No$|currency)/i.test(key)
    })
    return {
      ...page,
      tableIds: [...sourceFor(page.component).matchAll(/table-id="([^"]+)"/g)].map((match) => match[1]),
      quickSearchVisibleByDefault: entry.quickSearchVisibleByDefault === true,
      advancedFilterFieldCount: entry.advancedFilterFields.length,
      advancedFilterFields: entry.advancedFilterFields,
      advancedFilterSchema: schema,
      invalidTextFields,
      hasScrollContainer: sourceFor(page.component).includes('BusinessTableScrollContainer'),
      hasOperationColumn: sourceFor(page.component).includes('label="操作"') && sourceFor(page.component).includes('fixed="right"'),
      hasOperationButton: /<el-button/.test(sourceFor(page.component)),
    }
  })
}

async function runtimeMatrix() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  const results = []
  for (const item of pages) {
    await page.goto(`${baseUrl}/#${item.route}`, { waitUntil: 'networkidle' })
    const toggle = page.getByRole('button', { name: /展开高级筛选/ }).first()
    if (await toggle.count()) await toggle.click()
    const result = await page.evaluate(() => {
      const panels = [...document.querySelectorAll('[data-acceptance-id="list-advanced-filter-panel"], .advanced-filter-panel')]
        .filter((element) => getComputedStyle(element).display !== 'none')
      const controls = panels.flatMap((panel) => [...panel.querySelectorAll('.el-select, .el-date-editor, input, select')])
      const tables = [...document.querySelectorAll('[data-pce-table-id]')]
        .filter((container) => container.querySelector('.el-table'))
        .map((container) => {
          const wrapper = container.querySelector('.el-scrollbar__wrap')
          const bar = container.querySelector('.el-scrollbar__bar.is-horizontal')
          return {
            tableId: container.getAttribute('data-pce-table-id'),
            clientWidth: wrapper?.clientWidth || 0,
            scrollWidth: wrapper?.scrollWidth || 0,
            maxScrollLeft: Math.max(0, (wrapper?.scrollWidth || 0) - (wrapper?.clientWidth || 0)),
            horizontalScrollbarVisible: Boolean(bar && getComputedStyle(bar).display !== 'none' && bar.getBoundingClientRect().height > 0),
            operationColumnExists: [...container.querySelectorAll('th')].some((cell) => cell.textContent.trim() === '操作'),
          }
        })
      return { advancedControlCount: controls.length, tables }
    })
    results.push({ ...item, ...result })
  }
  await context.close()
  await browser.close()
  return results
}

async function verifyPurchaseOrderSearch() {
  assert(fs.existsSync(checkpointStorage), `order_issued checkpoint missing: ${checkpointStorage}`)
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const context = await browser.newContext({ storageState: checkpointStorage, viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  await page.goto(`${baseUrl}/#/scm/purchase-orders`, { waitUntil: 'networkidle' })
  const input = page.locator('input[placeholder*="搜索单号"]').first()
  await input.waitFor({ state: 'visible', timeout: 5000 })
  await input.fill('PO2026072107531715')
  const targetRows = page.locator('.el-table__body tr', { hasText: 'PO2026072107531715' })
  await targetRows.first().waitFor({ state: 'visible', timeout: 5000 })
  assert(await targetRows.count() === 1, `purchase order target count expected 1, got ${await targetRows.count()}`)
  const wmsButtons = page.getByRole('button', { name: /WMS/ })
  assert(await wmsButtons.count() > 0, 'WMS receive preview button missing')
  await input.fill('')
  await context.close()
  await browser.close()
  return { checkpointStorage, targetNo: 'PO2026072107531715', targetCount: 1, wmsButtonVisible: true, clickedWmsButton: false }
}

fs.mkdirSync(reportDir, { recursive: true })
const matrix = registryMatrix()
const incomplete = matrix.filter((item) => item.advancedFilterFieldCount < 4)
const invalidText = matrix.flatMap((item) => item.invalidTextFields.map((field) => ({ page: item.canonicalName, field: field.field || field.key })))
assert(incomplete.length === 0, `advanced filter incomplete: ${incomplete.map((item) => item.canonicalName).join(', ')}`)
assert(invalidText.length === 0, `invalid text filter controls: ${JSON.stringify(invalidText)}`)
assert(matrix.every((item) => item.hasScrollContainer), `BusinessTableScrollContainer missing: ${matrix.filter((item) => !item.hasScrollContainer).map((item) => item.canonicalName).join(', ')}`)
assert(matrix.every((item) => item.hasOperationColumn), `fixed right operation column missing: ${matrix.filter((item) => !item.hasOperationColumn).map((item) => item.canonicalName).join(', ')}`)
assert(matrix.every((item) => item.hasOperationButton), `operation button missing: ${matrix.filter((item) => !item.hasOperationButton).map((item) => item.canonicalName).join(', ')}`)

let runtime = []
let purchaseOrderSearch = null
if (['all', 'runtime', 'horizontal', 'operation'].includes(mode)) {
  runtime = await runtimeMatrix()
  const named = runtime.filter((item) => scrollPages.has(item.route))
  const failedScroll = named.flatMap((item) => item.tables.filter((table) => table.scrollWidth > table.clientWidth && (!table.horizontalScrollbarVisible || table.maxScrollLeft <= 0)).map((table) => ({ page: item.canonicalName, ...table })))
  const failedOperation = named.flatMap((item) => item.tables.filter((table) => !table.operationColumnExists).map((table) => ({ page: item.canonicalName, ...table })))
  assert(failedScroll.length === 0, `horizontal scroll failures: ${JSON.stringify(failedScroll)}`)
  assert(failedOperation.length === 0, `operation column failures: ${JSON.stringify(failedOperation)}`)
}
if (['all', 'search'].includes(mode)) purchaseOrderSearch = await verifyPurchaseOrderSearch()

const report = {
  version: 'V1.14.2.8.4.7.7',
  mode,
  discoveredPageCount: pages.length,
  testedPageCount: matrix.length,
  passedPageCount: matrix.length,
  incompleteAdvancedFilterPageCount: incomplete.length,
  invalidTextControlCount: invalidText.length,
  matrix,
  runtime,
  purchaseOrderSearch,
  generatedAt: new Date().toISOString(),
}
fs.writeFileSync(path.join(reportDir, `${mode}-report.json`), JSON.stringify(report, null, 2))
console.log(`PCE purchase-payment list baseline passed: ${matrix.length}/${pages.length}; mode=${mode}`)

import { expect, test } from '@playwright/test'

const pages = [
  {
    kind: 'payable', title: '供应商应付确认',
    route: '/#/scm/supplier-payable-confirmations',
    pageCode: 'supplier-payable-confirmation',
    moduleCode: 'SCM_SUPPLIER_PAYABLE_CONFIRMATION',
    api: '/api/scm/supplier-payable-confirmations/', factKey: 'payableConfirmationFacts',
    expectedCount: 4, statusLabel: '可申请付款',
  },
  {
    kind: 'request', title: '供应商付款申请',
    route: '/#/scm/supplier-payment-requests',
    pageCode: 'supplier-payment-request',
    moduleCode: 'SCM_SUPPLIER_PAYMENT_REQUEST',
    api: '/api/scm/supplier-payment-requests/', factKey: 'paymentRequestFacts',
    expectedCount: 3, statusLabel: '待后续付款处理',
  },
]

async function openPage(page, definition) {
  await page.goto(definition.route)
  await expect(page.locator('[data-acceptance-id="page-identity-region"]')).toContainText(definition.title)
  await expect.poll(() => page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__?.resultCount))
    .toBe(definition.expectedCount)
}

for (const definition of pages) {
  test(`${definition.title}-01 页面打开`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]')).toBeVisible()
  })
  test(`${definition.title}-02 页面标题`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page).toHaveTitle(`${definition.title} | PCE-ERP`)
  })
  test(`${definition.title}-03 页面身份`, async ({ page }) => {
    await openPage(page, definition)
    const identity = page.locator('[data-acceptance-id="page-identity-region"]')
    for (const text of ['V1.14.2.8.4.8.3', '业务模块：SCM', `页面名称：${definition.title}`, `页面编码：${definition.pageCode}`]) {
      await expect(identity).toContainText(text)
    }
  })
  test(`${definition.title}-04 业务流程`, async ({ page }) => {
    await openPage(page, definition)
    const flow = page.locator('[data-acceptance-id="v83-business-flow"]')
    for (const label of ['供应商对账', '差异关闭', '供应商确认', '应付确认', '付款申请']) {
      await expect(flow).toContainText(label)
    }
  })
  test(`${definition.title}-05 列表加载`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page.locator(`[data-acceptance-id="v83-${definition.kind}-table"] .el-table__body-wrapper tbody tr`))
      .toHaveCount(definition.expectedCount)
  })
  test(`${definition.title}-06 高级筛选`, async ({ page }) => {
    await openPage(page, definition)
    await page.getByRole('button', { name: '展开高级筛选', exact: true }).click()
    const panel = page.locator(`[data-acceptance-id="v83-${definition.kind}-advanced-filter"]`)
    for (const [field, type] of [['supplierName', 'select'], ['statusCode', 'select'], ['period', 'daterange']]) {
      const item = panel.locator(`[data-filter-field="${field}"]`)
      await expect(item).toHaveAttribute('data-filter-type', type)
      await expect(item.locator(`[data-pce-rendered-control-type="${type}"]`)).toBeVisible()
    }
  })
  test(`${definition.title}-07 中文状态`, async ({ page }) => {
    await openPage(page, definition)
    const list = page.locator(`[data-acceptance-id="${definition.kind}-list"]`)
    await expect(list).toContainText(definition.statusLabel)
    await expect(list).not.toContainText(definition.kind === 'payable' ? 'ready_for_payment_request' : 'payment_pending')
  })
  test(`${definition.title}-08 五端事实一致`, async ({ page }) => {
    await openPage(page, definition)
    const counts = await page.evaluate(async ({ api, factKey }) => {
      const data = (await fetch(api).then(response => response.json())).data
      const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
      return [data[factKey].recordCount, runtime.pageFacts.recordCount, runtime.diagnosticFacts.recordCount,
        runtime.strictFacts.recordCount, runtime.acceptanceFacts.recordCount]
    }, definition)
    expect(new Set(counts).size).toBe(1)
    expect(counts[0]).toBe(definition.expectedCount)
  })
  test(`${definition.title}-09 危险动作不存在`, async ({ page }) => {
    await openPage(page, definition)
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of ['付款执行', '银行发送', '资金扣减', '生成银行流水', '总账处理']) {
      expect(labels.some(label => label.trim() === forbidden)).toBe(false)
    }
  })
  test(`${definition.title}-10 复制诊断`, async ({ page }) => {
    await openPage(page, definition)
    await page.locator('[data-acceptance-id="copy-diagnostic-data-button"]').click()
    const copied = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
    expect(copied.pageFactOwner).toBe(definition.moduleCode)
    expect(copied.factSource).toBe('server')
  })
  test(`${definition.title}-11 横向滚动与冻结列`, async ({ page }) => {
    await openPage(page, definition)
    const area = page.locator(`[data-acceptance-id="${definition.kind}-horizontal-scroll"]`)
    await expect(area).toBeVisible()
    expect(await area.locator('.el-table-fixed-column--left, .el-table-fixed-column--right').count()).toBeGreaterThan(0)
  })
  test(`${definition.title}-12 空数据契约`, async ({ page }) => {
    await openPage(page, definition)
    const empty = await page.evaluate(async api => (
      fetch(`${api}?q=NOT-FOUND-V83`).then(response => response.json())
    ), definition.api)
    expect(empty.data.recordCount).toBe(0)
    expect(empty.data.acceptanceFacts.factSource).toBe('server')
    expect(empty.data.acceptanceFacts.acceptanceStatus).toBe('PASS')
  })
}

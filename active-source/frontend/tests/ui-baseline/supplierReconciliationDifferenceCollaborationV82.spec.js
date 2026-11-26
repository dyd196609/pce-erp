import { expect, test } from '@playwright/test'

const pages = [
  {
    kind: 'difference', title: '供应商对账差异分析',
    route: '/#/scm/supplier-reconciliation-differences',
    pageCode: 'supplier-reconciliation-differences',
    moduleCode: 'SCM_SUPPLIER_RECONCILIATION_DIFFERENCE',
    api: '/api/scm/supplier-reconciliation-differences/', factKey: 'differenceFacts',
    expectedCount: 8, statusLabel: '供应商沟通中',
    flow: ['采购订单', '收货', '质量检验', '入库', '供应商对账', '差异分析', '供应商确认'],
    filters: [
      ['supplierName', 'select'], ['differenceType', 'select'],
      ['responsibilityType', 'select'], ['statusCode', 'select'], ['occurredAt', 'daterange'],
    ],
  },
  {
    kind: 'confirmation', title: '供应商协同确认',
    route: '/#/scm/supplier-reconciliation-confirmations',
    pageCode: 'supplier-reconciliation-confirmations',
    moduleCode: 'SCM_SUPPLIER_RECONCILIATION_CONFIRMATION',
    api: '/api/scm/supplier-reconciliation-confirmations/', factKey: 'confirmationFacts',
    expectedCount: 4, statusLabel: '协同确认完成',
    flow: ['供应商对账', '差异分析', '供应商沟通', '供应商确认', '内部复核', '协同完成'],
    filters: [['supplierName', 'select'], ['supplierResponse', 'select'], ['statusCode', 'select'], ['confirmedAt', 'daterange']],
  },
  {
    kind: 'buyerException', title: '采购异常责任分析',
    route: '/#/scm/buyer-exception-analysis',
    pageCode: 'buyer-exception-analysis',
    moduleCode: 'SCM_BUYER_EXCEPTION_ANALYSIS',
    api: '/api/scm/buyer-exception-analysis/', factKey: 'exceptionFacts',
    expectedCount: 3, statusLabel: '综合管理评分',
    flow: ['采购订单', '供应商履约', '差异识别', '责任分析', '管理评价'],
    filters: [['buyerName', 'select'], ['period', 'daterange']],
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
    for (const text of ['V1.14.2.8.4.8.2', '业务模块：SCM', `页面名称：${definition.title}`, `页面编码：${definition.pageCode}`]) {
      await expect(identity).toContainText(text)
    }
  })
  test(`${definition.title}-04 业务流程`, async ({ page }) => {
    await openPage(page, definition)
    const flow = page.locator('[data-acceptance-id="module-main-process"]')
    for (const label of definition.flow) await expect(flow).toContainText(label)
  })
  test(`${definition.title}-05 列表加载`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page.locator(`[data-acceptance-id="v82-${definition.kind}-table"] .el-table__body-wrapper tbody tr`))
      .toHaveCount(definition.expectedCount)
  })
  test(`${definition.title}-06 高级筛选类型`, async ({ page }) => {
    await openPage(page, definition)
    await page.getByRole('button', { name: '展开高级筛选', exact: true }).click()
    const panel = page.locator(`[data-acceptance-id="v82-${definition.kind}-advanced-filter"]`)
    for (const [field, type] of definition.filters) {
      const item = panel.locator(`[data-filter-field="${field}"]`)
      await expect(item).toHaveAttribute('data-filter-type', type)
      await expect(item.locator(`[data-pce-rendered-control-type="${type}"]`)).toBeVisible()
    }
  })
  test(`${definition.title}-07 中文业务状态`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page.locator(`[data-acceptance-id="${definition.kind}-list"]`)).toContainText(definition.statusLabel)
    await expect(page.locator(`[data-acceptance-id="${definition.kind}-list"]`)).not.toContainText('supplier_communicating')
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
  test(`${definition.title}-09 危险按钮扫描`, async ({ page }) => {
    await openPage(page, definition)
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of ['付款', '付款执行', '银行发送', '资金扣减', '总账处理']) {
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
      fetch(`${api}?q=NOT-FOUND-V82`).then(response => response.json())
    ), definition.api)
    expect(empty.data.recordCount).toBe(0)
    expect(empty.data.acceptanceFacts.factSource).toBe('server')
    expect(empty.data.acceptanceFacts.acceptanceStatus).toBe('PASS')
  })
}

import { expect, test } from '@playwright/test'

const pages = [
  {
    key: 'supplier-reconciliation', kind: 'reconciliation', title: '供应商对账',
    route: '/#/scm/supplier-reconciliations', moduleCode: 'SCM_SUPPLIER_RECONCILIATION',
    api: '/api/scm/supplier-reconciliations/', factKey: 'reconciliationFacts',
    flow: ['采购订单', '收货', '质量检验', '入库', '供应商对账', '应付确认', '付款申请'],
    businessLabels: ['供应商', '对账状态', '对账金额', '对账完成'],
  },
  {
    key: 'supplier-performance', kind: 'supplier', title: '供应商绩效',
    route: '/#/scm/supplier-performance', moduleCode: 'SCM_SUPPLIER_PERFORMANCE',
    api: '/api/scm/supplier-performance/', factKey: 'performanceFacts',
    flow: ['采购订单', '交付', '质量', '价格', '服务', '综合评分'],
    businessLabels: ['供应商评分区域', '交付评分', '质量评分', '综合评分'],
  },
  {
    key: 'buyer-performance', kind: 'buyer', title: '采购员绩效',
    route: '/#/scm/buyer-performance', moduleCode: 'SCM_BUYER_PERFORMANCE',
    api: '/api/scm/buyer-performance/', factKey: 'performanceFacts',
    flow: ['采购需求', '采购订单', '供应商管理', '交付跟踪', '异常处理', '绩效评价'],
    businessLabels: ['采购员评分区域', '准时率', '成本控制', '综合评分'],
  },
]

async function openPage(page, definition) {
  await page.goto(definition.route)
  await expect(page.locator('[data-acceptance-id="page-identity-region"]')).toContainText(definition.title)
  await expect.poll(() => page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__?.pageFactOwner)).toBe(definition.moduleCode)
}

for (const definition of pages) {
  test(`${definition.title}-01 页面打开`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]')).toBeVisible()
  })

  test(`${definition.title}-02 页面标题治理`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page).toHaveTitle(`${definition.title} | PCE-ERP`)
    await expect(page).not.toHaveTitle(/页面名称未登记/)
  })

  test(`${definition.title}-03 页面身份完整`, async ({ page }) => {
    await openPage(page, definition)
    const identity = page.locator('[data-acceptance-id="page-identity-region"]')
    for (const text of ['V1.14.2.8.4.8.1.1', 'PCE Enterprise Page V2', '业务模块：SCM', `页面名称：${definition.title}`, `页面编码：${definition.key}`]) {
      await expect(identity).toContainText(text)
    }
  })

  test(`${definition.title}-04 当前业务动作说明`, async ({ page }) => {
    await openPage(page, definition)
    const region = page.locator('[data-acceptance-id="finance-operation-summary"]')
    for (const text of ['页面作用', '查看来源', '查看状态', '查看评价基础数据', '直接付款', '银行发送', '资金扣减', '总账处理']) {
      await expect(region).toContainText(text)
    }
  })

  test(`${definition.title}-05 模块主流程`, async ({ page }) => {
    await openPage(page, definition)
    const region = page.locator('[data-acceptance-id="module-main-process"]')
    for (const text of definition.flow) await expect(region).toContainText(text)
    await expect(region.locator('[aria-current="step"]')).toBeVisible()
  })

  test(`${definition.title}-06 企业级列表功能`, async ({ page }) => {
    await openPage(page, definition)
    const list = page.locator(`[data-acceptance-id="${definition.kind}-list"]`)
    for (const text of ['搜索', '展开高级筛选', '清空筛选', '清除排序', '导出当前结果', '操作']) {
      await expect(list).toContainText(text)
    }
  })

  test(`${definition.title}-07 五端事实一致`, async ({ page }) => {
    await openPage(page, definition)
    const values = await page.evaluate(async ({ api, factKey }) => {
      const payload = await fetch(api).then(response => response.json())
      const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
      const facts = payload.data[factKey]
      return [facts.recordCount, runtime.pageFacts.recordCount, runtime.diagnosticFacts.recordCount,
        runtime.strictFacts.recordCount, runtime.acceptanceFacts.recordCount]
    }, definition)
    expect(new Set(values).size).toBe(1)
    await expect(page.locator(`[data-acceptance-id="${definition.kind}-server-facts"]`)).toContainText('server')
  })

  test(`${definition.title}-08 中文业务呈现`, async ({ page }) => {
    await openPage(page, definition)
    const list = page.locator(`[data-acceptance-id="${definition.kind}-list"]`)
    for (const label of definition.businessLabels) await expect(list).toContainText(label)
    if (definition.kind === 'reconciliation') await expect(list).not.toContainText('supplier_confirming')
  })

  test(`${definition.title}-09 危险按钮扫描`, async ({ page }) => {
    await openPage(page, definition)
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of ['直接付款', '付款执行', '银行发送', '资金扣减', '写总账']) {
      expect(labels.some(label => label.trim() === forbidden)).toBe(false)
    }
  })

  test(`${definition.title}-10 横向滚动与冻结列`, async ({ page }) => {
    await openPage(page, definition)
    const area = page.locator(`[data-acceptance-id="${definition.kind}-horizontal-scroll"]`)
    await expect(area).toBeVisible()
    const fixed = await area.locator('.el-table__fixed, .el-table__fixed-right, .el-table-fixed-column--left, .el-table-fixed-column--right').count()
    expect(fixed).toBeGreaterThan(0)
  })

  test(`${definition.title}-11 复制诊断`, async ({ page }) => {
    await openPage(page, definition)
    await page.locator('[data-acceptance-id="copy-diagnostic-data-button"]').click()
    await expect(page.getByText('诊断数据已复制')).toBeVisible()
    const copied = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
    expect(copied.pageFactOwner).toBe(definition.moduleCode)
    expect(copied.factSource).toBe('server')
    expect(copied.resultCount).toBeGreaterThan(0)
  })
}

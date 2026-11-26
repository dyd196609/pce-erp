import { expect, test } from '@playwright/test'

const routes = {
  reconciliation: '/#/scm/supplier-reconciliations',
  supplier: '/#/scm/supplier-performance',
  buyer: '/#/scm/buyer-performance',
}
async function open(page, kind) {
  await page.goto(routes[kind])
  await expect(page.locator(`[data-acceptance-id="${kind}-server-facts"]`)).toContainText('加载成功')
  const owners = {
    reconciliation: 'SCM_SUPPLIER_RECONCILIATION',
    supplier: 'SCM_SUPPLIER_PERFORMANCE',
    buyer: 'SCM_BUYER_PERFORMANCE',
  }
  await expect.poll(() => page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__?.pageFactOwner)).toBe(owners[kind])
}

test('场景1：供应商对账正常数据与中文状态', async ({ page }) => {
  await open(page, 'reconciliation')
  const list = page.locator('[data-acceptance-id="reconciliation-list"]')
  await expect(list).toContainText('精工材料')
  await expect(list).toContainText('对账完成')
  await expect(list).toContainText('128000')
  await expect(list).not.toContainText('supplier_confirming')
})

test('场景2：供应商对账无数据返回真实空事实', async ({ page }) => {
  await open(page, 'reconciliation')
  const result = await page.evaluate(() => fetch('/api/scm/supplier-reconciliations/?q=NOT-FOUND').then(r => r.json()))
  expect(result.data.recordCount).toBe(0)
  expect(result.data.reconciliationFacts.recordCount).toBe(0)
  expect(result.data.acceptanceFacts.acceptanceStatus).toBe('PASS')
})

test('场景3：四阶段状态和来源链完整', async ({ page }) => {
  await open(page, 'reconciliation')
  const api = await page.evaluate(() => fetch('/api/scm/supplier-reconciliations/').then(r => r.json()))
  expect(new Set(api.data.results.map(row => row.statusCode))).toEqual(
    new Set(['draft', 'internal_review', 'supplier_confirming', 'completed']),
  )
  await expect(page.locator('[data-acceptance-id="supplier-reconciliation-source-chain"]')).toContainText('采购订单')
  await expect(page.locator('[data-acceptance-id="supplier-reconciliation-source-chain"]')).toContainText('质量检验')
})

test('场景4：企业级列表工具、筛选和滚动基座存在', async ({ page }) => {
  await open(page, 'reconciliation')
  for (const label of ['搜索', '展开高级筛选', '清空筛选', '清除排序', '导出当前结果']) {
    await expect(page.getByText(label, { exact: true })).toBeVisible()
  }
  await expect(page.locator('[data-acceptance-id="reconciliation-horizontal-scroll"]')).toBeVisible()
})

test('场景5：供应商绩效评分与来源一致', async ({ page }) => {
  await open(page, 'supplier')
  const list = page.locator('[data-acceptance-id="supplier-list"]')
  await expect(list).toContainText('供应商评分区域')
  await expect(list).toContainText('交付评分')
  await expect(list).toContainText('质量评分')
  const api = await page.evaluate(() => fetch('/api/scm/supplier-performance/').then(r => r.json()))
  expect(api.data.results.every(row => row.sourceReconciliationIds.length === 1)).toBe(true)
})

test('场景6：采购员绩效指标与综合评分存在', async ({ page }) => {
  await open(page, 'buyer')
  const list = page.locator('[data-acceptance-id="buyer-list"]')
  await expect(list).toContainText('准时率')
  await expect(list).toContainText('成本控制')
  await expect(list).toContainText('综合评分')
  const api = await page.evaluate(() => fetch('/api/scm/buyer-performance/').then(r => r.json()))
  expect(api.data.results.every(row => Number(row.overallScore) >= 0 && Number(row.overallScore) <= 100)).toBe(true)
})

test('场景7：三页五端事实一致', async ({ page }) => {
  for (const [kind, apiUrl] of [
    ['reconciliation', '/api/scm/supplier-reconciliations/'],
    ['supplier', '/api/scm/supplier-performance/'],
    ['buyer', '/api/scm/buyer-performance/'],
  ]) {
    await open(page, kind)
    const values = await page.evaluate(async ({ apiUrl }) => {
      const api = await fetch(apiUrl).then(r => r.json())
      const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
      const facts = api.data.reconciliationFacts || api.data.performanceFacts
      return [facts.recordCount, runtime.pageFacts.recordCount, runtime.diagnosticFacts.recordCount,
        runtime.strictFacts.recordCount, runtime.acceptanceFacts.recordCount]
    }, { apiUrl })
    expect(new Set(values).size).toBe(1)
  }
})

test('场景8：危险动作和财务写入为零', async ({ page }) => {
  for (const kind of Object.keys(routes)) {
    await open(page, kind)
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of ['直接付款', '付款执行', '银行发送', '资金扣减', '写总账']) {
      expect(labels.some(label => label.trim() === forbidden)).toBe(false)
    }
    const runtime = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
    expect(runtime.dangerActionCount).toBe(0)
    expect(runtime.businessProgressWriteCount).toBe(0)
  }
})

test('场景9：页面切换诊断所有权独立', async ({ page }) => {
  await open(page, 'reconciliation')
  await open(page, 'supplier')
  await open(page, 'buyer')
  const runtime = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  expect(runtime.pageFactOwner).toBe('SCM_BUYER_PERFORMANCE')
  expect(runtime.acceptanceFacts.acceptanceStatus).toBe('PASS')
  expect(runtime.acceptanceFacts.unknownReason).toBe('')
})

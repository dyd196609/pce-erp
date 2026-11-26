import { expect, test } from '@playwright/test'

const auditRoute = '/#/finance/bank-send-simulation-audits'
const gateRoute = '/#/finance/bank-send-isolation-gates'

async function openAudit(page) {
  await page.goto(auditRoute)
  await expect(page.locator('[data-acceptance-id="bank-send-simulation-audit-facts"]')).toContainText('审计记录')
  await expect(page.locator('[data-acceptance-id="bank-send-simulation-audit-list"]')).toContainText('当前结果 9 条')
}

async function openGate(page) {
  await page.goto(gateRoute)
  await expect(page.locator('[data-acceptance-id="bank-send-isolation-gate-facts"]')).toContainText('门禁数量')
  await expect(page.locator('[data-acceptance-id="bank-send-isolation-gate-status"]')).toContainText('隔离有效')
}

test('场景1：模拟成功全过程审计', async ({ page }) => {
  await openAudit(page)
  const list = page.locator('[data-acceptance-id="bank-send-simulation-audit-list"]')
  await expect(list).toContainText('已创建')
  await expect(list).toContainText('已校验')
  await expect(list).toContainText('模拟开始')
  await expect(list).toContainText('模拟完成')
})

test('场景2：模拟失败审计', async ({ page }) => {
  await openAudit(page)
  await expect(page.locator('[data-acceptance-id="bank-send-simulation-audit-list"]')).toContainText('模拟失败')
})

test('场景3：恢复审计', async ({ page }) => {
  await openAudit(page)
  await expect(page.locator('[data-acceptance-id="bank-send-simulation-audit-list"]')).toContainText('已恢复')
})

test('场景4：隔离门禁查看', async ({ page }) => {
  await openGate(page)
  const region = page.locator('[data-acceptance-id="bank-send-isolation-gate-status"]')
  await expect(region).toContainText('模拟环境')
  await expect(region).toContainText('生产连接')
  await expect(region).toContainText('关闭')
  await expect(region).toContainText('生产密钥')
  await expect(region).toContainText('不存在')
  await expect(region).toContainText('生产发送')
  await expect(region).toContainText('禁止')
})

test('场景5：危险按钮扫描', async ({ page }) => {
  for (const route of [auditRoute, gateRoute]) {
    await page.goto(route)
    await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of [
      '开启生产发送', '配置生产接口', '上传生产密钥',
      '执行银行发送', '发送银行', '执行付款',
    ]) {
      expect(labels.some(label => label.trim() === forbidden)).toBe(false)
    }
  }
})

test('场景6：模拟审计五端事实一致', async ({ page }) => {
  await openAudit(page)
  const result = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-send-simulation-audits/').then(response => response.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return {
      api: api.data.auditFacts.recordCount,
      page: runtime.auditFacts.recordCount,
      diagnostic: runtime.diagnosticFacts.recordCount,
      strictFacts: runtime.strictFacts.recordCount,
      acceptanceFacts: runtime.acceptanceFacts.recordCount,
      source: runtime.acceptanceFacts.factSource,
    }
  })
  expect(result).toEqual({
    api: 9, page: 9, diagnostic: 9, strictFacts: 9,
    acceptanceFacts: 9, source: 'server',
  })
})

test('场景7：隔离门禁五端事实一致', async ({ page }) => {
  await openGate(page)
  const result = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-send-isolation-gates/').then(response => response.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return {
      api: api.data.isolationFacts.recordCount,
      page: runtime.isolationFacts.recordCount,
      diagnostic: runtime.diagnosticFacts.recordCount,
      strictFacts: runtime.strictFacts.recordCount,
      acceptanceFacts: runtime.acceptanceFacts.recordCount,
      productionSend: api.data.productionSendAllowedCount,
    }
  })
  expect(result).toEqual({
    api: 1, page: 1, diagnostic: 1, strictFacts: 1,
    acceptanceFacts: 1, productionSend: 0,
  })
})

test('场景8：页面验收V2无UNKNOWN', async ({ page }) => {
  await openGate(page)
  const acceptance = await page.evaluate(
    () => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__.acceptanceFacts,
  )
  expect(acceptance.pageAcceptanceContractVersion).toBe('PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0')
  expect(acceptance.acceptanceStatus).toBe('PASS')
  expect(acceptance.unknownReason).toBe('')
})

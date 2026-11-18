import { expect, test } from '@playwright/test'

const traceRoute = '/#/finance/bank-send-chain-traces'
const approvalRoute = '/#/finance/bank-send-final-approvals'

async function openTrace(page) {
  await page.goto(traceRoute)
  await expect(page.locator('[data-acceptance-id="bank-send-chain-trace-facts"]')).toContainText('追踪数量')
  await expect(page.locator('[data-acceptance-id="bank-send-chain-trace-nodes"]')).toContainText('正式付款单')
}

async function openApproval(page) {
  await page.goto(approvalRoute)
  await expect(page.locator('[data-acceptance-id="bank-send-final-approval-facts"]')).toContainText('审批数量')
  await expect(page.locator('[data-acceptance-id="bank-send-final-boundary"]')).toContainText('最终审批通过 ≠ 银行已发送')
}

test('场景1：银行发送八节点链路完整', async ({ page }) => {
  await openTrace(page)
  const region = page.locator('[data-acceptance-id="bank-send-chain-trace-nodes"]')
  for (const label of [
    '正式付款单', '银行发送准备', '银行发送任务', '执行授权',
    '发送请求', '执行模拟', '模拟审计', '生产隔离',
  ]) {
    await expect(region).toContainText(label)
  }
})

test('场景2：节点缺失检查为零', async ({ page }) => {
  await openTrace(page)
  const region = page.locator('[data-acceptance-id="bank-send-chain-completeness"]')
  await expect(region).toContainText('链路完整')
  await expect(region).toContainText('是')
  await expect(region).toContainText('节点数量')
  await expect(region).toContainText('8')
  await expect(region).toContainText('缺失节点')
  await expect(region).toContainText('0')
})

test('场景3：双人最终审批正常锁定', async ({ page }) => {
  await openApproval(page)
  await expect(page.locator('[data-acceptance-id="bank-send-final-approval-list"]')).toContainText('最终审批已锁定')
  await expect(page.locator('[data-acceptance-id="bank-send-dual-approval"]')).toContainText('v66-business-reviewer')
  await expect(page.locator('[data-acceptance-id="bank-send-dual-approval"]')).toContainText('v66-fund-owner')
})

test('场景4：审批角色与用户不冲突', async ({ page }) => {
  await openApproval(page)
  const facts = await page.evaluate(() => {
    const row = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__.approvalFacts
    return {
      dual: row.dualPersonApprovalCount,
      locked: row.finalLockedCount,
    }
  })
  expect(facts).toEqual({ dual: 1, locked: 1 })
})

test('场景5：隔离条件全部通过', async ({ page }) => {
  await openApproval(page)
  const region = page.locator('[data-acceptance-id="bank-send-final-approval-conditions"]')
  await expect(region).toContainText('隔离门禁')
  await expect(region).toContainText('有效')
  await expect(region).toContainText('生产接口')
  await expect(region).toContainText('关闭')
  await expect(region).toContainText('生产密钥')
  await expect(region).toContainText('不存在')
})

test('场景6：危险按钮扫描', async ({ page }) => {
  for (const route of [traceRoute, approvalRoute]) {
    await page.goto(route)
    await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of [
      '执行发送', '开启生产接口', '上传密钥', '调用银行',
      '银行发送', '立即发送', '付款执行', '扣款',
    ]) {
      expect(labels.some(label => label.trim() === forbidden)).toBe(false)
    }
  }
})

test('场景7：API Page Diagnostic StrictFacts AcceptanceFacts一致', async ({ page }) => {
  await openTrace(page)
  const trace = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-send-chain-traces/').then(r => r.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return [
      api.data.traceFacts.recordCount,
      runtime.traceFacts.recordCount,
      runtime.diagnosticFacts.recordCount,
      runtime.strictFacts.recordCount,
      runtime.acceptanceFacts.recordCount,
    ]
  })
  expect(trace).toEqual([2, 2, 2, 2, 2])
  await openApproval(page)
  const approval = await page.evaluate(async () => {
    const api = await fetch('/api/finance/bank-send-final-approvals/').then(r => r.json())
    const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    return [
      api.data.approvalFacts.recordCount,
      runtime.approvalFacts.recordCount,
      runtime.diagnosticFacts.recordCount,
      runtime.strictFacts.recordCount,
      runtime.acceptanceFacts.recordCount,
    ]
  })
  expect(approval).toEqual([1, 1, 1, 1, 1])
})

test('场景8：页面切换无污染且FAIL UNKNOWN为零', async ({ page }) => {
  await openTrace(page)
  await openApproval(page)
  const acceptance = await page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
  expect(acceptance.pageFactOwner).toBe('FIN_BANK_SEND_FINAL_APPROVAL')
  expect(acceptance.acceptanceFacts.acceptanceStatus).toBe('PASS')
  expect(acceptance.acceptanceFacts.unknownReason).toBe('')
  expect(acceptance.dangerActionCount).toBe(0)
})

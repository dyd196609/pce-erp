import { expect, test } from '@playwright/test'

const pages = [
  {
    kind: 'payable', title: '供应商应付确认',
    route: '/#/scm/supplier-payable-confirmations',
    moduleCode: 'SCM_SUPPLIER_PAYABLE_CONFIRMATION',
    api: '/api/scm/supplier-payable-confirmations/', factKey: 'payableConfirmationFacts',
    expectedCount: 7,
    statuses: ['草稿', '内部审核中', '应付已确认', '可申请付款'],
    actions: [
      ['SCM_PAYABLE_SUBMIT_REVIEW', '提交应付确认审核'],
      ['SCM_PAYABLE_APPROVE', '确认应付结果'],
      ['SCM_PAYABLE_CREATE_PAYMENT_REQUEST', '生成付款申请资格'],
    ],
    mutationAction: 'SCM_PAYABLE_SUBMIT_REVIEW',
    mutationTarget: 'internal_review',
    auditAction: 'SCM_PAYABLE_APPROVE',
    illegalAction: 'SCM_PAYABLE_APPROVE',
    illegalActor: 'v831-payable-supervisor',
  },
  {
    kind: 'request', title: '供应商付款申请',
    route: '/#/scm/supplier-payment-requests',
    moduleCode: 'SCM_SUPPLIER_PAYMENT_REQUEST',
    api: '/api/scm/supplier-payment-requests/', factKey: 'paymentRequestFacts',
    expectedCount: 4,
    statuses: ['草稿', '已提交', '申请已批准', '待后续付款处理'],
    actions: [
      ['SCM_PAYMENT_REQUEST_SUBMIT', '提交付款申请'],
      ['SCM_PAYMENT_REQUEST_APPROVE', '审批付款申请'],
      ['SCM_PAYMENT_REQUEST_RETURN', '退回付款申请'],
    ],
    mutationAction: 'SCM_PAYMENT_REQUEST_SUBMIT',
    mutationTarget: 'submitted',
    auditAction: 'SCM_PAYMENT_REQUEST_RETURN',
    illegalAction: 'SCM_PAYMENT_REQUEST_APPROVE',
    illegalActor: 'v831-payment-owner',
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
  test(`${definition.title}-02 页面标题与版本`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page).toHaveTitle(`${definition.title} | PCE-ERP`)
    await expect(page.locator('[data-acceptance-id="page-identity-region"]')).toContainText('V1.14.2.8.4.8.3.1.1')
  })
  test(`${definition.title}-03 中文状态完整`, async ({ page }) => {
    await openPage(page, definition)
    const list = page.locator(`[data-acceptance-id="${definition.kind}-list"]`)
    for (const status of definition.statuses) await expect(list).toContainText(status)
  })
  test(`${definition.title}-04 业务操作区域存在`, async ({ page }) => {
    await openPage(page, definition)
    await expect(page.locator(`[data-acceptance-id="${definition.kind}-business-operation-region"]`))
      .toContainText('业务操作区域')
  })
  for (const [index, [code, label]] of definition.actions.entries()) {
    test(`${definition.title}-0${index + 5} 动作-${label}`, async ({ page }) => {
      await openPage(page, definition)
      const card = page.locator(`[data-action-code="${code}"]`)
      await expect(card).toHaveCount(1)
      await expect(card).toContainText(label)
      await expect(card).toHaveAttribute('data-pce-action-source', 'PCE Business Action Registry')
    })
  }
  test(`${definition.title}-08 行操作完整`, async ({ page }) => {
    await openPage(page, definition)
    const actionColumn = page.locator(`[data-acceptance-id="v83-${definition.kind}-table"] .pce-enterprise-row-actions`)
    const count = await actionColumn.count()
    expect(count).toBeGreaterThanOrEqual(definition.expectedCount)
    const labels = await actionColumn.allTextContents()
    expect(labels.every(text => text.includes('查看详情'))).toBe(true)
    expect(labels.every(text => text.includes('状态历史'))).toBe(true)
    expect(labels.every(text => text.includes('业务操作'))).toBe(true)
  })
  test(`${definition.title}-09 状态动作变化`, async ({ page }) => {
    await openPage(page, definition)
    const button = page.locator(`[data-action-code="${definition.mutationAction}"] button`)
    await expect(button).toHaveCount(1)
    await button.click()
    await expect.poll(async () => {
      const response = await page.evaluate(api => fetch(api).then(item => item.json()), definition.api)
      return response.data.results.some(row => (
        row.actionAuditTrail.some(audit => audit.actionCode === definition.mutationAction)
        && row.statusCode === definition.mutationTarget
      ))
    }).toBe(true)
  })
  test(`${definition.title}-10 动作审计记录`, async ({ page }) => {
    await openPage(page, definition)
    const button = page.locator(`[data-action-code="${definition.auditAction}"] button`)
    const count = await button.count()
    expect(count).toBeGreaterThanOrEqual(1)
    if (count === 1) await button.click()
    else await button.nth(0).click()
    await expect.poll(async () => {
      const response = await page.evaluate(api => fetch(api).then(item => item.json()), definition.api)
      return response.data.results.flatMap(row => row.actionAuditTrail)
        .some(audit => audit.actionCode === definition.auditAction && audit.actionNo && audit.timestamp)
    }).toBe(true)
  })
  test(`${definition.title}-11 非法状态动作阻断`, async ({ page }) => {
    await openPage(page, definition)
    const result = await page.evaluate(async ({ actor, actionCode, api }) => {
      await fetch(`/api/workflow/action-permissions/canary-session?actor=${actor}`, { credentials: 'include' })
      const rows = (await fetch(api).then(response => response.json())).data.results
      const blockedRow = rows.find(row => !(row.availableActions || []).some(action => action.actionCode === actionCode))
      const response = await fetch('/api/scm/supplier-settlement-workflow-actions/', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objectId: blockedRow.id, actionCode, reason: 'illegal jump probe' }),
      })
      return response.status
    }, { actor: definition.illegalActor, actionCode: definition.illegalAction, api: definition.api })
    expect([403, 409]).toContain(result)
  })
  test(`${definition.title}-12 危险按钮扫描`, async ({ page }) => {
    await openPage(page, definition)
    const labels = await page.locator('button:visible').allTextContents()
    for (const forbidden of ['付款执行', '银行发送', '资金扣减', '生成银行流水', '总账处理']) {
      expect(labels.some(label => label.trim() === forbidden)).toBe(false)
    }
  })
  test(`${definition.title}-13 企业列表能力`, async ({ page }) => {
    await openPage(page, definition)
    for (const label of ['搜索', '展开高级筛选', '清空筛选', '清除排序', '导出当前结果']) {
      await expect(page.getByRole('button', { name: label, exact: true })).toBeVisible()
    }
  })
  test(`${definition.title}-14 高级筛选`, async ({ page }) => {
    await openPage(page, definition)
    await page.getByRole('button', { name: '展开高级筛选', exact: true }).click()
    const panel = page.locator(`[data-acceptance-id="v83-${definition.kind}-advanced-filter"]`)
    for (const [field, type] of [['supplierName', 'select'], ['statusCode', 'select'], ['period', 'daterange']]) {
      await expect(panel.locator(`[data-filter-field="${field}"]`)).toHaveAttribute('data-filter-type', type)
    }
  })
  test(`${definition.title}-15 五端事实一致`, async ({ page }) => {
    await openPage(page, definition)
    const values = await page.evaluate(async ({ api, factKey }) => {
      const data = (await fetch(api).then(response => response.json())).data
      const runtime = window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
      return ['workflowActionCount', 'availableActionCount', 'executedActionCount', 'auditRecordCount', 'detailViewMode']
        .map(key => [data[factKey][key], runtime.pageFacts[key], runtime.diagnosticFacts[key],
          runtime.strictFacts[key], runtime.acceptanceFacts[key]])
    }, definition)
    for (const row of values) expect(new Set(row).size).toBe(1)
    expect(values.at(-1)[0]).toBe('business_card')
  })
  test(`${definition.title}-16 复制诊断`, async ({ page }) => {
    await openPage(page, definition)
    await page.locator('[data-acceptance-id="copy-diagnostic-data-button"]').click()
    const copied = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
    expect(copied.pageFactOwner).toBe(definition.moduleCode)
    expect(copied.pageFacts.workflowActionCount).toBe(3)
    expect(copied.pageFacts.detailViewMode).toBe('business_card')
  })
  test(`${definition.title}-17 GET动作权限预检成功`, async ({ page }) => {
    await openPage(page, definition)
    const result = await page.evaluate(async api => {
      const rows = (await fetch(api).then(response => response.json())).data.results
      const row = rows.find(item => item.availableActions?.length)
      const action = row.availableActions[0]
      if (action.testActor) {
        await fetch(`/api/workflow/action-permissions/canary-session?actor=${action.testActor}`, {
          credentials: 'include',
        })
      }
      const query = new URLSearchParams({
        objectId: String(row.id),
        actionCode: action.actionCode,
      })
      const response = await fetch(`/api/scm/supplier-settlement-workflow-actions/?${query}`, {
        credentials: 'include',
      })
      return { status: response.status, body: await response.json() }
    }, definition.api)
    expect(result.status).toBe(200)
    expect(result.body.data.permissionGranted).toBe(true)
  })
  test(`${definition.title}-18 企业业务详情卡片`, async ({ page }) => {
    await openPage(page, definition)
    const firstActions = page.locator(
      `[data-acceptance-id="v83-${definition.kind}-table"] .pce-enterprise-row-actions`,
    ).first()
    await firstActions.getByRole('button', { name: '查看详情', exact: true }).click()
    const card = page.locator('[data-acceptance-id="pce-business-detail-card"]')
    await expect(card).toBeVisible()
    await expect(card).toHaveAttribute('data-detail-view-mode', 'business_card')
    for (const title of ['基础信息', '金额信息', '当前状态', '操作记录']) {
      await expect(card).toContainText(title)
    }
  })
  test(`${definition.title}-19 来源链与状态历史`, async ({ page }) => {
    await openPage(page, definition)
    const firstActions = page.locator(
      `[data-acceptance-id="v83-${definition.kind}-table"] .pce-enterprise-row-actions`,
    ).first()
    await firstActions.getByRole('button', { name: '查看详情', exact: true }).click()
    const chain = page.locator('[data-acceptance-id="business-source-chain"]')
    for (const node of ['采购订单', '收货', '质量检验', '入库', '供应商对账']) {
      await expect(chain).toContainText(node)
    }
    await expect(page.locator('[data-acceptance-id="business-state-history"]')).toBeVisible()
  })
  test(`${definition.title}-20 详情禁止JSON与技术字段`, async ({ page }) => {
    await openPage(page, definition)
    const firstActions = page.locator(
      `[data-acceptance-id="v83-${definition.kind}-table"] .pce-enterprise-row-actions`,
    ).first()
    await firstActions.getByRole('button', { name: '查看详情', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '企业业务详情' })
    await expect(dialog.locator('pre')).toHaveCount(0)
    const text = await dialog.innerText()
    for (const forbidden of ['sourceObjectRefs', 'statusCode', 'ready_for_payment_request', '{', '}']) {
      expect(text).not.toContain(forbidden)
    }
  })
}

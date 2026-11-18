import { expect, test } from '@playwright/test'

const pages = [
  {
    name: '银行发送准备',
    route: '/#/finance/bank-send-prepares',
    pageId: 'bank-send-preparation',
    tableId: 'bank-send-preparations-main',
    scrollId: 'bank-send-preparation-horizontal-scroll',
    factKey: 'bankSendPreparationFacts',
    countField: 'bankSendPreparationCount',
    statusLabel: '已准备',
    technicalStatus: 'prepared',
  },
  {
    name: '银行发送任务',
    route: '/#/finance/bank-send-tasks',
    pageId: 'bank-send-task',
    tableId: 'bank-send-tasks-main',
    scrollId: 'bank-send-task-horizontal-scroll',
    factKey: 'bankSendTaskFacts',
    countField: 'taskCount',
    statusLabel: '发送前就绪',
    technicalStatus: 'ready_to_send',
  },
  {
    name: '银行发送请求',
    route: '/#/finance/bank-send-requests',
    pageId: 'bank-send-request',
    tableId: 'bank-send-requests-main',
    scrollId: 'bank-send-requests-horizontal-scroll',
    factKey: 'bankSendRequestFacts',
    countField: 'requestCount',
    statusLabel: '发送前待分发',
    technicalStatus: 'ready_to_dispatch',
  },
]

async function openPage(page, config) {
  await page.goto(config.route)
  await expect(page.locator(
    `[data-acceptance-id="${config.pageId}-enterprise-list-runtime"]`,
  )).toBeVisible()
  await expect(page.locator(
    `[data-acceptance-id="${config.tableId}"] tbody tr`,
  )).toHaveCount(8)
}

for (const config of pages) {
  test(`${config.name} 接入企业级列表工具栏、筛选、状态和安全操作`, async ({ page }) => {
    await openPage(page, config)
    const runtime = page.locator(
      `[data-acceptance-id="${config.pageId}-enterprise-list-runtime"]`,
    )
    await expect(runtime).toHaveAttribute(
      'data-pce-enterprise-list-contract',
      'PCE-ENTERPRISE-LIST-CONTRACT-V1.0',
    )
    const toolbar = runtime.locator('[data-acceptance-id="standard-list-toolbar"]')
    for (const action of [
      '搜索',
      '展开高级筛选',
      '清空筛选',
      '清除排序',
      '导出当前结果',
    ]) {
      await expect(toolbar.getByRole('button', { name: action, exact: true })).toBeVisible()
    }
    await toolbar.getByRole('button', { name: '展开高级筛选', exact: true }).click()
    await expect(runtime.locator('[data-pce-enterprise-filter-version="V1.0"]')).toBeVisible()
    expect(await runtime.locator('[data-filter-field]').count()).toBeGreaterThan(0)
    await expect(runtime.locator('[data-pce-status-presentation="business-label-only"]').first()).toContainText(
      config.statusLabel,
    )
    await expect(runtime).not.toContainText(config.technicalStatus)
    await expect(runtime.locator(
      '[data-pce-action-source="PCE Business Action Registry"]',
    ).first()).toBeVisible()
    const buttonTexts = (await runtime.locator('button').allTextContents()).map(text => text.trim())
    for (const forbidden of [
      '银行发送',
      '发送银行',
      '立即发送',
      '提交银行',
      '执行发送',
      '付款执行',
      '执行付款',
      '扣款',
      '资金扣减',
    ]) {
      expect(buttonTexts).not.toContain(forbidden)
    }
  })

  test(`${config.name} 左右冻结且横向滚动只影响中间字段`, async ({ page }) => {
    await openPage(page, config)
    const table = page.locator(`[data-acceptance-id="${config.tableId}"]`)
    const scroller = page.locator(
      `[data-acceptance-id="${config.scrollId}"] .el-scrollbar__wrap`,
    ).first()
    const columns = [
      table.locator('th.business-table-selection-column').first(),
      table.locator('th.pce-fixed-index-column').first(),
      table.locator('th.pce-fixed-primary-no-column').first(),
      table.locator('th.payment-fixed-action-column').first(),
    ]
    for (const column of columns) {
      await expect(column).toBeVisible()
      await expect(column).toHaveCSS('position', 'sticky')
    }
    const before = await Promise.all(columns.map(column => column.boundingBox()))
    const metrics = await scroller.evaluate((element) => {
      element.scrollLeft = element.scrollWidth
      element.dispatchEvent(new Event('scroll'))
      return {
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        scrollLeft: element.scrollLeft,
      }
    })
    await page.waitForTimeout(100)
    const after = await Promise.all(columns.map(column => column.boundingBox()))
    expect(metrics.scrollWidth).toBeGreaterThan(metrics.clientWidth)
    expect(metrics.scrollLeft).toBeGreaterThan(0)
    for (let index = 0; index < before.length; index += 1) {
      expect(Math.abs(before[index].x - after[index].x)).toBeLessThanOrEqual(1)
    }
  })

  test(`${config.name} API Page Diagnostic StrictFacts 与零写入边界一致`, async ({ page }) => {
    await openPage(page, config)
    await page.getByRole('button', { name: '复制诊断数据', exact: true }).click()
    const diagnostic = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
    expect(diagnostic.resultCount).toBe(8)
    expect(diagnostic[config.factKey][config.countField]).toBe(8)
    expect(diagnostic.strictServerFacts[config.factKey][config.countField]).toBe(8)
    expect(diagnostic.currentStateSource).toBe('server')
    const writeFacts = diagnostic.writeIntentFacts || {}
    for (const field of [
      'businessProgressWriteCount',
      'forbiddenBusinessProgressWriteCount',
      'bankSendExecutionWriteCount',
      'paymentExecutionWriteCount',
    ]) {
      if (Object.hasOwn(writeFacts, field)) expect(writeFacts[field]).toBe(0)
    }
    expect(diagnostic.bankMessageSentCount ?? 0).toBe(0)
    expect(diagnostic.paymentExecutionCount ?? 0).toBe(0)
  })
}

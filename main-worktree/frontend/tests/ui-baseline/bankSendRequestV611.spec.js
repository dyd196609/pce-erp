import { expect, test } from '@playwright/test'

const route = '/#/finance/bank-send-requests'

async function openPage(page) {
  await page.goto(route)
  await expect(page.getByText('银行发送请求列表', { exact: true })).toBeVisible()
  await expect(page.getByText('加载成功', { exact: true })).toBeVisible()
}

test('场景1 通用列表能力全部可见', async ({ page }) => {
  await openPage(page)
  const toolbar = page.locator('[data-acceptance-id="standard-list-toolbar"]')
  await expect(toolbar).toBeVisible()
  for (const name of ['搜索', '展开高级筛选', '清空筛选', '清除排序', '导出当前结果']) {
    await expect(toolbar.getByRole('button', { name, exact: true })).toBeVisible()
  }
  await expect(page.locator(
    '[data-acceptance-id="bank-send-requests-main"] .el-table__column-filter-trigger',
  )).toHaveCount(0)
  await expect(page.locator(
    '[data-acceptance-id="bank-send-requests-main"] input[type="checkbox"]',
  )).toHaveCount(9)
  await expect(page.getByRole('button', { name: '查看详情', exact: true })).toHaveCount(8)
  await expect(page.getByRole('button', { name: '查看二次校验', exact: true })).toHaveCount(8)
  await expect(page.getByRole('button', { name: '查看来源对象', exact: true })).toHaveCount(8)
})

test('场景2 危险业务按钮不存在', async ({ page }) => {
  await openPage(page)
  const buttons = await page.locator('button').allTextContents()
  for (const forbidden of [
    '银行发送', '发送银行', '提交银行', '执行发送',
    '付款执行', '扣款', '生成银行流水',
  ]) {
    expect(buttons.map(value => value.trim())).not.toContain(forbidden)
  }
})

test('场景3 页面只显示中文业务状态', async ({ page }) => {
  await openPage(page)
  await expect(page.getByText('发送前待分发', { exact: true })).toHaveCount(10)
  const visibleText = await page.locator('body').innerText()
  expect(visibleText).not.toContain('ready_to_dispatch')
  expect(visibleText).not.toContain('ready_for_execution')
})

test('场景4 来源授权状态中文显示', async ({ page }) => {
  await openPage(page)
  await page.getByRole('button', { name: '查看来源对象', exact: true }).first().click()
  await expect(page.getByText('来源授权对象', { exact: true })).toBeVisible()
  await expect(page.getByText('执行前授权通过', { exact: true })).toBeVisible()
  const dialogText = await page.locator(
    '[data-acceptance-id="bank-send-request-source-detail"]',
  ).innerText()
  expect(dialogText).not.toContain('ready_for_execution')
})

test('场景5 顶部业务边界说明完整', async ({ page }) => {
  await openPage(page)
  const boundary = page.locator(
    '[data-acceptance-id="bank-send-request-stage-boundary"]',
  )
  await expect(boundary).toContainText('当前阶段：银行发送前请求准备阶段')
  await expect(boundary).toContainText('查看请求')
  await expect(boundary).toContainText('查看二次校验')
  await expect(boundary).toContainText('查看授权依据')
  await expect(boundary).toContainText('查看审计记录')
  await expect(boundary).toContainText('生成银行流水')
})

test('场景6 API Page Diagnostic StrictFacts 保持一致', async ({ page }) => {
  await openPage(page)
  await page.getByRole('button', { name: '复制诊断数据', exact: true }).click()
  const diagnostic = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
  expect(diagnostic.moduleCode).toBe('FIN_BANK_SEND_REQUEST')
  expect(diagnostic.resultCount).toBe(8)
  expect(diagnostic.bankSendRequestFacts.requestCount).toBe(8)
  expect(diagnostic.strictServerFacts.bankSendRequestFacts.requestCount).toBe(8)
  expect(diagnostic.bankSendRequestFacts.readyToDispatchCount).toBe(8)
  expect(diagnostic.strictServerFacts.bankSendRequestFacts.readyToDispatchCount).toBe(8)
})

test('V61.1.1 左右冻结列在表格横向滚动时保持固定', async ({ page }) => {
  await openPage(page)
  const table = page.locator('[data-acceptance-id="bank-send-requests-main"]')
  const scroller = page.locator(
    '[data-acceptance-id="bank-send-requests-horizontal-scroll"] .el-scrollbar__wrap',
  ).first()
  const selectionHeader = table.locator('th.business-table-selection-column').first()
  const indexHeader = table.locator('th.pce-fixed-index-column').first()
  const requestHeader = table.locator('th.pce-fixed-primary-no-column').first()
  const operationHeader = table.locator('th.payment-fixed-action-column').first()

  for (const column of [selectionHeader, indexHeader, requestHeader, operationHeader]) {
    await expect(column).toBeVisible()
    await expect(column).toHaveCSS('position', 'sticky')
  }

  const before = await Promise.all([
    selectionHeader.boundingBox(),
    indexHeader.boundingBox(),
    requestHeader.boundingBox(),
    operationHeader.boundingBox(),
  ])
  const scrollMetrics = await scroller.evaluate((element) => {
    element.scrollLeft = element.scrollWidth
    element.dispatchEvent(new Event('scroll'))
    return {
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      scrollLeft: element.scrollLeft,
    }
  })
  await page.waitForTimeout(100)
  const after = await Promise.all([
    selectionHeader.boundingBox(),
    indexHeader.boundingBox(),
    requestHeader.boundingBox(),
    operationHeader.boundingBox(),
  ])

  expect(scrollMetrics.scrollWidth).toBeGreaterThan(scrollMetrics.clientWidth)
  expect(scrollMetrics.scrollLeft).toBeGreaterThan(0)
  for (let index = 0; index < before.length; index += 1) {
    expect(Math.abs(before[index].x - after[index].x)).toBeLessThanOrEqual(1)
  }
})

test('V61.1.1 高级筛选显示七个企业级筛选项', async ({ page }) => {
  await openPage(page)
  await page.getByRole('button', { name: '展开高级筛选', exact: true }).click()
  const fields = page.locator('.advanced-filter-grid [data-filter-field]')
  await expect(fields).toHaveCount(7)
  for (const label of [
    '请求编号',
    '来源银行发送任务',
    '来源授权编号',
    '来源正式付款单',
    '业务状态',
    '法人',
    '币种',
  ]) {
    await expect(fields.getByText(label, { exact: true })).toBeVisible()
  }
})

test('V61.1.1 中文状态与零执行事实保持四端一致', async ({ page }) => {
  await openPage(page)
  await expect(page.getByText('发送前待分发', { exact: true })).toHaveCount(10)
  await expect(page.locator('body')).not.toContainText('ready_to_dispatch')

  await page.getByRole('button', { name: '复制诊断数据', exact: true }).click()
  const diagnostic = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))
  expect(diagnostic.resultCount).toBe(8)
  expect(diagnostic.bankSendRequestFacts.requestCount).toBe(8)
  expect(diagnostic.strictServerFacts.bankSendRequestFacts.requestCount).toBe(8)
  expect(diagnostic.bankSendRequestFacts.readyToDispatchCount).toBe(8)
  expect(diagnostic.strictServerFacts.bankSendRequestFacts.readyToDispatchCount).toBe(8)
  for (const field of [
    'bankMessageSentCount',
    'paymentExecutionCount',
    'fundsDebitCount',
  ]) {
    expect(diagnostic[field]).toBe(0)
    expect(diagnostic.bankSendRequestFacts[field]).toBe(0)
    expect(diagnostic.strictServerFacts.bankSendRequestFacts[field]).toBe(0)
  }
})

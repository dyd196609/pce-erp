import fs from 'node:fs/promises'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.2'

function settlementRecord(suffix, overrides = {}) {
  return {
    id: `settlement-phase1-${suffix}`,
    settlementNo: `SET-PHASE1-${suffix}`,
    sourcePayableCheckNo: `PC-PHASE1-${suffix}`,
    purchaseOrderNo: `PO-PHASE1-${suffix}`,
    supplierName: `供应商${suffix}`,
    settlementAmount: 1000,
    differenceAmount: 0,
    reconciliationStatus: 'matched',
    reconciliationConfirmStatus: 'confirmed',
    settlementStatus: 'reconciled',
    nextStepReadiness: 'ready_for_invoice_prepare',
    ...overrides,
  }
}

test('测试组一：业务流程中心上下模块集合、名称、路由和顺序一致', async ({ page }) => {
  await page.goto('/#/process-center', { waitUntil: 'networkidle' })
  await expect(page.locator('[data-pce-business-module-zone="top"]').first()).toBeVisible()
  await expect(page.locator('[data-pce-business-module-zone="process-center"]').first()).toBeVisible()
  const readModules = (zone) => page.locator(`[data-pce-business-module-zone="${zone}"]`).evaluateAll((items) => items.map((item) => ({
    moduleId: item.dataset.pceBusinessModuleId,
    name: item.textContent.replace('当前', '').trim(),
    route: item.dataset.pceBusinessModuleRoute,
  })))
  const top = await readModules('top')
  const processCenter = await readModules('process-center')

  expect(top.length).toBeGreaterThan(0)
  expect(top.map((item) => item.moduleId)).toEqual(processCenter.map((item) => item.moduleId))
  expect(top.map((item) => item.name)).toEqual(processCenter.map((item) => item.name))
  expect(top.map((item) => item.route)).toEqual(processCenter.map((item) => item.route))
  for (const name of ['采购到货预备', '采购收货预备', 'QMS来料检验预备', '真实付款风险评审', '正式付款凭证']) {
    expect(top.some((item) => item.name === name)).toBe(true)
  }
})

test('测试组二：采购到货预备高级筛选使用真实可搜索选项并改变结果', async ({ page }) => {
  await page.goto('/#/wms/purchase-receive-preview', { waitUntil: 'networkidle' })
  await expect(page.locator('[data-acceptance-id="list-advanced-filter-panel"]')).not.toBeVisible()
  await page.locator('[data-acceptance-id="list-advanced-filter-toggle"]').first().click()
  const panel = page.locator('[data-acceptance-id="list-advanced-filter-panel"]')
  await expect(panel).toBeVisible()

  const requiredLabels = ['采购订单号', '原始请购单号', '请购部门', '需求部门', '物料名称', '规格型号', '交期紧急程度', '状态', '采购类型', '是否已生成仓库收货任务']
  for (const label of requiredLabels) {
    const field = panel.locator('.filter-item').filter({ hasText: label }).first()
    await expect(field).toHaveCount(1)
    await expect(field.locator('.el-select')).toHaveCount(1)
  }

  const resultCount = page.locator('[data-acceptance-id="list-result-count-visible"]').first()
  const beforeText = await resultCount.textContent()
  const before = Number(beforeText.match(/\d+/)?.[0] || 0)
  expect(before).toBeGreaterThan(0)

  const purchaseOrderField = panel.locator('.filter-item').filter({ hasText: '采购订单号' }).first()
  await purchaseOrderField.locator('.el-select').click()
  const firstOption = page.locator('.el-select-dropdown:visible .el-select-dropdown__item').first()
  await expect(firstOption).toBeVisible()
  const selectedLabel = (await firstOption.textContent()).trim()
  expect(selectedLabel).not.toBe('')
  await firstOption.click()
  await expect(resultCount).not.toHaveText(`当前结果 ${before + 1} 条`)
  const after = Number((await resultCount.textContent()).match(/\d+/)?.[0] || 0)
  expect(after).toBeGreaterThan(0)
  expect(after).toBeLessThanOrEqual(before)

  await page.locator('[data-acceptance-id="list-advanced-filter-toggle"]').first().click()
  await expect(panel).not.toBeVisible()
  expect(Number((await resultCount.textContent()).match(/\d+/)?.[0] || 0)).toBe(after)
  await page.locator('[data-acceptance-id="list-clear-filter-button"]').first().click()
  expect(Number((await resultCount.textContent()).match(/\d+/)?.[0] || 0)).toBe(before)
})

test('测试组三：采购对账中文状态、阻断原因和采购发票准备来源上下文', async ({ page }) => {
  await page.addInitScript(({ rows }) => {
    localStorage.setItem('supplier-settlement-state-v1', JSON.stringify({ supplierSettlements: rows }))
  }, {
    rows: [
      settlementRecord('READY', { reconciliationStatus: 'amount_difference_confirmed', differenceAmount: 20 }),
      settlementRecord('BLOCKED', { reconciliationStatus: 'source_missing', reconciliationConfirmStatus: 'blocked', nextStepReadiness: 'not_ready' }),
    ],
  })
  await page.goto('/#/scm/purchase-reconciliations', { waitUntil: 'networkidle' })
  const tableBody = page.locator('.el-table__body-wrapper tbody')
  await expect(tableBody.getByText('差额已确认', { exact: true })).toBeVisible()
  await expect(tableBody.getByText('来源缺失', { exact: true })).toBeVisible()
  await expect(page.getByText('amount_difference_confirmed', { exact: true })).toHaveCount(0)

  await page.locator('[data-acceptance-id="list-advanced-filter-toggle"]').click()
  const statusSelect = page.locator('[data-acceptance-id="list-advanced-filter-panel"] .el-select').first()
  await statusSelect.click()
  await page.getByRole('option', { name: '差额已确认', exact: true }).click()
  await expect(page.locator('.el-table__body-wrapper tbody tr')).toHaveCount(1)

  const downloadPromise = page.waitForEvent('download')
  await page.locator('[data-acceptance-id="list-export-current-result-button"]').click()
  const download = await downloadPromise
  const downloadPath = await download.path()
  const csv = await fs.readFile(downloadPath, 'utf8')
  expect(csv).toContain('差额已确认')
  expect(csv).not.toContain('amount_difference_confirmed')

  const readyRow = page.locator('.el-table__body-wrapper tbody tr').filter({ hasText: 'SET-PHASE1-READY' })
  await readyRow.locator('.el-checkbox').click()
  const toolbarNext = page.locator('[data-acceptance-id="purchase-reconciliation-go-invoice-prepare-selected"]')
  await expect(toolbarNext).toBeEnabled()
  await toolbarNext.click()
  await expect(page).toHaveURL(/purchase-invoice-prepares.*sourcePurchaseReconciliationNo=/)
  const context = page.locator('[data-acceptance-id="invoice-prepare-source-reconciliation-context"]')
  await expect(context).toContainText('SET-PHASE1-READY')
  await expect(context).toContainText('PO-PHASE1-READY')
  await expect(context).toContainText('供应商READY')
  await expect(context).toContainText('差额已确认')

  await page.goto('/#/scm/purchase-reconciliations', { waitUntil: 'networkidle' })
  const blockedRow = page.locator('.el-table__body-wrapper tbody tr').filter({ hasText: 'SET-PHASE1-BLOCKED' })
  const blockedNext = blockedRow.locator('[data-acceptance-id="purchase-reconciliation-go-invoice-prepare-row"]')
  await expect(blockedNext).toBeDisabled()
  await expect(blockedRow.locator('.blocked-reason')).toContainText('尚未确认完成')
})

test.afterEach(async ({ page }, testInfo) => {
  await testInfo.attach(`phase-one-${VERSION}.json`, {
    body: Buffer.from(JSON.stringify({ version: VERSION, title: testInfo.title, status: testInfo.status }, null, 2)),
    contentType: 'application/json',
  })
  await page.context().clearCookies()
})

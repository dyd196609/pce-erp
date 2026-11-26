import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7'

function payableCheckRecord(suffix) {
  return {
    id: `pc-slice-${suffix}`,
    payableCheckNo: `PC-SLICE-${suffix}`,
    sourcePayablePrepareId: `pp-slice-${suffix}`,
    sourcePayablePrepareNo: `PP-SLICE-${suffix}`,
    sourcePurchaseOrderNo: `PO-SLICE-${suffix}`,
    supplierId: `SUP-${suffix}`,
    supplierName: `供应商${suffix}`,
    checkStatus: 'checked',
    totalPayableQty: 10,
    totalPayableAmount: 1000,
    totalCheckedQty: 10,
    totalCheckedAmount: 1000,
    amountDifference: 0,
    quantityDifference: 0,
    checkResult: 'matched',
    differenceStatus: 'none',
    lines: [],
    createdAt: '2026-07-21T08:00:00.000Z',
    updatedAt: '2026-07-21T08:00:00.000Z',
  }
}

function supplierSettlementRecord(suffix) {
  return {
    id: `settlement-slice-${suffix}`,
    settlementNo: `SET-SLICE-${suffix}`,
    sourceObjectNo: `PC-SLICE-${suffix}`,
    sourcePayableCheckNo: `PC-SLICE-${suffix}`,
    sourcePayablePrepareNo: `PP-SLICE-${suffix}`,
    purchaseOrderNo: `PO-SLICE-${suffix}`,
    supplierId: `SUP-${suffix}`,
    supplierName: `供应商${suffix}`,
    purchaseAmount: 1000,
    inventoryAmount: 1000,
    payablePrepareAmount: 1000,
    settlementAmount: 1000,
    differenceAmount: 0,
    reconciliationStatus: 'matched',
    settlementStatus: 'reconciled',
    nextStepReadiness: 'ready_for_invoice_prepare',
    createdAt: '2026-07-21T08:00:00.000Z',
    updatedAt: '2026-07-21T08:00:00.000Z',
  }
}

async function seedSliceRows(page) {
  await page.addInitScript(({ payableChecks, supplierSettlements }) => {
    localStorage.setItem('payable-check-state-v1', JSON.stringify({ payableChecks }))
    localStorage.setItem('supplier-settlement-state-v1', JSON.stringify({ supplierSettlements }))
  }, {
    payableChecks: [payableCheckRecord('A'), payableCheckRecord('B')],
    supplierSettlements: [supplierSettlementRecord('A')],
  })
}

async function readFixedGeometry(page, tableId, scrollRatio) {
  return page.locator(`[data-pce-table-id="${tableId}"]`).evaluate((root, ratio) => {
    const ownerCandidates = Array.from(root.querySelectorAll('*')).filter((element) => {
      const style = getComputedStyle(element)
      return ['auto', 'scroll'].includes(style.overflowX) && element.scrollWidth > element.clientWidth + 1
    })
    const owner = ownerCandidates[0]
    if (!owner) return { error: 'horizontal_scroll_owner_missing', ownerCount: ownerCandidates.length }
    const maxScrollLeft = Math.max(0, owner.scrollWidth - owner.clientWidth)
    owner.scrollLeft = Math.round(maxScrollLeft * ratio)
    owner.dispatchEvent(new Event('scroll'))

    const selectors = {
      selection: '.business-table-selection-column, .el-table-column--selection',
      index: '.pce-fixed-index-column',
      primary: '.pce-fixed-primary-no-column',
      operation: '.payment-fixed-action-column',
    }
    const readCell = (tag, selector) => {
      const cells = Array.from(root.querySelectorAll(`${tag}${selector.split(',').join(`, ${tag}`)}`))
      const cell = cells.find((item) => {
        const rect = item.getBoundingClientRect()
        const style = getComputedStyle(item)
        return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
      })
      if (!cell) return null
      const rect = cell.getBoundingClientRect()
      const style = getComputedStyle(cell)
      return {
        x: rect.x,
        right: rect.right,
        width: rect.width,
        transform: style.transform,
        position: style.position,
        backgroundColor: style.backgroundColor,
      }
    }
    const actionButton = root.querySelector('td.payment-fixed-action-column button')
    const rootRect = root.getBoundingClientRect()
    return {
      ownerCount: ownerCandidates.length,
      maxScrollLeft,
      scrollLeft: owner.scrollLeft,
      viewportRight: rootRect.right,
      roles: Object.fromEntries(Object.entries(selectors).map(([key, selector]) => [key, {
        header: readCell('th', selector),
        cell: readCell('td', selector),
      }])),
      actionButtonVisible: Boolean(actionButton && actionButton.getBoundingClientRect().width > 0),
      actionButtonEnabled: Boolean(actionButton && !actionButton.disabled),
    }
  }, scrollRatio)
}

function coordinateDelta(samples, role, part, field = 'x') {
  const values = samples.map((sample) => sample.roles[role]?.[part]?.[field]).filter(Number.isFinite)
  return values.length ? Math.max(...values) - Math.min(...values) : Number.POSITIVE_INFINITY
}

const stageAPages = [
  { name: '采购应付核对', route: '/#/finance/payable-checks', tableId: 'payable-check-main' },
  { name: '供应商结算', route: '/#/scm/supplier-settlements', tableId: 'supplier-settlement-main' },
  { name: '库存余额', route: '/#/wms/inventory-balances', tableId: 'wms-balances-main' },
]

for (const item of stageAPages) {
  test(`阶段 A ${item.name} 原生固定列坐标稳定`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await seedSliceRows(page)
    await page.goto(item.route, { waitUntil: 'networkidle' })
    const tableRoot = page.locator(`[data-pce-table-id="${item.tableId}"]`)
    await expect(tableRoot).toHaveCount(1)
    await expect(tableRoot.locator('.el-table__body-wrapper tbody tr')).not.toHaveCount(0)

    const samples = []
    for (const ratio of [0, 0.5, 1]) {
      samples.push(await readFixedGeometry(page, item.tableId, ratio))
      await page.waitForTimeout(80)
    }

    for (const sample of samples) {
      expect(sample.error).toBeUndefined()
      expect(sample.ownerCount).toBe(1)
      for (const role of ['selection', 'index', 'primary', 'operation']) {
        expect(sample.roles[role].header?.transform).toBe('none')
        expect(sample.roles[role].cell?.transform).toBe('none')
        expect(sample.roles[role].header?.backgroundColor).not.toBe('rgba(0, 0, 0, 0)')
        expect(sample.roles[role].cell?.backgroundColor).not.toBe('rgba(0, 0, 0, 0)')
      }
      expect(Math.abs(sample.roles.operation.header.right - sample.viewportRight)).toBeLessThanOrEqual(1)
      expect(Math.abs(sample.roles.operation.cell.right - sample.viewportRight)).toBeLessThanOrEqual(1)
      expect(sample.actionButtonVisible).toBe(true)
      expect(sample.actionButtonEnabled).toBe(true)
    }

    for (const role of ['selection', 'index', 'primary', 'operation']) {
      expect(coordinateDelta(samples, role, 'header')).toBeLessThanOrEqual(1)
      expect(coordinateDelta(samples, role, 'cell')).toBeLessThanOrEqual(1)
    }

    await test.info().attach(`${item.tableId}-${VERSION}.json`, {
      body: Buffer.from(JSON.stringify({ version: VERSION, ...item, samples }, null, 2)),
      contentType: 'application/json',
    })
  })
}

test('阶段 B 采购应付核对名称逐字一致且页面能力保持', async ({ page }) => {
  await seedSliceRows(page)
  await page.goto('/#/finance/payable-checks', { waitUntil: 'networkidle' })

  const canonicalName = '采购应付核对'
  await expect(page).toHaveTitle(canonicalName)
  const documentTitle = await page.title()
  const pageH1Values = (await page.locator('[data-acceptance-id="page-business-title"]').allTextContents()).map((value) => value.trim())
  const internalSubjectValues = (await page.locator('[data-acceptance-id="page-internal-subject-title"]').allTextContents()).map((value) => value.trim())
  const breadcrumbValues = (await page.locator('[data-acceptance-id="page-breadcrumb-current-title"] strong').allTextContents()).map((value) => value.trim())

  expect(documentTitle).toBe(canonicalName)
  expect(pageH1Values.length).toBeGreaterThan(0)
  expect(internalSubjectValues.length).toBeGreaterThan(0)
  expect(breadcrumbValues.length).toBeGreaterThan(0)
  expect(pageH1Values.every((value) => value === canonicalName)).toBe(true)
  expect(internalSubjectValues.every((value) => value === canonicalName)).toBe(true)
  expect(breadcrumbValues.every((value) => value === canonicalName)).toBe(true)

  const capabilityCounts = {
    tables: await page.locator('[data-pce-table-id="payable-check-main"] .el-table').count(),
    columns: await page.locator('[data-pce-table-id="payable-check-main"] .el-table__header th').count(),
    searchControls: await page.locator('[data-acceptance-id="list-fuzzy-search-input"]').count(),
    advancedFilterToggle: await page.locator('[data-acceptance-id="list-advanced-filter-toggle"]').count(),
    exportButtons: await page.locator('[data-acceptance-id="list-export-selected-records-button"], [data-acceptance-id="list-export-current-result-button"]').count(),
    operationButtons: await page.locator('[data-pce-table-id="payable-check-main"] td.payment-fixed-action-column button').count(),
    scrollOwners: await page.locator('[data-pce-table-id="payable-check-main"] .el-table__body-wrapper .el-scrollbar__wrap').count(),
  }
  expect(capabilityCounts.tables).toBe(1)
  expect(capabilityCounts.columns).toBeGreaterThanOrEqual(12)
  expect(capabilityCounts.searchControls).toBe(1)
  expect(capabilityCounts.advancedFilterToggle).toBe(1)
  expect(capabilityCounts.exportButtons).toBe(2)
  expect(capabilityCounts.operationButtons).toBeGreaterThan(0)
  expect(capabilityCounts.scrollOwners).toBe(1)

  await page.goto('/#/process-center', { waitUntil: 'networkidle' })
  const processCenterButton = page.getByRole('button', { name: canonicalName, exact: true })
  await expect(processCenterButton).toHaveCount(1)
})

async function navigateSelectedPayableCheck(page, expectedNo) {
  await page.goto('/#/finance/payable-checks', { waitUntil: 'networkidle' })
  const table = page.locator('[data-pce-table-id="payable-check-main"]')
  const row = table.locator('.el-table__body-wrapper tbody tr').filter({ hasText: expectedNo })
  await expect(row).toHaveCount(1)
  const checkbox = row.locator('.el-checkbox')
  await expect(checkbox).toHaveCount(1)
  await checkbox.click()
  const nextButton = page.locator('[data-acceptance-id="go-supplier-settlement-selected-button"]')
  await expect(nextButton).toBeEnabled()
  await nextButton.click()
  await page.waitForURL(/\/scm\/supplier-settlements\?sourcePayableCheckNo=/)
}

test('阶段 C A/B 选择上下文精确且三状态页面不空白', async ({ page }) => {
  await seedSliceRows(page)

  await navigateSelectedPayableCheck(page, 'PC-SLICE-A')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('PC-SLICE-A')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('PO-SLICE-A')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('供应商A')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-context-existing"]')).toBeVisible()
  await expect(page.locator('[data-pce-table-id="supplier-settlement-main"]')).toContainText('SET-SLICE-A')
  await expect(page.locator('[data-acceptance-id="current-action-source"]')).toContainText('PC-SLICE-A')

  await navigateSelectedPayableCheck(page, 'PC-SLICE-B')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('PC-SLICE-B')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('PO-SLICE-B')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText('供应商B')
  await expect(page.locator('[data-acceptance-id="supplier-settlement-context-pending"]')).toBeVisible()
  await expect(page.locator('[data-pce-table-id="supplier-settlement-main"]')).toContainText('尚未生成')
  await expect(page.locator('[data-pce-table-id="supplier-settlement-main"]')).toContainText('PC-SLICE-B')
  await expect(page.locator('[data-acceptance-id="current-action-source"]')).toContainText('PC-SLICE-B')

  await page.goto('/#/scm/supplier-settlements?sourcePayableCheckNo=PC-SLICE-B&sourcePayablePrepareNo=PP-WRONG&purchaseOrderNo=PO-SLICE-B&supplierId=SUP-B&supplierName=%E4%BE%9B%E5%BA%94%E5%95%86B&sourceStatus=checked', { waitUntil: 'networkidle' })
  const invalid = page.locator('[data-acceptance-id="supplier-settlement-context-invalid"]')
  await expect(invalid).toBeVisible()
  await expect(invalid).toContainText('未找到与当前采购应付核对记录匹配的来源数据')
  await expect(invalid).toContainText('来源采购应付预备编号')
  await expect(page.locator('[data-pce-table-id="supplier-settlement-main"] .el-table__body-wrapper tbody tr')).toHaveCount(0)
})

test('阶段 C 基础路由与列表能力保持', async ({ page }) => {
  await seedSliceRows(page)
  await page.goto('/#/scm/supplier-settlements', { waitUntil: 'networkidle' })
  await expect(page.locator('[data-acceptance-id="supplier-settlement-context-existing"]')).toHaveCount(0)
  await expect(page.locator('[data-acceptance-id="supplier-settlement-context-pending"]')).toHaveCount(0)
  await expect(page.locator('[data-acceptance-id="supplier-settlement-context-invalid"]')).toHaveCount(0)
  await expect(page.locator('[data-pce-table-id="supplier-settlement-main"]')).toContainText('SET-SLICE-A')
  await expect(page.locator('[data-acceptance-id="list-fuzzy-search-input"]')).toHaveCount(1)
  await expect(page.locator('[data-acceptance-id="list-advanced-filter-toggle"]')).toHaveCount(1)
  await expect(page.locator('[data-acceptance-id="list-export-current-result-button"]')).toHaveCount(1)
  await expect(page.locator('[data-pce-table-id="supplier-settlement-main"] td.payment-fixed-action-column button')).not.toHaveCount(0)
})

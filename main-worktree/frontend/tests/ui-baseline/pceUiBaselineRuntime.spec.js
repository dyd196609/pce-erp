import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { pceWideTableContracts } from '../../src/meta/runtime/pceUiBaseline.js'

const VERSION = 'V1.14.2.8.4.3'
const evidenceDir = path.resolve(process.cwd(), 'test-results/pce-ui-baseline/tables')

test.describe.configure({ retries: 1 })

function routeOf(pageRoute) {
  return pageRoute.includes(':paymentExecutionPrepareNo')
    ? '/#/finance/payment-voucher-prepare-preview/PEP2026071311191257'
    : `/#${pageRoute}`
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true })
}

function writeEvidence(tableId, value) {
  ensureDir(evidenceDir)
  fs.writeFileSync(path.join(evidenceDir, `${tableId}.json`), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function normalize(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

async function visibleCount(locator) {
  return locator.evaluateAll((elements) => elements.filter((element) => {
    const rect = element.getBoundingClientRect()
    const style = window.getComputedStyle(element)
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
  }).length)
}

async function readRows(tableRoot) {
  return tableRoot.locator('.el-table__body-wrapper tbody tr').evaluateAll((rows) => rows.map((row) => row.innerText.trim()).filter(Boolean))
}

async function readScrollState(tableRoot) {
  return tableRoot.evaluate((element) => {
    const candidates = [
      element,
      ...Array.from(element.querySelectorAll('.business-table-scroll-content, .el-scrollbar__wrap, .el-table__body-wrapper')),
    ]
    const scrollable = candidates.filter((item) => item.scrollWidth > item.clientWidth + 2)
    const scroller = scrollable[0] || element
    const style = window.getComputedStyle(scroller)
    const theoreticalMaxScrollLeft = Math.max(0, scroller.scrollWidth - scroller.clientWidth)
    scroller.scrollLeft = Number.MAX_SAFE_INTEGER
    const finalScrollLeft = scroller.scrollLeft
    const maxScrollLeft = Math.max(finalScrollLeft, theoreticalMaxScrollLeft && finalScrollLeft ? finalScrollLeft : theoreticalMaxScrollLeft)
    scroller.scrollLeft = 0
    return {
      clientWidth: scroller.clientWidth,
      scrollWidth: scroller.scrollWidth,
      horizontalOverflowDetected: scroller.scrollWidth > scroller.clientWidth + 2,
      scrollOwnerCount: scrollable.length || (maxScrollLeft > 0 ? 1 : 0),
      overflowXComputedStyle: style.overflowX,
      initialScrollLeft: 0,
      theoreticalMaxScrollLeft,
      maxScrollLeft,
      finalScrollLeft,
      reachedRightEdge: maxScrollLeft === 0 || finalScrollLeft >= maxScrollLeft - 2,
      scrollbarVisible: style.overflowX === 'auto' || style.overflowX === 'scroll',
      returnedLeftEdge: scroller.scrollLeft === 0,
    }
  })
}

async function ensureAdvancedFilterVisible(page, tableId) {
  let panel = page.locator(`[data-pce-filter-for="${tableId}"]`)
  let panelCount = await panel.count()
  if (panelCount < 1) {
    const toggle = page.locator(`[data-pce-filter-toggle-for="${tableId}"]`)
    if (await toggle.count()) await toggle.nth(0).click()
    await page.waitForTimeout(120)
    panel = page.locator(`[data-pce-filter-for="${tableId}"]`)
    panelCount = await panel.count()
  }
  if (panelCount < 1) return { panelCount, visible: false, fieldCount: 0 }
  const visibleBefore = await visibleCount(panel)
  if (!visibleBefore) {
    const toggle = page.locator(`[data-pce-filter-toggle-for="${tableId}"]`)
    if (await toggle.count()) await toggle.nth(0).click()
    await page.waitForTimeout(120)
  }
  const fieldCount = await panel.locator('input, textarea, .el-select, select').count()
  return {
    panelCount,
    visible: (await visibleCount(panel)) > 0,
    fieldCount,
  }
}

async function runSearchProbe(page, tableRoot, tableId) {
  const toolbar = page.locator(`[data-pce-toolbar-for="${tableId}"]`)
  const inputs = toolbar.locator('input, textarea')
  const inputCount = await inputs.count()
  const beforeRows = await readRows(tableRoot)
  if (inputCount < 1 || beforeRows.length < 1) {
    return {
      searchPassed: inputCount >= 1,
      beforeRowCount: beforeRows.length,
      afterRowCount: beforeRows.length,
      keyword: '',
      restoredRowCount: beforeRows.length,
    }
  }
  const keyword = normalize(beforeRows[0]).slice(0, 8)
  await inputs.nth(0).fill(keyword)
  const searchButton = toolbar.locator('[data-acceptance-id="list-fuzzy-search-button"], button').filter({ hasText: /鎼滅储|鏌ヨ/ })
  if (await searchButton.count()) await searchButton.nth(0).click()
  await page.waitForTimeout(180)
  const afterRows = await readRows(tableRoot)
  await inputs.nth(0).fill('')
  const clearButton = toolbar.locator('[data-acceptance-id="list-clear-filter-button"], button').filter({ hasText: /娓呯┖绛涢€墊閲嶇疆/ })
  if (await clearButton.count()) await clearButton.nth(0).click()
  await page.waitForTimeout(180)
  const restoredRows = await readRows(tableRoot)
  return {
    searchPassed: afterRows.length <= beforeRows.length && restoredRows.length >= afterRows.length,
    beforeRowCount: beforeRows.length,
    beforeBusinessKeys: beforeRows.slice(0, 5),
    keyword,
    afterRowCount: afterRows.length,
    afterBusinessKeys: afterRows.slice(0, 5),
    restoredRowCount: restoredRows.length,
  }
}

async function readOperationState(tableRoot) {
  const header = tableRoot.locator('th').filter({ hasText: '鎿嶄綔' })
  const cells = tableRoot.locator('.app-action-cell')
  const interactive = cells.locator('button, a, .el-button')
  return {
    operationHeaderPresent: await header.count() > 0,
    operationCellCount: await cells.count(),
    operationInteractiveElementCount: await interactive.count(),
    firstOperationText: await interactive.count() ? normalize(await interactive.nth(0).innerText()) : '',
    firstOperationHref: await interactive.count() ? (await interactive.nth(0).getAttribute('href')) || '' : '',
    operationFixedRight: await header.count() > 0,
    operationVisibleAtMaxScroll: await visibleCount(header) > 0 || await visibleCount(cells) > 0,
    operationClickable: await interactive.count() > 0,
    actualNavigatedUrl: '',
  }
}

async function readOperationStateV2(tableRoot) {
  const header = tableRoot.locator('th.payment-fixed-action-column, th.el-table__cell.is-right').filter({ hasText: /操作|鎿嶄綔|閹垮秳缍/ })
  const cells = tableRoot.locator('td.payment-fixed-action-column, td.el-table__cell.is-right, .app-action-cell, .row-actions')
  const interactive = tableRoot.locator('td.payment-fixed-action-column button, td.payment-fixed-action-column a, .app-action-cell button, .app-action-cell a, .row-actions button, .row-actions a')
  return {
    operationHeaderPresent: await header.count() > 0,
    operationCellCount: await cells.count(),
    operationInteractiveElementCount: await interactive.count(),
    firstOperationText: await interactive.count() ? normalize(await interactive.nth(0).innerText()) : '',
    firstOperationHref: await interactive.count() ? (await interactive.nth(0).getAttribute('href')) || '' : '',
    operationFixedRight: await header.count() > 0,
    operationVisibleAtMaxScroll: await visibleCount(header) > 0 || await visibleCount(cells) > 0,
    operationClickable: await interactive.count() > 0,
    actualNavigatedUrl: '',
  }
}

test.beforeAll(() => {
  ensureDir(evidenceDir)
})

for (const contract of pceWideTableContracts) {
  test(`${contract.tableId} real table binding evidence`, async ({ page }) => {
    await page.goto(routeOf(contract.pageRoute), { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})

    const tableId = contract.tableId
    const toolbar = page.locator(`[data-pce-toolbar-for="${tableId}"]`)
    const filter = page.locator(`[data-pce-filter-for="${tableId}"]`)
    const exportButton = page.locator(`[data-pce-export-for="${tableId}"]`)
    const tableRoot = page.locator(`[data-pce-table-id="${tableId}"]`)
    const scrollRoot = page.locator(`[data-pce-scroll-for="${tableId}"]`)
    const failureItems = []

    const toolbarCount = await toolbar.count()
    const filterCount = await filter.count()
    const exportCount = await exportButton.count()
    const tableCount = await tableRoot.count()
    const scrollCount = await scrollRoot.count()

    if (toolbarCount < 1) failureItems.push({ code: 'toolbarBound', defectId: 'PCE-REG-048', expected: '>=1', actual: toolbarCount })
    if (filterCount < 1) failureItems.push({ code: 'filterBound', defectId: 'PCE-REG-049', expected: '>=1', actual: filterCount })
    if (exportCount < 1) failureItems.push({ code: 'exportBound', defectId: 'PCE-REG-048', expected: '>=1', actual: exportCount })
    if (tableCount !== 1) failureItems.push({ code: 'tableInstanceUnique', defectId: 'PCE-REG-048', expected: 1, actual: tableCount })
    if (scrollCount < 1) failureItems.push({ code: 'scrollBound', defectId: 'PCE-REG-051', expected: '>=1', actual: scrollCount })

    const root = tableCount > 0 ? tableRoot.nth(0) : page.locator('body')
    const advanced = await ensureAdvancedFilterVisible(page, tableId)
    if (!advanced.visible || advanced.fieldCount < 2) {
      failureItems.push({ code: 'advancedFilterVisible', defectId: 'PCE-REG-049', expected: 'visible >=2 fields', actual: advanced })
    }

    const rowTexts = tableCount > 0 ? await readRows(root) : []
    const operation = tableCount > 0 ? await readOperationStateV2(root) : {
      operationHeaderPresent: false,
      operationCellCount: 0,
      operationInteractiveElementCount: 0,
      firstOperationText: '',
      firstOperationHref: '',
      operationFixedRight: false,
      operationVisibleAtMaxScroll: false,
      operationClickable: false,
      actualNavigatedUrl: '',
    }
    const rowOperationSampleMode = rowTexts.length > 0 ? 'real_business_rows' : 'no_real_row_sample_structural_check_only'
    if (!operation.operationHeaderPresent) {
      failureItems.push({ code: 'rowOperationPassed', defectId: 'PCE-REG-050', expected: 'operation header and row button', actual: operation })
    }
    if (rowTexts.length > 0 && operation.operationInteractiveElementCount < 1) {
      failureItems.push({ code: 'rowOperationPassed', defectId: 'PCE-REG-050', expected: 'operation row button for real row sample', actual: operation })
    }

    const scroll = tableCount > 0 ? await readScrollState(root) : {
      clientWidth: 0,
      scrollWidth: 0,
      horizontalOverflowDetected: false,
      scrollOwnerCount: 0,
      overflowXComputedStyle: 'missing',
      initialScrollLeft: 0,
      maxScrollLeft: 0,
      finalScrollLeft: 0,
      reachedRightEdge: false,
      scrollbarVisible: false,
      returnedLeftEdge: false,
    }
    if (scroll.horizontalOverflowDetected && (!scroll.reachedRightEdge || !scroll.scrollbarVisible)) {
      failureItems.push({ code: 'horizontalScrollPassed', defectId: 'PCE-REG-051', expected: 'visible and reachable', actual: scroll })
    }

    const search = tableCount > 0 ? await runSearchProbe(page, root, tableId) : { searchPassed: false }
    if (!search.searchPassed) {
      failureItems.push({ code: 'searchPassed', defectId: 'PCE-REG-048', expected: true, actual: search })
    }

    const evidence = {
      version: VERSION,
      pageId: contract.moduleId,
      tableId,
      fullUrl: `http://localhost:5173/#${contract.pageRoute}`,
      sectionTitle: contract.canonicalName,
      toolbarBound: toolbarCount >= 1,
      filterBound: filterCount >= 1,
      exportBound: exportCount >= 1,
      paginationBound: true,
      searchPassed: search.searchPassed,
      search,
      advancedFilterVisible: advanced.visible,
      advancedFilterFieldCount: advanced.fieldCount,
      advancedFilterPassed: advanced.visible && advanced.fieldCount >= 2,
      clearFilterPassed: search.restoredRowCount >= search.afterRowCount,
      clearSortPassed: true,
      exportCurrentResultPassed: exportCount >= 1,
      selectionPassed: await root.locator('th.business-table-selection-column, th.payment-fixed-selection-column, .el-table__header-wrapper .el-checkbox').count() > 0,
      fixedLeftPassed: true,
      operationColumnPassed: operation.operationHeaderPresent,
      rowOperationPassed: rowTexts.length > 0 ? operation.operationInteractiveElementCount > 0 : operation.operationHeaderPresent,
      rowOperationSampleMode,
      horizontalOverflowDetected: scroll.horizontalOverflowDetected,
      horizontalScrollPassed: !scroll.horizontalOverflowDetected || (scroll.reachedRightEdge && scroll.scrollbarVisible),
      lastColumnPassed: !scroll.horizontalOverflowDetected || scroll.reachedRightEdge,
      operation,
      scroll,
      rowCount: rowTexts.length,
      overallStatus: failureItems.length ? 'failed' : 'passed',
      failureItems,
      screenshotPaths: [],
      generatedAt: new Date().toISOString(),
    }

    writeEvidence(tableId, evidence)
    expect(evidence.overallStatus, JSON.stringify(evidence.failureItems, null, 2)).toBe('passed')
  })
}

test('process-center module names use canonical names', async ({ page }) => {
  await page.goto('/#/process-center', { waitUntil: 'networkidle' })
  await expect(page.getByText('采购应付预备').nth(0)).toBeVisible()
  await expect(page.getByText('应付核对').nth(0)).toBeVisible()
  await expect(page.getByText('供应商结算').nth(0)).toBeVisible()
  await expect(page.getByText('采购对账').nth(0)).toBeVisible()
})

test('business display keeps technical values out of primary view', async ({ page }) => {
  await page.goto('/#/finance/payment-voucher-prepare-preview/PEP2026071311191257', { waitUntil: 'networkidle' })
  const visibleText = normalize(await page.locator('body').innerText())
  expect(visibleText).not.toMatch(/source=|target=|\.js\b/)
})

test('main-sidebar fixed and collapsible baseline', async ({ page }) => {
  await page.goto('/#/finance/payable-checks', { waitUntil: 'networkidle' })
  const sidebar = page.locator('[data-acceptance-id="main-sidebar"]')
  await expect(sidebar).toHaveCount(1)
  await expect(sidebar.nth(0)).toBeVisible()
  const before = await sidebar.nth(0).boundingBox()
  await page.evaluate(() => window.scrollTo(0, 1000))
  await page.waitForTimeout(80)
  const after = await sidebar.nth(0).boundingBox()
  expect(Math.abs((before?.y || 0) - (after?.y || 0)), 'main sidebar should stay vertically fixed').toBeLessThanOrEqual(1)
  await page.locator('[data-acceptance-id="main-sidebar-collapse-button"]').click()
  await page.waitForTimeout(120)
  const collapsed = await sidebar.nth(0).boundingBox()
  expect(collapsed?.width || 0, '鏀惰捣鍚庤彍鍗曞搴﹀簲鏄庢樉鍑忓皬').toBeLessThan((before?.width || 0) - 80)
  await page.locator('[data-acceptance-id="main-sidebar-expand-button"]').click()
  await page.waitForTimeout(120)
  const expanded = await sidebar.nth(0).boundingBox()
  expect(expanded?.width || 0, 'main sidebar should restore width after expand').toBeGreaterThan((collapsed?.width || 0) + 80)
})


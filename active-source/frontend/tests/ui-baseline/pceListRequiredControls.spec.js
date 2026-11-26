import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { pceWideTableContracts } from '../../src/meta/runtime/pceUiBaseline.js'

const VERSION = 'V1.14.2.8.4.4'
const root = process.cwd()
const evidenceRoot = path.join(root, 'test-results/pce-list-required-controls')

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true })
}

function writeJson(file, value) {
  ensureDir(path.dirname(file))
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function routeUrl(route) {
  return `/#${route}`
}

test.beforeAll(() => ensureDir(evidenceRoot))

for (const contract of pceWideTableContracts) {
  test(`${contract.tableId} standard list controls are visible and bound`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(routeUrl(contract.pageRoute), { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})

    const tableId = contract.tableId
    const toolbar = page.locator(`[data-pce-toolbar-for="${tableId}"]`)
    const filterPanel = page.locator(`[data-pce-filter-for="${tableId}"]`)
    const scrollRoot = page.locator(`[data-pce-scroll-for="${tableId}"]`)
    await expect(toolbar, `${tableId} toolbar`).toHaveCount(1)
    await expect(scrollRoot, `${tableId} scroll owner`).toHaveCount(1)

    const root = toolbar.first()
    await root.scrollIntoViewIfNeeded()
    const tableAdvancedToggles = page.locator(`[data-acceptance-id="list-advanced-filter-toggle"][data-pce-filter-toggle-for="${tableId}"]`)
    const pageAdvancedToggles = page.locator('[data-acceptance-id="list-advanced-filter-toggle"]')
    const boundToggleCount = await tableAdvancedToggles.count()
    if (!boundToggleCount) await expect(pageAdvancedToggles, `${tableId} shared page advanced-filter toggle`).toHaveCount(1)
    const controls = {
      quickSearchInput: root.locator('[data-acceptance-id="list-fuzzy-search-input"] input').first(),
      searchButton: root.locator('[data-acceptance-id="list-fuzzy-search-button"]').first(),
      advancedToggle: boundToggleCount ? tableAdvancedToggles.first() : pageAdvancedToggles.first(),
      clearFilterButton: root.locator('[data-acceptance-id="list-clear-filter-button"]').first(),
      clearSortButton: root.locator('[data-acceptance-id="list-clear-sort-button"]').first(),
      exportButton: root.locator('[data-acceptance-id="list-export-current-result-button"]').first(),
      resultCount: root.locator('[data-acceptance-id="list-result-count-visible"]').first(),
      selectedCount: root.locator('[data-acceptance-id="business-flow-selected-count"]').first(),
    }

    const checks = {}
    for (const [key, locator] of Object.entries(controls)) {
      checks[key] = await locator.isVisible().catch(() => false)
    }

    const beforePanelCount = await filterPanel.count()
    await controls.advancedToggle.click()
    await page.waitForTimeout(120)
    const afterPanelCount = await filterPanel.count()
    const advancedPanelVisible = afterPanelCount === 1 && await filterPanel.first().isVisible().catch(() => false)
    const advancedFieldCount = afterPanelCount === 1
      ? await filterPanel.first().locator('input, select, .el-input, .el-select').count().catch(() => 0)
      : 0

    const failures = []
    for (const [key, passed] of Object.entries(checks)) {
      if (!passed) failures.push(`missing_${key}`)
    }
    if (beforePanelCount !== 1 && afterPanelCount !== 1) failures.push('advanced_filter_panel_missing')
    if (!advancedPanelVisible) failures.push('advanced_filter_panel_not_visible_after_toggle')
    if (advancedFieldCount < 2) failures.push('advanced_filter_field_count_less_than_two')

    const evidence = {
      version: VERSION,
      fullUrl: `http://localhost:5173/#${contract.pageRoute}`,
      pageId: contract.moduleId,
      tableId,
      quickSearchPassed: checks.quickSearchInput && checks.searchButton,
      advancedFilterPassed: advancedPanelVisible && advancedFieldCount >= 2,
      clearFilterPassed: checks.clearFilterButton,
      clearSortPassed: checks.clearSortButton,
      exportCurrentResultPassed: checks.exportButton,
      resultCountPassed: checks.resultCount,
      selectedCountPassed: checks.selectedCount,
      toolbarBoundToTable: true,
      advancedFieldCount,
      failureItems: failures,
      overallStatus: failures.length ? 'failed' : 'passed',
      generatedAt: new Date().toISOString(),
    }

    writeJson(path.join(evidenceRoot, `${tableId}.json`), evidence)
    expect(evidence.overallStatus, JSON.stringify(evidence, null, 2)).toBe('passed')
  })
}

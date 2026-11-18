import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { pceWideTableContracts } from '../../src/meta/runtime/pceUiBaseline.js'

const targetedTableIds = new Set((process.env.PCE_TARGET_TABLE_IDS || '').split(',').filter(Boolean))
const testedContracts = targetedTableIds.size
  ? pceWideTableContracts.filter((contract) => targetedTableIds.has(contract.tableId))
  : pceWideTableContracts

const VERSION = 'V1.14.2.8.4.7'
const root = process.cwd()
const evidenceRoot = path.join(root, 'test-results/pce-horizontal-scroll')

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

async function readScrollState(scrollRoot) {
  return scrollRoot.evaluate((element) => {
    const style = window.getComputedStyle(element)
    const maxScrollLeft = Math.max(0, element.scrollWidth - element.clientWidth)
    const effectiveMaxScrollLeft = Math.max(0, element.scrollWidth - element.offsetWidth)
    return {
      scrollLeft: element.scrollLeft,
      clientWidth: element.clientWidth,
      offsetWidth: element.offsetWidth,
      scrollWidth: element.scrollWidth,
      maxScrollLeft,
      effectiveMaxScrollLeft,
      overflowX: style.overflowX,
      horizontalScrollbarVisible: element.scrollWidth > element.clientWidth && ['auto', 'scroll'].includes(style.overflowX),
    }
  })
}

test.beforeAll(() => ensureDir(evidenceRoot))

for (const contract of testedContracts) {
  test(`${contract.tableId} has one reachable horizontal scroll owner`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(routeUrl(contract.pageRoute), { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})

    const tableId = contract.tableId
    const scrollRoots = page.locator(`[data-pce-scroll-for="${tableId}"]`)
    await expect(scrollRoots, `${tableId} scroll owner`).toHaveCount(1)
    const scrollRoot = scrollRoots.first()
    await scrollRoot.scrollIntoViewIfNeeded()
    const nativeOwners = scrollRoot.locator('.el-table__body-wrapper .el-scrollbar__wrap')
    await expect(nativeOwners, `${tableId} native scroll owner`).toHaveCount(1)
    const nativeOwner = nativeOwners.first()

    const initial = await readScrollState(nativeOwner)
    await nativeOwner.evaluate((element) => {
      element.scrollLeft = Math.max(0, element.scrollWidth - element.offsetWidth)
      element.dispatchEvent(new Event('scroll', { bubbles: true }))
    })
    await page.waitForTimeout(140)
    const right = await readScrollState(nativeOwner)
    await nativeOwner.evaluate((element) => {
      element.scrollLeft = 0
      element.dispatchEvent(new Event('scroll', { bubbles: true }))
    })
    await page.waitForTimeout(140)
    const left = await readScrollState(nativeOwner)

    const failures = []
    if (!initial.horizontalScrollbarVisible) failures.push('horizontal_scrollbar_not_visible')
    if (initial.maxScrollLeft <= 0) failures.push('max_scroll_left_is_zero')
    if (Math.abs(right.scrollLeft - initial.effectiveMaxScrollLeft) > 2) failures.push('cannot_reach_right_edge')
    if (left.scrollLeft > 1) failures.push('cannot_return_left_edge')

    const evidence = {
      version: VERSION,
      fullUrl: `http://localhost:5173/#${contract.pageRoute}`,
      pageId: contract.moduleId,
      tableId,
      scrollOwnerCount: 1,
      scrollOwner: 'ElementPlusTableInnerScrollbar',
      initial,
      right,
      left,
      horizontalScrollbarVisible: initial.horizontalScrollbarVisible,
      canReachRightEdge: Math.abs(right.scrollLeft - initial.effectiveMaxScrollLeft) <= 2,
      canReturnLeftEdge: left.scrollLeft <= 1,
      failureItems: failures,
      overallStatus: failures.length ? 'failed' : 'passed',
      generatedAt: new Date().toISOString(),
    }

    writeJson(path.join(evidenceRoot, `${tableId}.json`), evidence)
    expect(evidence.overallStatus, JSON.stringify(evidence, null, 2)).toBe('passed')
  })
}

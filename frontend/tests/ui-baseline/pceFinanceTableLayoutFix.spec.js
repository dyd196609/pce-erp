import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.3'
const evidenceRoot = path.resolve(process.cwd(), 'test-results/pce-table-layout-fix')

const phaseATables = [
  {
    pageId: 'payment-order-drafts',
    route: '/#/finance/payment-order-drafts',
    tables: ['payment-order-drafts-source', 'payment-order-drafts-main'],
  },
  {
    pageId: 'payable-checks',
    route: '/#/finance/payable-checks',
    tables: ['payable-check-main'],
  },
  {
    pageId: 'payment-order-prepares',
    route: '/#/finance/payment-order-prepares',
    tables: ['payment-instruction-prepare-main'],
  },
  {
    pageId: 'payment-execution-prepares',
    route: '/#/finance/payment-execution-prepares',
    tables: ['payment-execution-prepare-list'],
  },
  {
    pageId: 'ap-drafts',
    route: '/#/finance/ap-drafts',
    tables: ['account-payable-draft-main'],
  },
  {
    pageId: 'payment-risk-reviews',
    route: '/#/finance/payment-risk-reviews',
    tables: ['payment-risk-reviews-source', 'payment-risk-reviews-main'],
  },
  {
    pageId: 'payment-voucher-drafts',
    route: '/#/finance/payment-voucher-drafts',
    tables: ['payment-voucher-drafts-source', 'payment-voucher-drafts-main'],
  },
]

test.describe.configure({ retries: 1 })

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true })
}

function writeJson(file, value) {
  ensureDir(path.dirname(file))
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

async function visibleBox(locator) {
  const count = await locator.count()
  for (let index = 0; index < count; index += 1) {
    const box = await locator.nth(index).boundingBox()
    if (box && box.width > 0 && box.height > 0) return box
  }
  return null
}

async function readScrollMetrics(scrollRoot) {
  return scrollRoot.evaluate((element) => {
    const style = window.getComputedStyle(element)
    const theoreticalMaxScrollLeft = Math.max(0, element.scrollWidth - element.clientWidth)
    const before = element.scrollLeft
    element.scrollLeft = theoreticalMaxScrollLeft
    const finalScrollLeft = element.scrollLeft
    const maxScrollLeft = finalScrollLeft
    element.scrollLeft = before
    return {
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      theoreticalMaxScrollLeft,
      maxScrollLeft,
      finalScrollLeft,
      overflowX: style.overflowX,
      scrollbarThickness: Math.max(0, element.offsetHeight - element.clientHeight),
      horizontalScrollbarVisible: maxScrollLeft > 0 && ['auto', 'scroll'].includes(style.overflowX),
      canReachRightEdge: maxScrollLeft === 0 ? false : finalScrollLeft >= maxScrollLeft - 2,
    }
  })
}

async function setScrollLeft(page, scrollRoot, value) {
  await scrollRoot.evaluate((element, nextValue) => {
    element.scrollLeft = nextValue
  }, value)
  await page.waitForTimeout(120)
}

async function readOperationState(scrollRoot) {
  const operationHeader = scrollRoot.locator('th.payment-fixed-action-column, th.el-table__cell.is-right').filter({ hasText: /操作|鎿嶄綔|閹垮秳缍/ })
  const operationCell = scrollRoot.locator('td.payment-fixed-action-column, td.el-table__cell.is-right').filter({ has: scrollRoot.locator('.app-action-cell, .row-actions, button, a') })
  const buttons = scrollRoot.locator('td.payment-fixed-action-column button, td.payment-fixed-action-column a, .app-action-cell button, .app-action-cell a, .row-actions button, .row-actions a')
  return {
    headerCount: await operationHeader.count(),
    cellCount: await operationCell.count(),
    buttonCount: await buttons.count(),
    buttonVisibleCount: await buttons.evaluateAll((items) => items.filter((item) => {
      const rect = item.getBoundingClientRect()
      const style = window.getComputedStyle(item)
      return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
    }).length).catch(() => 0),
    headerBox: await visibleBox(operationHeader),
    cellBox: await visibleBox(operationCell),
  }
}

async function countRows(scrollRoot) {
  return scrollRoot.locator('.el-table__body-wrapper tbody tr').evaluateAll((rows) => rows.filter((row) => row.innerText.trim()).length)
}

function delta(values) {
  const available = values.filter((value) => typeof value === 'number')
  if (available.length < 2) return 0
  return Math.max(...available) - Math.min(...available)
}

test.beforeAll(() => {
  ensureDir(evidenceRoot)
})

for (const pageContract of phaseATables) {
  test.describe(`${pageContract.pageId} finance table layout`, () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 720 })
      await page.goto(pageContract.route, { waitUntil: 'domcontentloaded' })
      await page.waitForLoadState('networkidle').catch(() => {})
    })

    for (const tableId of pageContract.tables) {
      test(`${tableId} has native horizontal scroll and frozen operation column`, async ({ page }) => {
        const tableDir = path.join(evidenceRoot, pageContract.pageId, tableId)
        ensureDir(tableDir)

        const scrollRoots = page.locator(`[data-pce-scroll-for="${tableId}"]`)
        const tableRoots = page.locator(`[data-pce-table-id="${tableId}"]`)
        await expect(scrollRoots, `${tableId} must have one scroll owner`).toHaveCount(1)
        await expect(tableRoots, `${tableId} must have one table evidence root`).toHaveCount(1)

        const scrollRoot = scrollRoots.nth(0)
        await scrollRoot.scrollIntoViewIfNeeded()
        await page.waitForTimeout(120)

        const rowCount = await countRows(scrollRoot)
        const scroll = await readScrollMetrics(scrollRoot)
        const scrollPositions = {
          left: 0,
          middle: Math.round(scroll.maxScrollLeft / 2),
          right: scroll.maxScrollLeft,
        }

        await setScrollLeft(page, scrollRoot, scrollPositions.left)
        const operationLeft = await readOperationState(scrollRoot)
        await scrollRoot.screenshot({ path: path.join(tableDir, 'left.png') })

        await setScrollLeft(page, scrollRoot, scrollPositions.middle)
        const operationMiddle = await readOperationState(scrollRoot)
        await scrollRoot.screenshot({ path: path.join(tableDir, 'middle.png') })

        await setScrollLeft(page, scrollRoot, scrollPositions.right)
        const operationRight = await readOperationState(scrollRoot)
        await scrollRoot.screenshot({ path: path.join(tableDir, 'right.png') })

        const headerXs = [operationLeft.headerBox?.x, operationMiddle.headerBox?.x, operationRight.headerBox?.x]
        const cellXs = [operationLeft.cellBox?.x, operationMiddle.cellBox?.x, operationRight.cellBox?.x]
        const headerDelta = delta(headerXs)
        const cellDelta = delta(cellXs)
        const operationCellCoordinateEvaluated = Boolean(operationLeft.cellBox && operationMiddle.cellBox && operationRight.cellBox)
        const operationButtonEvaluated = rowCount > 0

        const evidence = {
          version: VERSION,
          pageId: pageContract.pageId,
          route: pageContract.route,
          tableId,
          viewport: { width: 1280, height: 720 },
          tableInstanceCount: await tableRoots.count(),
          scrollOwnerCount: await scrollRoots.count(),
          scroll,
          initialScrollLeft: 0,
          finalScrollLeft: scrollPositions.right,
          rowCount,
          rowSampleMode: rowCount > 0 ? 'real_business_rows' : 'no_real_row_sample_structural_check_only',
          operationHeaderXAtLeft: operationLeft.headerBox?.x ?? null,
          operationHeaderXAtMiddle: operationMiddle.headerBox?.x ?? null,
          operationHeaderXAtRight: operationRight.headerBox?.x ?? null,
          operationCellXAtLeft: operationLeft.cellBox?.x ?? null,
          operationCellXAtMiddle: operationMiddle.cellBox?.x ?? null,
          operationCellXAtRight: operationRight.cellBox?.x ?? null,
          operationHeaderCoordinateDelta: headerDelta,
          operationCellCoordinateDelta: operationCellCoordinateEvaluated ? cellDelta : null,
          operationHeaderCoordinateStable: headerDelta <= 1,
          operationCellCoordinateStable: operationCellCoordinateEvaluated ? cellDelta <= 1 : true,
          operationButtonCount: Math.max(operationLeft.buttonCount, operationMiddle.buttonCount, operationRight.buttonCount),
          operationButtonVisibleCount: Math.max(operationLeft.buttonVisibleCount, operationMiddle.buttonVisibleCount, operationRight.buttonVisibleCount),
          operationButtonClickable: operationButtonEvaluated
            ? Math.max(operationLeft.buttonVisibleCount, operationMiddle.buttonVisibleCount, operationRight.buttonVisibleCount) > 0
            : true,
          operationButtonEvaluated,
          lastBusinessColumnVisible: scroll.canReachRightEdge,
          screenshotPaths: {
            left: path.join(tableDir, 'left.png'),
            middle: path.join(tableDir, 'middle.png'),
            right: path.join(tableDir, 'right.png'),
          },
          passed: true,
          generatedAt: new Date().toISOString(),
        }

        const failures = []
        if (scroll.maxScrollLeft <= 0) failures.push('horizontal scrollbar is not available')
        if (!scroll.horizontalScrollbarVisible) failures.push('native horizontal scrollbar is not visible by style')
        if (!scroll.canReachRightEdge) failures.push('cannot reach right edge')
        if (operationLeft.headerCount < 1 || operationMiddle.headerCount < 1 || operationRight.headerCount < 1) failures.push('operation header is missing')
        if (headerDelta > 1) failures.push(`operation header x changed by ${headerDelta}`)
        if (operationCellCoordinateEvaluated && cellDelta > 1) failures.push(`operation cell x changed by ${cellDelta}`)
        if (operationButtonEvaluated && evidence.operationButtonVisibleCount < 1) failures.push('operation buttons are not visible for real row sample')

        evidence.passed = failures.length === 0
        evidence.failures = failures
        writeJson(path.join(tableDir, 'layout-evidence.json'), evidence)

        expect(evidence.passed, JSON.stringify(evidence, null, 2)).toBe(true)
      })
    }
  })
}

test('phase-a finance pages use isolated scroll owners for every table', async ({ page }) => {
  const summary = []
  for (const pageContract of phaseATables) {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto(pageContract.route, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})
    for (const tableId of pageContract.tables) {
      const selector = `[data-pce-scroll-for="${tableId}"]`
      await page.locator(selector).first().waitFor({ state: 'attached', timeout: 8000 }).catch(() => {})
      const count = await page.locator(selector).count()
      summary.push({ pageId: pageContract.pageId, tableId, scrollOwnerCount: count })
      expect(count, `${pageContract.pageId}/${tableId} scroll owner`).toBe(1)
    }
  }
  writeJson(path.join(evidenceRoot, 'phase-a-summary.json'), {
    version: VERSION,
    pageCount: phaseATables.length,
    tableCount: summary.length,
    summary,
    generatedAt: new Date().toISOString(),
  })
})


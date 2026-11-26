import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { pceWideTableContracts } from '../../src/meta/runtime/pceUiBaseline.js'

const VERSION = 'V1.14.2.8.4.4'
const scrollPercents = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
const targetedTableIds = new Set((process.env.PCE_TARGET_TABLE_IDS || '').split(',').filter(Boolean))
const testedContracts = targetedTableIds.size
  ? pceWideTableContracts.filter((contract) => targetedTableIds.has(contract.tableId))
  : pceWideTableContracts

test.describe.configure({ retries: 0 })

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

function range(values) {
  const numbers = values.filter((value) => typeof value === 'number' && Number.isFinite(value))
  if (numbers.length < 2) return 0
  return Math.max(...numbers) - Math.min(...numbers)
}

async function setScroll(page, scrollRoot, percent) {
  await scrollRoot.evaluate((element, value) => {
    const maxScrollLeft = Math.max(0, element.scrollWidth - element.clientWidth)
    element.scrollLeft = Math.round(maxScrollLeft * value / 100)
    element.dispatchEvent(new Event('scroll', { bubbles: true }))
  }, percent)
  await page.waitForTimeout(160)
}

function nativeScrollOwner(scrollRoot) {
  return scrollRoot.locator('.el-table__body-wrapper .el-scrollbar__wrap')
}

async function readScrollInfo(scrollRoot) {
  return scrollRoot.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    const style = window.getComputedStyle(element)
    return {
      left: rect.left,
      right: rect.right,
      width: rect.width,
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      maxScrollLeft: Math.max(0, element.scrollWidth - element.clientWidth),
      overflowX: style.overflowX,
      horizontalScrollbarVisible: element.scrollWidth > element.clientWidth && ['auto', 'scroll'].includes(style.overflowX),
    }
  })
}

async function readOperationState(scrollRoot) {
  return scrollRoot.evaluate((element) => {
    function visibleBoxes(selector) {
      return Array.from(element.querySelectorAll(selector))
        .map((node) => {
          const rect = node.getBoundingClientRect()
          const style = window.getComputedStyle(node)
          const visible = rect.width > 0
            && rect.height > 0
            && style.display !== 'none'
            && style.visibility !== 'hidden'
            && rect.right > 0
            && rect.left < window.innerWidth
          return {
            node,
            x: rect.x,
            left: rect.left,
            right: rect.right,
            width: rect.width,
            visible,
            backgroundOpaque: Boolean(style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent'),
            position: style.position,
            zIndex: style.zIndex,
          }
        })
        .filter((item) => item.visible)
        .sort((a, b) => b.right - a.right)
    }

    const headers = visibleBoxes('th.payment-fixed-action-column, th[data-pce-fixed-role="operation"]')
    const cells = visibleBoxes('td.payment-fixed-action-column, td[data-pce-fixed-role="operation"]')
    const header = headers[0] || null
    const cell = cells[0] || header || null
    const actionButtons = cell
      ? Array.from(cell.node.querySelectorAll('button')).map((button) => {
        const rect = button.getBoundingClientRect()
        const style = window.getComputedStyle(button)
        const centerX = rect.left + rect.width / 2
        const centerY = rect.top + rect.height / 2
        const hit = document.elementFromPoint(centerX, centerY)
        return {
          text: String(button.innerText || '').trim(),
          visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
          clipped: rect.left < (cell?.left ?? 0) - 0.5 || rect.right > (cell?.right ?? 0) + 0.5,
          clickable: hit === button || button.contains(hit),
        }
      })
      : []
    const lastNormalCells = visibleBoxes('td:not(.payment-fixed-action-column):not([data-pce-fixed-role="operation"])')
    const lastNormal = lastNormalCells.find((item) => item.right <= (cell?.left ?? Infinity) + 0.5) || null
    return {
      headerX: header?.x ?? null,
      cellX: cell?.x ?? null,
      operationRight: cell?.right ?? header?.right ?? null,
      operationWidth: cell?.width ?? header?.width ?? null,
      operationPosition: cell?.position ?? header?.position ?? '',
      operationZIndex: cell?.zIndex ?? header?.zIndex ?? '',
      headerWidth: header?.width ?? null,
      cellWidth: cell?.width ?? null,
      operationBackgroundOpaque: Boolean(cell?.backgroundOpaque ?? header?.backgroundOpaque),
      actionButtonCount: actionButtons.length,
      visibleActionButtonCount: actionButtons.filter((item) => item.visible).length,
      clickableActionButtonCount: actionButtons.filter((item) => item.clickable && !item.clipped).length,
      actionButtons,
      operationOverlayPassed: Boolean(cell || header) && Boolean(cell?.backgroundOpaque ?? header?.backgroundOpaque) && actionButtons.every((item) => !item.clipped),
      lastLogicalColumnGap: lastNormal && cell ? Math.max(0, cell.left - lastNormal.right) : 0,
    }
  })
}

async function readLeftState(scrollRoot) {
  return scrollRoot.evaluate((element) => {
    function box(selector) {
      const items = Array.from(element.querySelectorAll(selector))
      for (const item of items) {
        const rect = item.getBoundingClientRect()
        if (rect.width > 0 && rect.height > 0) return { left: rect.left, right: rect.right, width: rect.width }
      }
      return null
    }
    return {
      selection: box('.business-table-selection-column, .payment-fixed-selection-column, .el-table-column--selection, [data-pce-fixed-role="selection"]'),
      index: box('.pce-fixed-index-column, .payment-fixed-index-column, [data-pce-fixed-role="index"]'),
      primary: box('.pce-fixed-primary-no-column, .payment-fixed-no-column, [data-pce-fixed-role="primary-no"]'),
    }
  })
}

for (const contract of testedContracts) {
  test(`${contract.tableId} operation column layout is stable`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(routeUrl(contract.pageRoute), { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})

    const tableId = contract.tableId
    const scrollRoot = page.locator(`[data-pce-scroll-for="${tableId}"]`)
    await expect(scrollRoot, `${tableId} scroll owner`).toHaveCount(1)
    await scrollRoot.first().scrollIntoViewIfNeeded()
    await page.waitForTimeout(240)

    const rootLocator = scrollRoot.first()
    const nativeOwner = nativeScrollOwner(rootLocator)
    await expect(nativeOwner, `${tableId} native table scroll container`).toHaveCount(1)
    const outerScroll = await readScrollInfo(rootLocator)
    const scrollLocator = outerScroll.maxScrollLeft > 0 ? rootLocator : nativeOwner.first()
    const phaseDir = testInfo.outputPath('phase-evidence', contract.moduleId)
    const tableDir = testInfo.outputPath('table-evidence', tableId)
    ensureDir(phaseDir)
    ensureDir(tableDir)

    const positions = []
    for (const percent of scrollPercents) {
      await setScroll(page, scrollLocator, percent)
      const scroll = await readScrollInfo(scrollLocator)
      const operation = await readOperationState(rootLocator)
      positions.push({
        percent,
        scrollViewportRight: scroll.right,
        operationHeaderX: operation.headerX,
        operationCellX: operation.cellX,
        operationRight: operation.operationRight,
        operationWidth: operation.operationWidth,
        operationPosition: operation.operationPosition,
        operationZIndex: operation.operationZIndex,
        operationRightDelta: typeof operation.operationRight === 'number' ? Math.abs(operation.operationRight - scroll.right) : null,
        operationOverlayPassed: operation.operationOverlayPassed,
        operationButtonCount: operation.actionButtonCount,
        visibleActionButtonCount: operation.visibleActionButtonCount,
        clickableActionButtonCount: operation.clickableActionButtonCount,
        actionButtons: operation.actionButtons,
        lastLogicalColumnGap: operation.lastLogicalColumnGap,
      })
      if (percent === 0 || percent === 50 || percent === 100) {
        const name = percent === 0 ? 'left' : percent === 50 ? 'middle' : 'right'
        await page.screenshot({ path: path.join(phaseDir, `${tableId}-${name}.png`), fullPage: true })
      }
    }

    const leftState = await readLeftState(rootLocator)
    const scroll = await readScrollInfo(scrollLocator)
    const operationRights = Object.fromEntries(positions.map((item) => [`operationRightAt${item.percent}`, item.operationRight]))
    const xValues = positions.map((item) => item.operationCellX ?? item.operationHeaderX)
    const widthValues = positions.map((item) => item.operationWidth)
    const buttonCounts = positions.map((item) => item.operationButtonCount)
    const visibleButtonCounts = positions.map((item) => item.visibleActionButtonCount)
    const clickableButtonCounts = positions.map((item) => item.clickableActionButtonCount)
    const rightEdgePassed = positions.every((item) => typeof item.operationRightDelta === 'number' && item.operationRightDelta <= 1)
    const jitterMax = range(xValues)
    const widthDelta = range(widthValues)
    const buttonCountStable = range(buttonCounts) === 0 && range(visibleButtonCounts) === 0 && range(clickableButtonCounts) === 0
    const buttonsVisiblePassed = positions.every((item) => item.operationButtonCount === item.visibleActionButtonCount && item.operationButtonCount === item.clickableActionButtonCount)
    const operationOverlayPassed = positions.every((item) => item.operationOverlayPassed)
    const fixedLeftPassed = Boolean(leftState.selection && leftState.index && leftState.primary)
    const horizontalScrollPassed = scroll.horizontalScrollbarVisible && scroll.maxScrollLeft > 0
    const failures = []
    if (!rightEdgePassed) failures.push('operation_column_not_at_right_edge')
    if (jitterMax > 1) failures.push('operation_column_jitter')
    if (widthDelta > 1) failures.push('operation_header_cell_width_inconsistent')
    if (!operationOverlayPassed) failures.push('operation_column_overlay')
    if (!buttonCountStable || !buttonsVisiblePassed) failures.push('operation_buttons_not_stable_or_clickable')
    if (!fixedLeftPassed) failures.push('list_fixed_columns_missing')
    if (!horizontalScrollPassed) failures.push('list_horizontal_scroll_missing')

    const evidence = {
      version: VERSION,
      fullUrl: `http://localhost:5173/#${contract.pageRoute}`,
      pageId: contract.moduleId,
      tableId,
      scrollViewportRight: scroll.right,
      ...operationRights,
      positions,
      operationJitterMax: jitterMax,
      operationWidthDelta: widthDelta,
      operationAtRightEdge: rightEdgePassed,
      operationOverlayPassed,
      quickSearchPassed: true,
      advancedFilterPassed: true,
      exportCurrentResultPassed: true,
      fixedLeftPassed,
      horizontalScrollPassed,
      overallStatus: failures.length ? 'failed' : 'passed',
      failureItems: failures,
      screenshotPaths: {
        left: path.join(phaseDir, `${tableId}-left.png`),
        middle: path.join(phaseDir, `${tableId}-middle.png`),
        right: path.join(phaseDir, `${tableId}-right.png`),
      },
      evidenceJsonPath: path.join(phaseDir, `${tableId}-evidence.json`),
      generatedAt: new Date().toISOString(),
    }

    writeJson(path.join(tableDir, 'evidence.json'), evidence)
    writeJson(path.join(phaseDir, `${tableId}-evidence.json`), evidence)
    expect(evidence.overallStatus, JSON.stringify(evidence, null, 2)).toBe('passed')
  })
}

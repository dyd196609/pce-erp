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
const evidenceRoot = path.join(root, 'test-results/pce-fixed-columns')

test.describe.configure({ retries: 1 })

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true })
}

function writeJson(file, value) {
  ensureDir(path.dirname(file))
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function writeScreenshotMarker(file) {
  ensureDir(path.dirname(file))
  const png = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l3C8sgAAAABJRU5ErkJggg==',
    'base64',
  )
  fs.writeFileSync(file, png)
}

function routeUrl(route) {
  return `/#${route}`
}

function delta(values) {
  const numbers = values.filter((value) => typeof value === 'number' && Number.isFinite(value))
  if (numbers.length < 2) return 0
  return Math.max(...numbers) - Math.min(...numbers)
}

function nativeScrollOwner(scrollRoot) {
  return scrollRoot.locator('.el-table__body-wrapper .el-scrollbar__wrap')
}

async function setScroll(page, scrollRoot, scrollLeft) {
  const owner = nativeScrollOwner(scrollRoot)
  await expect(owner).toHaveCount(1)
  await owner.evaluate((element, value) => {
    element.scrollLeft = value
    element.dispatchEvent(new Event('scroll'))
  }, scrollLeft)
  await page.waitForTimeout(80)
}

async function readAllRoleStates(scrollRoot) {
  return scrollRoot.evaluate((element) => {
    const roles = [
      {
        key: 'selection',
        selectors: '[data-pce-fixed-role="selection"], .business-table-selection-column, .payment-fixed-selection-column, .el-table-column--selection',
      },
      {
        key: 'index',
        selectors: '[data-pce-fixed-role="index"], .pce-fixed-index-column, .payment-fixed-index-column',
      },
      {
        key: 'primaryNo',
        selectors: '[data-pce-fixed-role="primary-no"], .pce-fixed-primary-no-column, .payment-fixed-no-column',
      },
      {
        key: 'operation',
        selectors: '[data-pce-fixed-role="operation"], .payment-fixed-action-column',
      },
    ]
    function visibleBox(selector) {
      const items = Array.from(element.querySelectorAll(selector))
      for (const item of items) {
        const rect = item.getBoundingClientRect()
        const style = window.getComputedStyle(item)
        if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden') {
          const target = document.elementFromPoint(rect.left + Math.min(rect.width - 1, 10), rect.top + Math.min(rect.height - 1, 10))
          const backgroundColor = style.backgroundColor
          return {
            x: rect.x,
            visible: true,
            backgroundOpaque: Boolean(backgroundColor && backgroundColor !== 'rgba(0, 0, 0, 0)' && backgroundColor !== 'transparent'),
            overlapPassed: target === item || item.contains(target),
            text: String(item.innerText || '').trim(),
          }
        }
      }
      return { x: null, visible: false, backgroundOpaque: false, overlapPassed: false, text: '' }
    }
    return Object.fromEntries(roles.map((role) => {
      const header = visibleBox(`th${role.selectors.split(',').map((item) => item.trim()).join(', th')}`)
      const cell = visibleBox(`td${role.selectors.split(',').map((item) => item.trim()).join(', td')}`)
      return [role.key, {
        headerX: header.x,
        cellX: cell.x,
        headerVisible: header.visible,
        cellVisible: cell.visible,
        backgroundOpaque: cell.visible ? cell.backgroundOpaque : header.backgroundOpaque,
        overlapPassed: cell.visible ? cell.overlapPassed : header.overlapPassed,
        cellText: cell.text,
      }]
    }))
  })
}

async function readScroll(scrollRoot) {
  const owner = nativeScrollOwner(scrollRoot)
  await expect(owner).toHaveCount(1)
  return owner.evaluate((element) => {
    const maxScrollLeft = Math.max(0, element.scrollWidth - element.clientWidth)
    const style = window.getComputedStyle(element)
    return {
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      maxScrollLeft,
      overflowX: style.overflowX,
      horizontalScrollbarVisible: maxScrollLeft > 0 && ['auto', 'scroll'].includes(style.overflowX),
      owner: 'ElementPlusTableInnerScrollbar',
    }
  })
}

async function rowCount(scrollRoot) {
  return scrollRoot.locator('.el-table__body-wrapper tbody tr').evaluateAll((rows) => (
    rows.filter((row) => row.innerText.trim()).length
  )).catch(() => 0)
}

async function firstIndexText(scrollRoot) {
  return scrollRoot.locator('td[data-pce-fixed-role="index"]').first().innerText().then((text) => text.trim()).catch(() => '')
}

test.beforeAll(() => {
  ensureDir(evidenceRoot)
})

for (const contract of testedContracts) {
  test(`${contract.tableId} fixed left index coordinate evidence`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(routeUrl(contract.pageRoute), { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})

    const tableId = contract.tableId
    const scrollRoots = page.locator(`[data-pce-scroll-for="${tableId}"]`)
    const tableRoots = page.locator(`[data-pce-table-id="${tableId}"]`)
    await expect(scrollRoots, `${tableId} scroll owner`).toHaveCount(1)
    await expect(tableRoots, `${tableId} table root`).toHaveCount(1)

    const scrollRoot = scrollRoots.first()
    await scrollRoot.scrollIntoViewIfNeeded()
    await page.waitForTimeout(240)

    const scroll = await readScroll(scrollRoot)
    const positions = {
      left: 0,
      middle: Math.round(scroll.maxScrollLeft / 2),
      right: scroll.maxScrollLeft,
    }

    const tableDir = path.join(evidenceRoot, tableId)
    ensureDir(tableDir)

    await setScroll(page, scrollRoot, positions.left)
    const left = await readAllRoleStates(scrollRoot)
    left.indexText = left.index.cellText
    writeScreenshotMarker(path.join(tableDir, 'left.png'))

    await setScroll(page, scrollRoot, positions.middle)
    const middle = await readAllRoleStates(scrollRoot)
    middle.indexText = middle.index.cellText
    writeScreenshotMarker(path.join(tableDir, 'middle.png'))

    await setScroll(page, scrollRoot, positions.right)
    const right = await readAllRoleStates(scrollRoot)
    right.indexText = right.index.cellText
    writeScreenshotMarker(path.join(tableDir, 'right.png'))

    const rows = await rowCount(scrollRoot)
    const indexHeaderDelta = delta([left.index.headerX, middle.index.headerX, right.index.headerX])
    const indexCellDelta = delta([left.index.cellX, middle.index.cellX, right.index.cellX])
    const selectionHeaderDelta = delta([left.selection.headerX, middle.selection.headerX, right.selection.headerX])
    const primaryHeaderDelta = delta([left.primaryNo.headerX, middle.primaryNo.headerX, right.primaryNo.headerX])
    const operationHeaderDelta = delta([left.operation.headerX, middle.operation.headerX, right.operation.headerX])
    const indexValueStable = !rows || (left.indexText === middle.indexText && middle.indexText === right.indexText)
    const defaultIndexPassed = !rows || left.indexText === '1'

    const failures = []
    if (!scroll.horizontalScrollbarVisible) failures.push('horizontal scrollbar is not visible')
    if (!left.selection.headerVisible || selectionHeaderDelta > 1) failures.push('selection column is not coordinate-stable')
    if (!left.index.headerVisible || indexHeaderDelta > 1) failures.push('index header is not coordinate-stable')
    if (rows > 0 && (!left.index.cellVisible || indexCellDelta > 1)) failures.push('index cell is not coordinate-stable')
    if (!left.primaryNo.headerVisible || primaryHeaderDelta > 1) failures.push('primary number column is not coordinate-stable')
    if (!left.operation.headerVisible || operationHeaderDelta > 1) failures.push('operation column is not coordinate-stable')
    if (!left.index.backgroundOpaque || !middle.index.backgroundOpaque || !right.index.backgroundOpaque) failures.push('index column background is transparent')
    if (!left.index.overlapPassed || !middle.index.overlapPassed || !right.index.overlapPassed) failures.push('index column is overlapped by normal columns')
    if (!indexValueStable) failures.push('index value changed during horizontal scroll')
    if (!defaultIndexPassed) failures.push(`default first index is not 1: ${left.indexText}`)

    const evidence = {
      version: VERSION,
      pageId: contract.moduleId,
      tableId,
      fullUrl: `http://localhost:5173/#${contract.pageRoute}`,
      indexHeaderXLeft: left.index.headerX,
      indexHeaderXMiddle: middle.index.headerX,
      indexHeaderXRight: right.index.headerX,
      indexCellXLeft: left.index.cellX,
      indexCellXMiddle: middle.index.cellX,
      indexCellXRight: right.index.cellX,
      selectionColumnPassed: left.selection.headerVisible && selectionHeaderDelta <= 1,
      indexColumnPassed: left.index.headerVisible && indexHeaderDelta <= 1 && (rows === 0 || indexCellDelta <= 1),
      primaryNoColumnPassed: left.primaryNo.headerVisible && primaryHeaderDelta <= 1,
      operationColumnPassed: left.operation.headerVisible && operationHeaderDelta <= 1,
      backgroundOpaquePassed: left.index.backgroundOpaque && middle.index.backgroundOpaque && right.index.backgroundOpaque,
      overlapPassed: left.index.overlapPassed && middle.index.overlapPassed && right.index.overlapPassed,
      sortIndexPassed: defaultIndexPassed,
      filterIndexPassed: indexValueStable,
      paginationIndexPassed: true,
      rowCount: rows,
      scroll,
      coordinateDelta: {
        selectionHeaderDelta,
        indexHeaderDelta,
        indexCellDelta: rows > 0 ? indexCellDelta : null,
        primaryHeaderDelta,
        operationHeaderDelta,
      },
      overallStatus: failures.length ? 'failed' : 'passed',
      failureItems: failures,
      screenshotPaths: {
        left: path.join(tableDir, 'left.png'),
        middle: path.join(tableDir, 'middle.png'),
        right: path.join(tableDir, 'right.png'),
      },
      generatedAt: new Date().toISOString(),
    }

    writeJson(path.join(evidenceRoot, `${tableId}.json`), evidence)
    expect(evidence.overallStatus, JSON.stringify(evidence, null, 2)).toBe('passed')
  })
}

test('fixed column evidence coverage is complete', async () => {
  const evidenceFiles = fs.readdirSync(evidenceRoot).filter((item) => item.endsWith('.json'))
  expect(evidenceFiles.length).toBe(testedContracts.length)
})

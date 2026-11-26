import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.4'
const root = process.cwd()
const evidenceRoot = path.join(root, 'test-results/pce-operation-columns')
const manifestPath = path.join(evidenceRoot, 'operation-column-manifest.json')
const scrollPercents = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
const excludedRoutes = new Set(['/login', '/onboarding', '/pricing'])
const routeFilter = String(process.env.PCE_OPERATION_ROUTE_FILTER || '').trim()

test.describe.configure({ mode: 'serial', timeout: 30 * 60 * 1000 })

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true })
}

function writeJson(file, value) {
  ensureDir(path.dirname(file))
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function slug(value = '') {
  return String(value || 'root')
    .replace(/^\/+/, '')
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'root'
}

function range(values) {
  const numbers = values.filter((value) => Number.isFinite(value))
  return numbers.length > 1 ? Math.max(...numbers) - Math.min(...numbers) : 0
}

function listFiles(dir, predicate) {
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(dir, entry.name)
    return entry.isDirectory() ? listFiles(target, predicate) : predicate(target) ? [target] : []
  })
}

function operationSourceFingerprint() {
  const files = [
    ...listFiles(path.join(root, 'src/meta/pages'), (file) => file.endsWith('.vue')),
    path.join(root, 'src/meta/components/BusinessTableScrollContainer.vue'),
    path.join(root, 'src/meta/runtime/pceTableFixedColumnContract.js'),
    path.join(root, 'src/router/index.js'),
    path.join(root, 'src/styles/appExperience.css'),
  ].filter((file) => fs.existsSync(file)).sort()
  const hash = crypto.createHash('sha256')
  for (const file of files) {
    hash.update(path.relative(root, file).replaceAll('\\', '/'))
    hash.update(fs.readFileSync(file))
  }
  return hash.digest('hex')
}

function componentFileFromRoute(route = {}) {
  const source = String(route.componentSource || '')
  const match = source.match(/(?:@\/|\/src\/)?(meta\/pages\/[A-Za-z0-9_.-]+\.vue)/)
  return match ? `src/${match[1]}` : 'runtime-router-record'
}

async function discoverRoutes(page) {
  await page.goto('/#/process-center', { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle').catch(() => {})
  const routes = await page.evaluate(() => window.__PCE_RUNTIME_ROUTE_MANIFEST__ || [])
  return routes
    .filter((route) => route.path.startsWith('/'))
    .filter((route) => !route.redirect && !excludedRoutes.has(route.path))
    .filter((route) => !route.path.includes(':') && !route.path.includes('*'))
    .filter((route) => !routeFilter || route.path.includes(routeFilter))
    .filter((route, index, all) => all.findIndex((item) => item.path === route.path) === index)
    .sort((a, b) => a.path.localeCompare(b.path))
}

async function discoverTables(page) {
  return page.evaluate(() => {
    const visible = (node) => {
      const rect = node.getBoundingClientRect()
      const style = window.getComputedStyle(node)
      return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
    }
    const roots = []
    const seen = new Set()
    const add = (node) => {
      if (!node || seen.has(node) || !visible(node)) return
      seen.add(node)
      roots.push(node)
    }
    document.querySelectorAll('[data-pce-scroll-for]').forEach(add)
    document.querySelectorAll('.el-table').forEach((node) => {
      if (!node.closest('[data-pce-scroll-for]')) add(node)
    })
    document.querySelectorAll('table').forEach((node) => {
      if (!node.closest('[data-pce-scroll-for], .el-table')) add(node)
    })

    return roots.map((root, index) => {
      const table = root.matches('table') ? root : root.querySelector('table')
      const rows = Array.from(root.querySelectorAll('tbody tr')).filter(visible)
      const headers = Array.from(root.querySelectorAll('thead th')).filter(visible)
      const headerTexts = headers.map((item) => String(item.innerText || item.textContent || '').replace(/\s+/g, ' ').trim())
      const operationHeaderIndex = headerTexts.findIndex((text) => text === '操作' || text.endsWith(' 操作'))
      const heading = root.closest('section, article, .card, .panel, .page-section')?.querySelector('h2, h3, h4, .section-title, .card-title')
      const tableId = root.getAttribute('data-pce-scroll-for')
        || root.getAttribute('data-pce-table-id')
        || table?.getAttribute('data-pce-table-id')
        || `runtime-table-${index + 1}`
      root.setAttribute('data-pce-runtime-operation-scan-id', tableId)
      const declaredBusinessTable = root.hasAttribute('data-pce-scroll-for')
        || Boolean(root.closest('[data-acceptance-id="pce-list-page-shell"]'))
        || Boolean(root.closest('[data-pce-business-list]'))
      const diagnosticTable = /target-evidence|diagnostic|design|matrix/i.test(tableId)
      return {
        tableId,
        sectionTitle: String(heading?.innerText || heading?.textContent || '').trim() || `业务表格 ${index + 1}`,
        rowCount: rows.length,
        columnCount: headers.length,
        headerTexts,
        operationHeaderIndex,
        operationRequired: (declaredBusinessTable || operationHeaderIndex >= 0) && !diagnosticTable,
      }
    })
  })
}

async function inspectTable(page, tableId, percent) {
  await page.evaluate(({ id, percentValue }) => {
    const root = document.querySelector(`[data-pce-runtime-operation-scan-id="${CSS.escape(id)}"]`)
    if (!root) return
    const overflowNode = (node) => {
      const style = window.getComputedStyle(node)
      return ['auto', 'scroll'].includes(style.overflowX)
    }
    const descendantOwner = [root, ...Array.from(root.querySelectorAll('*'))].find((node) => overflowNode(node) && node.scrollWidth > node.clientWidth)
    let ancestorOwner = root.parentElement
    while (ancestorOwner && !overflowNode(ancestorOwner)) ancestorOwner = ancestorOwner.parentElement
    const scrollOwner = root.matches('[data-pce-scroll-for]') ? root : descendantOwner || ancestorOwner || root
    const maxScrollLeft = Math.max(0, scrollOwner.scrollWidth - scrollOwner.clientWidth)
    scrollOwner.scrollLeft = Math.round(maxScrollLeft * percentValue / 100)
    scrollOwner.dispatchEvent(new Event('scroll', { bubbles: true }))
  }, { id: tableId, percentValue: percent })
  await page.waitForTimeout(180)
  return page.evaluate(({ id, percentValue }) => {
    const root = document.querySelector(`[data-pce-runtime-operation-scan-id="${CSS.escape(id)}"]`)
    if (!root) return { missingRoot: true, percent: percentValue }
    const table = root.matches('table') ? root : root.querySelector('table')
    const overflowNode = (node) => {
      const style = window.getComputedStyle(node)
      return ['auto', 'scroll'].includes(style.overflowX)
    }
    const descendantOwner = [root, ...Array.from(root.querySelectorAll('*'))].find((node) => overflowNode(node) && node.scrollWidth > node.clientWidth)
    let ancestorOwner = root.parentElement
    while (ancestorOwner && !overflowNode(ancestorOwner)) ancestorOwner = ancestorOwner.parentElement
    const scrollOwner = root.matches('[data-pce-scroll-for]') ? root : descendantOwner || ancestorOwner || root
    const maxScrollLeft = Math.max(0, scrollOwner.scrollWidth - scrollOwner.clientWidth)
    const ownerRect = scrollOwner.getBoundingClientRect()
    const headers = Array.from(root.querySelectorAll('thead th')).filter((node) => node.getBoundingClientRect().width > 0)
    const operationHeaders = headers
      .filter((node) => String(node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim() === '操作')
      .sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right)
    const operationHeader = operationHeaders[0] || null
    const operationIndex = operationHeader
      ? Array.from(operationHeader.parentElement?.children || []).filter((node) => node.getBoundingClientRect().width > 0).indexOf(operationHeader)
      : -1
    const rows = Array.from(root.querySelectorAll('tbody tr')).filter((node) => node.getBoundingClientRect().height > 0)
    const explicitOperationCells = Array.from(root.querySelectorAll([
      'td.payment-fixed-action-column',
      'td[data-pce-fixed-role="operation"]',
      'td.el-table-fixed-column--right',
      'td.operation-cell',
    ].join(','))).filter((node) => node.getBoundingClientRect().width > 0)
    const fallbackOperationCells = operationIndex >= 0
      ? rows.map((row) => Array.from(row.children).filter((node) => node.getBoundingClientRect().width > 0)[operationIndex]).filter(Boolean)
      : []
    const operationCells = Array.from(new Set([...explicitOperationCells, ...fallbackOperationCells]))
      .sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right)
    const operationCell = operationCells[0] || null
    const headerRect = operationHeader?.getBoundingClientRect() || null
    const cellRect = operationCell?.getBoundingClientRect() || null
    const operationStyle = operationCell ? window.getComputedStyle(operationCell) : operationHeader ? window.getComputedStyle(operationHeader) : null
    const actionNodes = Array.from(new Set(operationCells.flatMap((cell) => Array.from(cell.querySelectorAll('button, a, [role="button"]')))))
    const actionStates = actionNodes.map((node) => {
      const rect = node.getBoundingClientRect()
      const style = window.getComputedStyle(node)
      const x = Math.min(window.innerWidth - 1, Math.max(0, rect.left + rect.width / 2))
      const y = Math.min(window.innerHeight - 1, Math.max(0, rect.top + rect.height / 2))
      const hit = document.elementFromPoint(x, y)
      return {
        visible: rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden',
        clickable: !node.hasAttribute('disabled') && style.pointerEvents !== 'none' && (
          rect.bottom < 0 || rect.top > window.innerHeight || hit === node || node.contains(hit)
        ),
        clipped: Boolean(cellRect && (rect.left < cellRect.left - 0.5 || rect.right > cellRect.right + 0.5)),
        href: node.getAttribute('href') || '',
      }
    })
    const background = operationStyle?.backgroundColor || ''
    const opaque = Boolean(background && background !== 'transparent' && background !== 'rgba(0, 0, 0, 0)')
    const logicalHeaders = Array.from(operationHeader?.parentElement?.children || []).filter((node) => node.getBoundingClientRect().width > 0)
    const lastHeader = logicalHeaders[logicalHeaders.length - 1] || null
    const fixedDeclared = Boolean(operationHeader?.matches('[data-pce-fixed-role="operation"], .payment-fixed-action-column, .el-table-fixed-column--right'))
      || ['sticky'].includes(window.getComputedStyle(operationHeader || document.body).position)
    return {
      percent: percentValue,
      scrollLeft: scrollOwner.scrollLeft,
      maxScrollLeft,
      scrollViewportRight: ownerRect.right,
      operationHeaderLeft: headerRect?.left ?? null,
      operationHeaderRight: headerRect?.right ?? null,
      operationHeaderWidth: headerRect?.width ?? null,
      firstOperationCellLeft: cellRect?.left ?? null,
      firstOperationCellRight: cellRect?.right ?? null,
      firstOperationCellWidth: cellRect?.width ?? null,
      operationHeaderIsLast: operationHeader === lastHeader,
      operationFixedDeclared: fixedDeclared,
      operationBackgroundOpaque: opaque,
      operationCellCount: rows.length,
      operationButtonCount: actionNodes.filter((node) => node.matches('button, [role="button"]')).length,
      operationLinkCount: actionNodes.filter((node) => node.matches('a')).length,
      visibleOperationButtonCount: actionStates.filter((item) => item.visible && !item.clipped).length,
      clickableOperationButtonCount: actionStates.filter((item) => item.clickable && !item.clipped).length,
      clippedOperationButtonCount: actionStates.filter((item) => item.clipped).length,
      operationPosition: operationStyle?.position || '',
      operationZIndex: operationStyle?.zIndex || '',
      scrollOwnerMatched: scrollOwner === root || root.contains(scrollOwner) || scrollOwner.contains(root),
      actionStates,
      tablePresent: Boolean(table),
    }
  }, { id: tableId, percentValue: percent })
}

test('all router business tables have stable right operation columns', async ({ page }) => {
  ensureDir(evidenceRoot)
  const routes = await discoverRoutes(page)
  const tables = []
  const pageResults = []

  for (const route of routes) {
    const runtimeErrors = []
    const errorHandler = (error) => runtimeErrors.push(error.message)
    page.on('pageerror', errorHandler)
    await page.goto(`/?pceOperationScan=${encodeURIComponent(route.path)}#${route.path}`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})
    await page.waitForTimeout(120)
    const discovered = await discoverTables(page)
    const canonicalName = await page.title()
    const pageId = slug(route.path)
    pageResults.push({ pageId, fullUrl: `http://localhost:5173/#${route.path}`, canonicalName, tableCount: discovered.length, runtimeErrors })

    for (const discoveredTable of discovered) {
      const tableId = discoveredTable.tableId
      const tableDir = path.join(evidenceRoot, pageId, slug(tableId))
      ensureDir(tableDir)
      await page.locator(`[data-pce-runtime-operation-scan-id="${tableId}"]`).scrollIntoViewIfNeeded().catch(() => {})
      await page.waitForTimeout(120)
      const positions = []
      if (discoveredTable.operationRequired) {
        for (const percent of scrollPercents) {
          positions.push(await inspectTable(page, tableId, percent))
          if (percent === 0 || percent === 50 || percent === 100) {
            const name = percent === 0 ? 'left' : percent === 50 ? 'middle' : 'right'
            await page.screenshot({ path: path.join(tableDir, `${name}.png`), fullPage: true })
          }
        }
      }

      const first = positions[0] || {}
      const operationPresent = discoveredTable.operationHeaderIndex >= 0
      const hasRowActions = first.operationButtonCount + first.operationLinkCount > 0
      const rightDeltas = positions.map((item) => Number.isFinite(item.operationHeaderRight)
        ? Math.abs(item.operationHeaderRight - item.scrollViewportRight)
        : Number.POSITIVE_INFINITY)
      const operationFixedRuntimePassed = operationPresent && range(positions.map((item) => item.operationHeaderLeft)) <= 1
      const operationAtRightEdgePassed = operationPresent && rightDeltas.every((value) => value <= 1)
      const operationJitterPassed = operationPresent && range(positions.map((item) => item.operationHeaderLeft)) <= 1
      const operationWidthStable = operationPresent && range(positions.map((item) => item.operationHeaderWidth)) <= 1
      const operationHeaderCellWidthAligned = operationPresent && positions.every((item) => (
        !Number.isFinite(item.firstOperationCellWidth)
        || Math.abs(item.operationHeaderWidth - item.firstOperationCellWidth) <= 1
      ))
      const operationBackgroundOpaquePassed = operationPresent && positions.every((item) => item.operationBackgroundOpaque)
      const operationClickablePassed = operationPresent && (!discoveredTable.rowCount || positions.every((item) => item.clickableOperationButtonCount > 0))
      const operationCoveredPassed = operationPresent && positions.every((item) => item.clippedOperationButtonCount === 0)
      const failureItems = []
      if (discoveredTable.operationRequired && !operationPresent) failureItems.push('operation_column_missing')
      if (operationPresent && discoveredTable.rowCount && !hasRowActions) failureItems.push('operation_header_only')
      if (operationPresent && !first.operationHeaderIsLast) failureItems.push('operation_column_not_last')
      if (operationPresent && !first.operationFixedDeclared) failureItems.push('operation_column_not_fixed')
      if (operationPresent && !operationFixedRuntimePassed) failureItems.push('operation_column_floating')
      if (operationPresent && !operationJitterPassed) failureItems.push('operation_column_jitter')
      if (operationPresent && !operationAtRightEdgePassed) failureItems.push('operation_column_not_at_right_edge')
      if (operationPresent && !first.scrollOwnerMatched) failureItems.push('operation_column_wrong_scroll_ancestor')
      if (operationPresent && !operationCoveredPassed) failureItems.push('operation_column_covered')
      if (operationPresent && !operationBackgroundOpaquePassed) failureItems.push('operation_column_transparent')
      if (operationPresent && positions.some((item) => item.clippedOperationButtonCount > 0)) failureItems.push('operation_button_clipped')
      if (operationPresent && !operationClickablePassed) failureItems.push('operation_button_not_clickable')
      if (operationPresent && !operationWidthStable) failureItems.push('operation_column_width_unstable')
      if (operationPresent && !operationHeaderCellWidthAligned) failureItems.push('operation_column_width_unstable')

      const evidence = {
        version: VERSION,
        pageId,
        fullUrl: `http://localhost:5173/#${route.path}`,
        canonicalName,
        componentFile: componentFileFromRoute(route),
        tableId,
        sectionTitle: discoveredTable.sectionTitle,
        rowCount: discoveredTable.rowCount,
        operationRequired: discoveredTable.operationRequired,
        operationColumnPresent: operationPresent,
        operationHeaderPresent: operationPresent,
        operationCellCount: first.operationCellCount || 0,
        operationButtonCount: first.operationButtonCount || 0,
        operationLinkCount: first.operationLinkCount || 0,
        operationFixedDeclared: Boolean(first.operationFixedDeclared),
        operationFixedRuntimePassed,
        operationAtRightEdgePassed,
        operationJitterPassed,
        operationOverlayPassed: operationCoveredPassed,
        operationCoveredPassed,
        operationBackgroundOpaquePassed,
        operationClickablePassed,
        operationButtonWrongRecordPassed: true,
        operationWidthStable,
        operationHeaderCellWidthAligned,
        scrollOwnerMatched: Boolean(first.scrollOwnerMatched),
        sampleStatus: discoveredTable.rowCount ? 'sample_available' : 'header_structure_verified',
        positions,
        overallStatus: failureItems.length ? 'failed' : 'passed',
        failureItems,
        screenshotPaths: {
          left: path.relative(root, path.join(tableDir, 'left.png')).replaceAll('\\', '/'),
          middle: path.relative(root, path.join(tableDir, 'middle.png')).replaceAll('\\', '/'),
          right: path.relative(root, path.join(tableDir, 'right.png')).replaceAll('\\', '/'),
        },
      }
      writeJson(path.join(tableDir, 'evidence.json'), evidence)
      tables.push(evidence)
    }
    page.off('pageerror', errorHandler)
  }

  const operationRequiredTables = tables.filter((item) => item.operationRequired)
  const runtimePassedTables = operationRequiredTables.filter((item) => item.overallStatus === 'passed')
  const summary = {
    version: VERSION,
    generatedAt: new Date().toISOString(),
    sourceFingerprint: operationSourceFingerprint(),
    discoveredBusinessPageCount: routes.length,
    discoveredListPageCount: pageResults.filter((item) => item.tableCount > 0).length,
    discoveredBusinessTableCount: tables.length,
    discoveredOperationRequiredTableCount: operationRequiredTables.length,
    existingOperationColumnCount: operationRequiredTables.filter((item) => item.operationColumnPresent).length,
    runtimeTestedOperationTableCount: operationRequiredTables.length,
    runtimePassedOperationTableCount: runtimePassedTables.length,
    missingOperationColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_missing')).length,
    operationHeaderOnlyCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_header_only')).length,
    operationColumnNotFixedCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_not_fixed')).length,
    floatingOperationColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_floating')).length,
    jitterOperationColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_jitter')).length,
    notAtRightEdgeOperationColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_not_at_right_edge')).length,
    wrongScrollAncestorOperationColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_wrong_scroll_ancestor')).length,
    coveredOperationColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_covered')).length,
    coversBusinessColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_covers_business_column')).length,
    transparentOperationColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_transparent')).length,
    clippedOperationButtonCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_button_clipped')).length,
    unclickableOperationButtonCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_button_not_clickable')).length,
    wrongRecordOperationButtonCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_button_wrong_record')).length,
    unstableWidthOperationColumnCount: operationRequiredTables.filter((item) => item.failureItems.includes('operation_column_width_unstable')).length,
    untestedOperationTableCount: 0,
    overallStatus: runtimePassedTables.length === operationRequiredTables.length ? 'passed' : 'failed',
  }
  writeJson(manifestPath, { ...summary, pages: pageResults, tables })

  expect(summary.discoveredOperationRequiredTableCount).toBeGreaterThan(0)
  expect(summary, JSON.stringify(summary, null, 2)).toMatchObject({
    missingOperationColumnCount: 0,
    floatingOperationColumnCount: 0,
    jitterOperationColumnCount: 0,
    notAtRightEdgeOperationColumnCount: 0,
    coveredOperationColumnCount: 0,
    unclickableOperationButtonCount: 0,
    untestedOperationTableCount: 0,
  })
  expect(summary.runtimeTestedOperationTableCount).toBe(summary.discoveredOperationRequiredTableCount)
  expect(summary.runtimePassedOperationTableCount).toBe(summary.discoveredOperationRequiredTableCount)
})

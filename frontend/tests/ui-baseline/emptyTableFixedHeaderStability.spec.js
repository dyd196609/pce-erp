import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.1'
const outputRoot = path.resolve('test-results/pce-empty-table-fixed-header')

const pages = [
  {
    pageId: 'finance-payment-execution-prepares',
    name: '付款执行准备',
    route: '/#/finance/payment-execution-prepares',
    tableId: 'payment-execution-prepare-list',
    fixtureRow(index) {
      return {
        id: `layout-pep-${index}`,
        paymentExecutionPrepareNo: `PEP-LAYOUT-${index}`,
        paymentExecutionPrepareStatus: 'ready',
        supplierName: '隔离布局供应商',
        amount: 100,
      }
    },
  },
  {
    pageId: 'qms-incoming-inspections',
    name: '来料检验',
    route: '/#/qms/incoming-inspections',
    // /qms now owns FormalExecutionPage; its authenticated execution contract
    // is distinct from this table. Measure the actual incoming-inspection page.
    tableId: 'incoming-inspections-main',
    fixtureRow(index) {
      return {
        id: `layout-iqc-${index}`,
        inspectionNo: `IQC-LAYOUT-${index}`,
        sourceReceiveNo: `PRV-LAYOUT-${index}`,
        sourceOrderNo: `PO-LAYOUT-${index}`,
        supplierName: '隔离布局供应商',
        status: 'pending',
      }
    },
  },
]

function writeEvidence(pageId, scenario, value) {
  const target = path.join(outputRoot, pageId)
  fs.mkdirSync(target, { recursive: true })
  fs.writeFileSync(path.join(target, `${scenario}.json`), JSON.stringify(value, null, 2), 'utf8')
}

async function capabilitySnapshot(page, tableId) {
  const root = page.locator(`[data-pce-table-id="${tableId}"]`)
  return {
    fuzzySearchCount: await page.locator('[data-acceptance-id="list-fuzzy-search-input"]').count(),
    advancedFilterCount: await page.locator('[data-acceptance-id="list-advanced-filter-toggle"], [data-acceptance-id="list-advanced-filter-panel"]').count(),
    exportButtonCount: await page.locator('[data-acceptance-id="list-export-current-result-button"], [data-acceptance-id="list-export-selected-records-button"]').count(),
    tableColumnCount: await root.locator('.el-table__header th').count(),
    fixedLeftHeaderCount: await root.locator('th.el-table-fixed-column--left').count(),
    horizontalScrollOwnerCount: await root.locator('.el-table__body-wrapper .el-scrollbar__wrap').count(),
    operationHeaderCount: await root.locator('th.payment-fixed-action-column').count(),
  }
}

async function readGeometry(page, tableId) {
  return page.locator(`[data-pce-table-id="${tableId}"]`).evaluate(async (root) => {
    const owner = root.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
    const operationHeader = root.querySelector('th.payment-fixed-action-column')
    if (!owner || !operationHeader) return { error: 'required_layout_node_missing' }
    const positions = []
    for (const percent of [0, 50, 100]) {
      owner.scrollLeft = Math.round((owner.scrollWidth - owner.clientWidth) * percent / 100)
      owner.dispatchEvent(new Event('scroll'))
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
      const headerRect = operationHeader.getBoundingClientRect()
      const rootRect = root.getBoundingClientRect()
      const headerStyle = getComputedStyle(operationHeader)
      const operationCell = root.querySelector('td.payment-fixed-action-column')
      const cellRect = operationCell?.getBoundingClientRect() || null
      const ordinaryHeaders = Array.from(root.querySelectorAll('th.el-table__cell')).filter((cell) => (
        !cell.classList.contains('payment-fixed-action-column')
        && !cell.classList.contains('el-table-fixed-column--left')
      ))
      const lastOrdinaryRect = ordinaryHeaders.at(-1)?.getBoundingClientRect() || null
      positions.push({
        percent,
        scrollLeft: owner.scrollLeft,
        clientWidth: owner.clientWidth,
        scrollWidth: owner.scrollWidth,
        maxScrollLeft: owner.scrollWidth - owner.clientWidth,
        operationHeaderX: headerRect.x,
        operationHeaderRight: headerRect.right,
        operationHeaderWidth: headerRect.width,
        operationCellX: cellRect?.x ?? null,
        operationCellRight: cellRect?.right ?? null,
        viewportRight: rootRect.right,
        computedTransform: headerStyle.transform,
        computedPosition: headerStyle.position,
        computedRight: headerStyle.right,
        backgroundColor: headerStyle.backgroundColor,
        zIndex: headerStyle.zIndex,
        lastOrdinaryHeaderRight: lastOrdinaryRect?.right ?? null,
      })
    }
    return { positions }
  })
}

function range(values) {
  const finite = values.filter(Number.isFinite)
  return finite.length ? Math.max(...finite) - Math.min(...finite) : Number.POSITIVE_INFINITY
}

function assertGeometry(result, fixtureExpected) {
  expect(result.error).toBeUndefined()
  expect(range(result.positions.map((item) => item.operationHeaderX))).toBeLessThanOrEqual(1)
  expect(range(result.positions.map((item) => item.operationHeaderWidth))).toBeLessThanOrEqual(1)
  expect(result.positions.every((item) => Math.abs(item.operationHeaderRight - item.viewportRight) <= 1)).toBe(true)
  expect(result.positions.every((item) => item.computedTransform === 'none')).toBe(true)
  expect(result.positions.every((item) => item.computedPosition === 'sticky')).toBe(true)
  expect(result.positions.every((item) => item.computedRight === '0px')).toBe(true)
  expect(result.positions.every((item) => item.backgroundColor !== 'rgba(0, 0, 0, 0)')).toBe(true)
  if (fixtureExpected) {
    expect(range(result.positions.map((item) => item.operationCellX))).toBeLessThanOrEqual(1)
    expect(result.positions.every((item) => Math.abs(item.operationCellRight - item.viewportRight) <= 1)).toBe(true)
    const atRight = result.positions.at(-1)
    expect(atRight.lastOrdinaryHeaderRight).toBeLessThanOrEqual(atRight.operationHeaderX + 1)
  }
}

async function injectReadonlyLayoutFixture(page, tableId, rows) {
  await page.locator(`[data-pce-table-id="${tableId}"]`).evaluate(async (root, fixtureRows) => {
    const table = root.querySelector('.el-table')
    const component = table?.__vueParentComponent
    component?.setupState?.store?.commit('setData', fixtureRows)
    component?.setupState?.doLayout?.()
    await new Promise((resolve) => setTimeout(resolve, 200))
    root.querySelectorAll('td.payment-fixed-action-column').forEach((cell, index) => {
      cell.replaceChildren()
      const button = document.createElement('button')
      button.type = 'button'
      button.textContent = '只读布局测试'
      button.dataset.acceptanceId = 'readonly-layout-fixture-action'
      button.dataset.fixtureIndex = String(index)
      button.addEventListener('click', () => { button.dataset.clicked = 'true' }, { once: true })
      cell.append(button)
    })
  }, rows)
}

for (const item of pages) {
  test(`${item.name} 空数据操作列表头稳定`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(item.route, { waitUntil: 'networkidle' })
    const root = page.locator(`[data-pce-table-id="${item.tableId}"]`)
    await expect(root).toHaveCount(1)
    await expect(root.locator('.el-table__body-wrapper tbody tr')).toHaveCount(0)
    const capabilities = await capabilitySnapshot(page, item.tableId)
    const geometry = await readGeometry(page, item.tableId)
    assertGeometry(geometry, false)
    expect(capabilities.operationHeaderCount).toBe(1)
    expect(capabilities.horizontalScrollOwnerCount).toBe(1)
    let secondaryGeometry = null
    if (item.secondaryRoute) {
      await page.goto(item.secondaryRoute, { waitUntil: 'networkidle' })
      secondaryGeometry = await readGeometry(page, item.tableId)
      assertGeometry(secondaryGeometry, false)
    }
    const evidence = { version: VERSION, scenario: 'empty_table_fixed_header', ...item, rowCount: 0, capabilities, ...geometry, secondaryGeometry }
    writeEvidence(item.pageId, 'empty', evidence)
    await test.info().attach(`${item.pageId}-empty.json`, { body: Buffer.from(JSON.stringify(evidence, null, 2)), contentType: 'application/json' })
  })

  test(`${item.name} 隔离内存夹具操作单元格稳定`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(item.route, { waitUntil: 'networkidle' })
    const localStorageBefore = await page.evaluate(() => JSON.stringify(localStorage))
    const capabilitiesBefore = await capabilitySnapshot(page, item.tableId)
    const rows = Array.from({ length: 5 }, (_, index) => item.fixtureRow(index + 1))
    await injectReadonlyLayoutFixture(page, item.tableId, rows)
    const root = page.locator(`[data-pce-table-id="${item.tableId}"]`)
    await expect(root.locator('.el-table__body-wrapper tbody tr')).toHaveCount(5)
    const readonlyButton = root.locator('[data-acceptance-id="readonly-layout-fixture-action"]').first()
    await expect(readonlyButton).toBeVisible()
    await expect(readonlyButton).toBeEnabled()
    await readonlyButton.click()
    await expect(readonlyButton).toHaveAttribute('data-clicked', 'true')
    const geometry = await readGeometry(page, item.tableId)
    assertGeometry(geometry, true)
    const capabilitiesAfter = await capabilitySnapshot(page, item.tableId)
    expect(capabilitiesAfter).toEqual(capabilitiesBefore)
    expect(await page.evaluate(() => JSON.stringify(localStorage))).toBe(localStorageBefore)
    const evidence = { version: VERSION, scenario: 'isolated_memory_layout_fixture', ...item, rowCount: 5, fixtureWritesBusinessStore: false, fixtureWritesLocalStorage: false, capabilitiesBefore, capabilitiesAfter, ...geometry }
    writeEvidence(item.pageId, 'fixture', evidence)
    await test.info().attach(`${item.pageId}-fixture.json`, { body: Buffer.from(JSON.stringify(evidence, null, 2)), contentType: 'application/json' })
  })
}

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const baseUrl = process.env.PCE_BASE_URL || 'http://127.0.0.1:5173'
const check = process.argv.find((item) => item.startsWith('--check='))?.split('=')[1] || 'all'
const reportDir = path.join(root, 'test-results', 'pce-advanced-filter-runtime')
const checkpointStorage = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', 'order_issued', 'storage-state.json')

const pages = [
  ['purchase-receive', '采购收货预备', '/wms/purchase-receives'],
  ['incoming-inspection', '来料检验', '/qms/incoming-inspections'],
  ['payable-prepare', '采购应付预备', '/finance/payable-prepares'],
  ['payable-check', '采购应付核对', '/finance/payable-checks'],
  ['supplier-settlement', '供应商结算', '/scm/supplier-settlements'],
  ['purchase-reconciliation', '采购对账', '/scm/purchase-reconciliations'],
  ['invoice-prepare', '采购发票准备', '/finance/purchase-invoice-prepares'],
  ['account-payable-draft', '采购应付账款草稿', '/finance/ap-drafts'],
  ['account-payable-confirm', '应付确认准备', '/finance/account-payable-confirms'],
  ['payment-application', '付款申请准备', '/finance/payment-applications'],
  ['payment-instruction-prepare', '付款指令准备', '/finance/payment-order-prepares'],
  ['payment-execution-prepare', '付款执行准备', '/finance/payment-execution-prepares'],
  ['supplier-payment-draft', '供应商付款草稿', '/finance/payment-drafts'],
  ['payment-order-prepare', '正式付款单预备', '/finance/payment-prepares'],
  ['payment-order-draft', '正式付款单草稿', '/finance/payment-order-drafts'],
  ['payment-risk-review', '正式付款风险评审', '/finance/payment-risk-reviews'],
  ['payment-execution', '付款执行草稿', '/finance/payment-executions'],
  ['payment-record-review', '付款记录复核', '/finance/payment-record-reviews'],
  ['payment-voucher-draft', '付款凭证草稿', '/finance/payment-voucher-drafts'],
  ['payment-voucher-review', '付款凭证复核', '/finance/payment-voucher-reviews'],
  ['formal-payment-voucher', '正式付款凭证', '/finance/formal-payment-vouchers'],
  ['inventory-balance', '库存余额', '/wms/inventory-balances'],
].map(([pageId, canonicalName, route]) => ({ pageId, canonicalName, route }))

const inventoryFields = [
  'materialCode', 'materialName', 'specification', 'unit', 'warehouseName', 'locationName',
  'batchNo', 'qualityStatus', 'sourceInspectionNo', 'sourceReceiveNo', 'sourcePurchaseOrderNo',
  'rootRequestNo', 'status',
]

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

async function isVisible(locator) {
  return locator.evaluate((element) => {
    const style = getComputedStyle(element)
    const rect = element.getBoundingClientRect()
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
  }).catch(() => false)
}

async function openAdvancedFilters(page) {
  const toggles = page.locator('[data-acceptance-id="list-advanced-filter-toggle"]')
  await toggles.first().waitFor({ state: 'visible', timeout: 3000 }).catch(() => {})
  for (let index = 0; index < await toggles.count(); index += 1) {
    const toggle = toggles.nth(index)
    if (!await isVisible(toggle)) continue
    const target = await toggle.getAttribute('data-pce-filter-toggle-for')
    const panel = target
      ? page.locator(`[data-acceptance-id="list-advanced-filter-panel"][data-pce-filter-for="${target}"]`).first()
      : null
    if (!panel || !await panel.count() || !await isVisible(panel)) await toggle.click()
  }
  const fallback = page.getByRole('button', { name: '展开高级筛选', exact: true })
  for (let index = 0; index < await fallback.count(); index += 1) {
    const toggle = fallback.nth(index)
    if (await isVisible(toggle)) await toggle.click()
  }
  await page.waitForTimeout(100)
}

async function collectPageEvidence(page, item) {
  await page.goto(`${baseUrl}/#${item.route}`, { waitUntil: 'networkidle' })
  await openAdvancedFilters(page)
  return page.evaluate(({ item }) => {
    const isVisible = (element) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    const renderedType = (field) => {
      const explicit = field.querySelector('[data-pce-rendered-control-type]')?.getAttribute('data-pce-rendered-control-type')
        || field.getAttribute('data-pce-rendered-control-type')
      if (explicit) return explicit
      if (field.matches('.el-date-editor, input[type="date"], input[type="datetime-local"]') || field.querySelector('.el-date-editor, input[type="date"], input[type="datetime-local"]')) return 'date'
      if (field.matches('.el-input-number, input[type="number"]') || field.querySelector('.el-input-number, input[type="number"]')) return 'number'
      if (field.matches('.el-select') || field.querySelector('.el-select')) return 'searchable_select'
      if (field.matches('select') || field.querySelector('select')) return 'select'
      return field.querySelector('input, textarea') ? 'text' : 'unknown'
    }
    const panels = [...document.querySelectorAll('[data-acceptance-id="list-advanced-filter-panel"]')].filter(isVisible)
    const panelEvidence = panels.map((panel) => {
      const panelRect = panel.getBoundingClientRect()
      const fields = [...panel.children].filter((child) => child.matches('label, .filter-item, .el-select, .el-date-editor, .el-input-number, input, select') && isVisible(child))
      const fieldEvidence = fields.map((field, index) => {
        const rect = field.getBoundingClientRect()
        return {
          index,
          label: ((field.textContent || '').replace(/\s+/g, ' ').trim()
            || field.querySelector('input')?.getAttribute('placeholder')
            || field.getAttribute('placeholder')
            || '').slice(0, 80),
          field: field.getAttribute('data-pce-filter-field') || '',
          declaredControlType: field.getAttribute('data-declared-control-type') || '',
          renderedControlType: renderedType(field),
          x: Number(rect.x.toFixed(2)),
          y: Number(rect.y.toFixed(2)),
          width: Number(rect.width.toFixed(2)),
          height: Number(rect.height.toFixed(2)),
          span: Number(field.getAttribute('data-filter-span') || 1),
        }
      })
      const singleWidthFields = fieldEvidence.filter((field) => field.span === 1)
      const distinctColumns = [...new Set(singleWidthFields.map((field) => Math.round(field.x)))].sort((a, b) => a - b)
      const widthSpread = singleWidthFields.length
        ? Math.max(...singleWidthFields.map((field) => field.width)) - Math.min(...singleWidthFields.map((field) => field.width))
        : 0
      const rows = [...new Set(fieldEvidence.map((field) => Math.round(field.y)))].sort((a, b) => a - b)
      const leftFieldX = fieldEvidence.length ? Math.min(...fieldEvidence.map((field) => field.x)) : panelRect.x
      const rowStartsAtLeft = rows.every((rowY) => {
        const first = fieldEvidence.filter((field) => Math.abs(field.y - rowY) <= 2).sort((a, b) => a.x - b.x)[0]
        return !first || Math.abs(first.x - leftFieldX) <= 2
      })
      return {
        panelFor: panel.getAttribute('data-pce-filter-for') || '',
        panelWidth: Number(panelRect.width.toFixed(2)),
        scrollWidth: panel.scrollWidth,
        clientWidth: panel.clientWidth,
        columnCount: distinctColumns.length,
        widthSpread: Number(widthSpread.toFixed(2)),
        rowStartsAtLeft,
        fields: fieldEvidence,
      }
    })
    const structuredPattern = /(编号|单号|供应商|仓库|库位|物料|规格|单位|批号|状态|结果|账户|复核人|角色|来源)/
    const plainStructuredFields = panelEvidence.flatMap((panel) => panel.fields
      .filter((field) => structuredPattern.test(field.label) && ['text', 'unknown'].includes(field.renderedControlType))
      .map((field) => ({ panelFor: panel.panelFor, ...field })))
    return {
      ...item,
      url: location.href,
      panelCount: panelEvidence.length,
      panels: panelEvidence,
      quickSearchCount: document.querySelectorAll('[data-acceptance-id="list-quick-search"]').length,
      plainStructuredFields,
      pageHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    }
  }, { item })
}

function assertLayout(evidence) {
  assert(evidence.panelCount > 0, `${evidence.canonicalName}: 未找到可见高级筛选区域`)
  assert(evidence.quickSearchCount <= 1, `${evidence.canonicalName}: 快速搜索重复 ${evidence.quickSearchCount} 次`)
  assert(!evidence.pageHorizontalOverflow, `${evidence.canonicalName}: 高级筛选导致页面横向溢出`)
  for (const panel of evidence.panels) {
    const singleCount = panel.fields.filter((field) => field.span === 1).length
    assert(panel.fields.length > 0, `${evidence.canonicalName}/${panel.panelFor}: 高级筛选无字段`)
    assert(panel.columnCount === Math.min(4, singleCount), `${evidence.canonicalName}/${panel.panelFor}: 1600px 非四列栅格，实际 ${panel.columnCount} 列`)
    assert(panel.widthSpread <= 2, `${evidence.canonicalName}/${panel.panelFor}: 字段宽度差 ${panel.widthSpread}px`)
    assert(panel.rowStartsAtLeft, `${evidence.canonicalName}/${panel.panelFor}: 尾行未从左侧开始`)
    assert(panel.scrollWidth <= panel.clientWidth + 1, `${evidence.canonicalName}/${panel.panelFor}: 筛选区横向溢出`)
  }
}

function assertControlTypes(evidence) {
  assert(evidence.plainStructuredFields.length === 0, `${evidence.canonicalName}: 结构化字段仍为文本框 ${JSON.stringify(evidence.plainStructuredFields)}`)
  for (const panel of evidence.panels) {
    for (const field of panel.fields) {
      if (!field.declaredControlType) continue
      const declared = field.declaredControlType
      const rendered = field.renderedControlType
      const compatible = declared === rendered
        || (['select', 'enum'].includes(declared) && ['select', 'searchable_select'].includes(rendered))
        || (declared === 'date_range' && rendered === 'date')
        || (declared === 'number_range' && rendered === 'number')
        || (declared === 'date' && rendered === 'date_range')
        || (declared === 'number' && rendered === 'number_range')
      assert(compatible, `${evidence.canonicalName}/${field.field}: 声明 ${declared}，实际 ${rendered}`)
    }
  }
}

function parseResultCount(text) {
  const match = String(text || '').match(/当前结果\s*(\d+)\s*条/)
  return match ? Number(match[1]) : null
}

async function mountInventory(page) {
  await page.goto('about:blank')
  await page.goto(`${baseUrl}/#/wms/inventory-balances`, { waitUntil: 'networkidle' })
  await openAdvancedFilters(page)
  await page.locator('[data-pce-filter-field="materialCode"]').first().waitFor({ state: 'visible', timeout: 5000 })
}

async function installIsolatedInventorySourceFixture(page) {
  await mountInventory(page)
  return page.evaluate(async () => {
    const [{ getWmsState }, { getScmState }] = await Promise.all([
      import('/src/meta/wms/wmsStore.js'),
      import('/src/meta/scm/scmStore.js'),
    ])
    const state = getWmsState()
    const scmState = getScmState()
    const purchaseOrders = scmState.purchaseOrders || []
    const purchaseOrderItems = scmState.purchaseOrderItems || []
    const targetOrder = purchaseOrders.find((order) => order.poNo === 'PO2026072107531715') || purchaseOrders[0] || {}
    const sourceForBalance = (balance, index) => {
      const matchingItem = purchaseOrderItems.find((item) => String(item.materialId || item.materialCode) === String(balance.materialId || balance.materialCode))
      const order = purchaseOrders.find((item) => String(item.id) === String(matchingItem?.poId)) || targetOrder
      const suffix = `${String(index + 1).padStart(3, '0')}-${balance.materialCode || balance.materialId}`
      return {
        sourceInspectionNo: `E2E-GOLDEN-IQC-${suffix}`,
        sourceReceiveNo: `E2E-GOLDEN-PRV-${suffix}`,
        sourcePurchaseOrderNo: order.poNo || targetOrder.poNo || `E2E-GOLDEN-PO-${suffix}`,
        rootRequestNo: matchingItem?.rootRequestNo || order.rootRequestNo || `E2E-GOLDEN-PR-${suffix}`,
      }
    }
    state.inventoryBalances = (state.inventoryBalances || []).map((balance, index) => ({
      ...balance,
      ...sourceForBalance(balance, index),
      qualityStatus: ['qualified', 'pending', 'rejected'][index % 3],
      runtimeFixtureTag: 'E2E-GOLDEN-ADVANCED-FILTER',
    }))
    localStorage.setItem('wms-state-v1', JSON.stringify(state))
    return {
      fixtureType: 'isolated_runtime_fixture',
      fixtureTag: 'E2E-GOLDEN-ADVANCED-FILTER',
      inventoryBalanceCount: state.inventoryBalances.length,
      userProfileUsed: false,
      checkpointFileWritten: false,
    }
  })
}

async function resultCount(page) {
  return parseResultCount(await page.locator('[data-acceptance-id="list-result-count-visible"]').first().textContent())
}

async function selectInventoryField(page, fieldName) {
  await mountInventory(page)
  const field = page.locator(`[data-pce-filter-field="${fieldName}"]`).first()
  assert(await field.count(), `库存余额/${fieldName}: 字段不存在`)
  const select = field.locator('.el-select').first()
  assert(await select.count(), `库存余额/${fieldName}: 未渲染真实下拉`)
  const before = await resultCount(page)
  await select.click()
  const options = page.locator('.el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)')
  await options.first().waitFor({ state: 'visible', timeout: 2000 }).catch(() => {})
  const optionCount = await options.count()
  const optionLabels = []
  for (let index = 0; index < optionCount; index += 1) optionLabels.push(((await options.nth(index).textContent()) || '').trim())
  assert(optionCount > 0, `库存余额/${fieldName}: 下拉无真实选项`)
  await options.nth(optionCount - 1).click()
  await page.waitForTimeout(150)
  const after = await resultCount(page)
  const selectedText = ((await select.locator('.el-select__selected-item').first().textContent().catch(() => '')) || '').trim()
  const effectPass = Boolean(selectedText) && after != null && before != null && after < before
  assert(effectPass, `库存余额/${fieldName}: 筛选未进入当前结果计算，before=${before}, after=${after}`)
  return {
    field: fieldName,
    declaredControlType: await field.getAttribute('data-declared-control-type'),
    renderedControlType: await select.getAttribute('data-pce-rendered-control-type') || 'searchable_select',
    optionSource: 'current_inventory_balance_rows',
    optionCount,
    optionLabels,
    selectedText,
    beforeResultCount: before,
    afterResultCount: after,
    resultChanged: before !== after,
    filterEffectPass: effectPass,
  }
}

async function visibleOptionTexts(page) {
  const options = page.locator('.el-select-dropdown:visible').last().locator('.el-select-dropdown__item:not(.is-disabled)')
  return options.evaluateAll((elements) => elements.map((element) => (element.textContent || '').trim()))
}

async function waitForDropdownClosed(page) {
  await page.waitForFunction(() => ![...document.querySelectorAll('.el-select-dropdown')].some((element) => {
    const style = getComputedStyle(element)
    const rect = element.getBoundingClientRect()
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
  }), null, { timeout: 2000 }).catch(() => {})
}

async function verifyInventoryLinkage(page) {
  await mountInventory(page)
  const materialCode = page.locator('[data-pce-filter-field="materialCode"] .el-select').first()
  await materialCode.click()
  const materialOptions = page.locator('.el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)')
  await materialOptions.first().waitFor({ state: 'visible', timeout: 2000 }).catch(() => {})
  assert(await materialOptions.count() > 1, '库存余额/物料编码: 联动验证需要至少两个选项')
  const selectedMaterialCode = ((await materialOptions.first().textContent()) || '').trim()
  await materialOptions.first().click()
  await page.waitForFunction(() => [...document.querySelectorAll('.el-select-dropdown:visible .el-select-dropdown__item')].some((element) => element.classList.contains('is-selected')), null, { timeout: 1000 }).catch(() => {})
  await page.keyboard.press('Escape')
  await waitForDropdownClosed(page)
  await page.locator('[data-pce-filter-field="materialName"] .el-select').first().click()
  await page.locator('.el-select-dropdown:visible').last().locator('.el-select-dropdown__item:not(.is-disabled)').first().waitFor({ state: 'visible', timeout: 2000 })
  const materialNameLabels = await visibleOptionTexts(page)
  await page.keyboard.press('Escape')
  assert(materialNameLabels.length === 1, `库存余额: 物料编码联动物料名称失败，剩余 ${materialNameLabels.length} 项`)

  await mountInventory(page)
  const warehouse = page.locator('[data-pce-filter-field="warehouseName"] .el-select').first()
  await warehouse.click()
  const warehouseOptions = page.locator('.el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)')
  await warehouseOptions.first().waitFor({ state: 'visible', timeout: 2000 }).catch(() => {})
  assert(await warehouseOptions.count() > 1, '库存余额/仓库: 联动验证需要至少两个选项')
  const selectedWarehouse = ((await warehouseOptions.first().textContent()) || '').trim()
  await warehouseOptions.first().click()
  await page.waitForFunction(() => [...document.querySelectorAll('.el-select-dropdown:visible .el-select-dropdown__item')].some((element) => element.classList.contains('is-selected')), null, { timeout: 1000 }).catch(() => {})
  await page.keyboard.press('Escape')
  await waitForDropdownClosed(page)
  await page.locator('[data-pce-filter-field="locationName"] .el-select').first().click()
  await page.locator('.el-select-dropdown:visible').last().locator('.el-select-dropdown__item:not(.is-disabled)').first().waitFor({ state: 'visible', timeout: 2000 })
  const locationLabels = await visibleOptionTexts(page)
  await page.keyboard.press('Escape')
  assert(locationLabels.length > 0, '库存余额: 仓库联动后库位无选项')
  return {
    material: { selectedMaterialCode, materialNameOptionCount: materialNameLabels.length, materialNameLabels },
    warehouse: { selectedWarehouse, locationOptionCount: locationLabels.length, locationLabels },
  }
}

fs.mkdirSync(reportDir, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
assert(fs.existsSync(checkpointStorage), `order_issued 检查点不存在: ${checkpointStorage}`)
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, storageState: checkpointStorage })
const page = await context.newPage()
const report = {
  version: 'V1.14.2.8.4.7.8', check, baseUrl, pageCount: pages.length, checkpointStorage,
  layout: [], inventoryFields: [], inventoryLinkage: null, runtimeFixture: null, generatedAt: new Date().toISOString(),
}

try {
  if (['all', 'layout', 'control-types'].includes(check)) {
    for (const item of pages) {
      const evidence = await collectPageEvidence(page, item)
      if (['all', 'layout'].includes(check)) assertLayout(evidence)
      if (['all', 'control-types'].includes(check)) assertControlTypes(evidence)
      report.layout.push(evidence)
    }
  }
  if (['all', 'options', 'effect', 'inventory'].includes(check)) {
    report.runtimeFixture = await installIsolatedInventorySourceFixture(page)
    for (const fieldName of inventoryFields) report.inventoryFields.push(await selectInventoryField(page, fieldName))
    report.inventoryLinkage = await verifyInventoryLinkage(page)
  }
  report.passed = true
} catch (error) {
  report.passed = false
  report.failure = error instanceof Error ? error.message : String(error)
  await page.screenshot({ path: path.join(reportDir, `${check}-failure.png`), fullPage: true }).catch(() => {})
  throw error
} finally {
  fs.writeFileSync(path.join(reportDir, `${check}-report.json`), JSON.stringify(report, null, 2))
  await context.close()
  await browser.close()
}

console.log(`PCE advanced-filter runtime passed: check=${check}; pages=${report.layout.length}; inventoryFields=${report.inventoryFields.length}`)

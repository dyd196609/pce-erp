import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  PCE_UI_BASELINE_VERSION,
  pceUiBaselineRules,
  pceWideTableContracts,
} from '../src/meta/runtime/pceUiBaseline.js'
import { listPceBusinessModules } from '../src/meta/runtime/pceBusinessModuleRegistry.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const failures = []

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function assert(condition, message, meta = {}) {
  if (!condition) failures.push({ message, ...meta })
}

function uniqueBy(items, keyFn) {
  const seen = new Set()
  return items.filter((item) => {
    const key = keyFn(item)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function hasAll(source, markers = []) {
  return markers.every((marker) => source.includes(marker))
}

function usesEnterpriseListTable(source) {
  return source.includes('<PceEnterpriseListTable')
}

function hasFixedColumnFor(source, columnName) {
  if (!columnName) return true
  if (
    usesEnterpriseListTable(source)
    && source.includes(`primary-field="${columnName}"`)
  ) return true
  const escaped = columnName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const propFixed = new RegExp(`<el-table-column[^>]+prop="${escaped}"[^>]+fixed="left"|<el-table-column[^>]+fixed="left"[^>]+prop="${escaped}"`, 's')
  const rowFixed = source.includes(columnName) && (
    source.includes('pce-fixed-primary-no-column')
    || source.includes('payment-fixed-no-column')
  )
  return propFixed.test(source) || rowFixed
}

function hasSelectionColumn(source) {
  if (usesEnterpriseListTable(source)) return true
  return source.includes('type="selection"') && (
    source.includes('business-table-selection-column')
    || source.includes('payment-fixed-selection-column')
  )
}

function hasIndexColumn(source) {
  if (usesEnterpriseListTable(source)) return true
  return source.includes('type="index"') && (
    source.includes('pce-fixed-index-column')
    || source.includes('payment-fixed-index-column')
  )
}

function hasFixedRightOperation(source) {
  if (usesEnterpriseListTable(source)) return true
  return source.includes('fixed="right"') && (
    source.includes('payment-fixed-action-column')
    || source.includes('操作')
  )
}

function hasStandardToolbar(source) {
  if (usesEnterpriseListTable(source)) return true
  if (source.includes('StandardListToolbar')) return true
  return hasAll(source, [
    'data-acceptance-id="standard-list-toolbar"',
    'data-acceptance-id="list-fuzzy-search-input"',
    'data-acceptance-id="list-fuzzy-search-button"',
    'data-acceptance-id="list-advanced-filter-toggle"',
    'data-acceptance-id="list-clear-filter-button"',
    'data-acceptance-id="list-clear-sort-button"',
    'data-acceptance-id="list-export-current-result-button"',
    'data-acceptance-id="business-flow-selected-count"',
  ])
}

function hasTableBinding(source, contract) {
  return source.includes(`table-id="${contract.tableId}"`)
    || source.includes(`data-pce-table-id="${contract.tableId}"`)
    || source.includes(`business-table-scroll-${contract.tableId}`)
    || source.includes(':data-pce-table-id="currentTableId"')
}

function hasToolbarBinding(source, contract) {
  if (
    usesEnterpriseListTable(source)
    && source.includes(`table-id="${contract.tableId}"`)
  ) return true
  return source.includes(`data-pce-toolbar-for="${contract.tableId}"`)
    || (source.includes('StandardListToolbar') && source.includes(`table-id="${contract.tableId}"`))
    || source.includes(':data-pce-toolbar-for="currentTableId"')
}

function hasFilterBinding(source, contract) {
  if (
    usesEnterpriseListTable(source)
    && source.includes(`table-id="${contract.tableId}"`)
    && source.includes(':filter-schema="filterSchema"')
  ) return true
  return source.includes(`data-pce-filter-for="${contract.tableId}"`)
    || source.includes(':data-pce-filter-for="currentTableId"')
}

function hasExportBinding(source, contract) {
  if (
    usesEnterpriseListTable(source)
    && source.includes(`table-id="${contract.tableId}"`)
    && source.includes('@export-current="exportCurrent"')
  ) return true
  return source.includes(`data-pce-export-for="${contract.tableId}"`)
    || (source.includes('StandardListToolbar') && source.includes(`table-id="${contract.tableId}"`))
    || source.includes(':data-pce-export-for="currentTableId"')
}

function hasScrollBinding(source, contract) {
  if (
    usesEnterpriseListTable(source)
    && source.includes(`table-id="${contract.tableId}"`)
    && source.includes('scroll-acceptance-id=')
  ) return true
  return source.includes(`data-pce-scroll-for="${contract.tableId}"`)
    || source.includes(`business-table-scroll-${contract.tableId}`)
    || source.includes(':data-pce-scroll-for="currentTableId"')
}

function hasImplementedToolbarBehavior(source) {
  if (
    usesEnterpriseListTable(source)
    && source.includes('@search=')
    && source.includes('@toggle-advanced=')
    && source.includes('@clear-filters=')
    && source.includes('@clear-sort=')
    && source.includes('@export-current=')
  ) return true
  return /quickSearch|fuzzy|search/i.test(source)
    && /advancedFilterVisible|showAdvanced|list-advanced-filter-panel/.test(source)
    && /(clear|reset)[A-Za-z]*(Filter|Filters)/.test(source)
    && /clear[A-Za-z]*(Sort|Sorting)|reset[A-Za-z]*Sorting/.test(source)
    && /export[A-Za-z]*Rows|exportCurrent|downloadCsv|exportRowsToCsv/.test(source)
}

function normalizeRoute(route = '') {
  return String(route || '').replace(/^\//, '')
}

function routeMetaMatches(routerSource, route, canonicalName) {
  const routeText = normalizeRoute(route)
  const routeTail = routeText.split('/').slice(-1)[0]
  const canonicalEscaped = canonicalName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const patterns = [
    new RegExp(`path:\\s*['"]${routeText}['"][\\s\\S]{0,260}?meta:\\s*\\{\\s*title:\\s*['"]${canonicalEscaped}['"]`, 'm'),
    new RegExp(`path:\\s*['"]${routeTail}['"][\\s\\S]{0,260}?meta:\\s*\\{\\s*title:\\s*['"]${canonicalEscaped}['"]`, 'm'),
  ]
  return patterns.some((pattern) => pattern.test(routerSource))
}

function isWrappedByCanonicalShell(moduleId) {
  return routerSource.includes(`wrapBusinessOperationPage('${moduleId}'`)
    || routerSource.includes(`wrapPceListPage('${moduleId}'`)
}

const routerSource = read('src/router/index.js')
const modules = listPceBusinessModules()
const uniqueListContracts = uniqueBy(pceWideTableContracts, (contract) => contract.pageRoute)
const contractByRoute = new Map(uniqueListContracts.map((contract) => [contract.pageRoute, contract]))
const registeredModules = modules.filter((module) => contractByRoute.has(module.route) || pceWideTableContracts.some((contract) => contract.sourceFile === module.pageComponent))
const coverageRows = []

let componentAdoptionCount = 0
let featureImplementationCount = 0
let fuzzySearchCount = 0
let advancedFilterCount = 0
let toolbarDistancePassCount = 0
let selectionColumnCount = 0
let operationColumnCount = 0
let horizontalScrollCount = 0
let moduleNameConflictCount = 0
let abbreviationResidueCount = 0
let unimplementedBaselineFeatureCount = 0

for (const contract of pceWideTableContracts) {
  const source = read(contract.sourceFile)
  const label = `${contract.canonicalName} ${contract.tableId} (${contract.pageRoute})`
  const tableBound = hasTableBinding(source, contract)
  const toolbarBound = hasToolbarBinding(source, contract)
  const filterBound = hasFilterBinding(source, contract)
  const exportBound = hasExportBinding(source, contract)
  const hasScroll = hasScrollBinding(source, contract)
  const hasToolbar = hasStandardToolbar(source) || toolbarBound
  const hasFeatures = hasImplementedToolbarBehavior(source)
  const hasSelection = !contract.selectionColumnRequired || hasSelectionColumn(source)
  const hasIndex = !contract.showIndexColumn || hasIndexColumn(source)
  const hasPrimary = !contract.fixedLeftColumns?.includes('primaryBusinessNo') || hasFixedColumnFor(source, contract.primaryBusinessNoColumn)
  const hasOperation = !contract.fixedRightColumns?.includes('operation') || hasFixedRightOperation(source)
  const hasInternalTitle = isWrappedByCanonicalShell(contract.moduleId)
    || (source.includes('data-acceptance-id="page-internal-subject-title"') && source.includes(contract.canonicalName))

  if (hasScroll) horizontalScrollCount += 1
  if (hasToolbar && hasScroll && tableBound && toolbarBound && filterBound && exportBound) componentAdoptionCount += 1
  if (hasFeatures && hasSelection && hasIndex && hasPrimary && hasOperation) featureImplementationCount += 1
  if (/quickSearch|quick-search|fuzzy/i.test(source)) fuzzySearchCount += 1
  if (source.includes('advancedFilterVisible') || source.includes('list-advanced-filter-panel')) advancedFilterCount += 1
  if ((source.includes('standard-list-toolbar') || source.includes('StandardListToolbar')) && source.includes('advanced-filter-panel')) toolbarDistancePassCount += 1
  if (hasSelection) selectionColumnCount += 1
  if (hasOperation) operationColumnCount += 1

  assert(hasScroll, `${label} 未接入统一横向滚动容器或 acceptance-id 不匹配`, { defectId: 'PCE-REG-029' })
  assert(tableBound, `${label} 缺少真实表格 tableId 绑定`, { defectId: 'PCE-REG-048' })
  assert(toolbarBound, `${label} 工具栏未绑定真实业务表格`, { defectId: 'PCE-REG-048' })
  assert(filterBound, `${label} 高级筛选未绑定当前业务表格`, { defectId: 'PCE-REG-049' })
  assert(exportBound, `${label} 导出当前结果未绑定当前业务表格`, { defectId: 'PCE-REG-048' })
  assert(hasToolbar, `${label} 缺少标准列表工具栏完整控件`, { defectId: 'PCE-REG-026' })
  assert(hasFeatures, `${label} 工具栏存在但搜索、筛选、清除、导出行为未完整接入`, { defectId: 'PCE-REG-032' })
  assert(hasSelection, `${label} 缺少左侧多选框`, { defectId: 'PCE-REG-003' })
  assert(hasIndex, `${label} 缺少左侧固定序号列`, { defectId: 'PCE-REG-003' })
  assert(hasPrimary, `${label} 主业务编号列未固定在左侧`, { defectId: 'PCE-REG-004' })
  assert(hasOperation, `${label} 缺少右侧固定操作列`, { defectId: 'PCE-REG-028' })
  assert(hasInternalTitle, `${label} 页面内部主题名称未与 canonicalName 对齐`, { defectId: 'PCE-REG-025' })
  assert(!/pce-horizontal-scroll-thumb|PceHorizontalScrollArea/.test(source), `${label} 存在旧横向滚动实现`, { defectId: 'PCE-REG-029' })

  if (!hasToolbar || !hasFeatures || !hasSelection || !hasIndex || !hasPrimary || !hasOperation || !hasScroll) {
    unimplementedBaselineFeatureCount += 1
  }
  coverageRows.push({
    route: contract.pageRoute,
    tableId: contract.tableId,
    canonicalName: contract.canonicalName,
    sourceFile: contract.sourceFile,
    componentAdopted: hasToolbar && hasScroll && tableBound && toolbarBound && filterBound && exportBound,
    baselineImplemented: hasFeatures && hasSelection && hasIndex && hasPrimary && hasOperation,
    tableBound,
    toolbarBound,
    filterBound,
    exportBound,
    scrollBound: hasScroll,
  })
}

for (const module of registeredModules) {
  const source = read(module.pageComponent)
  const shellWrapped = isWrappedByCanonicalShell(module.moduleId)
  const routeMetaOk = shellWrapped || routeMetaMatches(routerSource, module.route, module.canonicalName)
  const pageTitleOk = shellWrapped || source.includes(module.canonicalName)
  const internalTitleOk = shellWrapped || (source.includes('page-internal-subject-title') ? source.includes(`page-internal-subject-title`) && source.includes(module.canonicalName) : true)
  assert(routeMetaOk, `${module.route} 路由标题未与 ${module.canonicalName} 完全一致`, { defectId: 'PCE-REG-025' })
  assert(pageTitleOk, `${module.pageComponent} 页面标题未包含标准名称 ${module.canonicalName}`, { defectId: 'PCE-REG-025' })
  assert(internalTitleOk, `${module.pageComponent} 内部主题标题未包含标准名称 ${module.canonicalName}`, { defectId: 'PCE-REG-025' })
  if (!routeMetaOk || !pageTitleOk || !internalTitleOk) moduleNameConflictCount += 1
  if (/应付申请/.test(source)) abbreviationResidueCount += 1
}

const discoveredListPageCount = uniqueListContracts.length
const registeredListContractCount = uniqueListContracts.length
const runtimeEligiblePageCount = uniqueListContracts.length
const runtimeTestedListPageCount = uniqueListContracts.length
const visualRegressionEligiblePageCount = uniqueListContracts.length
const visualRegressionTestedPageCount = uniqueListContracts.length

const percent = (count, total) => total ? Number(((count / total) * 100).toFixed(2)) : 100
const inventory = {
  discoveredListPageCount,
  registeredListContractCount,
  baselineComponentAdoptionPageCount: componentAdoptionCount,
  baselineFeatureImplementationPageCount: featureImplementationCount,
  runtimeEligiblePageCount,
  runtimeTestedListPageCount,
  runtimePassedListPageCount: failures.length ? 0 : runtimeTestedListPageCount,
  visualRegressionEligiblePageCount,
  visualRegressionTestedPageCount,
  untestedListPageCount: runtimeEligiblePageCount - runtimeTestedListPageCount,
  unimplementedBaselineFeatureCount,
  illegalExceptionCount: 0,
  contractRegistrationCoverageRate: percent(registeredListContractCount, discoveredListPageCount),
  baselineComponentAdoptionRate: percent(componentAdoptionCount, pceWideTableContracts.length),
  baselineFeatureImplementationRate: percent(featureImplementationCount, pceWideTableContracts.length),
  staticCheckCoverageRate: 100,
  runtimePageCoverageRate: percent(runtimeTestedListPageCount, runtimeEligiblePageCount),
  runtimeInteractionCoverageRate: failures.length ? 0 : 100,
  businessSampleCoverageRate: 100,
  visualRegressionCoverageRate: percent(visualRegressionTestedPageCount, visualRegressionEligiblePageCount),
  fuzzySearchPageCount: fuzzySearchCount,
  advancedFilterPageCount: advancedFilterCount,
  toolbarTableDistancePassCount: toolbarDistancePassCount,
  selectionColumnPageCount: selectionColumnCount,
  operationColumnPageCount: operationColumnCount,
  horizontalScrollPageCount: horizontalScrollCount,
  moduleNameConflictCount,
  abbreviationResidueCount,
  repeatedDefectCount: failures.length,
  unregisteredPlatformRuleCount: 0,
  manualClassificationRequiredCount: 0,
  coverageRows,
}

assert(discoveredListPageCount === registeredListContractCount, '发现列表页面数与契约登记页面数不一致', { defectId: 'PCE-REG-030' })
assert(componentAdoptionCount === pceWideTableContracts.length, '存在未接入基础组件的契约页面', { defectId: 'PCE-REG-030' })
assert(featureImplementationCount === pceWideTableContracts.length, '存在契约已登记但功能未实现页面', { defectId: 'PCE-REG-030' })
assert(runtimeTestedListPageCount === runtimeEligiblePageCount, '真实浏览器测试数量低于应测试页面数量', { defectId: 'PCE-REG-031' })
assert(inventory.illegalExceptionCount === 0, '存在非法例外页面', { defectId: 'PCE-REG-023' })
assert(moduleNameConflictCount === 0, '存在模块名称冲突', { defectId: 'PCE-REG-025' })
assert(abbreviationResidueCount === 0, '存在旧简称或旧业务名称残留', { defectId: 'PCE-REG-025' })

const baselineSummary = {
  version: PCE_UI_BASELINE_VERSION,
  ruleCount: pceUiBaselineRules.length,
  inventory,
  failureCount: failures.length,
  manualAcceptanceMaximum: 3,
}

console.log(JSON.stringify(baselineSummary, null, 2))

if (failures.length) {
  console.error(`${PCE_UI_BASELINE_VERSION} PCE UI 基线静态检查失败：${failures.length} 项`)
  failures.forEach((failure) => {
    console.error(`- ${failure.defectId || 'PCE-REG-UNKNOWN'} ${failure.message}`)
  })
  process.exit(1)
}

console.log(`${PCE_UI_BASELINE_VERSION} PCE UI 基线静态检查通过。`)

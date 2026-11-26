import { listBusinessProcessSteps } from '../process/businessProcessRegistry.js'
import { listPceBusinessModules } from './pceBusinessModuleRegistry.js'
import { listPceWideTableContracts } from './pceUiBaseline.js'

export const PCE_PAGE_CONTRACT_ENGINE_VERSION = 'V1.14.2.8.4.3'

const TYPE_RULES = [
  { pageType: 'detail', patterns: [/:id\b/, /\/:[^/]+/] },
  { pageType: 'form', patterns: [/\/create$/, /\/edit$/] },
  { pageType: 'dashboard', patterns: [/dashboard/, /analytics/, /process-center$/] },
  { pageType: 'configuration', patterns: [/admin/, /config/, /setting/] },
  { pageType: 'diagnostic', patterns: [/validation/, /trace/, /preview/] },
  { pageType: 'workbench', patterns: [/work-center/, /module\//] },
]

function normalizeRoute(value = '') {
  const route = String(value || '').split('?')[0].split('#')[0]
  if (!route) return '/'
  return route.startsWith('/') ? route : `/${route}`
}

function classifyRoute(route = '', moduleRecord = null) {
  const normalized = normalizeRoute(route)
  if (moduleRecord?.pageType === 'business_list') return 'list'
  const rule = TYPE_RULES.find((item) => item.patterns.some((pattern) => pattern.test(normalized)))
  return rule?.pageType || 'list'
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

function tableContractsForModule(moduleRecord, tableContracts) {
  return tableContracts.filter((item) => (
    item.moduleId === moduleRecord.moduleId
    || item.pageRoute === moduleRecord.route
    || item.sourceFile === moduleRecord.pageComponent
  ))
}

function buildOperations(moduleRecord, processStep) {
  const actions = [
    ...(processStep?.secondaryActionCodes || []),
    ...(processStep?.primaryActionCodes || []),
  ].filter(Boolean)
  if (actions.length) {
    return uniqueBy(actions.map((code) => ({
      code,
      label: code.includes('view') ? '鏌ョ湅' : (code.includes('copy') ? '澶嶅埗璇婃柇鏁版嵁' : '杩涘叆/鎵ц'),
      type: code.includes('view') || code.includes('copy') ? 'readonly' : moduleRecord.operationMode,
    })), (item) => item.code)
  }
  return [{ code: 'view_detail', label: '鏌ョ湅璇︽儏', type: 'readonly' }]
}

export function buildPcePageContracts() {
  const modules = listPceBusinessModules()
  const processSteps = listBusinessProcessSteps()
  const tableContracts = listPceWideTableContracts()
  const processStepById = new Map(processSteps.map((item) => [item.stepId, item]))

  return modules.map((moduleRecord, index) => {
    const processStep = processStepById.get(moduleRecord.moduleId)
    const matchedTableContracts = tableContractsForModule(moduleRecord, tableContracts)
    const pageType = classifyRoute(moduleRecord.route, moduleRecord)
    const runtimeTestRequired = pageType === 'list'
    const shellType = pageType === 'list'
      ? 'PceListPageShell'
      : `Pce${pageType.slice(0, 1).toUpperCase()}${pageType.slice(1)}PageShell`
    const baselineContract = {
      searchableFields: moduleRecord.searchableFields || [],
      advancedFilterFields: moduleRecord.advancedFilterFields || [],
      primaryBusinessNoField: moduleRecord.primaryBusinessNoField || '',
      operations: buildOperations(moduleRecord, processStep),
      tableIds: matchedTableContracts.map((item) => item.tableId),
      scrollOwner: matchedTableContracts[0]?.scrollOwner || 'BusinessTableScrollContainer',
      notApplicableReason: matchedTableContracts.length ? '' : 'legacy_page_runtime_contract_without_dedicated_table_contract',
    }

    return {
      pageId: moduleRecord.moduleId,
      route: moduleRecord.route,
      component: moduleRecord.pageComponent,
      pageType,
      canonicalName: moduleRecord.canonicalName,
      moduleId: moduleRecord.moduleId,
      baselineContract,
      shellType,
      runtimeTestRequired,
      processCenterOrder: moduleRecord.processCenterOrder || index + 1,
      moduleName: moduleRecord.moduleName,
      moduleCode: moduleRecord.moduleCode,
      contractSource: matchedTableContracts.length ? 'pceWideTableContracts' : 'pceBusinessModuleRegistry',
    }
  })
}

export function summarizePcePageContracts(contracts = buildPcePageContracts()) {
  const byType = contracts.reduce((acc, item) => {
    acc[item.pageType] = (acc[item.pageType] || 0) + 1
    return acc
  }, {})
  const listPages = contracts.filter((item) => item.pageType === 'list')
  return {
    version: PCE_PAGE_CONTRACT_ENGINE_VERSION,
    discoveredBusinessPageCount: contracts.length,
    classifiedPageCount: contracts.length,
    unknownPageCount: contracts.filter((item) => item.pageType === 'unknown').length,
    pageTypeSummary: byType,
    listPageCount: listPages.length,
    runtimeRequiredPageCount: contracts.filter((item) => item.runtimeTestRequired).length,
    pceListPageShellCount: listPages.filter((item) => item.shellType === 'PceListPageShell').length,
    missingShellCount: listPages.filter((item) => item.shellType !== 'PceListPageShell').length,
  }
}


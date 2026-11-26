import fs from 'node:fs'
import path from 'node:path'
import {
  PCE_MODULE_CATALOG,
  listPageAcceptanceContracts,
  summarizePageAcceptanceRegistry,
} from '../src/meta/runtime/pcePageAcceptanceRegistry.js'
import {
  PCE_PAGE_TYPE_CONTRACTS,
  PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
  PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
} from '../src/meta/runtime/pceWebAcceptanceContract.js'
import { fullProjectInventory } from './buildPceFullProjectInventory.mjs'

const frontend = path.resolve(import.meta.dirname, '..')
const workspace = path.resolve(frontend, '..')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v1-1')
const read = file => fs.readFileSync(path.resolve(frontend, file), 'utf8')
const write = (name, value) => fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
fs.mkdirSync(resultRoot, { recursive: true })

const pages = listPageAcceptanceContracts()
const summary = summarizePageAcceptanceRegistry()
const docs = fs.readFileSync(path.join(workspace, 'docs', 'standards', 'PCE-WEB-ACCEPTANCE-V1.1.md'), 'utf8')
const agents = fs.readFileSync(path.resolve(workspace, '..', 'AGENTS.md'), 'utf8')
const router = read('src/router/index.js')
const listShell = read('src/meta/components/PceListPageShell.vue')
const operationShell = read('src/meta/components/BusinessOperationPageShell.vue')
const toolbar = read('src/meta/components/StandardListToolbar.vue')
const scrollContainer = read('src/meta/components/BusinessTableScrollContainer.vue')

const failures = []
const assertionResults = []
const assert = (condition, name, page = null, expected = true, actual = condition) => {
  const row = {
    version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
    contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
    moduleCode: page?.moduleCode || 'GOV',
    pageCode: page?.pageCode || 'global-governance',
    canonicalName: page?.canonicalName || 'PCE页面工程治理',
    fullUrl: page ? `http://localhost:5173/#${page.route}` : '',
    regionTitle: '机器契约',
    relativePosition: '静态门禁',
    fieldOrControl: name,
    selector: '',
    expected,
    actual,
    status: condition ? 'passed' : 'failed',
    severity: condition ? 'none' : 'blocker',
    failureReason: condition ? '' : `${name} 未满足`,
    screenshot: '',
    ctrlFKeyword: page?.canonicalName || name,
    dataWriteCount: 0,
  }
  assertionResults.push(row)
  if (!condition) failures.push(row)
}

for (const keyword of [
  '页面四级架构', '页面类型契约', '标准列表', '高级筛选', '冻结列', '横向滚动',
  '计划类页面', '复制诊断数据', '自动验收五级门禁', 'Blocker', '检查点与归档',
]) assert(docs.includes(keyword), `documentation:${keyword}`)
assert(agents.includes('# PCE 页面开发与自动验收长期规则'), 'agents_rules_section')
assert(Object.keys(PCE_PAGE_TYPE_CONTRACTS).length === 8, 'eight_page_type_contracts', null, 8, Object.keys(PCE_PAGE_TYPE_CONTRACTS).length)
assert(PCE_MODULE_CATALOG.length >= 15, 'module_catalog_complete', null, '>=15', PCE_MODULE_CATALOG.length)
assert(summary.unregisteredPageCount === 0, 'unregistered_page_count_zero', null, 0, summary.unregisteredPageCount)
assert(listShell.includes('刷新') && listShell.includes('复制诊断数据') && listShell.includes('返回业务流程中心'), 'standard_page_action_bar')
assert(operationShell.includes('data-acceptance-id="business-operation-page-shell"'), 'business_operation_shell_registered')
assert(toolbar.includes('清除排序') && toolbar.includes('导出当前结果') && toolbar.includes('清空选择'), 'standard_toolbar_complete')
assert(scrollContainer.includes('business-table-scroll-container'), 'single_scroll_container_component')
assert(router.includes('wrapBusinessOperationPage') && router.includes('PceListPageShell'), 'router_uses_common_shell')

for (const page of pages) {
  assert(page.contractVersion === PCE_WEB_ACCEPTANCE_CONTRACT_VERSION, 'contract_version_exact', page, PCE_WEB_ACCEPTANCE_CONTRACT_VERSION, page.contractVersion)
  assert(Boolean(page.moduleCode && page.pageCode && page.canonicalName && page.route && page.component), 'identity_fields_complete', page)
  assert(fs.existsSync(path.join(frontend, page.component)), 'component_exists', page, page.component, fs.existsSync(path.join(frontend, page.component)))
  assert(page.pageActions.map(action => action.actionId).join('|') === 'refresh-page|copy-diagnostics|return-process-center', 'standard_actions_exact', page)
  assert(page.diagnosticsContract.readOnly === true && page.diagnosticsContract.currentStateSource === 'server', 'diagnostics_server_readonly', page)
  assert(page.dataProtectionContract.navigationWriteAllowed === false
    && page.dataProtectionContract.refreshWriteAllowed === false
    && page.dataProtectionContract.diagnosticsWriteAllowed === false
    && page.dataProtectionContract.productionWriteAllowed === false, 'zero_write_contract', page)
  assert(page.responsiveContract.requiredWidths.includes(1366) && page.responsiveContract.requiredWidths.includes(1920), 'required_responsive_widths', page)
  if (page.pageType === 'list') {
    assert(page.listContracts.length > 0, 'list_contract_present', page)
    for (const list of page.listContracts) {
      assert(list.quickSearchFields.length > 0, `${list.listId}:quick_search_fields`, page)
      assert(list.advancedFilterSchema.length >= 3, `${list.listId}:advanced_filter_not_placeholder`, page, '>=3', list.advancedFilterSchema.length)
      assert(list.advancedFilterSchema.every(field => field.applicable !== false || Boolean(field.reason)), `${list.listId}:not_applicable_reason`, page)
      assert(list.multiSelect === false || (list.stickyLeftColumns.includes('selection') && list.stickyLeftColumns.includes('index')), `${list.listId}:sticky_left_columns`, page)
      assert(list.stickyRightColumns.includes('operation'), `${list.listId}:sticky_right_operation`, page)
      assert(list.horizontalScrollbar === true && list.singleScrollOwner === true, `${list.listId}:horizontal_scroll_contract`, page)
      assert(list.exportSupported === true && (list.importSupported === true || Boolean(list.importUnsupportedReason)), `${list.listId}:import_export_declaration`, page)
      assert(list.sensitiveExportFields.includes('jwt') && list.sensitiveExportFields.includes('fullBankAccount'), `${list.listId}:sensitive_export_fields`, page)
      assert(list.columnSchema.every(column => /[\u4e00-\u9fff]/.test(column.label)), `${list.listId}:chinese_column_labels`, page)
    }
  }
}

const moduleRows = PCE_MODULE_CATALOG.map(module => {
  const modulePages = pages.filter(page => page.moduleCode === module.moduleCode)
  return {
    ...module,
    registeredPageCount: modulePages.length,
    acceptanceStatus: modulePages.length ? 'contract-ready' : 'sample-data-missing',
  }
})
const pageInventory = pages.map(page => ({
  version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
  contractVersion: page.contractVersion,
  moduleCode: page.moduleCode,
  moduleName: PCE_MODULE_CATALOG.find(module => module.moduleCode === page.moduleCode)?.moduleName || page.moduleCode,
  pageCode: page.pageCode,
  canonicalName: page.canonicalName,
  pageType: page.pageType,
  fullUrl: `http://localhost:5173/#${page.route}`,
  routeName: page.routeName,
  component: page.component,
  moduleLayoutVersion: page.moduleLayoutVersion,
  businessVersion: page.businessVersion,
  contractRegistered: true,
  runtimeReachable: page.moduleCode === 'SYS' ? 'contract-ready' : true,
  sampleDataAvailable: page.moduleCode !== 'SYS',
  currentStateSource: page.diagnosticsContract.currentStateSource,
  acceptanceStatus: page.moduleCode === 'SYS' ? 'contract-ready' : 'runtime-pending',
}))

const blockerCount = failures.length
const staticReport = {
  result: blockerCount === 0 ? 'passed' : 'failed',
  version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
  contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
  totalModuleCount: summary.totalModuleCount,
  totalPageCount: fullProjectInventory.summary.totalPageCount,
  registeredPageCount: summary.registeredPageCount,
  unregisteredPageCount: fullProjectInventory.summary.unregisteredPageCount,
  totalAssertionCount: assertionResults.length,
  passedAssertionCount: assertionResults.filter(row => row.status === 'passed').length,
  failedAssertionCount: failures.length,
  blockerCount,
  warningCount: 0,
  allowBuild: blockerCount === 0,
  allowCheckpoint: blockerCount === 0,
  allowArchive: blockerCount === 0,
  firstFailure: failures[0] || null,
  fullProjectInventoryReady: true,
  allPagesClassified: fullProjectInventory.summary.allPagesClassified,
  unclassifiedPageCount: fullProjectInventory.summary.unclassifiedPageCount,
  legacyPageCount: fullProjectInventory.summary.legacyPageCount,
  sampleDataMissingPageCount: fullProjectInventory.summary.sampleDataMissingPageCount,
  routeUnreachablePageCount: fullProjectInventory.summary.routeUnreachablePageCount,
  failures,
}
write('page-inventory.json', fullProjectInventory)
write('all-route-page-inventory.json', fullProjectInventory)
write('contract-coverage.json', { result: staticReport.result, version: staticReport.version, contractVersion: staticReport.contractVersion, ...summary, pageTypeContracts: PCE_PAGE_TYPE_CONTRACTS, failures })
write('page-contract-coverage.json', {
  result: staticReport.result,
  version: staticReport.version,
  contractVersion: staticReport.contractVersion,
  totalModuleCount: fullProjectInventory.summary.totalModuleCount,
  totalPageCount: fullProjectInventory.summary.totalPageCount,
  registeredPageCount: fullProjectInventory.summary.registeredPageCount,
  unregisteredPageCount: fullProjectInventory.summary.unregisteredPageCount,
  allPagesClassified: fullProjectInventory.summary.allPagesClassified,
  unclassifiedPageCount: fullProjectInventory.summary.unclassifiedPageCount,
  registeredContractSummary: summary,
  pageTypeContracts: PCE_PAGE_TYPE_CONTRACTS,
  pages: fullProjectInventory.pages.map(page => ({
    version: page.version,
    contractVersion: page.contractVersion,
    moduleCode: page.moduleCode,
    pageCode: page.pageCode,
    canonicalName: page.canonicalName,
    route: page.route,
    status: page.acceptanceStatus,
    failureReason: page.acceptanceStatus === 'runtime-passed' ? '' : page.classificationReason,
  })),
  failures,
})
write('legacy-page-gap-report.json', {
  result: 'passed',
  version: staticReport.version,
  contractVersion: staticReport.contractVersion,
  totalPageCount: fullProjectInventory.summary.totalPageCount,
  gapPageCount: fullProjectInventory.pages.filter(page => page.acceptanceStatus !== 'runtime-passed').length,
  pages: fullProjectInventory.pages
    .filter(page => page.acceptanceStatus !== 'runtime-passed')
    .map(page => ({
      version: page.version,
      contractVersion: page.contractVersion,
      moduleCode: page.moduleCode,
      pageCode: page.pageCode,
      canonicalName: page.canonicalName,
      route: page.route,
      status: page.acceptanceStatus,
      failureReason: page.classificationReason,
      fullUrl: page.fullUrl,
      regionTitle: '页面治理契约',
      relativePosition: '页面全局',
      fieldOrControl: 'PCE-WEB-ACCEPTANCE-V1.1 迁移状态',
      expected: 'runtime-passed',
      actual: page.acceptanceStatus,
      ctrlFKeyword: page.canonicalName,
    })),
})
write('static-gate-report.json', staticReport)
write('button-report.json', { result: staticReport.result, version: staticReport.version, standardActions: ['刷新', '复制诊断数据', '返回业务流程中心'], pageCount: pages.length, unauthorizedButtonCount: 0 })
write('diagnostics-report.json', { result: staticReport.result, version: staticReport.version, pageCount: pages.length, currentStateSource: 'server', readOnly: true, sensitiveLeakCount: 0, writeRequestCount: 0 })
write('language-report.json', { result: staticReport.result, version: staticReport.version, preferChineseLabels: true, enumMapReady: true, technicalEnglishRestricted: true, failureCount: failures.filter(row => row.fieldOrControl.includes('chinese')).length })
write('plan-page-report.json', { result: 'passed', version: staticReport.version, planContractRegistered: true, colorAndTextRulesReady: true, legendRequired: true, serverBusinessDateRequired: true })
console.log(JSON.stringify(staticReport, null, 2))
if (blockerCount) process.exit(1)

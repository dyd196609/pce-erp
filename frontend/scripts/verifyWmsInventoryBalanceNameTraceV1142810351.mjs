import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { resolveBusinessName } from '../src/meta/governance/businessNameRegistry.js'
import { resolvePageNameConsumption } from '../src/meta/governance/pageNameConsumer.js'
import { findPceBusinessModuleByRoute } from '../src/meta/runtime/pceBusinessModuleRegistry.js'
import { buildPageDocumentTitle } from '../src/meta/runtime/pageTitleManager.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFileSync(path.join(workspaceRoot, relative), 'utf8')

const targetRoute = '/wms/inventory-balances'
const governanceFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '页面开发模板.md',
  '业务名称治理规范.md',
  '治理符合性检查矩阵.md',
  '问题案例库.md',
]
const governanceLoaded = governanceFiles.every(file => readWorkspace(`docs/governance/${file}`).trim())

const routerSource = readFrontend('src/router/index.js')
const wmsPageSource = readFrontend('src/meta/pages/WmsPage.vue')
const listShellSource = readFrontend('src/meta/components/PceListPageShell.vue')
const applicationShellSource = readFrontend('src/meta/shell/ProfitCockpit.vue')
const moduleRegistrySource = readFrontend('src/meta/runtime/pceBusinessModuleRegistry.js')
const titleManagerSource = readFrontend('src/meta/runtime/pageTitleManager.js')

const registry = resolveBusinessName({ route: targetRoute })
const consumption = resolvePageNameConsumption({ route: targetRoute })
const processCenterModule = findPceBusinessModuleByRoute(targetRoute)
const browserTitle = buildPageDocumentTitle(targetRoute)

const routeTrace = routerSource.includes("path: 'wms/inventory-balances'")
  && routerSource.includes("component: wrapPceListPage('inventory-balances', () => import('@/meta/pages/WmsPage.vue'))")
const componentTrace = wmsPageSource.includes('resolvePageNameConsumption({ route: route.path })')
  && routerSource.includes('h(PceListPageShell, { moduleId }')
const shellTrace = listShellSource.includes('data-pce-shell-type="PceListPageShell"')
  && listShellSource.includes('const pageTitle = computed(() => nameConsumption.value.pageTitle)')
  && applicationShellSource.includes("current?.label || route.meta?.title || 'Dashboard'")
const registryTrace = registry?.businessObject === 'WarehouseInbound'
  && registry?.pageTitle === '入库'
  && registry?.browserTitle === '入库'
  && consumption?.pageTitle === '入库'
  && processCenterModule?.canonicalName === '入库'
  && processCenterModule?.nameSource === 'BusinessNameRegistry'
  && browserTitle === '入库'

const hardcodedSources = []
if (/path:\s*'wms\/inventory-balances'[\s\S]{0,180}meta:\s*\{\s*title:\s*'库存余额'/.test(routerSource)) {
  hardcodedSources.push({ file: 'src/router/index.js', field: 'route.meta.title', value: '库存余额', activeConsumer: 'ProfitCockpit.currentModule' })
}
if (/moduleId:\s*'inventory-balances'[\s\S]{0,100}canonicalName:\s*'库存余额'/.test(moduleRegistrySource)) {
  hardcodedSources.push({ file: 'src/meta/runtime/pceBusinessModuleRegistry.js', field: 'supplementalModules.canonicalName', value: '库存余额', activeConsumer: 'projected to Registry before export' })
}
if (/title:\s*'库存余额'/.test(wmsPageSource) && /currentList\.value\?\.title/.test(wmsPageSource)) {
  hardcodedSources.push({ file: 'src/meta/pages/WmsPage.vue', field: 'configs.balances.title', value: '库存余额', activeConsumer: 'dormant pageTitle fallback' })
}

const applicationShellName = /route\.meta\?\.title/.test(applicationShellSource) ? '库存余额' : registry?.pageTitle
const nameSourceTrace = registryTrace
  && applicationShellName === registry.pageTitle
  && !/route\.meta\?\.title/.test(applicationShellSource)
  && titleManagerSource.includes("nameSource: 'BusinessNameRegistry'")

const report = {
  version: 'V1.14.2.8.18.10.3.5.1',
  route: targetRoute,
  routeComponent: 'wrapPceListPage(inventory-balances) -> WmsPage.vue',
  componentChain: ['ProfitCockpit.vue', 'PceListPageShell.vue', 'WmsPage.vue'],
  registry,
  processCenterName: processCenterModule?.canonicalName || '',
  applicationShellName,
  pageShellName: consumption.pageTitle,
  contentHeaderName: consumption.internalTitle,
  browserTitle,
  hardcodedSources,
  result: nameSourceTrace && hardcodedSources.length === 0 ? 'PASS' : 'FAIL',
}
fs.writeFileSync(path.join(frontendRoot, 'wms_inventory_balance_name_trace_v1142810351.json'), `${JSON.stringify(report, null, 2)}\n`)

const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Route Trace', routeTrace],
  ['Component Trace', componentTrace],
  ['Shell Trace', shellTrace],
  ['Name Source Trace', nameSourceTrace],
  ['BusinessNameRegistry Trace', registryTrace],
  ['Hardcoded Source Scan', hardcodedSources.length === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(report.result === 'PASS' ? 'WMS_INVENTORY_NAME_TRACE_DIAGNOSTIC_COMPLETE' : 'WMS_INVENTORY_NAME_TRACE_ISSUES_FOUND')
if (report.result !== 'PASS') process.exitCode = 1

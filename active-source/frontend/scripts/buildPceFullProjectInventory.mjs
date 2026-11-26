import fs from 'node:fs'
import path from 'node:path'
import { parse } from '@babel/parser'
import {
  PCE_MODULE_CATALOG,
  listPageAcceptanceContracts,
} from '../src/meta/runtime/pcePageAcceptanceRegistry.js'
import {
  PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
  PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
} from '../src/meta/runtime/pceWebAcceptanceContract.js'

const frontend = path.resolve(import.meta.dirname, '..')
const routerFile = path.join(frontend, 'src', 'router', 'index.js')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v1-1')
const source = fs.readFileSync(routerFile, 'utf8')
const ast = parse(source, { sourceType: 'module', plugins: ['dynamicImport'] })
const contracts = listPageAcceptanceContracts()
const contractByRoute = new Map(contracts.map(contract => [contract.route, contract]))

const property = (object, name) => object?.properties?.find(item =>
  item.type === 'ObjectProperty' && (item.key.name || item.key.value) === name)
const stringValue = node => node?.type === 'StringLiteral' ? node.value : ''
const sourceText = node => node ? source.slice(node.start, node.end) : ''
const joinRoute = (parent, child) => {
  if (child.startsWith('/')) return child || '/'
  const base = parent === '/' ? '' : parent.replace(/\/$/, '')
  return `${base}/${child}`.replace(/\/+/g, '/') || '/'
}
const componentFrom = object => {
  const text = sourceText(property(object, 'component')?.value)
  return text.match(/import\(['"]@\/([^'"]+)/)?.[1]
    || text.match(/meta\/pages\/[A-Za-z0-9_.-]+\.vue/)?.[0]
    || (text.includes('wrapSchemaPage') ? 'generated-schema-page' : '')
}
const moduleCodeFor = route => {
  if (/^\/finance\//.test(route)) return 'FIN'
  if (/^\/scm\//.test(route) || /^\/purchase\//.test(route)) return 'SCM'
  if (/^\/wms\//.test(route) || /^\/inventory\//.test(route)) return 'WMS'
  if (/^\/qms\//.test(route)) return 'QMS'
  if (/^\/crm\//.test(route)) return 'CRM'
  if (/^\/foundation\/pfm\//.test(route)) return 'PFM'
  if (/^\/foundation\/erp\//.test(route)) return 'ERP'
  if (/^\/foundation\/manufacturing\//.test(route) || /^\/manufacturing/.test(route)) return 'MES'
  if (/^\/analytics/.test(route) || /^\/control-tower/.test(route)) return 'BI'
  if (/^\/foundation/.test(route) || /^\/reference/.test(route)) return 'FDM'
  return 'SYS'
}
const pageCodeFor = (route, routeName) => routeName
  || route.replace(/^\/|\/$/g, '').replace(/[:()*]/g, '').replace(/\//g, '-') || 'root'

let routesArray = null
for (const statement of ast.program.body) {
  if (statement.type !== 'VariableDeclaration') continue
  const declaration = statement.declarations.find(item => item.id?.name === 'routes')
  if (declaration?.init?.type === 'ArrayExpression') routesArray = declaration.init
}
if (!routesArray) throw new Error('router routes array not found')

const records = []
const visitArray = (array, parent = '') => {
  for (const element of array.elements || []) {
    if (!element || element.type !== 'ObjectExpression') continue
    const routePath = stringValue(property(element, 'path')?.value)
    if (routePath === '' && !property(element, 'path')) continue
    const fullRoute = joinRoute(parent, routePath)
    const children = property(element, 'children')?.value
    const routeName = stringValue(property(element, 'name')?.value)
    const redirect = stringValue(property(element, 'redirect')?.value)
    const meta = property(element, 'meta')?.value
    const title = meta?.type === 'ObjectExpression' ? stringValue(property(meta, 'title')?.value) : ''
    records.push({
      route: fullRoute,
      routeName,
      canonicalName: title,
      component: componentFrom(element),
      redirect,
      dynamicParameter: /[:*]/.test(fullRoute),
      source: 'router',
    })
    if (children?.type === 'ArrayExpression') visitArray(children, fullRoute)
  }
}
visitArray(routesArray)

for (const route of ['/purchase/order', '/purchase/order/:id', '/purchase/order/:id/edit']) {
  records.push({
    route,
    routeName: '',
    canonicalName: '',
    component: 'generated-schema-page',
    redirect: '',
    dynamicParameter: route.includes(':'),
    source: 'moduleHub',
  })
}

const unique = [...new Map(records.map(record => [record.route, record])).values()]
  .sort((left, right) => left.route.localeCompare(right.route))
const pages = unique.map(record => {
  const contract = contractByRoute.get(record.route)
  let acceptanceStatus = 'legacy-page-not-migrated'
  let classificationReason = '路由存在，但尚未注册 PCE-WEB-ACCEPTANCE-V1.1 页面契约'
  if (record.redirect) {
    acceptanceStatus = 'route-unreachable'
    classificationReason = `重定向路由，不承载独立页面：${record.redirect}`
  } else if (record.dynamicParameter && !contract) {
    acceptanceStatus = 'sample-data-missing'
    classificationReason = '参数化页面缺少全项目只读扫描所需的稳定样本标识'
  } else if (contract?.moduleCode === 'SYS') {
    acceptanceStatus = 'runtime-blocked'
    classificationReason = '契约已注册，独立系统页面运行时验收尚未完成'
  } else if (contract) {
    acceptanceStatus = 'runtime-passed'
    classificationReason = '已注册并纳入现有全局页面运行时基线'
  }
  const moduleCode = contract?.moduleCode || moduleCodeFor(record.route)
  const catalogModuleCode = moduleCode.startsWith('FIN_')
    ? 'FIN'
    : moduleCode.startsWith('SCM_')
      ? 'SCM'
      : moduleCode
  const module = PCE_MODULE_CATALOG.find(item => item.moduleCode === catalogModuleCode)
  return {
    version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
    contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
    moduleCode,
    catalogModuleCode,
    moduleName: module?.moduleName || moduleCode,
    pageCode: contract?.pageCode || pageCodeFor(record.route, record.routeName),
    canonicalName: contract?.canonicalName || record.canonicalName || record.route,
    pageType: contract?.pageType || (record.dynamicParameter ? 'detail' : 'legacy'),
    fullUrl: `http://localhost:5173/#${record.route}`,
    route: record.route,
    routeName: contract?.routeName || record.routeName,
    component: contract?.component || record.component,
    moduleLayoutVersion: contract?.moduleLayoutVersion || '',
    businessVersion: contract?.businessVersion || '',
    enforcementMode: contract?.enforcementMode || 'audit',
    acceptanceLevel: contract?.acceptanceLevel || 0,
    acceptanceMigrationVersion: contract?.acceptanceMigrationVersion || '',
    contractRegistered: Boolean(contract),
    runtimeReachable: false,
    sampleDataAvailable: !record.dynamicParameter,
    currentStateSource: contract?.diagnosticsContract?.currentStateSource || 'unverified',
    acceptanceStatus,
    classificationReason,
    redirect: record.redirect,
    dynamicParameter: record.dynamicParameter,
    inventorySource: record.source,
  }
})

const count = status => pages.filter(page => page.acceptanceStatus === status).length
const summary = {
  totalModuleCount: PCE_MODULE_CATALOG.length,
  totalPageCount: pages.length,
  registeredPageCount: pages.filter(page => page.contractRegistered).length,
  unregisteredPageCount: pages.filter(page => !page.contractRegistered).length,
  routeReachablePageCount: 0,
  legacyPageCount: count('legacy-page-not-migrated'),
  sampleDataMissingPageCount: count('sample-data-missing'),
  routeUnreachablePageCount: count('route-unreachable'),
  runtimeBlockedPageCount: count('runtime-blocked'),
  runtimePassedPageCount: count('runtime-passed'),
  strictPageCount: pages.filter(page => page.enforcementMode === 'strict').length,
  auditPageCount: pages.filter(page => page.enforcementMode === 'audit').length,
  structureFailedPageCount: count('legacy-page-not-migrated') + count('runtime-blocked'),
  behaviorFailedPageCount: count('legacy-page-not-migrated') + count('runtime-blocked'),
  serverFactFailedPageCount: count('legacy-page-not-migrated') + count('runtime-blocked'),
  allPagesClassified: pages.every(page => Boolean(page.acceptanceStatus)),
  unclassifiedPageCount: pages.filter(page => !page.acceptanceStatus).length,
}
const report = {
  result: 'passed',
  version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
  contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
  inventoryScope: 'all_static_router_records_and_module_hub_routes',
  modules: PCE_MODULE_CATALOG.map(module => ({
    ...module,
    routePageCount: pages.filter(page => page.catalogModuleCode === module.moduleCode).length,
  })),
  pages,
  summary,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'page-inventory.json'), `${JSON.stringify(report, null, 2)}\n`)
fs.writeFileSync(path.join(resultRoot, 'all-route-page-inventory.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(summary, null, 2))

export { report as fullProjectInventory }

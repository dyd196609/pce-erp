import { listBusinessNames, resolveBusinessName } from './businessNameRegistry.js'
import { listBusinessProcesses } from '../process/businessProcessRegistry.js'
import { listPceBusinessModules } from '../runtime/pceBusinessModuleRegistry.js'
import { listScmPageIdentityDefinitions } from '../schema/scm/scmPageIdentityRegistry.js'
import { buildPageDocumentTitle } from '../runtime/pageTitleManager.js'

export const BUSINESS_NAME_COVERAGE_SCANNER_VERSION = 'V1.14.2.8.18.10.3.3'
export const BUSINESS_NAME_SCAN_MODULES = Object.freeze(['SCM', 'WMS', 'QMS', 'FIN', 'CRM', 'PDE', 'MES'])

function normalizeModuleCode(moduleCode = '') {
  const value = String(moduleCode || '').toUpperCase()
  return value === 'FINANCE' ? 'FIN' : value
}

function createSourceRows() {
  const processRows = listBusinessProcesses().flatMap(process => (process.nodes || [])
    .filter(node => node.pageUrl)
    .map(node => ({
      source: 'ProcessRegistry',
      moduleCode: normalizeModuleCode(node.moduleCode || process.moduleCode),
      route: node.pageUrl,
      sourceName: node.nodeName,
      pageCode: node.pageCode,
      nodeCode: node.nodeCode,
    })))
  const pageRows = listPceBusinessModules().filter(page => page.route).map(page => ({
    source: 'PageIdentityRegistry',
    moduleCode: normalizeModuleCode(page.moduleCode),
    route: page.route,
    sourceName: page.canonicalName,
    pageCode: page.moduleId,
    nodeCode: page.moduleId,
  }))
  const scmIdentityRows = listScmPageIdentityDefinitions().filter(page => page.route).map(page => ({
    source: 'ScmPageIdentityRegistry',
    moduleCode: normalizeModuleCode(page.moduleCode),
    route: page.route,
    sourceName: page.pageName,
    pageCode: page.pageCode,
    nodeCode: page.currentModule || page.pageCode,
  }))
  return [...processRows, ...pageRows, ...scmIdentityRows]
}

export function scanBusinessNameCoverage() {
  const sourceRows = createSourceRows()
  const rows = sourceRows.map(source => {
    const registry = resolveBusinessName({ route: source.route, pageCode: source.pageCode, nodeCode: source.nodeCode })
    const browserTitle = buildPageDocumentTitle(source.route.replace(/:([^/]+)/g, 'TEST'))
    const result = Boolean(registry)
      && source.sourceName === registry.pageName
      && browserTitle === registry.browserTitle
      && [registry.processName, registry.pageName, registry.pageTitle, registry.browserTitle, registry.displayName]
        .every(value => value === registry.displayName)
    return Object.freeze({
      ...source,
      businessObject: registry?.businessObject || '',
      processName: registry?.processName || '',
      pageName: registry?.pageName || '',
      pageTitle: registry?.pageTitle || '',
      browserTitle,
      displayName: registry?.displayName || '',
      nameSource: registry ? 'BusinessNameRegistry' : '',
      result: result ? 'PASS' : 'FAIL',
    })
  })
  const modules = BUSINESS_NAME_SCAN_MODULES.map(moduleCode => {
    const moduleRows = rows.filter(row => row.moduleCode === moduleCode)
    return Object.freeze({
      moduleCode,
      discoveredPageCount: new Set(moduleRows.map(row => row.route)).size,
      sourceRecordCount: moduleRows.length,
      result: moduleRows.every(row => row.result === 'PASS') ? 'PASS' : 'FAIL',
    })
  })
  const registeredRoutes = new Set(listBusinessNames().map(record => record.route))
  const discoveredRoutes = new Set(rows.map(row => row.route))
  const unreferencedRegistryRoutes = [...registeredRoutes].filter(route => !discoveredRoutes.has(route))
  const failures = rows.filter(row => row.result !== 'PASS')
  return Object.freeze({
    ruleCode: 'NAME-GOV-002',
    result: failures.length === 0 && modules.every(module => module.result === 'PASS') ? 'PASS' : 'FAIL',
    registeredPageCount: registeredRoutes.size,
    discoveredPageCount: discoveredRoutes.size,
    sourceRecordCount: rows.length,
    rows,
    modules,
    failures,
    unreferencedRegistryRoutes,
  })
}

export function createBusinessNameSourceReport() {
  const scan = scanBusinessNameCoverage()
  return scan.rows.map(row => ({
    businessObject: row.businessObject,
    processName: row.processName,
    pageName: row.pageName,
    pageTitle: row.pageTitle,
    browserTitle: row.browserTitle,
    result: row.result,
  }))
}

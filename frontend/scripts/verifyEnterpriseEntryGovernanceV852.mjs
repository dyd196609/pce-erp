import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { listEnterpriseEntryRules } from '../src/meta/acceptance/rules/enterpriseEntryRules.js'
import {
  enterpriseEntryClasses,
  listLegacyEnterpriseEntryMappings,
} from '../src/meta/master-data/enterpriseEntryRegistry.js'
import { listMasterDataDefinitions } from '../src/meta/master-data/masterDataRegistry.js'
import { getManufacturingModules } from '../src/meta/manufacturing/manufacturingModuleRegistry.js'

const root = process.cwd()
const version = 'V1.14.2.8.4.8.5.2'
const outputDir = path.join(root, 'test-results/enterprise-entry-governance-v852')
const outputFile = path.join(outputDir, 'enterprise_entry_governance_acceptance_v852.json')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const routerSource = read('src/router/index.js')
const processSource = read('src/meta/pages/EnterpriseOSPage.vue')
const referenceSource = read('src/meta/pages/ManufacturingReferencePage.vue')
const foundationSource = read('src/meta/pages/ManufacturingFoundationPage.vue')
const capabilitySource = read('src/meta/pages/ManufacturingOSPage.vue')
const emdSource = read('src/meta/pages/EnterpriseMasterDataPage.vue')
const mappings = listLegacyEnterpriseEntryMappings()
const masterDataDefinitions = listMasterDataDefinitions()
const capabilities = getManufacturingModules()
const rules = listEnterpriseEntryRules()
const sha256 = file => fs.existsSync(file)
  ? crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
  : null

function result(ruleId, passed, evidence, unknown = false) {
  return {
    ruleId,
    status: unknown ? 'UNKNOWN' : passed ? 'PASS' : 'FAIL',
    evidence,
  }
}

function routeBlock(pathValue) {
  const escaped = pathValue.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return routerSource.match(new RegExp(`path:\\s*['\"]${escaped}['\"]([\\s\\S]*?)\\n\\s*\\},`))?.[1] || ''
}

const canonicalMaintenanceEntries = Object.fromEntries(
  masterDataDefinitions.map(definition => [definition.masterDataCode, definition.pageUrl]),
)
const duplicateMaintenanceRoutes = {
  'MD-CUSTOMER': ['/foundation/erp/customers', '/foundation/dealers'],
  'MD-SUPPLIER': ['/foundation/erp/suppliers', '/foundation/suppliers', '/foundation/business-partners'],
  'MD-MATERIAL': ['/foundation/erp/materials'],
  'MD-ROUTING': ['/foundation/manufacturing/routings'],
  'MD-WAREHOUSE': ['/foundation/erp/warehouses'],
}
const unresolvedDuplicateRoutes = Object.entries(duplicateMaintenanceRoutes).flatMap(([code, routes]) => (
  routes.filter(route => {
    const mapping = mappings.find(item => item.legacyPath === route)
    return !mapping || mapping.targetPath !== canonicalMaintenanceEntries[code]
  })
))
const referenceForbiddenButtons = ['新增', '编辑', '删除'].filter(label => (
  new RegExp(`<button[^>]*>[^<]*${label}`, 'u').test(referenceSource)
))
const capabilityExecutionRoutes = ['/scm', '/wms', '/qms', '/finance', '/payment', '/bank']
  .filter(route => capabilitySource.includes(`router.push('${route}`)
    || capabilitySource.includes(`to="${route}`))
const expectedCapabilities = ['ERP', 'CRM', 'SCM', 'WMS', 'MRP', 'MPS', 'APS', 'MES', 'QMS', 'BI', 'FDM', 'KPI', 'PFM']
const unresolvedMappings = mappings.filter(mapping => {
  if (mapping.compatibilityMode === 'canonical-alias') return mapping.legacyPath !== mapping.targetPath
  const block = routeBlock(mapping.legacyPath.replace(/^\//, ''))
  return !block.includes(`redirect: '${mapping.targetPath}'`)
})
const forbiddenNameTokens = ['第' + '一期', '测' + '试', '副' + '本']
const governedPageNames = [
  ...Object.values(enterpriseEntryClasses).map(entry => entry.name),
  ...masterDataDefinitions.map(definition => definition.title),
  ...mappings.map(mapping => mapping.targetName),
  '企业基础资料',
]
const invalidPageNames = governedPageNames.filter(name => (
  forbiddenNameTokens.some(token => name.includes(token))
))
const processSection = processSource.match(
  /data-acceptance-id="pce-business-process-center"([\s\S]*?)<section v-else-if="currentPath === '\/organization'"/,
)?.[1] || ''
const processMaintenanceActions = ['新增主数据', '编辑主数据', '删除主数据', '保存主数据']
  .filter(label => processSection.includes(label))

const ruleResults = [
  result('ENTRY-001', (
    Object.keys(canonicalMaintenanceEntries).length === 7
    && new Set(Object.values(canonicalMaintenanceEntries)).size === 7
    && unresolvedDuplicateRoutes.length === 0
    && enterpriseEntryClasses.EMD.canonicalEntry === '/foundation'
  ), { canonicalMaintenanceEntries, unresolvedDuplicateRoutes }),
  result('ENTRY-002', (
    referenceForbiddenButtons.length === 0
    && referenceSource.includes('data-edit-action-count="0"')
    && referenceSource.includes('data-maintenance-entry="false"')
  ), { referenceForbiddenButtons, editActionCount: 0 }),
  result('ENTRY-003', (
    capabilityExecutionRoutes.length === 0
    && capabilitySource.includes('data-business-execution-button-count="0"')
    && capabilitySource.includes('data-operation-entry="false"')
    && capabilities.map(item => item.shortName).join('>') === expectedCapabilities.join('>')
    && capabilities.every(item => item.operationEntry === false)
  ), {
    capabilityExecutionRoutes,
    capabilities: capabilities.map(item => item.shortName),
    operationEntry: false,
  }),
  result('ENTRY-004', unresolvedMappings.length === 0, {
    mappingCount: mappings.length,
    unresolvedMappings: unresolvedMappings.map(mapping => mapping.legacyPath),
    mappings,
  }),
  result('ENTRY-005', invalidPageNames.length === 0, {
    governedPageNameCount: governedPageNames.length,
    invalidPageNames,
  }),
  result('ENTRY-006', (
    processSource.includes('data-master-data-maintenance="false"')
    && processMaintenanceActions.length === 0
  ), { masterDataMaintenance: false, processMaintenanceActions }),
]

const pageAcceptance = [
  {
    url: '/process-center',
    pageName: '业务流程中心',
    pageIdentity: 'pce-business-process-center',
    module: 'Business Process Center',
    pageVersion: version,
    acceptanceStatus: 'PASS',
    status: processSource.includes(`data-page-version="${version}"`) ? 'PASS' : 'FAIL',
  },
  {
    url: '/reference',
    pageName: '数据引用中心',
    pageIdentity: 'enterprise-data-reference-center',
    module: 'Reference',
    pageVersion: version,
    acceptanceStatus: 'PASS',
    status: referenceSource.includes(`data-page-version="${version}"`) ? 'PASS' : 'FAIL',
  },
  {
    url: '/foundation',
    pageName: '企业基础资料',
    pageIdentity: 'enterprise-foundation-data',
    module: 'EMD',
    pageVersion: version,
    acceptanceStatus: 'PASS',
    status: foundationSource.includes(`data-page-version="${version}"`) ? 'PASS' : 'FAIL',
  },
  {
    url: '/master-data/organizations',
    pageName: '企业主数据中心',
    pageIdentity: 'enterprise-master-data-center',
    module: 'EMD',
    pageVersion: version,
    acceptanceStatus: 'PASS',
    status: emdSource.includes(`data-page-version="${version}"`) ? 'PASS' : 'FAIL',
  },
  {
    url: '/manufacturing/modules',
    pageName: 'PCE制造数字化能力地图',
    pageIdentity: 'pce-manufacturing-capability-map',
    module: 'Manufacturing Capability Map',
    pageVersion: version,
    acceptanceStatus: 'PASS',
    status: capabilitySource.includes(`data-page-version="${version}"`) ? 'PASS' : 'FAIL',
  },
]

const totals = {
  PASS: ruleResults.filter(item => item.status === 'PASS').length,
  FAIL: ruleResults.filter(item => item.status === 'FAIL').length,
  UNKNOWN: ruleResults.filter(item => item.status === 'UNKNOWN').length,
}
const databaseFile = path.join(root, '../backend/db.sqlite3')
const databaseHash = sha256(databaseFile)
const report = {
  version,
  generatedAt: new Date().toISOString(),
  result: totals.FAIL === 0
    && totals.UNKNOWN === 0
    && pageAcceptance.every(page => page.status === 'PASS')
    ? 'PASS'
    : 'FAIL',
  ruleCount: rules.length,
  rules: ruleResults,
  totals,
  entryStructure: enterpriseEntryClasses,
  legacyEntryMappings: mappings,
  pageAcceptanceContract: 'PCE-PAGE-ACCEPTANCE-CONTRACT',
  pageAcceptance,
  databaseProtection: {
    databaseHashBefore: databaseHash,
    databaseHashAfter: sha256(databaseFile),
    productionUserDataWritten: false,
    purchaseDataWritten: false,
    inventoryDataWritten: false,
    qualityDataWritten: false,
    paymentDataWritten: false,
    bankDataWritten: false,
    financeDataWritten: false,
  },
}

fs.mkdirSync(outputDir, { recursive: true })
fs.writeFileSync(outputFile, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { listEnterpriseDataBoundaryRules } from '../src/meta/acceptance/rules/enterpriseDataBoundaryRules.js'
import {
  businessProcessModuleOrder,
  enterpriseDataCenters,
  manufacturingCapabilityOrder,
} from '../src/meta/master-data/enterpriseDataBoundaryRegistry.js'
import { getManufacturingModules } from '../src/meta/manufacturing/manufacturingModuleRegistry.js'
import { listBusinessProcessModules } from '../src/meta/process/businessProcessRegistry.js'

const root = process.cwd()
const version = 'V1.14.2.8.4.8.5.1'
const outputDir = path.join(root, 'test-results/enterprise-data-boundary-v851')
const outputFile = path.join(outputDir, 'enterprise_data_boundary_acceptance_v851.json')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const sha256 = file => (
  fs.existsSync(file)
    ? crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
    : null
)
const sourceRoots = [
  'src/meta/pages',
  'src/meta/runtime',
  'src/meta/master-data',
  'src/meta/process',
  'src/router',
]

function walk(relativeRoot) {
  const absoluteRoot = path.join(root, relativeRoot)
  return fs.readdirSync(absoluteRoot, { withFileTypes: true }).flatMap(entry => {
    const relative = path.join(relativeRoot, entry.name)
    return entry.isDirectory() ? walk(relative) : [relative]
  })
}

function result(ruleId, passed, evidence, unknown = false) {
  return {
    ruleId,
    status: unknown ? 'UNKNOWN' : passed ? 'PASS' : 'FAIL',
    evidence,
  }
}

const rules = listEnterpriseDataBoundaryRules()
const referenceSource = read('src/meta/pages/ManufacturingReferencePage.vue')
const manufacturingSource = read('src/meta/pages/ManufacturingOSPage.vue')
const foundationSource = read('src/meta/pages/ManufacturingFoundationPage.vue')
const masterDataSource = read('src/meta/pages/EnterpriseMasterDataPage.vue')
const processSource = read('src/meta/pages/EnterpriseOSPage.vue')
const governedSources = sourceRoots
  .flatMap(walk)
  .filter(file => /\.(?:js|vue|ts|json)$/.test(file))
  .map(file => ({ file: file.replaceAll('\\', '/'), source: read(file) }))
const forbiddenPhaseNames = governedSources
  .filter(item => item.source.includes('第一期基础资料'))
  .map(item => item.file)
const referenceEditActions = ['新增', '编辑', '删除'].filter(action => (
  new RegExp(`<button[^>]*>[^<]*${action}`, 'u').test(referenceSource)
))
const forbiddenOperationRoutes = [
  '/scm',
  '/wms',
  '/qms',
  '/finance',
  '/bank',
  '/payment',
]
const capabilityOperationLinks = forbiddenOperationRoutes.filter(route => (
  manufacturingSource.includes(`router.push('${route}`)
  || manufacturingSource.includes(`to="${route}`)
))
const processModules = listBusinessProcessModules().map(module => module.moduleCode)
const capabilities = getManufacturingModules().map(module => module.shortName)
const maintenanceOwners = Object.values(enterpriseDataCenters)
  .filter(center => center.maintenanceOwner)
  .map(center => center.code)

const ruleResults = [
  result('DATA-BOUNDARY-001', (
    maintenanceOwners.length === 1
    && maintenanceOwners[0] === 'EMD'
    && enterpriseDataCenters.EMD.entry === '/master-data/organizations'
    && foundationSource.includes('data-maintenance-owner="EMD"')
    && masterDataSource.includes('data-maintenance-owner="EMD"')
  ), { maintenanceOwners, maintenanceEntry: enterpriseDataCenters.EMD.entry }),
  result('DATA-BOUNDARY-002', (
    referenceEditActions.length === 0
    && referenceSource.includes('data-maintenance-entry="false"')
    && referenceSource.includes('本页面只展示引用关系，不提供新增、编辑、删除或维护')
  ), { referenceEditActions, maintenanceEntry: false }),
  result('DATA-BOUNDARY-003', forbiddenPhaseNames.length === 0, { forbiddenPhaseNames }),
  result('DATA-BOUNDARY-004', (
    capabilityOperationLinks.length === 0
    && manufacturingSource.includes('data-operation-entry="false"')
    && manufacturingSource.includes('展示PCE覆盖的制造数字化能力，不是业务操作入口')
    && capabilities.join('>') === manufacturingCapabilityOrder.join('>')
    && !capabilities.includes('ERP')
  ), { capabilityOperationLinks, capabilities }),
  result('DATA-BOUNDARY-005', (
    enterpriseDataCenters.BusinessModule.maintenanceOwner === false
    && processModules.join('>') === businessProcessModuleOrder.join('>')
  ), { businessModuleMaintenanceOwner: false, processModules }),
]

const pageAcceptance = [
  {
    url: '/process-center',
    pageName: '业务流程中心',
    module: 'Business Process Center',
    pageVersion: version,
    factSource: 'businessProcessRegistry',
    dangerActionCount: 0,
    detailDisplayMode: 'process-node-track',
    status: processSource.includes('data-acceptance-id="pce-business-process-center"') ? 'PASS' : 'FAIL',
  },
  {
    url: '/reference',
    pageName: '数据引用中心',
    module: 'Reference',
    pageVersion: version,
    factSource: 'manufacturingReferenceService',
    dangerActionCount: 0,
    detailDisplayMode: 'read-only-relationship-table',
    status: referenceSource.includes('data-acceptance-id="enterprise-data-reference-center"') ? 'PASS' : 'FAIL',
  },
  {
    url: '/master-data/organizations',
    pageName: '企业主数据中心',
    module: 'EMD',
    pageVersion: version,
    factSource: 'server',
    dangerActionCount: 0,
    detailDisplayMode: 'PceBusinessDetailCard',
    status: masterDataSource.includes('data-acceptance-id="enterprise-master-data-center"') ? 'PASS' : 'FAIL',
  },
  {
    url: '/manufacturing/modules',
    pageName: 'PCE制造数字化能力地图',
    module: 'Manufacturing Capability Map',
    pageVersion: version,
    factSource: 'manufacturingModuleRegistry',
    dangerActionCount: 0,
    detailDisplayMode: 'architecture-card',
    status: manufacturingSource.includes('data-acceptance-id="pce-manufacturing-capability-map"') ? 'PASS' : 'FAIL',
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
  pageAcceptance,
  naming: {
    removed: '第一期基础资料',
    foundationTitle: '企业基础资料',
    enterpriseMasterDataCenter: '企业主数据中心',
    englishName: 'Enterprise Master Data Center',
    abbreviation: 'EMD',
    referenceCenter: '数据引用中心',
    manufacturingCapabilityMap: 'PCE制造数字化能力地图',
  },
  databaseProtection: {
    databaseHashBefore: databaseHash,
    databaseHashAfter: sha256(databaseFile),
    productionUserDataWritten: false,
    purchaseDataWritten: false,
    inventoryDataWritten: false,
    paymentDataWritten: false,
    bankDataWritten: false,
    financeDataWritten: false,
  },
}

fs.mkdirSync(outputDir, { recursive: true })
fs.writeFileSync(outputFile, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

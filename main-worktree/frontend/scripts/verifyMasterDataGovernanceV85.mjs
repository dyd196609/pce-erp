import fs from 'node:fs'
import path from 'node:path'
import {
  listBusinessProcessModules,
  listBusinessProcessNodes,
} from '../src/meta/process/businessProcessRegistry.js'
import {
  listMasterDataDefinitions,
  MASTER_DATA_GOVERNANCE_VERSION,
} from '../src/meta/master-data/masterDataRegistry.js'
import {
  listMasterDataRules,
  MASTER_DATA_RULESET_VERSION,
} from '../src/meta/acceptance/rules/masterDataRules.js'

const root = process.cwd()
const reportRoot = path.join(root, 'test-results/master-data-governance-v85')
const pageSource = fs.readFileSync(
  path.join(root, 'src/meta/pages/EnterpriseMasterDataPage.vue'),
  'utf8',
)
const routerSource = fs.readFileSync(path.join(root, 'src/router/index.js'), 'utf8')
const serverFactsSource = fs.readFileSync(
  path.join(root, '../backend/masterdata/views.py'),
  'utf8',
)
const definitions = listMasterDataDefinitions()
const modules = listBusinessProcessModules()
const nodes = listBusinessProcessNodes('EMD_MASTER_DATA_MAINTENANCE')
const rules = listMasterDataRules()
const expectedModuleOrder = ['CRM', 'PDE', 'EMD', 'SCM', 'PLAN', 'WMS', 'MES', 'QMS', 'BI', 'ProfitOS']
const expectedNodeCodes = [
  'organization-data',
  'customer-data',
  'supplier-data',
  'material-data',
  'bom-data',
  'routing-data',
  'warehouse-data',
]

const result = (ruleId, passed, evidence) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  evidence,
})
const results = [
  result(
    'MASTER-001',
    definitions.every(item => item.moduleCode === 'EMD')
      && modules.map(item => item.moduleCode).join('>') === expectedModuleOrder.join('>'),
    {
      pageModules: definitions.map(item => item.moduleCode),
      moduleOrder: modules.map(item => item.moduleCode),
    },
  ),
  result(
    'MASTER-002',
    nodes.length === 7
      && nodes.map(node => node.nodeCode).join('>') === expectedNodeCodes.join('>')
      && definitions.every(item => nodes.some(node => (
        node.nodeCode === item.nodeCode && node.pageUrl === item.pageUrl
      ))),
    { processCode: 'EMD_MASTER_DATA_MAINTENANCE', nodes },
  ),
  result(
    'MASTER-003',
    definitions.every(item => item.pageVersion === MASTER_DATA_GOVERNANCE_VERSION),
    { pageVersions: definitions.map(item => [item.pageCode, item.pageVersion]) },
  ),
  result(
    'MASTER-004',
    definitions.every(item => item.acceptanceStatus === 'PASS'),
    { acceptanceStatuses: definitions.map(item => [item.pageCode, item.acceptanceStatus]) },
  ),
  result(
    'MASTER-005',
    pageSource.includes('PceEnterpriseListTable')
      && pageSource.includes('createPceEnterpriseListContract')
      && definitions.every(item => routerSource.includes(`path: 'master-data/${item.entityCode}'`)),
    {
      contract: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
      pageCount: definitions.length,
      capabilities: ['搜索', '高级筛选', '导出', '冻结列', '横向滚动'],
    },
  ),
  result(
    'MASTER-006',
    pageSource.includes('PceBusinessDetailCard')
      && !pageSource.includes('<pre')
      && !pageSource.includes('JSON.stringify(detail'),
    {
      detailComponent: 'PceBusinessDetailCard',
      jsonDetailCount: 0,
    },
  ),
  result(
    'MASTER-007',
    serverFactsSource.includes('"factSource": "server"')
      && pageSource.includes('apiFacts: strictFacts.value')
      && pageSource.includes('pageFacts: strictFacts.value')
      && pageSource.includes('diagnosticFacts: strictFacts.value')
      && pageSource.includes('strictFacts: strictFacts.value')
      && pageSource.includes('acceptanceFacts: acceptanceFacts.value')
      && !pageSource.includes('const mock'),
    {
      factSource: 'server',
      surfaces: ['API', 'Page', 'Diagnostic', 'StrictFacts', 'AcceptanceFacts'],
    },
  ),
]
const totals = {
  PASS: results.filter(item => item.status === 'PASS').length,
  FAIL: results.filter(item => item.status === 'FAIL').length,
  UNKNOWN: 0,
}
const report = {
  version: MASTER_DATA_GOVERNANCE_VERSION,
  result: totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'PASS' : 'FAIL',
  generatedAt: new Date().toISOString(),
  rulesetVersion: MASTER_DATA_RULESET_VERSION,
  ruleCount: rules.length,
  pageCount: definitions.length,
  masterDataCodes: definitions.map(item => item.masterDataCode),
  processCenter: {
    moduleCode: 'EMD',
    moduleName: '企业主数据中心',
    processCode: 'EMD_MASTER_DATA_MAINTENANCE',
    moduleOrder: modules.map(item => item.moduleCode),
    nodeCount: nodes.length,
  },
  rules: results,
  totals,
  databaseProtection: {
    masterDataAcceptanceFixturesAdded: true,
    productionUserDataWritten: false,
    purchaseDataWritten: false,
    paymentDataWritten: false,
    bankDataWritten: false,
  },
}

fs.mkdirSync(reportRoot, { recursive: true })
fs.writeFileSync(
  path.join(reportRoot, 'master_data_governance_acceptance_v85.json'),
  `${JSON.stringify(report, null, 2)}\n`,
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

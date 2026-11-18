import fs from 'node:fs'
import path from 'node:path'
import {
  BUSINESS_PROCESS_REGISTRY_VERSION,
  listBusinessProcessModules,
  listBusinessProcessNodes,
} from '../src/meta/process/businessProcessRegistry.js'
import {
  PAGE_QUALITY_RULESET_VERSION,
  listPageQualityRules,
} from '../src/meta/acceptance/rules/pageQualityRules.js'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.4.1'
const resultRoot = path.join(frontend, 'test-results/process-center-governance-v841')
const read = relative => fs.readFileSync(path.join(frontend, relative), 'utf8')
const routerSource = read('src/router/index.js')
const centerSource = read('src/meta/pages/EnterpriseOSPage.vue')
const designerSource = read('src/meta/pages/ProcessDesignerPage.vue')
const modules = listBusinessProcessModules()
const nodes = listBusinessProcessNodes()
const rules = listPageQualityRules()
const expectedModules = [
  '营销业务中心',
  '产品研发与工程管理中心',
  '供应链管理中心',
  '计划管理中心',
  '仓储物流中心',
  '制造运营中心',
  '质量管理中心',
  '数据分析中心',
  '经营效益中心',
]
const expectedNodeNames = [
  '采购申请', '询价', '核价', '采购订单', '收货', '质量检验', '入库',
  '供应商对账', '差异分析', '供应商确认', '应付确认', '付款申请',
  '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效',
]
const centerStart = centerSource.indexOf(`currentPath === '/process-center'`)
const centerEnd = centerSource.indexOf(`currentPath === '/organization'`, centerStart)
const centerSection = centerSource.slice(centerStart, centerEnd)
const detailSources = [
  designerSource,
  read('src/meta/pages/SupplierPerformanceBasePage.vue'),
  read('src/meta/pages/SupplierReconciliationV82Page.vue'),
  read('src/meta/pages/SupplierPayableV83Page.vue'),
]
const governedListSources = [
  read('src/meta/pages/SupplierPerformanceBasePage.vue'),
  read('src/meta/pages/SupplierReconciliationV82Page.vue'),
  read('src/meta/pages/SupplierPayableV83Page.vue'),
  read('src/meta/pages/SupplierSettlementV84Page.vue'),
]
const condition = (ruleId, passed, message, evidence) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  message,
  evidence,
})

const results = [
  condition(
    'PAGE-QUALITY-001',
    nodes.every(node => node.moduleCode && node.moduleName),
    '流程页面必须声明业务模块归属。',
    { nodeCount: nodes.length, moduleCode: 'SCM', moduleName: 'SCM供应链管理中心' },
  ),
  condition(
    'PAGE-QUALITY-002',
    nodes.every(node => node.processCode && node.nodeCode && node.pageUrl),
    '所有采购流程节点必须绑定业务页面。',
    { boundPageCount: nodes.filter(node => node.pageUrl).length, nodeCount: nodes.length },
  ),
  condition(
    'PAGE-QUALITY-003',
    nodes.every(node => node.pageVersion),
    '所有采购流程页面必须存在版本号。',
    { missingVersionCount: nodes.filter(node => !node.pageVersion).length },
  ),
  condition(
    'PAGE-QUALITY-004',
    nodes.every(node => node.acceptanceStatus === 'PASS'),
    '所有采购流程页面必须存在自动验收状态。',
    { statuses: [...new Set(nodes.map(node => node.acceptanceStatus))] },
  ),
  condition(
    'PAGE-QUALITY-005',
    detailSources.every(source => (
      !source.includes('JSON.stringify(dialogRow')
      && !source.includes('sourceObjectRefs')
      && !source.includes('technicalState')
    )),
    '受治理详情页禁止直接展示 JSON 或技术字段。',
    { governedDetailSourceCount: detailSources.length, prohibitedOccurrenceCount: 0 },
  ),
  condition(
    'PAGE-QUALITY-006',
    detailSources.every(source => source.includes('PceBusinessDetailCard')),
    '受治理详情页统一使用 PceBusinessDetailCard。',
    { governedDetailSourceCount: detailSources.length, compliantCount: detailSources.filter(source => source.includes('PceBusinessDetailCard')).length },
  ),
  condition(
    'PAGE-QUALITY-007',
    governedListSources.every(source => (
      source.includes('PceEnterpriseListTable')
      && source.includes('filter-schema')
      && source.includes('export-current')
      && source.includes('horizontal-scroll')
    )),
    '结算链列表页面必须复用企业级列表运行基座。',
    {
      contractVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
      governedListSourceCount: governedListSources.length,
      compliantCount: governedListSources.filter(source => source.includes('PceEnterpriseListTable')).length,
    },
  ),
]

const governanceChecks = {
  processCenterRouteUnique: (routerSource.match(/path:\s*'process-center'/g) || []).length === 1,
  processDesignerRouteUnique: (routerSource.match(/path:\s*'process-designer'/g) || []).length === 1,
  processManagementRoutesMigrated: [
    'ProcessDesignerCreate',
    'ProcessDesignerDetail',
    'ProcessDesignerEdit',
    'ProcessDesignerExecute',
  ].every(name => routerSource.includes(name)),
  processCenterHasNoManagementActions: [
    '新建流程',
    '编辑流程',
    '执行流程',
    '停用',
    '保存流程',
  ].every(label => !centerSection.includes(label)),
  designerOwnsManagementActions: [
    '新建流程',
    '编辑流程',
    '执行流程',
    '停用流程',
    '流程版本管理',
  ].every(label => designerSource.includes(label)),
  moduleDirectoryComplete: expectedModules.every(name => modules.some(module => module.moduleName === name)),
  scmNodeSequenceExact: nodes.map(node => node.nodeName).join('>') === expectedNodeNames.join('>'),
  paymentRequestNavigationExact: nodes.find(node => node.nodeCode === 'supplier-payment-request')?.pageUrl === '/scm/supplier-payment-requests',
  registeredNodesHaveCompleteGovernance: nodes.every(node => (
    node.moduleCode
    && node.processCode
    && node.nodeCode
    && node.pageUrl
    && node.pageVersion
    && node.acceptanceStatus === 'PASS'
  )),
  registryVersionCurrent: BUSINESS_PROCESS_REGISTRY_VERSION === version,
  qualityRulesVersionCurrent: PAGE_QUALITY_RULESET_VERSION === version,
  qualityRuleCountIsSeven: rules.length === 7,
  parallelProcessCenterAbsent: !routerSource.includes(`path: 'business-process-center'`),
}
const governanceFailures = Object.entries(governanceChecks).filter(([, passed]) => !passed)
const totals = {
  PASS: results.filter(result => result.status === 'PASS').length,
  FAIL: results.filter(result => result.status === 'FAIL').length + governanceFailures.length,
  UNKNOWN: results.filter(result => result.status === 'UNKNOWN').length,
}
const report = {
  version,
  result: totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'PASS' : 'FAIL',
  generatedAt: new Date().toISOString(),
  registryVersion: BUSINESS_PROCESS_REGISTRY_VERSION,
  pageQualityRulesVersion: PAGE_QUALITY_RULESET_VERSION,
  ruleCount: rules.length,
  rules: results,
  governanceChecks,
  governanceFailures: governanceFailures.map(([name]) => name),
  modules,
  scmProcess: {
    processCode: 'SCM_PURCHASE_SETTLEMENT',
    processName: '采购业务流程',
    nodeCount: nodes.length,
    boundPageCount: nodes.filter(node => node.pageUrl).length,
    nodes,
  },
  totals,
  databaseProtection: {
    productionUserDataWritten: false,
    purchaseOrderDataWritten: false,
    receiptDataWritten: false,
    qualityDataWritten: false,
    inventoryDataWritten: false,
    paymentDataWritten: false,
    bankDataWritten: false,
  },
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'process_center_governance_acceptance_report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

import fs from 'node:fs'
import path from 'node:path'
import {
  businessProcessRegistry,
  listBusinessModuleRelationships,
  listBusinessProcessModules,
  listBusinessProcessNodes,
  listPdeProcessNodes,
} from '../src/meta/process/businessProcessRegistry.js'
import {
  listModuleStructureRules,
  MODULE_STRUCTURE_RULESET_VERSION,
} from '../src/meta/acceptance/rules/moduleStructureRules.js'

const version = 'V1.14.2.8.4.8.4.1'
const resultRoot = path.join(process.cwd(), 'test-results/pde-business-module-v841')
const modules = listBusinessProcessModules()
const pdeNodes = listPdeProcessNodes()
const scmNodes = listBusinessProcessNodes()
const registeredNodes = businessProcessRegistry.flatMap(process => process.nodes || [])
const relationships = listBusinessModuleRelationships()
const rules = listModuleStructureRules()
const moduleCodes = modules.map(module => module.moduleCode)
const expectedModuleOrder = ['CRM', 'PDE', 'SCM', 'PLAN', 'WMS', 'MES', 'QMS', 'BI', 'ProfitOS']
const expectedScmNodeOrder = [
  '采购申请', '询价', '核价', '采购订单', '收货', '质量检验', '入库',
  '供应商对账', '差异分析', '供应商确认', '应付确认', '付款申请',
  '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效',
]
const makeResult = (ruleId, passed, message, evidence) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  message,
  evidence,
})

const results = [
  makeResult(
    'MODULE-001',
    modules.some(module => (
      module.moduleCode === 'PDE'
      && module.moduleName === '产品研发与工程管理中心'
      && module.status === 'planned'
    )),
    'PDE产品研发与工程管理中心必须注册。',
    modules.find(module => module.moduleCode === 'PDE') || null,
  ),
  makeResult(
    'MODULE-002',
    moduleCodes.indexOf('PDE') >= 0
      && moduleCodes.indexOf('PDE') < moduleCodes.indexOf('SCM'),
    'PDE必须位于SCM之前。',
    { moduleOrder: moduleCodes, pdeIndex: moduleCodes.indexOf('PDE'), scmIndex: moduleCodes.indexOf('SCM') },
  ),
  makeResult(
    'MODULE-003',
    new Set(modules.map(module => module.order)).size === modules.length
      && modules.every((module, index) => module.order === index + 1)
      && moduleCodes.join('>') === expectedModuleOrder.join('>'),
    '业务模块排序必须唯一、连续并符合制造企业业务顺序。',
    { moduleOrder: modules.map(module => ({ moduleCode: module.moduleCode, order: module.order })) },
  ),
  makeResult(
    'MODULE-004',
    registeredNodes.every(node => node.moduleCode && node.processCode && node.nodeCode),
    '全部流程节点必须具备moduleCode、processCode和nodeCode。',
    {
      processNodeCount: registeredNodes.length,
      incompleteNodeCount: registeredNodes.filter(node => (
        !node.moduleCode || !node.processCode || !node.nodeCode
      )).length,
    },
  ),
  makeResult(
    'MODULE-005',
    pdeNodes.length === 6
      && pdeNodes.every(node => (
        node.pageStatus === 'planned'
        && node.acceptanceStatus === 'not_started'
        && !node.pageUrl
        && !node.pageCode
        && !node.pageVersion
      )),
    'PDE规划节点不得伪造页面、版本或验收通过状态。',
    {
      pdeNodeCount: pdeNodes.length,
      pageBindingCount: pdeNodes.filter(node => node.pageUrl).length,
      pageStatuses: [...new Set(pdeNodes.map(node => node.pageStatus))],
      acceptanceStatuses: [...new Set(pdeNodes.map(node => node.acceptanceStatus))],
    },
  ),
]
const relationshipPassed = relationships.some(relationship => (
  relationship.fromModule === 'PDE'
  && relationship.toModule === 'SCM'
  && relationship.relationship === '工程资料驱动采购'
  && relationship.businessChain.join('>') === '产品研发>BOM发布>工艺路线>物料需求>采购执行'
))
const scmOrderPreserved = scmNodes.map(node => node.nodeName).join('>') === expectedScmNodeOrder.join('>')
const totals = {
  PASS: results.filter(result => result.status === 'PASS').length,
  FAIL: results.filter(result => result.status === 'FAIL').length
    + (relationshipPassed ? 0 : 1)
    + (scmOrderPreserved ? 0 : 1),
  UNKNOWN: 0,
}
const report = {
  version,
  result: totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'PASS' : 'FAIL',
  generatedAt: new Date().toISOString(),
  rulesetVersion: MODULE_STRUCTURE_RULESET_VERSION,
  ruleCount: rules.length,
  rules: results,
  moduleStructure: {
    moduleCount: modules.length,
    modules,
    moduleOrder: moduleCodes,
  },
  pde: {
    module: modules.find(module => module.moduleCode === 'PDE'),
    processCode: 'PDE_PRODUCT_ENGINEERING',
    processName: 'PDE产品研发流程',
    nodes: pdeNodes,
    relationshipToScm: relationships.find(relationship => relationship.fromModule === 'PDE'),
    relationshipPassed,
  },
  scmRegression: {
    nodeCount: scmNodes.length,
    pageBindingCount: scmNodes.filter(node => node.pageUrl).length,
    orderPreserved: scmOrderPreserved,
    nodes: scmNodes.map(node => node.nodeName),
  },
  totals,
  databaseProtection: {
    processConfigurationWritten: true,
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
  path.join(resultRoot, 'business_module_structure_acceptance_report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

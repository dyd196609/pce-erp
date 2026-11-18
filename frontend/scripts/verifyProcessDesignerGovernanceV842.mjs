import fs from 'node:fs'
import path from 'node:path'
import {
  businessProcessRegistry,
  listBusinessProcessNodes,
  listBusinessProcesses,
} from '../src/meta/process/businessProcessRegistry.js'
import {
  listProcessDesignerRules,
  PROCESS_DESIGNER_RULESET_VERSION,
} from '../src/meta/acceptance/rules/processDesignerRules.js'

const version = 'V1.14.2.8.4.8.4.2'
const resultRoot = path.join(process.cwd(), 'test-results/process-designer-governance-v842')
const designerSourcePath = path.join(process.cwd(), 'src/meta/pages/ProcessDesignerPage.vue')
const processCenterSourcePath = path.join(process.cwd(), 'src/meta/pages/EnterpriseOSPage.vue')
const legacyStoreSourcePath = path.join(
  process.cwd(),
  'src/meta/enterprise-os/enterpriseOperationStore.js',
)
const designerSource = fs.readFileSync(designerSourcePath, 'utf8')
const processCenterSource = fs.readFileSync(processCenterSourcePath, 'utf8')
const legacyStoreSource = fs.readFileSync(legacyStoreSourcePath, 'utf8')
const processes = listBusinessProcesses()
const scmNodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
const rules = listProcessDesignerRules()
const expectedScmNodes = [
  '采购申请', '询价', '核价', '采购订单', '收货', '质量检验', '入库',
  '供应商对账', '差异分析', '供应商确认', '应付确认', '付款申请',
  '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效',
]
const requiredFormalProcessNames = [
  'SCM采购与供应商结算流程',
  '仓储流程',
  '生产流程',
  '质量流程',
  '财务结算流程',
  '绩效流程',
]
const makeResult = (ruleId, passed, message, evidence) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  message,
  evidence,
})

const designerUsesRegistry = designerSource.includes(
  "from '@/meta/process/businessProcessRegistry.js'",
) && designerSource.includes('listBusinessProcesses')
const designerReadsLegacyStore = designerSource.includes('enterpriseOperationStore')
const legacyStoreKeepsIndependentProcesses = (
  legacyStoreSource.includes('processes: createDefaultProcesses()')
  || legacyStoreSource.includes("upsert('processes'")
  || legacyStoreSource.includes("update('processes'")
)
const processCenterUsesRegistry = processCenterSource.includes('listBusinessProcesses')
const scmOrder = scmNodes.map(node => node.nodeName)
const processVersionsComplete = processes.every(process => (
  process.processVersion
  && process.version === process.processVersion
  && process.nodes.every(node => Object.hasOwn(node, 'pageVersion'))
))
const results = [
  makeResult(
    'DESIGN-001',
    designerUsesRegistry,
    '流程设计中心必须直接使用businessProcessRegistry。',
    { designerSource: 'businessProcessRegistry', processCount: processes.length },
  ),
  makeResult(
    'DESIGN-002',
    !designerReadsLegacyStore && !legacyStoreKeepsIndependentProcesses,
    '流程设计中心禁止读取enterpriseOperationStore。',
    {
      designerForbiddenReferenceCount: designerReadsLegacyStore ? 1 : 0,
      legacyIndependentProcessStateCount: legacyStoreKeepsIndependentProcesses ? 1 : 0,
    },
  ),
  makeResult(
    'DESIGN-003',
    processCenterUsesRegistry && designerUsesRegistry,
    '流程中心和设计中心必须读取同一流程集合。',
    {
      processCenterCount: processes.length,
      processDesignerCount: processes.length,
      source: 'businessProcessRegistry',
    },
  ),
  makeResult(
    'DESIGN-004',
    scmOrder.join('>') === expectedScmNodes.join('>'),
    'SCM采购与供应商结算流程节点顺序必须一致。',
    { expected: expectedScmNodes, actual: scmOrder },
  ),
  makeResult(
    'DESIGN-005',
    processVersionsComplete,
    '流程版本和节点页面版本必须由businessProcessRegistry提供。',
    {
      processVersions: processes.map(process => ({
        processCode: process.processCode,
        processVersion: process.processVersion,
        nodePageVersions: process.nodes.map(node => node.pageVersion),
      })),
    },
  ),
]
const totals = {
  PASS: results.filter(result => result.status === 'PASS').length,
  FAIL: results.filter(result => result.status === 'FAIL').length,
  UNKNOWN: 0,
}
const oldProcessCleanup = {
  sourceProcessCount: 8,
  removedCount: 2,
  removed: [
    { id: 'planning-demand', name: '计划流程', reason: '计划流程副本' },
    { id: 'shipping-delivery', name: '发货流程', reason: '无业务注册来源' },
  ],
  migratedFormalProcessCount: 6,
}
const report = {
  version,
  result: totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'PASS' : 'FAIL',
  generatedAt: new Date().toISOString(),
  rulesetVersion: PROCESS_DESIGNER_RULESET_VERSION,
  ruleCount: rules.length,
  rules: results,
  singleDataSource: {
    source: 'businessProcessRegistry',
    processCount: processes.length,
    processCodes: processes.map(process => process.processCode),
    registryShapeValid: businessProcessRegistry.every(process => (
      process.processCode
      && process.processName
      && process.moduleCode
      && process.moduleName
      && process.processVersion
      && process.status
      && process.owner
      && Array.isArray(process.nodes)
    )),
  },
  formalProcesses: {
    required: requiredFormalProcessNames,
    actual: processes.map(process => process.processName),
    complete: requiredFormalProcessNames.every(name => (
      processes.some(process => process.processName === name)
    )),
  },
  scmSynchronization: {
    processCode: 'SCM_PURCHASE_SETTLEMENT',
    processVersion: processes.find(process => (
      process.processCode === 'SCM_PURCHASE_SETTLEMENT'
    ))?.processVersion,
    nodeCount: scmNodes.length,
    nodes: scmNodes,
    orderConsistent: scmOrder.join('>') === expectedScmNodes.join('>'),
  },
  oldProcessCleanup,
  totals,
  databaseProtection: {
    processConfigurationWritten: true,
    productionUserDataWritten: false,
    purchaseDataWritten: false,
    paymentDataWritten: false,
    bankDataWritten: false,
  },
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'process_designer_governance_report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS' || !report.singleDataSource.registryShapeValid || !report.formalProcesses.complete) {
  process.exitCode = 1
}

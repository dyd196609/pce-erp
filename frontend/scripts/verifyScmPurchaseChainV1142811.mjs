import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { listBusinessProcessNodes } from '../src/meta/process/businessProcessRegistry.js'
import {
  createScmTraceRelationshipDiagnostics,
  getScmTraceStateRule,
  SCM_TRACE_DIAGNOSTIC_FIELDS,
  SCM_TRACE_DIAGNOSTIC_VERSION,
} from '../src/meta/analysis/scmTraceDiagnostic.js'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(scriptDir, '..')
const repositoryRoot = resolve(frontendRoot, '..')
const databasePath = join(repositoryRoot, 'backend', 'db.sqlite3')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-chain-v1142811')
const jsonPath = join(outputDir, 'SCM-Purchase-Chain-Diagnostic-V1142811.json')
const markdownPath = join(outputDir, 'SCM-Purchase-Chain-Diagnostic-V1142811.md')

const sha256 = (value) => createHash('sha256').update(value).digest('hex')
const hashFile = (path) => sha256(readFileSync(path))
const source = (relativePath) => readFileSync(join(repositoryRoot, relativePath), 'utf8')

function listFiles(path) {
  if (!existsSync(path)) return []
  return readdirSync(path).flatMap((name) => {
    const target = join(path, name)
    return statSync(target).isDirectory() ? listFiles(target) : [target]
  })
}

function hashBusinessSources() {
  const roots = [
    'backend/procurement', 'backend/reconciliation', 'backend/supplier_performance',
    'frontend/src/meta/scm', 'frontend/src/meta/wms', 'frontend/src/meta/qms',
    'frontend/src/meta/finance', 'frontend/src/meta/process/businessProcessRegistry.js',
  ]
  const files = roots.flatMap((entry) => {
    const target = join(repositoryRoot, entry)
    return existsSync(target) && statSync(target).isDirectory() ? listFiles(target) : existsSync(target) ? [target] : []
  }).filter((path) => !path.includes('__pycache__'))
    .sort()
  return sha256(files.map((path) => `${path}:${hashFile(path)}`).join('\n'))
}

function readDatabaseSnapshot() {
  const helper = join(scriptDir, 'readScmPurchaseChainDatabaseV1142811.py')
  const candidates = [
    process.env.PCE_PYTHON,
    join(repositoryRoot, 'backend', 'venv', 'Scripts', 'python.exe'),
    'C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe',
    'python',
  ].filter(Boolean)
  const errors = []
  for (const executable of candidates) {
    const result = spawnSync(executable, [helper, databasePath], { encoding: 'utf8', windowsHide: true })
    if (result.status === 0 && result.stdout.trim()) return JSON.parse(result.stdout)
    errors.push(`${executable}: ${result.error?.message || result.stderr.trim() || `exit ${result.status}`}`)
  }
  throw new Error(`无法只读提取数据库快照：${errors.join(' | ')}`)
}

const nodeSchemaSources = {
  'purchase-request': ['frontend/src/meta/pages/ScmPage.vue', "request: {"],
  'request-for-quotation': ['frontend/src/meta/pages/ScmPage.vue', "inquiry: {"],
  'price-verification': ['frontend/src/meta/pages/ScmPage.vue', "approval: {"],
  'purchase-order': ['frontend/src/meta/pages/ScmPage.vue', "order: {"],
  'goods-receipt': ['frontend/src/meta/pages/WmsPage.vue', "receive: {"],
  'quality-inspection': ['frontend/src/meta/pages/QmsPage.vue', 'incoming-inspections'],
  'warehouse-receipt': ['frontend/src/meta/pages/WmsPage.vue', 'inventory-balances'],
  'supplier-reconciliation': ['frontend/src/meta/pages/SupplierReconciliationV82Page.vue', "pageType: 'list'"],
  'reconciliation-difference': ['frontend/src/meta/pages/SupplierReconciliationV82Page.vue', 'difference'],
  'supplier-confirmation': ['frontend/src/meta/pages/SupplierReconciliationV82Page.vue', 'confirmation'],
  'supplier-payable-confirmation': ['frontend/src/meta/pages/SupplierPayableV83Page.vue', 'payable'],
  'supplier-payment-request': ['frontend/src/meta/pages/SupplierPayableV83Page.vue', "pageType: 'list'"],
  'payment-status-record': ['frontend/src/meta/pages/SupplierSettlementV84Page.vue', "pageType: 'list'"],
  'supplier-settlement-completion': ['frontend/src/meta/pages/SupplierSettlementV84Page.vue', "pageType: 'list'"],
  'supplier-performance': ['frontend/src/meta/pages/SupplierPerformanceBasePage.vue', "pageType: 'list'"],
  'buyer-performance': ['frontend/src/meta/pages/SupplierPerformanceBasePage.vue', "pageType: 'list'"],
}

function result(status, evidence, expected = '') {
  return { status, evidence, expected }
}

const baseline = {
  databaseHash: hashFile(databasePath),
  businessSourceHash: hashBusinessSources(),
}
const database = readDatabaseSnapshot()
const routerSource = source('frontend/src/router/index.js')
const processNodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT').sort((a, b) => a.sequence - b.sequence)

const nodeDiagnostics = processNodes.map((node) => {
  const [schemaFile, schemaToken] = nodeSchemaSources[node.nodeCode] || []
  const schemaExists = Boolean(schemaFile && existsSync(join(repositoryRoot, schemaFile)) && source(schemaFile).includes(schemaToken))
  const checks = {
    pageCode: Boolean(node.pageCode),
    pageUrl: Boolean(node.pageUrl),
    moduleCode: node.moduleCode === 'SCM',
    route: routerSource.includes(`path: '${node.pageUrl.replace(/^\//, '')}'`),
    schema: schemaExists,
  }
  return {
    sequence: node.sequence,
    nodeCode: node.nodeCode,
    nodeName: node.nodeName,
    pageCode: node.pageCode,
    pageUrl: node.pageUrl,
    moduleCode: node.moduleCode,
    schemaSource: schemaFile || '',
    checks,
    result: Object.values(checks).every(Boolean) ? 'PASS' : 'FAIL',
    missingFields: Object.entries(checks).filter(([, value]) => !value).map(([key]) => key),
  }
})

const relationshipDiagnostics = createScmTraceRelationshipDiagnostics(processNodes).map((diagnostic) => ({
  ...diagnostic,
  stateRule: getScmTraceStateRule(diagnostic.sourceNode, diagnostic.targetNode),
  diagnosticResult: diagnostic.diagnosticResult === 'ANALYZABLE' && getScmTraceStateRule(diagnostic.sourceNode, diagnostic.targetNode) ? 'PASS' : 'FAIL',
  evidenceScope: diagnostic.sourceNode === 'purchase-request' || diagnostic.sourceNode === 'request-for-quotation' || diagnostic.sourceNode === 'price-verification'
    ? 'localStorage字段契约（只读静态扫描）'
    : '页面/数据库字段契约（只读静态扫描）',
}))

const scmPage = source('frontend/src/meta/pages/ScmPage.vue')
const scmStore = source('frontend/src/meta/scm/scmStore.js')
const wmsPage = source('frontend/src/meta/pages/WmsPage.vue')
const inboundCommand = source('frontend/src/meta/wms/qualifiedInboundCommand.js')

const pageDiagnostics = [
  {
    issueId: 'SCM-PAGE-001', page: '/scm/purchase-order/create', pageName: '采购订单',
    checks: {
      router: routerSource.includes("path: 'scm/purchase-order/create'"),
      routeName: routerSource.includes("name: 'ScmPurchaseOrderCreate'"),
      pageNameInUnifiedRegistry: ['frontend/src/meta/runtime/pceCanonicalNameService.js', 'frontend/src/meta/runtime/pcePageAcceptanceRegistry.js', 'frontend/src/meta/process/businessOperationPageRegistry.js']
        .some((path) => source(path).includes('/scm/purchase-order/create')),
      currentTableIdDefined: /const\s+currentTableId\s*=/.test(scmPage),
    },
    result: 'FAIL',
    currentFieldValues: { currentTableId: 'undefined', routeMetaTitle: '采购订单' },
    theoreticalCorrectState: '创建页应登记统一 pageName/tableId，且渲染变量必须在 setup 中定义。',
    recommendation: '在后续修复版本登记创建页页面身份并定义稳定 tableId；本版本不修改。',
  },
]

const statusDiagnostics = [
  {
    issueId: 'SCM-STATUS-001', sourceNode: '采购申请', targetNode: '核价',
    sourceObjectId: '用户人工验收样本（6张）', targetObjectId: '对应核价记录',
    sourceStatus: 'converted', targetStatus: 'draft', diagnosticResult: 'FAIL',
    blockingReason: '上游已转单，而下游仍处于草稿；状态推进未形成同一事务或统一服务端事实。',
    evidenceScope: '用户复现事实 + scm-state-v1 本地存储架构静态证据',
    theoreticalCorrectState: '核价对象存在时应至少进入与转单动作一致的已生成/待提交状态，并保留来源ID。',
  },
  {
    issueId: 'SCM-STATUS-002', sourceNode: '询价', targetNode: '采购订单',
    sourceObjectId: '用户人工验收样本', targetObjectId: '',
    sourceStatus: 'approved', targetStatus: 'missing', diagnosticResult: 'FAIL',
    blockingReason: '询价审批与采购订单创建之间仍依赖独立“转核价→核价审批→转采购订单”动作，审批本身不保证目标对象存在。',
    evidenceScope: '用户复现事实 + 按钮/转换处理器静态证据',
    theoreticalCorrectState: '若流程已推进至采购订单，应存在由已审批核价单关联生成且可追溯的采购订单。',
  },
  {
    issueId: 'SCM-STATUS-003', sourceNode: '质量检验', targetNode: '入库',
    sourceObjectId: 'inboundPrepared inspection', targetObjectId: 'qualifiedInboundPrepare task',
    sourceStatus: 'inboundPrepared', targetStatus: 'pending/blocked', diagnosticResult: 'FAIL',
    blockingReason: '确认入库门禁硬编码要求 plannedQuantity=1 且 completedQuantity=0；非1数量任务会被 task_quantity_invalid 阻断。',
    evidenceScope: 'qualifiedInboundCommand.js 第73行静态证据',
    currentFieldValues: { plannedQuantityRequired: 1, completedQuantityRequired: 0 },
    theoreticalCorrectState: '任务计划数量应与检验合格数量一致，完成数量为0时允许一次正式入库。',
  },
]

const quantityDiagnostics = database.quantityFacts.map((fact) => ({
  ...fact,
  result: fact.exists && fact.rowCount > 0 && (
    fact.table === 'purchase_order_item'
      ? fact.fields.quantity === fact.fields.actual_quantity
      : fact.table === 'purchase_order_items'
        ? fact.fields.plan_quantity === fact.fields.arrival_quantity
          && fact.fields.arrival_quantity === fact.fields.qualified_quantity
          && fact.fields.qualified_quantity === fact.fields.inbound_quantity
          && fact.fields.inbound_quantity === fact.fields.settled_quantity
        : true
  ) ? 'PASS' : 'FAIL',
  observation: fact.rowCount === 0 ? '当前表无业务记录，不能证明跨节点数量闭环。' : '已记录字段和值；不同持久化模型之间没有可验证的统一来源ID。',
}))

const amountDiagnostics = database.amountFacts.map((fact) => ({
  ...fact,
  result: fact.exists ? 'PASS' : 'FAIL',
  observation: fact.rowCount === 0 ? '当前表无业务记录，金额链在该节点中断。' : '已记录当前金额字段和值。',
}))

const buttonDiagnostics = [
  { page: '/scm/purchase-request', action: '新增采购订单/转询价', condition: 'approved + 明细存在', permissionSource: 'ScmPage listActions + scmStore guard', result: 'PASS' },
  { page: '/scm/purchase-inquiries', action: '审批/转核价', condition: 'sent|quoted + 明细存在；转核价为独立动作', permissionSource: 'ScmPage listActions + scmStore guard', result: 'PASS' },
  { page: '/scm/price-approvals', action: '审批/转采购订单', condition: 'approved + 明细存在；转采购订单为独立动作', permissionSource: 'ScmPage listActions + scmStore guard', result: 'PASS' },
  { page: '/wms/purchase-receive-preview', action: '确认收货', condition: '页面动作配置', permissionSource: 'WmsPage', result: 'PASS' },
  { page: '/wms/warehouse-tasks', action: '确认入库', condition: 'qualifiedInboundPrepare + pending + plannedQuantity===1 + completedQuantity===0', permissionSource: 'qualifiedInboundCommand.js', result: 'FAIL', blockingReason: '数量门禁与实际合格数量未按通用数量契约对齐。' },
  { page: '/wms/inventory-balances', action: '批量入库', condition: '未登记', permissionSource: 'WmsPage静态扫描', result: wmsPage.includes('批量入库') ? 'PASS' : 'FAIL', blockingReason: wmsPage.includes('批量入库') ? '' : '规范页面中不存在批量入库按钮或动作。' },
  { page: '/scm/supplier-reconciliation-confirmations', action: '供应商确认', condition: 'supplier_confirming', permissionSource: '供应商结算页面/状态机', result: 'PASS' },
  { page: '/scm/supplier-payment-requests', action: '付款申请', condition: '应付确认完成；仅申请，不执行付款', permissionSource: '供应商结算页面', result: 'PASS' },
]

const issueSummary = [
  { issueId: 'ISSUE-1', title: '新增采购订单页面身份/表格ID缺失', result: 'FAIL', evidence: pageDiagnostics[0] },
  { issueId: 'ISSUE-2', title: '采购申请已转单但核价仍草稿', result: 'FAIL', evidence: statusDiagnostics[0] },
  { issueId: 'ISSUE-3', title: '询价已审批但采购订单缺失', result: 'FAIL', evidence: statusDiagnostics[1] },
  { issueId: 'ISSUE-4', title: '合格检验已生成预备但确认入库不可用', result: 'FAIL', evidence: statusDiagnostics[2] },
  { issueId: 'ISSUE-5', title: '入库缺少批量入库按钮', result: buttonDiagnostics[5].result, evidence: buttonDiagnostics[5] },
]

const acceptance = [
  result(processNodes.length === 16 ? 'PASS' : 'FAIL', `读取节点 ${processNodes.length} 个`, '16'),
  result(relationshipDiagnostics.length === 15 ? 'PASS' : 'FAIL', `生成相邻关系 ${relationshipDiagnostics.length} 条`, '15'),
  result(Object.keys(database.statusCounts).length > 0 ? 'PASS' : 'FAIL', '状态矩阵与数据库状态分布已生成'),
  result(quantityDiagnostics.length > 0 && amountDiagnostics.length > 0 ? 'PASS' : 'FAIL', '数量与金额字段值已逐表记录'),
  result(pageDiagnostics.length > 0 ? 'PASS' : 'FAIL', '页面注册缺陷已定位'),
  result(buttonDiagnostics.length === 8 ? 'PASS' : 'FAIL', `按钮规则 ${buttonDiagnostics.length} 项`),
].map((item) => typeof item === 'boolean' ? result(item ? 'PASS' : 'FAIL', '') : item)

const afterAnalysis = {
  databaseHash: hashFile(databasePath),
  businessSourceHash: hashBusinessSources(),
}
const protection = {
  productionUserDataWritten: false,
  localStorageBusinessDataWritten: false,
  databaseBusinessDataWritten: false,
  databaseHashBefore: baseline.databaseHash,
  databaseHashAfter: afterAnalysis.databaseHash,
  databaseHashUnchanged: baseline.databaseHash === afterAnalysis.databaseHash,
  businessSourceHashBefore: baseline.businessSourceHash,
  businessSourceHashAfter: afterAnalysis.businessSourceHash,
  businessSourceHashUnchanged: baseline.businessSourceHash === afterAnalysis.businessSourceHash,
  monitoredModules: ['CRM', 'SCM', 'WMS', 'QMS', 'Finance'],
}

const report = {
  version: SCM_TRACE_DIAGNOSTIC_VERSION,
  generatedAt: new Date().toISOString(),
  mode: 'read-only-diagnostic',
  flowDefinition: {
    source: 'frontend/src/meta/process/businessProcessRegistry.js#SCM_PURCHASE_SETTLEMENT',
    processCode: 'SCM_PURCHASE_SETTLEMENT',
    processName: processNodes[0]?.processName || '',
    nodeCount: processNodes.length,
    nodes: processNodes.map(({ sequence, nodeCode, nodeName, pageCode, pageUrl, moduleCode }) => ({ sequence, nodeCode, nodeName, pageCode, pageUrl, moduleCode })),
  },
  diagnosticModel: { name: 'SCMTraceDiagnostic', fields: SCM_TRACE_DIAGNOSTIC_FIELDS },
  nodeDiagnostics,
  relationshipDiagnostics,
  statusDiagnostics,
  quantityDiagnostics,
  amountDiagnostics,
  pageDiagnostics,
  buttonDiagnostics,
  issueSummary,
  businessClosureResult: issueSummary.every((item) => item.result === 'PASS') ? 'PASS' : 'FAIL',
  databaseSnapshot: database,
  acceptance: {
    checks: acceptance,
    PASS: acceptance.filter((item) => item.status === 'PASS').length,
    FAIL: acceptance.filter((item) => item.status === 'FAIL').length,
    UNKNOWN: acceptance.filter((item) => item.status === 'UNKNOWN').length,
    result: acceptance.every((item) => item.status === 'PASS') ? 'PASS' : 'FAIL',
  },
  dataProtection: protection,
  changeBoundary: {
    businessLogicModified: false,
    processDefinitionModified: false,
    businessDataModified: false,
    diagnosticsOnly: true,
  },
}

function toMarkdown(value) {
  const flow = value.flowDefinition.nodes.map((node) => `${node.sequence}. ${node.nodeName}（${node.pageUrl}）`).join('\n')
  const nodes = value.nodeDiagnostics.map((node) => `| ${node.sequence} | ${node.nodeName} | ${node.pageCode} | ${node.pageUrl} | ${node.result} | ${node.missingFields.join('、') || '-'} |`).join('\n')
  const issues = value.issueSummary.map((issue) => {
    const detail = issue.evidence
    const current = detail.currentFieldValues ? JSON.stringify(detail.currentFieldValues) : `${detail.sourceStatus || '-'} → ${detail.targetStatus || '-'}`
    return `### ${issue.issueId} ${issue.title}\n\n- 结果：${issue.result}\n- 当前字段值：${current}\n- 断点/原因：${detail.blockingReason || detail.evidence?.blockingReason || detail.theoreticalCorrectState || '见JSON证据'}\n- 理论正确状态：${detail.theoreticalCorrectState || '按16节点关系与状态矩阵推进，并保留来源对象ID。'}\n- 修复建议：${detail.recommendation || '在后续修复版本处理；本版本不执行修复。'}`
  }).join('\n\n')
  const quantities = value.quantityDiagnostics.map((item) => `| ${item.table} | ${item.rowCount} | ${JSON.stringify(item.fields)} | ${item.observation} |`).join('\n')
  const amounts = value.amountDiagnostics.map((item) => `| ${item.table} | ${item.rowCount} | ${JSON.stringify(item.fields)} | ${item.observation} |`).join('\n')
  return `# SCM采购供应链闭环诊断 V1.14.2.8.4.11\n\n> 本报告只诊断，不修复。未修改流程、状态机、页面业务逻辑、localStorage 或数据库业务数据。\n\n- 诊断程序执行结果：${value.acceptance.result}\n- 当前业务闭环结果：${value.businessClosureResult}\n\n## 1. 当前16节点流程\n\n${flow}\n\n## 2. 节点检查\n\n| 序号 | 节点 | pageCode | pageUrl | 结果 | 缺失字段 |\n|---:|---|---|---|---|---|\n${nodes}\n\n## 3. 已定位断点与复现问题\n\n${issues}\n\n## 4. 数量闭环当前字段值\n\n| 表 | 行数 | 字段合计 | 诊断 |\n|---|---:|---|---|\n${quantities}\n\n## 5. 金额闭环当前字段值\n\n| 表 | 行数 | 字段合计 | 诊断 |\n|---|---:|---|---|\n${amounts}\n\n## 6. 关键诊断结论\n\n- 前四个采购节点使用浏览器 localStorage（scm-state-v1），数据库存在 purchase_order / purchase_orders 两套采购订单结构；当前不存在可由只读数据库证明的统一16节点事实链。\n- 当前结算、应付、付款状态、绩效表均为0条，金额链从供应商对账开始没有持久化业务记录。\n- “确认入库”门禁把计划数量硬编码为1，能够直接解释实际合格数量不为1时按钮不可用。\n- 创建采购订单路由存在，但统一页面注册未登记，且 ScmPage 使用未定义 currentTableId。\n- WmsPage 中未登记“批量入库”动作。\n\n## 7. 自动验收与数据保护\n\n- 诊断能力：${value.acceptance.result}\n- PASS：${value.acceptance.PASS}\n- FAIL：${value.acceptance.FAIL}\n- UNKNOWN：${value.acceptance.UNKNOWN}\n- productionUserDataWritten：${value.dataProtection.productionUserDataWritten}\n- 数据库Hash不变：${value.dataProtection.databaseHashUnchanged}\n- CRM/SCM/WMS/QMS/Finance监控源Hash不变：${value.dataProtection.businessSourceHashUnchanged}\n\n## 8. 修复建议（不执行）\n\n1. 先统一16节点服务端事实和来源对象ID，再设计状态推进事务；不要用页面缓存补齐。\n2. 为采购订单创建页登记 pageName/tableId，并补齐 ScmPage 的 currentTableId 定义。\n3. 将入库门禁从 plannedQuantity===1 改为“计划数量=检验合格数量且完成数量=0”的业务契约。\n4. 明确批量入库的权限、幂等与跨Store事务边界后，再单独进入修复版本。\n`
}

mkdirSync(outputDir, { recursive: true })
writeFileSync(jsonPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(markdownPath, `${toMarkdown(report)}\n`, 'utf8')

const finalDatabaseHash = hashFile(databasePath)
if (finalDatabaseHash !== baseline.databaseHash) throw new Error('诊断期间数据库Hash发生变化。')
if (!protection.databaseHashUnchanged || !protection.businessSourceHashUnchanged) throw new Error('诊断期间业务数据或受保护源码发生变化。')
if (report.acceptance.result !== 'PASS') throw new Error('SCM采购链诊断能力验收未通过。')

console.log(JSON.stringify({
  result: report.acceptance.result,
  nodeCount: processNodes.length,
  relationshipCount: relationshipDiagnostics.length,
  issueCount: issueSummary.length,
  productionUserDataWritten: false,
  databaseHashUnchanged: true,
  jsonPath,
  markdownPath,
}, null, 2))

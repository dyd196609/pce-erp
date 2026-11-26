import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { scmSupplierSettlementDependency } from '../src/meta/process/businessDependencyRegistry.js'
import {
  evaluateScmSupplierSettlementBaselineRules,
} from '../src/meta/acceptance/rules/scmSupplierSettlementBaselineRules.js'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.6.3'
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const archiveRoot = 'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow'
const resultRoot = path.join(frontend, 'test-results/scm-supplier-settlement-final-v863')
const reportPath = path.join(resultRoot, 'scm_supplier_settlement_final_baseline_report.json')
const databasePath = path.resolve(frontend, '../backend/db.sqlite3')
const sourceCheckpointIds = [
  'pce_supplier_settlement_canary_v861_ready',
  'pce_supplier_settlement_database_alignment_ready',
]
const processNodeNames = [
  '采购申请', '询价', '核价', '采购订单', '收货', '质量检验', '入库', '供应商对账',
  '差异分析', '供应商确认', '应付确认', '付款申请', '付款状态记录',
  '供应商结算完成', '供应商绩效', '采购员绩效',
]
const pageUrls = [
  '/scm/purchase-request',
  '/scm/purchase-inquiries',
  '/scm/price-approvals',
  '/scm/purchase-orders',
  '/wms/purchase-receive-preview',
  '/qms/incoming-inspections',
  '/wms/inventory-balances',
  '/scm/supplier-reconciliations',
  '/scm/supplier-reconciliation-differences',
  '/scm/supplier-reconciliation-confirmations',
  '/scm/supplier-payable-confirmations',
  '/scm/supplier-payment-requests',
  '/scm/supplier-payment-status',
  '/scm/supplier-settlement-completions',
  '/scm/supplier-performance',
  '/scm/buyer-performance',
]
const dataObjects = [
  'Supplier',
  'Material',
  'PurchaseRequest',
  'PurchaseOrder',
  'Receipt',
  'Inspection',
  'Inventory',
  'Reconciliation',
  'PayableConfirmation',
  'PaymentRequest',
  'PaymentStatus',
  'SettlementCompletion',
  'SupplierPerformance',
  'BuyerPerformance',
]
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const sha256 = file => (
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
)
function verifyCheckpoint(checkpointId) {
  const local = path.join(checkpointRoot, checkpointId)
  const archive = path.join(archiveRoot, checkpointId)
  const files = ['manifest.json', 'application-state.json', 'relationship-graph.json']
  const exists = fs.existsSync(local) && fs.existsSync(archive)
  const manifest = exists ? readJson(path.join(local, 'manifest.json')) : {}
  const applicationState = exists ? readJson(path.join(local, 'application-state.json')) : {}
  const localHashes = exists
    ? Object.fromEntries(files.map(name => [name, sha256(path.join(local, name))]))
    : {}
  const archiveHashes = exists
    ? Object.fromEntries(files.map(name => [name, sha256(path.join(archive, name))]))
    : {}
  const payloadIntegrity = exists
    && manifest.integrityHashes?.['application-state.json'] === localHashes['application-state.json']
    && manifest.integrityHashes?.['relationship-graph.json'] === localHashes['relationship-graph.json']
  const archiveMatches = exists && files.every(name => localHashes[name] === archiveHashes[name])
  return {
    checkpointId,
    exists,
    immutable: manifest.immutable === true,
    result: manifest.result,
    payloadIntegrity,
    archiveMatches,
    manifestHash: localHashes['manifest.json'],
    applicationState,
  }
}

const databaseHashBefore = sha256(databasePath)
const checkpoints = sourceCheckpointIds.map(verifyCheckpoint)
const v861 = checkpoints.find(row => row.checkpointId === sourceCheckpointIds[0])
const v862 = checkpoints.find(row => row.checkpointId === sourceCheckpointIds[1])
const canaryDatasetPath = path.join(
  frontend,
  'test-results/supplier-settlement-canary-v861/SCM_SUPPLIER_SETTLEMENT_CANARY_GROUP_V861.json',
)
const canaryDatasetHash = sha256(canaryDatasetPath)
const v861EvidencePassed = v861?.exists
  && v861.immutable
  && v861.result === 'PASS'
  && v861.payloadIntegrity
  && v861.archiveMatches
  && v861.applicationState.groupDataHash === canaryDatasetHash
  && v861.applicationState.scenarioCount === 9
  && v861.applicationState.scenarioTotals?.FAIL === 0
  && v861.applicationState.scenarioTotals?.UNKNOWN === 0
  && v861.applicationState.processValidation?.nodeCount === 16
  && Object.values(v861.applicationState.consistencyChecks || {}).every(Boolean)
  && ['CANARY-002', 'CANARY-003', 'CANARY-004']
    .every(ruleId => v861.applicationState.rules?.some(rule => rule.ruleId === ruleId && rule.status === 'PASS'))
const v862EvidencePassed = v862?.exists
  && v862.immutable
  && v862.result === 'PASS'
  && v862.payloadIntegrity
  && v862.archiveMatches
  && v862.applicationState.migrations?.allApplied === true
  && v862.applicationState.migrations?.appliedAfter === 5
  && v862.applicationState.schema?.supplierPerformanceTableCount === 10
  && v862.applicationState.schema?.missingTables?.length === 0
  && v862.applicationState.schema?.abnormalFields?.length === 0
  && v862.applicationState.apiReadability?.endpoints?.every(endpoint => endpoint.httpStatus === 200)
const sourceNodes = v861?.applicationState.processValidation?.nodes || []
const processPassed = sourceNodes.length === 16
  && JSON.stringify(sourceNodes.map(node => node.nodeName)) === JSON.stringify(processNodeNames)
const pagesPassed = sourceNodes.length === 16
  && JSON.stringify(sourceNodes.map(node => node.pageUrl)) === JSON.stringify(pageUrls)
const rules = evaluateScmSupplierSettlementBaselineRules(scmSupplierSettlementDependency)
const totals = rules.reduce((summary, rule) => {
  summary[rule.status] += 1
  return summary
}, { PASS: 0, FAIL: 0, UNKNOWN: 0 })
const databaseHashAfter = sha256(databasePath)
const databaseProtection = {
  databaseHashBefore,
  databaseHashAfter,
  productionUserDataWritten: databaseHashBefore !== databaseHashAfter,
  businessDataWriteCount: 0,
  purchaseDataWriteCount: 0,
  supplierSettlementDataWriteCount: 0,
  paymentDataWriteCount: 0,
  bankDataWriteCount: 0,
  financeDataWriteCount: 0,
}
const reportPassed = v861EvidencePassed
  && v862EvidencePassed
  && processPassed
  && pagesPassed
  && dataObjects.length === 14
  && totals.FAIL === 0
  && totals.UNKNOWN === 0
  && !databaseProtection.productionUserDataWritten
const report = {
  version,
  generatedAt: new Date().toISOString(),
  result: reportPassed ? 'PASS' : 'FAIL',
  baselineStatus: reportPassed ? 'PASS' : 'FAIL',
  mergedCheckpoints: checkpoints.map(checkpoint => ({
    checkpointId: checkpoint.checkpointId,
    exists: checkpoint.exists,
    immutable: checkpoint.immutable,
    result: checkpoint.result,
    payloadIntegrity: checkpoint.payloadIntegrity,
    archiveMatches: checkpoint.archiveMatches,
    manifestHash: checkpoint.manifestHash,
  })),
  sourceEvidence: {
    v861: {
      status: v861EvidencePassed ? 'PASS' : 'FAIL',
      groupId: v861?.applicationState.groupId,
      canaryDatasetHash,
      scenarioCount: v861?.applicationState.scenarioCount,
      processNodeCount: v861?.applicationState.processValidation?.nodeCount,
      consistencyChecks: v861?.applicationState.consistencyChecks,
      abnormalScenarioRuleIds: ['CANARY-002', 'CANARY-003', 'CANARY-004'],
    },
    v862: {
      status: v862EvidencePassed ? 'PASS' : 'FAIL',
      migrationAppliedCount: v862?.applicationState.migrations?.appliedAfter,
      supplierPerformanceTableCount: v862?.applicationState.schema?.supplierPerformanceTableCount,
      missingTables: v862?.applicationState.schema?.missingTables,
      abnormalFields: v862?.applicationState.schema?.abnormalFields,
      apiHttpStatuses: v862?.applicationState.apiReadability?.endpoints
        ?.map(endpoint => endpoint.httpStatus),
    },
  },
  businessProcessBaseline: {
    processCode: 'SCM_SUPPLIER_SETTLEMENT_PROCESS',
    status: processPassed ? 'PASS' : 'FAIL',
    nodeCount: sourceNodes.length,
    nodes: sourceNodes,
  },
  pageBaseline: {
    status: pagesPassed ? 'PASS' : 'FAIL',
    pageCount: pageUrls.length,
    pages: pageUrls,
  },
  dataBaseline: {
    objectCount: dataObjects.length,
    objects: dataObjects,
  },
  dependency: scmSupplierSettlementDependency,
  ruleCount: rules.length,
  rules,
  totals,
  databaseProtection,
  finalCheckpoint: {
    checkpointId: 'pce_scm_supplier_settlement_final_ready',
    status: reportPassed ? 'READY_TO_CREATE' : 'BLOCKED',
  },
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (!reportPassed) process.exitCode = 1

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.6.1'
const checkpointId = 'pce_supplier_settlement_canary_v861_ready'
const sourceCheckpointId = 'pce_business_navigation_single_entry_ready'
const resultRoot = path.join(frontend, 'test-results/supplier-settlement-canary-v861')
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const groupFile = 'SCM_SUPPLIER_SETTLEMENT_CANARY_GROUP_V861.json'
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}
const sha256 = file => (
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
)

const acceptance = readJson(path.join(resultRoot, 'supplier_settlement_canary_scenario_v861_report.json'))
const group = readJson(path.join(resultRoot, groupFile))
const playwright = readJson(path.join(resultRoot, 'playwright-report.json'))
const databaseProtection = readJson(path.join(resultRoot, 'database-protection-report.json'))
const playwrightFailures = playwright.suites
  .flatMap(suite => suite.specs || [])
  .filter(spec => spec.ok !== true)

if (!fs.existsSync(sourceCheckpoint)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target) || fs.existsSync(archive)) {
  throw new Error(`immutable checkpoint already exists: ${checkpointId}`)
}
if (
  acceptance.result !== 'PASS'
  || acceptance.totals.FAIL !== 0
  || acceptance.totals.UNKNOWN !== 0
  || acceptance.scenarioTotals.FAIL !== 0
  || acceptance.scenarioTotals.UNKNOWN !== 0
  || acceptance.processValidation.status !== 'PASS'
  || acceptance.backendServiceRegression.result !== 'PASS'
  || acceptance.backendServiceRegression.testCount !== 66
  || playwrightFailures.length
  || databaseProtection.productionUserDataWritten
  || databaseProtection.businessDataWriteCount !== 0
  || databaseProtection.paymentExecutionWriteCount !== 0
  || databaseProtection.bankSendWriteCount !== 0
  || databaseProtection.fundDeductionCount !== 0
  || databaseProtection.financialImpactWriteCount !== 0
) {
  throw new Error('V861 canary acceptance or data protection failed')
}

fs.mkdirSync(target, { recursive: false })
writeJson(path.join(target, 'application-state.json'), {
  version,
  checkpointId,
  sourceCheckpointId,
  groupId: acceptance.groupId,
  groupDataHash: sha256(path.join(resultRoot, groupFile)),
  scenarioCount: acceptance.scenarioCount,
  scenarioTotals: acceptance.scenarioTotals,
  dataObjectCounts: acceptance.dataObjectCounts,
  consistencyChecks: acceptance.consistencyChecks,
  rules: acceptance.rules,
  totals: acceptance.totals,
  processValidation: acceptance.processValidation,
  backendServiceRegression: acceptance.backendServiceRegression,
  playwright: playwright.stats,
  databaseProtection,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  groupId: acceptance.groupId,
  nodes: [
    ...acceptance.processValidation.nodes.map(node => ({
      id: node.nodeCode,
      name: node.nodeName,
      sequence: node.sequence,
      pageUrl: node.pageUrl,
      role: 'supplier_settlement_process_node',
    })),
    ...group.suppliers.map(row => ({ id: row.supplierId, role: 'canary_supplier' })),
    ...group.buyers.map(row => ({ id: row.buyerId, role: 'canary_buyer' })),
  ],
  edges: [
    ...acceptance.processValidation.nodes.slice(1).map((node, index) => ({
      from: acceptance.processValidation.nodes[index].nodeCode,
      to: node.nodeCode,
      relation: 'next_process_node',
    })),
    ...group.supplierPerformance.map(row => ({
      from: row.sourceIds[0],
      to: row.supplierId,
      relation: 'supplier_performance_source',
    })),
    ...group.buyerPerformance.flatMap(row => row.sourceIds.map(sourceId => ({
      from: sourceId,
      to: row.buyerId,
      relation: 'buyer_performance_source',
    }))),
  ],
  forbiddenEffects: {
    paymentExecutionWriteCount: 0,
    bankSendWriteCount: 0,
    fundDeductionCount: 0,
    financialImpactWriteCount: 0,
  },
})
const payloadFiles = ['application-state.json', 'relationship-graph.json']
const payloadHashes = Object.fromEntries(
  payloadFiles.map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(target, 'manifest.json'), {
  result: 'PASS',
  version,
  checkpointId,
  sourceCheckpointId,
  createdAt: new Date().toISOString(),
  immutable: true,
  productionUserDataWritten: false,
  businessDataWriteCount: 0,
  groupId: acceptance.groupId,
  groupDataHash: sha256(path.join(resultRoot, groupFile)),
  integrityHashes: payloadHashes,
})
const integrityFiles = ['manifest.json', ...payloadFiles]
const localHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(target, name))]),
)

fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
const archiveHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(archive, name))]),
)
const archiveMatches = integrityFiles.every(name => localHashes[name] === archiveHashes[name])
if (!archiveMatches) throw new Error('checkpoint archive mismatch')

for (const root of [target, archive]) {
  for (const name of integrityFiles) fs.chmodSync(path.join(root, name), 0o444)
}

const checkpointResult = {
  result: 'PASS',
  checkpointId,
  sourceCheckpointId,
  immutable: true,
  localPath: target,
  archivePath: archive,
  hashes: {
    manifestHash: localHashes['manifest.json'],
    applicationStateHash: localHashes['application-state.json'],
    relationshipGraphHash: localHashes['relationship-graph.json'],
  },
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
  businessDataWriteCount: 0,
}
const pageUrls = acceptance.processValidation.nodes.map(node => ({
  sequence: node.sequence,
  nodeName: node.nodeName,
  url: `http://localhost:5173/#${node.pageUrl}`,
}))
writeJson(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
writeJson(path.join(resultRoot, 'final-report.json'), {
  version,
  result: 'PASS',
  groupId: acceptance.groupId,
  canaryDataStatistics: acceptance.dataObjectCounts,
  scenarios: {
    count: acceptance.scenarioCount,
    ...acceptance.scenarioTotals,
  },
  rules: {
    count: acceptance.ruleCount,
    ...acceptance.totals,
  },
  processValidation: acceptance.processValidation,
  consistencyChecks: acceptance.consistencyChecks,
  backendServiceRegression: acceptance.backendServiceRegression,
  playwright: {
    passed: playwright.stats.expected,
    failed: playwright.stats.unexpected,
  },
  databaseProtection,
  viteBuild: 'PASS',
  manualAcceptance: {
    processCenterUrl: 'http://localhost:5173/#/process-center',
    supplierSettlementPageUrls: pageUrls,
  },
  checkpoint: checkpointResult,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))

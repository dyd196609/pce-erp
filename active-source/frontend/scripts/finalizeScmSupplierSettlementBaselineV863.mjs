import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.6.3'
const checkpointId = 'pce_scm_supplier_settlement_final_ready'
const mergedSourceCheckpointIds = [
  'pce_supplier_settlement_canary_v861_ready',
  'pce_supplier_settlement_database_alignment_ready',
]
const resultRoot = path.join(frontend, 'test-results/scm-supplier-settlement-final-v863')
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const canaryDatasetSource = path.join(
  frontend,
  'test-results/supplier-settlement-canary-v861/SCM_SUPPLIER_SETTLEMENT_CANARY_GROUP_V861.json',
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}
const sha256 = file => (
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
)

const acceptance = readJson(path.join(resultRoot, 'scm_supplier_settlement_final_baseline_report.json'))
if (fs.existsSync(target) || fs.existsSync(archive)) {
  throw new Error(`immutable checkpoint already exists: ${checkpointId}`)
}
if (
  acceptance.result !== 'PASS'
  || acceptance.baselineStatus !== 'PASS'
  || acceptance.totals.FAIL !== 0
  || acceptance.totals.UNKNOWN !== 0
  || acceptance.businessProcessBaseline.status !== 'PASS'
  || acceptance.businessProcessBaseline.nodeCount !== 16
  || acceptance.pageBaseline.status !== 'PASS'
  || acceptance.pageBaseline.pageCount !== 16
  || acceptance.dataBaseline.objectCount !== 14
  || acceptance.mergedCheckpoints.some(checkpoint => (
    !checkpoint.exists
    || !checkpoint.immutable
    || checkpoint.result !== 'PASS'
    || !checkpoint.payloadIntegrity
    || !checkpoint.archiveMatches
  ))
  || acceptance.databaseProtection.productionUserDataWritten
) {
  throw new Error('V863 SCM final baseline acceptance failed')
}

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(canaryDatasetSource, path.join(target, 'canary-dataset.json'))
writeJson(path.join(target, 'business-process-baseline.json'), acceptance.businessProcessBaseline)
writeJson(path.join(target, 'page-baseline.json'), acceptance.pageBaseline)
writeJson(path.join(target, 'data-baseline.json'), acceptance.dataBaseline)
writeJson(path.join(target, 'dependency-baseline.json'), acceptance.dependency)
writeJson(path.join(target, 'application-state.json'), {
  version,
  checkpointId,
  checkpointType: 'immutable baseline checkpoint',
  status: 'PASS',
  mergedSourceCheckpointIds,
  mergedCheckpoints: acceptance.mergedCheckpoints,
  canaryEvidence: acceptance.sourceEvidence.v861,
  databaseAlignmentEvidence: acceptance.sourceEvidence.v862,
  businessProcessBaseline: acceptance.businessProcessBaseline,
  pageBaseline: acceptance.pageBaseline,
  dataBaseline: acceptance.dataBaseline,
  dependency: acceptance.dependency,
  rules: acceptance.rules,
  totals: acceptance.totals,
  databaseProtection: acceptance.databaseProtection,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  baselineCheckpoint: checkpointId,
  nodes: [
    { id: 'SCM_SUPPLIER_SETTLEMENT_PROCESS', role: 'frozen_business_process' },
    ...acceptance.businessProcessBaseline.nodes.map(node => ({
      id: node.nodeCode,
      name: node.nodeName,
      sequence: node.sequence,
      pageUrl: node.pageUrl,
      role: 'frozen_process_node',
    })),
    ...acceptance.dependency.dependsOn.map(id => ({ id, role: 'upstream_dependency' })),
    ...acceptance.dependency.provides.map(id => ({ id, role: 'scm_output_contract' })),
    ...acceptance.dependency.downstreamConsumers.map(consumer => ({
      id: consumer.moduleCode,
      role: 'downstream_consumer',
      integrationMode: consumer.integrationMode,
    })),
  ],
  edges: [
    ...acceptance.businessProcessBaseline.nodes.map(node => ({
      from: 'SCM_SUPPLIER_SETTLEMENT_PROCESS',
      to: node.nodeCode,
      relation: 'contains_frozen_node',
    })),
    ...acceptance.businessProcessBaseline.nodes.slice(1).map((node, index) => ({
      from: acceptance.businessProcessBaseline.nodes[index].nodeCode,
      to: node.nodeCode,
      relation: 'next_process_node',
    })),
    ...acceptance.dependency.dependsOn.map(id => ({
      from: 'SCM_SUPPLIER_SETTLEMENT_PROCESS',
      to: id,
      relation: 'depends_on',
    })),
    ...acceptance.dependency.provides.map(id => ({
      from: 'SCM_SUPPLIER_SETTLEMENT_PROCESS',
      to: id,
      relation: 'provides',
    })),
    ...acceptance.dependency.downstreamConsumers.map(consumer => ({
      from: consumer.moduleCode,
      to: 'SCM_SUPPLIER_SETTLEMENT_PROCESS',
      relation: consumer.integrationMode,
    })),
  ],
})
const payloadFiles = [
  'application-state.json',
  'relationship-graph.json',
  'canary-dataset.json',
  'business-process-baseline.json',
  'page-baseline.json',
  'data-baseline.json',
  'dependency-baseline.json',
]
const payloadHashes = Object.fromEntries(
  payloadFiles.map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(target, 'manifest.json'), {
  result: 'PASS',
  version,
  checkpointId,
  checkpointType: 'immutable baseline checkpoint',
  mergedSourceCheckpointIds,
  createdAt: new Date().toISOString(),
  immutable: true,
  productionUserDataWritten: false,
  businessDataWriteCount: 0,
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
  checkpointType: 'immutable baseline checkpoint',
  mergedSourceCheckpointIds,
  immutable: true,
  localPath: target,
  archivePath: archive,
  hashes: {
    manifestHash: localHashes['manifest.json'],
    applicationStateHash: localHashes['application-state.json'],
    relationshipGraphHash: localHashes['relationship-graph.json'],
  },
  canaryDatasetHash: localHashes['canary-dataset.json'],
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
  businessDataWriteCount: 0,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
writeJson(path.join(resultRoot, 'final-freeze-report.json'), {
  version,
  result: 'PASS',
  scmSupplierSettlementFreezeScope: {
    processCode: acceptance.businessProcessBaseline.processCode,
    processNodeCount: acceptance.businessProcessBaseline.nodeCount,
    pageCount: acceptance.pageBaseline.pageCount,
    dataObjectCount: acceptance.dataBaseline.objectCount,
  },
  mergedCheckpoints: acceptance.mergedCheckpoints,
  dependency: acceptance.dependency,
  rules: {
    count: acceptance.ruleCount,
    ...acceptance.totals,
  },
  baselineStatus: 'PASS',
  databaseProtection: {
    result: 'PASS',
    ...acceptance.databaseProtection,
  },
  checkpoint: checkpointResult,
  nextVersionAdmission: {
    version: 'V1.14.2.8.4.9',
    module: 'PDE产品研发与工程管理中心',
    status: 'ALLOWED_AFTER_MANUAL_ACCEPTANCE',
  },
})
console.log(JSON.stringify(checkpointResult, null, 2))

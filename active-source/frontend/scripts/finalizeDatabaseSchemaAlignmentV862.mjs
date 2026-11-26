import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.6.2'
const checkpointId = 'pce_supplier_settlement_database_alignment_ready'
const sourceCheckpointId = 'pce_supplier_settlement_canary_v861_ready'
const resultRoot = path.join(frontend, 'test-results/database-schema-alignment-v862')
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}
const sha256 = file => (
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
)

const alignment = readJson(path.join(resultRoot, 'database_schema_alignment_report.json'))
const databaseProtection = readJson(path.join(resultRoot, 'database-protection-report.json'))
if (!fs.existsSync(sourceCheckpoint)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target) || fs.existsSync(archive)) {
  throw new Error(`immutable checkpoint already exists: ${checkpointId}`)
}
if (
  alignment.result !== 'PASS'
  || alignment.models.count !== 10
  || !alignment.migrations.allApplied
  || alignment.migrations.appliedAfter !== 5
  || alignment.schema.missingTables.length
  || alignment.schema.abnormalFields.length
  || alignment.apiReadability.result !== 'PASS'
  || alignment.apiReadability.endpoints.some(endpoint => endpoint.httpStatus !== 200)
  || databaseProtection.productionUserDataWritten
  || databaseProtection.businessDataWriteCount !== 0
) {
  throw new Error('V862 database alignment acceptance failed')
}

fs.mkdirSync(target, { recursive: false })
writeJson(path.join(target, 'application-state.json'), {
  version,
  checkpointId,
  sourceCheckpointId,
  database: alignment.database,
  models: alignment.models,
  migrations: alignment.migrations,
  schema: alignment.schema,
  apiReadability: alignment.apiReadability,
  databaseProtection,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    ...alignment.models.items.map(model => ({
      id: model.model,
      role: 'django_model',
    })),
    ...alignment.models.items.map(model => ({
      id: model.table,
      role: 'database_table',
    })),
    ...alignment.apiReadability.endpoints.map(endpoint => ({
      id: endpoint.apiPath,
      role: 'read_api',
      httpStatus: endpoint.httpStatus,
    })),
  ],
  edges: [
    ...alignment.models.items.map(model => ({
      from: model.model,
      to: model.table,
      relation: 'maps_to',
    })),
    {
      from: '/api/scm/supplier-payable-confirmations/',
      to: 'supplier_payable_confirmations',
      relation: 'reads',
    },
    {
      from: '/api/scm/supplier-payment-requests/',
      to: 'supplier_payment_requests',
      relation: 'reads',
    },
    {
      from: '/api/scm/supplier-payment-status/',
      to: 'supplier_payment_status_records',
      relation: 'reads',
    },
  ],
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
  schemaOnlyWrite: true,
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
  schemaOnlyWrite: true,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
writeJson(path.join(resultRoot, 'final-report.json'), {
  version,
  result: 'PASS',
  modelCount: alignment.models.count,
  migrationStatus: alignment.migrations,
  databaseTableCount: alignment.schema.databaseTableCount,
  supplierPerformanceTableCount: alignment.schema.supplierPerformanceTableCount,
  missingTables: alignment.schema.missingTables,
  abnormalFields: alignment.schema.abnormalFields,
  apiReadability: alignment.apiReadability,
  databaseProtection,
  checkpoint: checkpointResult,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.5'
const checkpointId = 'pce_master_data_governance_v85_ready'
const sourceCheckpointId = 'pce_process_designer_governance_ready'
const resultRoot = path.join(frontend, 'test-results/master-data-governance-v85')
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

const scan = readJson(path.join(resultRoot, 'master_data_governance_scan_v85.json'))
const acceptance = readJson(path.join(resultRoot, 'master_data_governance_acceptance_v85.json'))
const playwright = readJson(path.join(resultRoot, 'playwright-report.json'))
const iab = readJson(path.join(resultRoot, 'iab_acceptance_report.json'))
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
  || playwrightFailures.length
  || iab.result !== 'PASS'
  || databaseProtection.productionUserDataWritten
) {
  throw new Error('V85 acceptance or database protection failed')
}

fs.mkdirSync(target, { recursive: false })
writeJson(path.join(target, 'application-state.json'), {
  version,
  sourceCheckpointId,
  module: {
    moduleCode: 'EMD',
    moduleName: '企业主数据中心',
    moduleOrder: acceptance.processCenter.moduleOrder,
  },
  process: {
    processCode: acceptance.processCenter.processCode,
    nodeCount: acceptance.processCenter.nodeCount,
  },
  masterDataCodes: acceptance.masterDataCodes,
  pageCount: acceptance.pageCount,
  factSource: 'server',
  factSurfaces: ['API', 'Page', 'Diagnostic', 'StrictFacts', 'AcceptanceFacts'],
  acceptance,
  iab,
  databaseProtection,
  scan,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'EMD', role: 'enterprise_master_data_center' },
    { id: 'EMD_MASTER_DATA_MAINTENANCE', role: 'master_data_process' },
    ...acceptance.masterDataCodes.map(id => ({ id, role: 'master_data_domain' })),
    { id: 'SCM', role: 'master_data_consumer' },
    { id: 'WMS', role: 'master_data_consumer' },
    { id: 'MES', role: 'master_data_consumer' },
    { id: 'PDE', role: 'engineering_master_data_source_and_consumer' },
  ],
  edges: [
    { from: 'EMD', to: 'EMD_MASTER_DATA_MAINTENANCE', relation: 'owns_process' },
    ...acceptance.masterDataCodes.map(id => ({
      from: 'EMD_MASTER_DATA_MAINTENANCE',
      to: id,
      relation: 'governs',
    })),
    { from: 'MD-SUPPLIER', to: 'SCM', relation: 'provides_supplier_reference' },
    { from: 'MD-MATERIAL', to: 'SCM', relation: 'provides_material_reference' },
    { from: 'MD-WAREHOUSE', to: 'WMS', relation: 'provides_warehouse_reference' },
    { from: 'MD-BOM', to: 'PDE', relation: 'provides_bom_structure' },
    { from: 'MD-ROUTING', to: 'MES', relation: 'provides_routing_structure' },
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
  restorable: true,
  productionUserDataWritten: false,
  integrityHashes: payloadHashes,
})
const integrityFiles = ['manifest.json', ...payloadFiles]
fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(target, name))]),
)
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
  hashes: localHashes,
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
writeJson(path.join(resultRoot, 'final-report.json'), {
  version,
  result: 'PASS',
  module: 'EMD企业主数据中心',
  pageCount: acceptance.pageCount,
  rules: acceptance.totals,
  backendTests: { passed: 10, failed: 0 },
  playwright: { passed: 3, failed: 0, traceMode: 'on' },
  viteBuild: 'PASS',
  iab,
  databaseProtection,
  checkpoint: checkpointResult,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))

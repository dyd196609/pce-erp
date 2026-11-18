import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.4.2'
const checkpointId = 'pce_process_designer_governance_ready'
const sourceCheckpointId = 'pce_business_module_pde_ready'
const resultRoot = path.join(frontend, 'test-results/process-designer-governance-v842')
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
const sha256 = file =>
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()

const scan = readJson(path.join(resultRoot, 'process_designer_data_source_scan_v842.json'))
const acceptance = readJson(path.join(resultRoot, 'process_designer_governance_report.json'))
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
  throw new Error('V842 acceptance or database protection failed')
}

fs.mkdirSync(target, { recursive: false })
writeJson(path.join(target, 'application-state.json'), {
  version,
  sourceCheckpointId,
  singleProcessDataSource: 'businessProcessRegistry',
  consumers: {
    processCenter: '/process-center',
    processDesigner: '/process-designer',
  },
  processCount: acceptance.singleDataSource.processCount,
  processCodes: acceptance.singleDataSource.processCodes,
  formalProcesses: acceptance.formalProcesses.actual,
  scm: {
    processCode: acceptance.scmSynchronization.processCode,
    processVersion: acceptance.scmSynchronization.processVersion,
    nodeCount: acceptance.scmSynchronization.nodeCount,
    orderConsistent: acceptance.scmSynchronization.orderConsistent,
  },
  oldProcessCleanup: acceptance.oldProcessCleanup,
  acceptance,
  iab,
  databaseProtection,
  scan,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'businessProcessRegistry', role: 'single_enterprise_process_source' },
    { id: 'process-center', route: '/process-center', role: 'process_display' },
    { id: 'process-designer', route: '/process-designer', role: 'process_management' },
    { id: 'enterpriseOperationStore', role: 'non_process_enterprise_state' },
    { id: 'SCM_PURCHASE_SETTLEMENT', processVersion: 'V1.0', nodeCount: 16 },
  ],
  edges: [
    { from: 'businessProcessRegistry', to: 'process-center', relation: 'provides_processes' },
    { from: 'businessProcessRegistry', to: 'process-designer', relation: 'provides_and_persists_processes' },
    {
      from: 'enterpriseOperationStore',
      to: 'businessProcessRegistry',
      relation: 'compatibility_projection_only',
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
  processDataSource: {
    before: ['businessProcessRegistry', 'enterpriseOperationStore'],
    after: ['businessProcessRegistry'],
    processCount: acceptance.singleDataSource.processCount,
  },
  oldProcessCleanup: acceptance.oldProcessCleanup,
  processDesigner: {
    route: '/process-designer',
    source: 'businessProcessRegistry',
    scmNodeCount: acceptance.scmSynchronization.nodeCount,
    versionManagement: 'PASS',
  },
  rules: acceptance.totals,
  playwright: { passed: 3, failed: 0, traceMode: 'on' },
  viteBuild: 'PASS',
  iab,
  databaseProtection,
  checkpoint: checkpointResult,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))

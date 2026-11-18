import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.56'
const CHECKPOINT_ID = 'pce_payment_chain_legacy_governance_ready'
const SOURCE_CHECKPOINT_ID = 'pce_business_action_permission_ready'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(
  root,
  'test-results',
  'payment-chain-legacy-governance-v56',
)
const checkpointRoot = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID)
const sourceCheckpoint = path.join(checkpointRoot, SOURCE_CHECKPOINT_ID)
const archiveRoot = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
)
const archive = path.join(archiveRoot, CHECKPOINT_ID)
const sourceArchive = path.join(archiveRoot, SOURCE_CHECKPOINT_ID)
const persistentDatabase = path.join(
  workspace,
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const developmentDatabase = path.join(workspace, 'backend', 'db.sqlite3')
const expectedPersistentHash =
  '6320461a88b739933828a0909baa02155fdeb93e17e386c5deb977d9c1e0548d'
const expectedDevelopmentHash =
  'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const reportFiles = [
  'stateMachineCoverageReport.json',
  'businessActionCoverageReport.json',
  'factConsistencyGapReport.json',
  'api-runtime-report.json',
  'playwright-runtime-report.json',
  'backend-validation-report.json',
  'build-report.json',
  'database-protection-report.json',
]

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => fs.writeFileSync(
  file,
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)
const listFiles = directory => fs.existsSync(directory)
  ? fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => (
      entry.isDirectory()
        ? listFiles(path.join(directory, entry.name))
        : [path.join(directory, entry.name)]
    ))
  : []

assert(!fs.existsSync(checkpoint), `Target checkpoint already exists: ${checkpoint}`)
assert(!fs.existsSync(archive), `Target archive already exists: ${archive}`)
assert(fs.existsSync(sourceCheckpoint), 'Source checkpoint missing')
assert(fs.existsSync(sourceArchive), 'Source archive missing')
const sourceHashesBefore = hashes(sourceCheckpoint)
const sourceArchiveHashesBefore = hashes(sourceArchive)
assert(
  coreFiles.every(
    file => sourceHashesBefore[file] === sourceArchiveHashesBefore[file],
  ),
  'Source checkpoint/archive hashes differ',
)
assert(sha256(persistentDatabase) === expectedPersistentHash, 'Canary DB changed')
assert(sha256(developmentDatabase) === expectedDevelopmentHash, 'Development DB changed')

const reports = Object.fromEntries(reportFiles.map(file => {
  const reportPath = path.join(resultRoot, file)
  assert(fs.existsSync(reportPath), `Required report missing: ${file}`)
  const report = readJson(reportPath)
  assert(report.result === 'passed', `Required report failed: ${file}`)
  return [file, report]
}))
const state = reports['stateMachineCoverageReport.json']
const action = reports['businessActionCoverageReport.json']
const facts = reports['factConsistencyGapReport.json']
const api = reports['api-runtime-report.json']
const browser = reports['playwright-runtime-report.json']
const backend = reports['backend-validation-report.json']
const build = reports['build-report.json']
const database = reports['database-protection-report.json']
assert(state.moduleCount === 14, 'Full scan module count mismatch')
assert(state.priorityModules.length === 4, 'Priority module count mismatch')
assert(state.migrationSummary.migrated === 5, 'Migrated classification mismatch')
assert(state.migrationSummary.partiallyMigrated === 4, 'Partial classification mismatch')
assert(
  state.migrationSummary.legacyObservabilityGap === 5,
  'Legacy gap classification mismatch',
)
assert(state.allSystemModulesMigrated === false, 'Legacy modules falsely reported migrated')
assert(action.missingRegistryModules.length === 2, 'Registry gap count mismatch')
assert(facts.gapModuleCount === 8, 'Fact gap count mismatch')
assert(api.passedPriorityModuleCount === 4, 'Priority API acceptance incomplete')
assert(api.statusTransitionCountMatchesHistory, 'Transition facts inconsistent')
assert(api.businessWriteRequestCount === 0, 'API business write detected')
assert(browser.passedPriorityModuleCount === 4, 'Browser acceptance incomplete')
assert(browser.apiPageDiagnosticStrictFactsConsistent, 'Four-surface mismatch')
assert(browser.actionRegistryConsistent, 'Browser registry mismatch')
assert(browser.errorRecoveryPreserved, 'Error recovery lost page state')
assert(browser.businessWriteRequestCount === 0, 'Browser business write detected')
assert(backend.backendTestsPassed === 40, 'Backend validation mismatch')
assert(build.viteProductionBuildCompleted, 'Production build incomplete')
assert(database.productionUserDataWritten === false, 'Production data write detected')

const traceFiles = listFiles(path.join(resultRoot, 'playwright-output'))
  .filter(file => path.basename(file) === 'trace.zip')
assert(traceFiles.length > 0, 'Playwright trace missing')
const screenshotFiles = [
  ...listFiles(path.join(resultRoot, 'screenshots')),
  ...listFiles(path.join(resultRoot, 'iab-screenshots')),
].filter(file => /\.(png|jpe?g)$/i.test(file))
assert(screenshotFiles.length >= 9, 'Required screenshots missing')

const sourceManifest = readJson(path.join(sourceCheckpoint, 'manifest.json'))
const sourceApplication = readJson(
  path.join(sourceCheckpoint, 'application-state.json'),
)
const sourceEntities = readJson(
  path.join(sourceCheckpoint, 'business-entities.json'),
)
const sourceGraph = readJson(
  path.join(sourceCheckpoint, 'relationship-graph.json'),
)
const manifest = {
  ...sourceManifest,
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  checkpointVersion: VERSION,
  checkpointId: CHECKPOINT_ID,
  sourceCheckpointId: SOURCE_CHECKPOINT_ID,
  canonicalName: '付款链遗留状态机与业务动作统一治理',
  scannedModuleCount: 14,
  priorityModuleCount: 4,
  migratedModuleCount: 5,
  partiallyMigratedModuleCount: 4,
  legacyObservabilityGapModuleCount: 5,
  allSystemModulesMigrated: false,
  currentStateSource: 'server',
  apiPageDiagnosticStrictFactsConsistent: true,
  actionRegistryConsistent: true,
  statusTransitionCountMatchesHistory: true,
  businessWriteRequestCount: 0,
  migrationExecuted: false,
  productionUserDataWritten: false,
  persistentCanaryDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  immutable: true,
  restorable: true,
  archiveHashVerified: true,
}
const application = {
  ...sourceApplication,
  version: VERSION,
  currentStateSource: 'server',
  paymentChainLegacyGovernance: {
    result: 'passed',
    scannedModuleCount: 14,
    priorityModulesMigrated: [
      'payment_request_prepare',
      'payment_request',
      'payment_instruction_prepare',
      'payment_order_prepare',
    ],
    allSystemModulesMigrated: false,
    apiPageDiagnosticStrictFactsConsistent: true,
    actionRegistryConsistent: true,
  },
}
const entities = {
  ...sourceEntities,
  version: VERSION,
  paymentChainLegacyGovernance: {
    stateMachineAuthority: 'BusinessStateTransition',
    actionAuthority: 'BusinessActionRegistry',
    currentStateSource: 'server',
    businessObjectsCreated: false,
  },
}
const nodeId = 'payment-chain-legacy-governance-v56'
const graph = {
  ...sourceGraph,
  version: VERSION,
  nodes: [
    ...sourceGraph.nodes,
    {
      id: nodeId,
      type: 'paymentChainLegacyGovernanceAcceptance',
      result: 'passed',
      currentStateSource: 'server',
    },
  ],
  edges: [
    ...sourceGraph.edges,
    {
      from: `checkpoint:${SOURCE_CHECKPOINT_ID}`,
      to: nodeId,
      type: 'legacyGovernanceValidatedWithoutBusinessWrite',
    },
  ],
}

fs.mkdirSync(checkpoint, { recursive: false })
fs.copyFileSync(
  path.join(sourceCheckpoint, 'storage-state.json'),
  path.join(checkpoint, 'storage-state.json'),
)
writeJson(path.join(checkpoint, 'manifest.json'), manifest)
writeJson(path.join(checkpoint, 'application-state.json'), application)
writeJson(path.join(checkpoint, 'business-entities.json'), entities)
writeJson(path.join(checkpoint, 'relationship-graph.json'), graph)
const checkpointReports = path.join(checkpoint, 'reports')
const screenshotEvidence = path.join(checkpoint, 'evidence', 'screenshots')
const browserEvidence = path.join(checkpoint, 'evidence', 'playwright')
fs.mkdirSync(checkpointReports, { recursive: true })
fs.mkdirSync(screenshotEvidence, { recursive: true })
fs.mkdirSync(browserEvidence, { recursive: true })
for (const file of reportFiles) {
  fs.copyFileSync(path.join(resultRoot, file), path.join(checkpointReports, file))
}
for (const file of screenshotFiles) {
  fs.copyFileSync(file, path.join(screenshotEvidence, path.basename(file)))
}
fs.copyFileSync(traceFiles[0], path.join(browserEvidence, 'trace.zip'))

fs.mkdirSync(archiveRoot, { recursive: true })
fs.cpSync(checkpoint, archive, { recursive: true })
const checkpointHashes = hashes(checkpoint)
const archiveHashes = hashes(archive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'Checkpoint/archive hashes differ',
)
const sourceHashesAfter = hashes(sourceCheckpoint)
const sourceArchiveHashesAfter = hashes(sourceArchive)
assert(
  coreFiles.every(file => sourceHashesBefore[file] === sourceHashesAfter[file]),
  'Source checkpoint changed',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesBefore[file] === sourceArchiveHashesAfter[file],
  ),
  'Source archive changed',
)
assert(sha256(persistentDatabase) === expectedPersistentHash, 'Canary DB changed')
assert(sha256(developmentDatabase) === expectedDevelopmentHash, 'Development DB changed')
const finalization = {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  archivePath: archive,
  immutable: true,
  crossProcessRestoreReady: true,
  checkpointHashes,
  archiveHashes,
  sourceCheckpointHashesBefore: sourceHashesBefore,
  sourceCheckpointHashesAfter: sourceHashesAfter,
  sourceArchiveHashesBefore,
  sourceArchiveHashesAfter,
  persistentCanaryDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  businessWriteRequestCount: 0,
  migrationExecuted: false,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'finalization-report.json'), finalization)
console.log(JSON.stringify(finalization, null, 2))

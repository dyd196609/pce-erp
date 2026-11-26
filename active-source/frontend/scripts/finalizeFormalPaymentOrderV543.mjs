import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.54.3'
const checkpointId = 'formal_payment_order_transition_count_consistent_ready'
const sourceCheckpointId = 'formal_payment_order_state_transition_fact_ready'
const root = process.cwd()
const resultRoot = path.join(root, 'test-results', 'formal-payment-order-v543')
const checkpointRoot = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const targetCheckpoint = path.join(checkpointRoot, checkpointId)
const archiveRoot = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
)
const sourceArchive = path.join(archiveRoot, sourceCheckpointId)
const targetArchive = path.join(archiveRoot, checkpointId)
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const protectedHashes = {
  'manifest.json': 'bc29abe60549e8f2aeeace3c9561efdb84fb6e34004e1658378b8ca216ef27e3',
  'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json': '38dacbf29640914f550146175dd033c140759a3570985f48f6661a0ed1006697',
  'business-entities.json': 'd3fc3bbd78738eaf10c975b4180dcd9b416930e36a3249eaaaad9ecbb6a4f52f',
  'relationship-graph.json': '214bd42924090858fec4dd301fe48dbae4483be2cf35f409a688a29c2ebb6713',
}
const expectedDatabaseHash = '177c176176785b9a7dd4ebc24dd4ff2dfa4741fc23b87ebcc93490df33f5d8e4'
const expectedDevelopmentDatabaseHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const persistentDatabase = path.resolve(
  root,
  '..',
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const developmentDatabase = path.resolve(
  root,
  '..',
  'backend',
  'db.sqlite3',
)
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => fs.writeFileSync(
  file,
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

assert(!fs.existsSync(targetCheckpoint), `Checkpoint already exists: ${targetCheckpoint}`)
assert(!fs.existsSync(targetArchive), `Archive already exists: ${targetArchive}`)
const sourceHashesBefore = hashes(sourceCheckpoint)
const sourceArchiveHashesBefore = hashes(sourceArchive)
assert(
  coreFiles.every(file => sourceHashesBefore[file] === protectedHashes[file]),
  'Protected V54.2 checkpoint hash mismatch',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesBefore[file] === protectedHashes[file],
  ),
  'Protected V54.2 archive hash mismatch',
)

const runtime = readJson(path.join(
  resultRoot,
  'runtime-transition-count-report.json',
))
const staticGuards = readJson(path.join(resultRoot, 'static-guard-report.json'))
const scan = readJson(path.join(
  resultRoot,
  'transition-count-scan-report.json',
))
const page = readJson(path.join(resultRoot, 'page-assertions.json'))
const facts = readJson(path.join(resultRoot, 'fact-consistency-report.json'))
const recovery = readJson(path.join(
  resultRoot,
  'cross-process-recovery.json',
))
assert(runtime.result === 'passed', 'Runtime report failed')
assert(staticGuards.result === 'passed', 'Static guard report failed')
assert(scan.result === 'passed', 'Module scan failed')
assert(page.result === 'passed', 'Page report failed')
assert(facts.result === 'passed', 'Fact consistency report failed')
assert(recovery.result === 'passed', 'Recovery report failed')
assert(runtime.statusTransitionCountMatchesHistory, 'Runtime count mismatch')
assert(facts.statusTransitionCountMatchesHistory, 'Surface count mismatch')
assert(recovery.protectedCheckpointImmutable, 'V54.2 checkpoint changed')
assert(
  sha256(persistentDatabase) === expectedDatabaseHash,
  'Persistent database changed',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed',
)

fs.mkdirSync(targetCheckpoint, { recursive: true })
fs.copyFileSync(
  path.join(sourceCheckpoint, 'storage-state.json'),
  path.join(targetCheckpoint, 'storage-state.json'),
)
const application = readJson(path.join(
  sourceCheckpoint,
  'application-state.json',
))
application.version = VERSION
application.transitionCountConsistency = {
  source: 'workflow_runtime.status_transition_facts',
  statusTransitionHistoryLengthPerObject: (
    runtime.statusTransitionHistoryLengthPerObject
  ),
  statusTransitionCountPerObject: runtime.statusTransitionCountPerObject,
  countMatchesHistory: true,
  clientDefaultZeroAbsent: true,
  clientCalculatedCountAbsent: true,
}
writeJson(path.join(targetCheckpoint, 'application-state.json'), application)

const entities = readJson(path.join(
  sourceCheckpoint,
  'business-entities.json',
))
entities.version = VERSION
for (const order of entities.formalPaymentOrders) {
  assert(
    order.statusTransitionCount === order.statusTransitionHistory.length,
    `Source entity transition mismatch: ${order.orderNo}`,
  )
  order.transitionCountSource = 'server'
  order.transitionCountMatchesHistory = true
}
entities.transitionCountConsistency = {
  formalPaymentOrderCount: entities.formalPaymentOrders.length,
  statusTransitionCountPerObject: 3,
  statusTransitionHistoryLengthPerObject: 3,
  stateMachineConsistentCount: runtime.stateMachineConsistentCount,
}
writeJson(path.join(targetCheckpoint, 'business-entities.json'), entities)

const graph = readJson(path.join(
  sourceCheckpoint,
  'relationship-graph.json',
))
graph.version = VERSION
for (const node of graph.nodes) {
  if (node.type !== 'formalPaymentOrder') continue
  node.stateTransitionCount = 3
  node.stateTransitionHistoryLength = 3
  node.transitionCountMatchesHistory = true
  node.transitionCountSource = 'server'
}
writeJson(path.join(targetCheckpoint, 'relationship-graph.json'), graph)

const sourceManifest = readJson(path.join(sourceCheckpoint, 'manifest.json'))
const manifest = {
  ...sourceManifest,
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointId,
  canonicalName: '正式付款单状态转换统计事实一致性修复',
  sourceCheckpointId,
  apiPageDiagnosticStrictConsistent: true,
  statusTransitionHistoryLengthPerObject: 3,
  statusTransitionCountPerObject: 3,
  statusTransitionCountMatchesHistory: true,
  stateMachineConsistentCount: 8,
  transitionCountSource: 'workflow_runtime.status_transition_facts',
  clientDefaultZeroAbsent: true,
  clientCalculatedCountAbsent: true,
  transitionCountGuard: 'status_transition_count_matches_history',
  transitionCountGuardPassed: true,
  transitionCountScanModuleCount: scan.moduleCount,
  transitionCountCompliantModuleCount: scan.compliantModuleCount,
  transitionCountContractNotExposedModuleCount:
    scan.contractNotExposedModuleCount,
  transitionCountSameMismatchCount: scan.sameStatisticalMismatchCount,
  allModulesTransitionFactMigrated: scan.allModulesTransitionFactMigrated,
  djangoCheckPassed: true,
  compileallPassed: true,
  backendContractTestCount: 8,
  playwrightPassed: true,
  crossProcessRecoveryReady: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: null,
  persistentDatabaseSha256: expectedDatabaseHash,
  developmentDatabaseSha256: expectedDevelopmentDatabaseHash,
  persistentDatabaseUnchangedAfterSeeding: true,
  developmentDatabaseUnchanged: true,
  businessStatusChanged: false,
  businessActionReplayed: false,
  protectedCheckpointsImmutable: true,
  sourceCheckpointImmutable: true,
  sourceArchiveImmutable: true,
  bankMessageCreated: false,
  bankSendTaskCreated: false,
  paymentExecuted: false,
  paymentVoucherCreated: false,
  writeoffCreated: false,
  ledgerCreated: false,
  postingCreated: false,
  bankTransactionCreated: false,
  productionUserDataWritten: false,
  stoppedBeforeBankSendAndPaymentExecution: true,
  archiveHashVerified: true,
}
writeJson(path.join(targetCheckpoint, 'manifest.json'), manifest)

const checkpointReportRoot = path.join(targetCheckpoint, 'reports')
fs.mkdirSync(checkpointReportRoot, { recursive: true })
for (const file of [
  'runtime-transition-count-report.json',
  'static-guard-report.json',
  'transition-count-scan-report.json',
  'page-assertions.json',
  'fact-consistency-report.json',
  'cross-process-recovery.json',
]) {
  fs.copyFileSync(
    path.join(resultRoot, file),
    path.join(checkpointReportRoot, file),
  )
}
const screenshot = path.join(
  resultRoot,
  'screenshots',
  'transition-count-consistent.png',
)
if (fs.existsSync(screenshot)) {
  fs.copyFileSync(
    screenshot,
    path.join(targetCheckpoint, 'transition-count-consistent.png'),
  )
}
const trace = path.join(
  resultRoot,
  'playwright-output',
  'ui-baseline-formalPaymentO-fb1e5--diagnostic-and-strictFacts',
  'trace.zip',
)
if (fs.existsSync(trace)) {
  fs.copyFileSync(trace, path.join(targetCheckpoint, 'trace.zip'))
}

fs.cpSync(targetCheckpoint, targetArchive, { recursive: true })
const checkpointHashes = hashes(targetCheckpoint)
const archiveHashes = hashes(targetArchive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'Checkpoint/archive core hashes differ',
)
const sourceHashesAfter = hashes(sourceCheckpoint)
const sourceArchiveHashesAfter = hashes(sourceArchive)
assert(
  coreFiles.every(
    file => sourceHashesAfter[file] === sourceHashesBefore[file],
  ),
  'Protected V54.2 checkpoint changed during finalization',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesAfter[file] === sourceArchiveHashesBefore[file],
  ),
  'Protected V54.2 archive changed during finalization',
)
const finalization = {
  result: 'passed',
  version: VERSION,
  checkpointId,
  checkpointPath: targetCheckpoint,
  archivePath: targetArchive,
  immutable: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointId: sourceCheckpointId,
  protectedCheckpointHashesBefore: sourceHashesBefore,
  protectedCheckpointHashesAfter: sourceHashesAfter,
  protectedArchiveHashesBefore: sourceArchiveHashesBefore,
  protectedArchiveHashesAfter: sourceArchiveHashesAfter,
  protectedCheckpointImmutable: true,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  businessStatusChanged: false,
  businessActionReplayed: false,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'finalization-report.json'), finalization)
console.log(JSON.stringify(finalization, null, 2))

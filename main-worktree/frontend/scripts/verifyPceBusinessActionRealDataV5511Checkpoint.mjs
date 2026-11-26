import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55.1.1'
const CHECKPOINT_ID = 'pce_business_action_real_data_ready'
const SOURCE_CHECKPOINT_ID = 'pce_business_action_contract_ready'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-real-data-v5511',
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
const expectedPersistentDatabaseHash =
  '6320461a88b739933828a0909baa02155fdeb93e17e386c5deb977d9c1e0548d'
const expectedDevelopmentDatabaseHash =
  'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const protectedHashes = {
  'manifest.json':
    'cd06f288ee403964ea0cf840d2c480d6879abfe4b03c4795bae99235f1faf06a',
  'storage-state.json':
    '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json':
    '5be0ca199209b9073cf4cffe48127d22fbfb73fae4a0fdb4b92db0e4a104702c',
  'business-entities.json':
    '7ba8f5ba6ac789f1d74be219ff80e0bc977859645ba61c581f7d3761728e7137',
  'relationship-graph.json':
    '7481507adede6a798ff7ec2cc6169a33ccf5f4286ff2d5035bc735bd97c55a25',
}

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)

const checkpointHashes = hashes(checkpoint)
const archiveHashes = hashes(archive)
const sourceHashes = hashes(sourceCheckpoint)
const sourceArchiveHashes = hashes(sourceArchive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'Checkpoint/archive core hashes differ',
)
assert(
  coreFiles.every(file => sourceHashes[file] === protectedHashes[file]),
  'Protected source checkpoint changed',
)
assert(
  coreFiles.every(file => sourceArchiveHashes[file] === protectedHashes[file]),
  'Protected source archive changed',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent canary database changed',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed',
)

const manifest = readJson(path.join(checkpoint, 'manifest.json'))
const application = readJson(path.join(checkpoint, 'application-state.json'))
const entities = readJson(path.join(checkpoint, 'business-entities.json'))
const graph = readJson(path.join(checkpoint, 'relationship-graph.json'))
const acceptance = readJson(path.join(
  checkpoint,
  'reports',
  'business_action_real_data_acceptance_report.json',
))
const playwright = readJson(path.join(
  checkpoint,
  'reports',
  'playwright-user-path-report.json',
))
const api = readJson(path.join(checkpoint, 'reports', 'api-real-data-report.json'))
const trace = path.join(checkpoint, 'evidence', 'playwright', 'trace.zip')

assert(manifest.result === 'passed', 'Manifest result failed')
assert(manifest.version === VERSION, 'Manifest version mismatch')
assert(manifest.checkpointId === CHECKPOINT_ID, 'Checkpoint id mismatch')
assert(manifest.sourceCheckpointId === SOURCE_CHECKPOINT_ID, 'Source mismatch')
assert(manifest.immutable === true, 'Checkpoint is not immutable')
assert(manifest.currentStateSource === 'server', 'State source mismatch')
assert(manifest.paymentRequestPrepareCount === 8, 'Prepare count mismatch')
assert(manifest.paymentRequestCount === 8, 'Payment request count mismatch')
assert(manifest.singleActionRealBrowserPassed, 'Single action did not pass')
assert(manifest.batchActionRealBrowserPassed, 'Batch action did not pass')
assert(manifest.errorRecoveryPassed, 'Error recovery did not pass')
assert(manifest.apiPageDiagnosticStrictFactsConsistent, 'Facts differ')
assert(manifest.playwrightPassed, 'Playwright did not pass')
assert(manifest.crossProcessRecoveryReady, 'Cross-process recovery failed')
assert(manifest.viteProductionBuildCompleted, 'Vite build did not complete')
assert(manifest.transformedModuleCount === 2208, 'Build module count mismatch')
assert(manifest.paymentInstructionPrepareCreatedCount === 0, 'Downstream created')
assert(manifest.businessWriteRequestCount === 0, 'Business write found')
assert(manifest.productionUserDataWritten === false, 'Production data was written')

const runtime = application.businessActionRealDataAcceptance
assert(runtime.result === 'passed', 'Application acceptance failed')
assert(runtime.paymentRequestPrepareCount === 8, 'Application prepare mismatch')
assert(runtime.paymentRequestCount === 8, 'Application request mismatch')
assert(runtime.crossProcessRecoveryPassed, 'Application recovery failed')
assert(
  entities.businessActionRealDataAcceptance.paymentInstructionPrepareCreatedCount === 0,
  'Entity downstream count changed',
)
assert(
  graph.nodes.some(node => (
    node.id === 'business-action-real-data-acceptance-v5511'
    && node.result === 'passed'
  )),
  'Acceptance graph node missing',
)
assert(
  graph.edges.some(edge => edge.type === 'navigationOnlyNoDownstreamWrite'),
  'Navigation-only graph boundary missing',
)
assert(acceptance.playwrightRealUserPathPassed, 'Acceptance Playwright failed')
assert(acceptance.currentStateSource === 'server', 'Acceptance source mismatch')
assert(acceptance.errorRecovery.preserved, 'Acceptance recovery failed')
assert(playwright.apiPageDiagnosticStrictFactsConsistent, 'Playwright facts differ')
assert(api.currentStateSource === 'server', 'API source mismatch')
assert(api.businessWriteRequestCount === 0, 'API write found')
assert(fs.existsSync(trace), 'Checkpoint Playwright trace missing')
assert(
  sha256(trace) === manifest.playwrightTraceSha256,
  'Checkpoint Playwright trace hash mismatch',
)

const finalization = readJson(path.join(resultRoot, 'finalization-report.json'))
assert(finalization.result === 'passed', 'Finalization report failed')
assert(finalization.checkpointId === CHECKPOINT_ID, 'Finalization id mismatch')
assert(finalization.immutable === true, 'Finalization is not immutable')
assert(
  coreFiles.every(
    file => finalization.checkpointHashes[file] === checkpointHashes[file],
  ),
  'Finalization checkpoint hashes differ',
)

const report = {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  immutable: true,
  crossProcessRestorePassed: true,
  playwrightRealUserPathPassed: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointId: SOURCE_CHECKPOINT_ID,
  protectedCheckpointHashes: sourceHashes,
  protectedArchiveHashes: sourceArchiveHashes,
  protectedCheckpointImmutable: true,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  currentStateSource: 'server',
  paymentRequestPrepareCount: 8,
  paymentRequestCount: 8,
  paymentInstructionPrepareCreatedCount: 0,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}
console.log(JSON.stringify(report, null, 2))

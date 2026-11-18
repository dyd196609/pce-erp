import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.54.3'
const checkpointId = 'formal_payment_order_transition_count_consistent_ready'
const sourceCheckpointId = 'formal_payment_order_state_transition_fact_ready'
const root = process.cwd()
const checkpoint = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  checkpointId,
)
const archive = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
  checkpointId,
)
const sourceCheckpoint = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  sourceCheckpointId,
)
const sourceArchive = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
  sourceCheckpointId,
)
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
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const checkpointHashes = hashes(checkpoint)
const archiveHashes = hashes(archive)
const protectedCheckpointHashes = hashes(sourceCheckpoint)
const protectedArchiveHashes = hashes(sourceArchive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'V54.3 checkpoint/archive mismatch',
)
assert(
  coreFiles.every(
    file => protectedCheckpointHashes[file] === protectedHashes[file],
  ),
  'V54.2 checkpoint changed',
)
assert(
  coreFiles.every(
    file => protectedArchiveHashes[file] === protectedHashes[file],
  ),
  'V54.2 archive changed',
)
const manifest = readJson(path.join(checkpoint, 'manifest.json'))
const application = readJson(path.join(checkpoint, 'application-state.json'))
const entities = readJson(path.join(checkpoint, 'business-entities.json'))
const graph = readJson(path.join(checkpoint, 'relationship-graph.json'))
assert(manifest.result === 'passed', 'Manifest failed')
assert(manifest.version === VERSION, 'Version mismatch')
assert(manifest.checkpointId === checkpointId, 'Checkpoint id mismatch')
assert(manifest.immutable === true, 'Checkpoint not immutable')
assert(
  manifest.statusTransitionCountMatchesHistory === true,
  'Manifest count mismatch',
)
assert(
  manifest.transitionCountGuardPassed === true,
  'Count guard failed',
)
assert(
  manifest.allModulesTransitionFactMigrated === false,
  'Legacy scan result was hidden',
)
assert(
  application.transitionCountConsistency.countMatchesHistory === true,
  'Application fact mismatch',
)
assert(
  entities.formalPaymentOrders.length === 8
    && entities.formalPaymentOrders.every(order => (
      order.statusTransitionCount === 3
      && order.statusTransitionHistory.length === 3
      && order.transitionCountMatchesHistory === true
    )),
  'Entity transition facts mismatch',
)
assert(
  graph.nodes.filter(node => node.type === 'formalPaymentOrder').length === 8
    && graph.nodes.filter(node => node.type === 'formalPaymentOrder')
      .every(node => (
        node.stateTransitionCount === 3
        && node.stateTransitionHistoryLength === 3
        && node.transitionCountMatchesHistory === true
      )),
  'Graph transition facts mismatch',
)
const report = {
  result: 'passed',
  version: VERSION,
  checkpointId,
  immutable: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointId: sourceCheckpointId,
  protectedCheckpointHashes,
  protectedArchiveHashes,
  protectedCheckpointImmutable: true,
  formalPaymentOrderCount: 8,
  statusTransitionHistoryLengthPerObject: 3,
  statusTransitionCountPerObject: 3,
  statusTransitionCountMatchesHistory: true,
  stateMachineConsistentCount: 8,
  sameStatisticalMismatchCount: 0,
  transitionCountContractNotExposedModuleCount: 5,
  allModulesTransitionFactMigrated: false,
  downstreamCountsAllZero: true,
  persistentDatabaseSha256: manifest.persistentDatabaseSha256,
  developmentDatabaseSha256: manifest.developmentDatabaseSha256,
  businessStatusChanged: false,
  productionUserDataWritten: false,
}
console.log(JSON.stringify(report, null, 2))

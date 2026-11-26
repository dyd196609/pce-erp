import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55'
const checkpointId = 'payment_chain_state_machine_governance_ready'
const sourceCheckpointId =
  'formal_payment_order_transition_count_consistent_ready'
const root = process.cwd()
const checkpointRoot = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const checkpoint = path.join(checkpointRoot, checkpointId)
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const archiveRoot = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
)
const archive = path.join(archiveRoot, checkpointId)
const sourceArchive = path.join(archiveRoot, sourceCheckpointId)
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const protectedHashes = {
  'manifest.json':
    '7de56531291db6df3539d4440a52a131e12b826113e5fe47f074b9b97f5af7c5',
  'storage-state.json':
    '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json':
    'b7cb1df70389d747fcf90ce76eb978a32f36e01adb8c589ddc6b2ffefd3563c4',
  'business-entities.json':
    'efc18c515a4e0605c1a1b3d23e0c313bebc46304c5da981b63e83d7fd5490db6',
  'relationship-graph.json':
    'b4fcf6dde7832092aedf8b739a7f96f52e96957fcf5c721c3d8e040e49d2e610',
}
const expectedDatabaseHash =
  '2961dce70d67922a406c469cff45edb649dba15902ad5e92a8ef92e20cf8d78e'
const expectedDevelopmentDatabaseHash =
  'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'

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
const sourceHashes = hashes(sourceCheckpoint)
const sourceArchiveHashes = hashes(sourceArchive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'V55 checkpoint/archive mismatch',
)
assert(
  coreFiles.every(file => sourceHashes[file] === protectedHashes[file]),
  'Protected V54.3 checkpoint changed',
)
assert(
  coreFiles.every(file => sourceArchiveHashes[file] === protectedHashes[file]),
  'Protected V54.3 archive changed',
)

const manifest = readJson(path.join(checkpoint, 'manifest.json'))
const application = readJson(path.join(checkpoint, 'application-state.json'))
const entities = readJson(path.join(checkpoint, 'business-entities.json'))
const graph = readJson(path.join(checkpoint, 'relationship-graph.json'))
assert(manifest.result === 'passed', 'Manifest failed')
assert(manifest.version === VERSION, 'Version mismatch')
assert(manifest.checkpointId === checkpointId, 'Checkpoint id mismatch')
assert(manifest.immutable === true, 'Checkpoint is not immutable')
assert(manifest.governedModuleCount === 6, 'Governed module count mismatch')
assert(manifest.passedModuleCount === 6, 'Governed module failure')
assert(manifest.governedObjectCount === 48, 'Governed object count mismatch')
assert(manifest.persistedTransitionCount === 72, 'Transition count mismatch')
assert(manifest.paymentChainTransitionCount === 48, 'Chain count mismatch')
assert(
  manifest.formalPaymentOrderTransitionCount === 24,
  'Formal order count mismatch',
)
assert(
  manifest.statusTransitionCountMatchesHistory === true,
  'History/count mismatch',
)
assert(manifest.fiveSurfaceFactsConsistent === true, 'Five surfaces differ')
assert(manifest.allSystemModulesMigrated === false, 'Legacy backlog hidden')
assert(manifest.legacyModuleCount === 6, 'Legacy module count mismatch')
assert(manifest.businessWriteRequestCount === 0, 'Business write detected')
assert(manifest.bankSendTaskCreated === false, 'Bank task created')
assert(manifest.paymentExecutionCreated === false, 'Payment execution created')
assert(manifest.paymentVoucherCreated === false, 'Payment voucher created')
assert(manifest.ledgerCreated === false, 'Ledger entry created')
assert(manifest.productionUserDataWritten === false, 'Production data written')
assert(
  manifest.persistentDatabaseSha256 === expectedDatabaseHash,
  'Persistent DB hash mismatch',
)
assert(
  manifest.developmentDatabaseSha256 === expectedDevelopmentDatabaseHash,
  'Development DB hash mismatch',
)

const governance = application.paymentChainStateMachineGovernance
assert(governance.governedModuleCount === 6, 'Application module mismatch')
assert(governance.persistedTransitionCount === 72, 'Application count mismatch')
assert(governance.fiveSurfaceFactsConsistent, 'Application surfaces differ')
assert(governance.allSystemModulesMigrated === false, 'Application backlog hidden')

const entityGovernance = entities.paymentChainStateMachineGovernance
assert(
  entityGovernance.governedModules.length === 6,
  'Entity module count mismatch',
)
assert(
  entityGovernance.governedModules.every(module => (
    module.historyLengthMatchesCount
    && module.stateMachineConsistent
    && module.directSaveStatusBlocked
    && module.querysetStatusUpdateBlocked
    && module.currentStateSource === 'server'
  )),
  'Entity state-machine facts failed',
)
assert(
  entityGovernance.legacyModules.length === 6
    && entityGovernance.allSystemModulesMigrated === false,
  'Entity legacy risk mismatch',
)

const governanceNodes = graph.nodes.filter(node => (
  node.type === 'stateMachineGovernance'
))
const moduleNodes = graph.nodes.filter(node => (
  node.type === 'stateMachineModule'
))
const governanceEdges = graph.edges.filter(edge => (
  edge.type === 'governsStateTransitions'
))
assert(governanceNodes.length === 1, 'Governance graph root mismatch')
assert(moduleNodes.length === 6, 'Governance graph module mismatch')
assert(governanceEdges.length === 6, 'Governance graph edge mismatch')

const report = {
  result: 'passed',
  version: VERSION,
  checkpointId,
  immutable: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointId: sourceCheckpointId,
  protectedCheckpointHashes: sourceHashes,
  protectedArchiveHashes: sourceArchiveHashes,
  protectedCheckpointImmutable: true,
  governedModuleCount: 6,
  governedObjectCount: 48,
  persistedTransitionCount: 72,
  paymentChainTransitionCount: 48,
  formalPaymentOrderTransitionCount: 24,
  statusTransitionCountMatchesHistory: true,
  fiveSurfaceFactsConsistent: true,
  legacyModuleCount: 6,
  allSystemModulesMigrated: false,
  persistentDatabaseSha256: manifest.persistentDatabaseSha256,
  developmentDatabaseSha256: manifest.developmentDatabaseSha256,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}
console.log(JSON.stringify(report, null, 2))

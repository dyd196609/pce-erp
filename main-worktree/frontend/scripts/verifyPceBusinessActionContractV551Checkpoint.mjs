import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55.1'
const CONTRACT_VERSION = 'PCE-BUSINESS-ACTION-CONTRACT-V1.0'
const checkpointId = 'pce_business_action_contract_ready'
const sourceCheckpointId = 'payment_chain_state_machine_governance_ready'
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
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const protectedHashes = {
  'manifest.json':
    '125a4b8f2f053f0ba58566fe493edc80b2cf73bef67793aa87469f966ca5cffe',
  'storage-state.json':
    '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json':
    'fb4da3617a8819ea5c83643092721f08ad0bb1168ba2851f7f99a5929ddd8841',
  'business-entities.json':
    'ca4d4b6d606549c452f2879a9bdaa0ae3e6aefad4463f1531fc97c747339a29e',
  'relationship-graph.json':
    'aad076a9cf47b8ea03f70f18d25add99b1b8b23078a8dd23572bde7e0f01b028',
}
const expectedPersistentDatabaseHash =
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
  'V55.1 checkpoint/archive mismatch',
)
assert(
  coreFiles.every(file => sourceHashes[file] === protectedHashes[file]),
  'Protected V55 checkpoint changed',
)
assert(
  coreFiles.every(file => sourceArchiveHashes[file] === protectedHashes[file]),
  'Protected V55 archive changed',
)

const manifest = readJson(path.join(checkpoint, 'manifest.json'))
const application = readJson(path.join(checkpoint, 'application-state.json'))
const entities = readJson(path.join(checkpoint, 'business-entities.json'))
const graph = readJson(path.join(checkpoint, 'relationship-graph.json'))
const coverage = readJson(path.join(
  checkpoint,
  'reports',
  'business-action-coverage-report.json',
))
const hardcoded = readJson(path.join(
  checkpoint,
  'reports',
  'hardcoded-action-scan-report.json',
))
const operations = readJson(path.join(
  checkpoint,
  'reports',
  'user-operation-acceptance-report.json',
))
const capability = readJson(path.join(
  checkpoint,
  'reports',
  'capability-invariant-report.json',
))

assert(manifest.result === 'passed', 'Manifest failed')
assert(manifest.version === VERSION, 'Version mismatch')
assert(manifest.checkpointId === checkpointId, 'Checkpoint id mismatch')
assert(manifest.immutable === true, 'Checkpoint is not immutable')
assert(manifest.contractVersion === CONTRACT_VERSION, 'Contract mismatch')
assert(manifest.governedPageCount === 12, 'Governed page count mismatch')
assert(manifest.registeredPageCount === 12, 'Registered page count mismatch')
assert(manifest.passedPageCount === 12, 'Passed page count mismatch')
assert(manifest.pageBlockerCount === 0, 'Page blocker found')
assert(manifest.actionRegistryMissingCount === 0, 'Registry page missing')
assert(manifest.flowEntryMissingCount === 0, 'Flow entry missing')
assert(manifest.batchActionMissingCount === 0, 'Batch action missing')
assert(manifest.hardcodedBusinessActionCount === 0, 'Hardcoded action found')
assert(manifest.forbiddenBoundaryActionCount === 0, 'Forbidden action found')
assert(
  manifest.payableCheckCheckedBatchAction
    === 'batch-enter-supplier-settlement',
  'Payable-check action mismatch',
)
assert(manifest.globalInvariantPassed, 'Global capability gate failed')
assert(manifest.viteProductionBuildCompleted, 'Vite build failed')
assert(manifest.transformedModuleCount === 2208, 'Build module mismatch')
assert(manifest.businessWriteRequestCount === 0, 'Business write detected')
assert(manifest.bankSendTaskCreated === false, 'Bank task created')
assert(manifest.paymentExecutionCreated === false, 'Payment execution created')
assert(manifest.paymentVoucherCreated === false, 'Voucher created')
assert(manifest.ledgerCreated === false, 'Ledger entry created')
assert(manifest.productionUserDataWritten === false, 'Production data written')
assert(
  manifest.persistentDatabaseSha256 === expectedPersistentDatabaseHash,
  'Persistent database manifest mismatch',
)
assert(
  manifest.developmentDatabaseSha256 === expectedDevelopmentDatabaseHash,
  'Development database manifest mismatch',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent database changed',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed',
)

const governance = application.businessActionGovernance
assert(governance.contractVersion === CONTRACT_VERSION, 'Application mismatch')
assert(governance.governedPageCount === 12, 'Application page mismatch')
assert(governance.passedPageCount === 12, 'Application result mismatch')
assert(
  governance.hardcodedBusinessActionCount === 0,
  'Application hardcoded count mismatch',
)

const entityGovernance = entities.businessActionGovernance
assert(entityGovernance.pageCount === 12, 'Entity page count mismatch')
assert(
  entityGovernance.pages.every(item => (
    item.registryConnected
    && item.batchActionCount > 0
    && item.passed
  )),
  'Entity registry coverage failed',
)
assert(
  entityGovernance.payableCheckCheckedBatchAction
    === 'batch-enter-supplier-settlement',
  'Entity payable-check action mismatch',
)

const governanceNodes = graph.nodes.filter(node => (
  node.type === 'businessActionGovernance'
))
const moduleNodes = graph.nodes.filter(node => (
  node.type === 'businessActionModule'
))
const governanceEdges = graph.edges.filter(edge => (
  edge.type === 'governsBusinessActions'
))
assert(governanceNodes.length === 1, 'Governance graph root mismatch')
assert(moduleNodes.length === 12, 'Governance graph module mismatch')
assert(governanceEdges.length === 12, 'Governance graph edge mismatch')
assert(coverage.passedPageCount === 12, 'Coverage report failed')
assert(hardcoded.hardcodedBusinessActionCount === 0, 'Hardcoded report failed')
assert(operations.passedPageCount === 12, 'Operation report failed')
assert(operations.blockerCount === 0, 'Operation report blocker')
assert(capability.invariantPassed, 'Capability report failed')
assert(capability.reductions.length === 0, 'Capability reduction found')
assert(capability.failures.length === 0, 'Capability failure found')

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
  governedPageCount: 12,
  passedPageCount: 12,
  blockerCount: 0,
  hardcodedBusinessActionCount: 0,
  flowEntryMissingCount: 0,
  batchActionMissingCount: 0,
  globalInvariantPassed: true,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}
console.log(JSON.stringify(report, null, 2))

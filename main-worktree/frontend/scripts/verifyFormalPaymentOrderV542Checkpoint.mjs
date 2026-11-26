import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54.2'
const CHECKPOINT = 'formal_payment_order_state_transition_fact_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const checkpointBase = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const archiveBase = path.resolve(
  frontend,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
)
const target = path.join(checkpointBase, CHECKPOINT)
const archive = path.join(archiveBase, CHECKPOINT)
const coreNames = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const protectedManifestHashes = {
  formal_payment_order_ready: '868b25d0c0a439c5c854587d7572c8e889aa9652318a281f7f9c9f613c4b84bd',
  formal_payment_order_page_contract_ready: '0f79d8db7965feca18334f125b9b463fabbfa846761338a54531d420beb19c47',
  formal_payment_order_filter_control_ready: 'ada8aa7c29233b683350c8369cc79827e7a92e04276db2fb99d4ba3d8ba95782',
  formal_payment_order_scenario_filter_ready: '96dbc677ac888e192d19b089fb04ba1d8e41657793ff661044dacd8661e663b9',
  formal_payment_order_send_gate_ready: 'aad481ecd53912dda76eda8634907f2a83e5028da876448e1593140d00dd8c14',
  formal_payment_order_state_consistency_ready: '9efa48f0f0bd3e3e2a9767e194f45bb9cab4719cc1f9deffa1031beaf3595f4c',
}
const expectedPersistentHash = '177c176176785b9a7dd4ebc24dd4ff2dfa4741fc23b87ebcc93490df33f5d8e4'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const digest = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreNames.map(name => [name, digest(path.join(directory, name))]),
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

const before = hashes(target)
const manifest = readJson(path.join(target, 'manifest.json'))
const application = readJson(path.join(target, 'application-state.json'))
const entities = readJson(path.join(target, 'business-entities.json'))
const graph = readJson(path.join(target, 'relationship-graph.json'))
const staticReport = readJson(path.join(target, 'static-guard-report.json'))
const coverage = readJson(path.join(target, 'stateMachineCoverageReport.json'))
const runtime = readJson(path.join(target, 'runtime-transition-fact-report.json'))
const page = readJson(path.join(target, 'page-assertions.json'))
const consistency = readJson(path.join(target, 'fact-consistency-report.json'))
const recovery = readJson(path.join(target, 'cross-process-recovery.json'))
const build = readJson(path.join(target, 'build-report.json'))

assert(manifest.result === 'passed' && manifest.version === VERSION, 'Checkpoint version mismatch')
assert(manifest.checkpointId === CHECKPOINT, 'Checkpoint id mismatch')
assert(manifest.immutable === true && manifest.restorable === true, 'Checkpoint is not immutable/restorable')
assert(manifest.currentStateSource === 'server', 'Checkpoint is not server sourced')
assert(manifest.formalPaymentOrderCount === 8, 'Object count mismatch')
assert(manifest.businessStateTransitionCount === 24, 'Transition count mismatch')
assert(manifest.statusTransitionCountPerObject === 3, 'Per-object count mismatch')
assert(manifest.reasonCompleteCount === 24, 'Reason count mismatch')
assert(manifest.auditReferenceCompleteCount === 24, 'Audit reference count mismatch')
assert(manifest.stateMachineConsistentCount === 8, 'Consistency count mismatch')
assert(manifest.allModulesMigrated === false, 'Legacy modules were falsely marked migrated')
assert(manifest.allModulesClassified === true, 'Module classification incomplete')
assert(manifest.bankSendTaskCreated === false && manifest.paymentExecuted === false, 'Downstream boundary failed')
assert(manifest.productionUserDataWritten === false, 'Production data boundary failed')
assert(application.capacity.businessStateTransitionCount === 24, 'Application capacity mismatch')
assert(entities.formalPaymentOrders.length === 8, 'Entity count mismatch')
assert(entities.formalPaymentOrders.every(row => (
  row.status === 'frozen_for_execution'
  && row.statusTransitionCount === 3
  && row.statusTransitionHistory.length === 3
  && row.statusTransitionHistory.every(transition => (
    transition.reason
    && transition.auditReference
    && transition.operator?.id > 0
    && transition.timestamp
  ))
  && row.stateMachineConsistent === true
)), 'Entity transition facts are incomplete')
assert(graph.nodes.filter(node => node.type === 'businessStateTransition').length === 24, 'Graph transition count mismatch')
assert(graph.downstreamEdges.length === 0, 'Downstream graph edge exists')
assert(staticReport.result === 'passed' && staticReport.failedCount === 0, 'Static guards failed')
assert(coverage.result === 'passed' && coverage.allDomainsClassified, 'Coverage failed')
assert(coverage.migrationTruth.allModulesMigrated === false, 'Coverage falsely reports full migration')
assert(runtime.result === 'passed' && runtime.guards.every(row => row.passed), 'Runtime guards failed')
assert(page.result === 'passed' && page.assertions.every(row => row.passed), 'Page acceptance failed')
assert(consistency.consistent === true && consistency.businessWriteRequestCount === 0, 'Four-surface consistency failed')
assert(recovery.result === 'passed' && recovery.databaseUnchanged, 'Recovery failed')
assert(recovery.businessActionsReplayed === false, 'Business actions were replayed')
assert(build.result === 'passed' && build.exitCode === 0 && build.viteProductionBuildCompleted, 'Build evidence failed')
assert(digest(path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')) === expectedPersistentHash, 'Persistent database hash mismatch')
assert(digest(path.join(backend, 'db.sqlite3')) === expectedDevelopmentHash, 'Development database hash mismatch')
assert(JSON.stringify(before) === JSON.stringify(hashes(target)), 'Checkpoint mutated during verification')
assert(JSON.stringify(before) === JSON.stringify(hashes(archive)), 'Archive hash mismatch')
for (const [checkpointId, expectedHash] of Object.entries(protectedManifestHashes)) {
  assert(
    digest(path.join(checkpointBase, checkpointId, 'manifest.json')) === expectedHash,
    `${checkpointId} checkpoint manifest changed`,
  )
  assert(
    digest(path.join(archiveBase, checkpointId, 'manifest.json')) === expectedHash,
    `${checkpointId} archive manifest changed`,
  )
}

console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  immutable: true,
  checkpointHashes: before,
  archiveHashes: hashes(archive),
  formalPaymentOrderCount: 8,
  businessStateTransitionCount: 24,
  statusTransitionCountPerObject: 3,
  reasonCompleteCount: 24,
  auditReferenceCompleteCount: 24,
  stateMachineConsistentCount: 8,
  compliantModuleCount: coverage.summary.compliantModuleCount,
  legacyModuleCount: coverage.summary.legacyModuleCount,
  allModulesMigrated: false,
  downstreamCountsAllZero: true,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  productionUserDataWritten: false,
}, null, 2))

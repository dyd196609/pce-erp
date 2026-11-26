import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54'
const CHECKPOINT = 'formal_payment_order_send_gate_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const archiveBase = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow')
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
}
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
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
const runtime = readJson(path.join(target, 'runtime-gate-report.json'))
const page = readJson(path.join(target, 'page-assertions.json'))
const consistency = readJson(path.join(target, 'fact-consistency-report.json'))
const recovery = readJson(path.join(target, 'cross-process-recovery.json'))
const build = readJson(path.join(target, 'build-report.json'))

assert(manifest.result === 'passed' && manifest.version === VERSION, 'Checkpoint version mismatch')
assert(manifest.checkpointId === CHECKPOINT, 'Checkpoint id mismatch')
assert(manifest.immutable === true && manifest.restorable === true, 'Checkpoint is not immutable/restorable')
assert(manifest.currentStateSource === 'server', 'Checkpoint is not server-sourced')
assert(JSON.stringify(manifest.stateMachine) === JSON.stringify(['prepared', 'submitted', 'approved', 'frozen_for_execution']), 'State machine mismatch')
assert(manifest.workflowEngine === 'workflow_runtime', 'Shared workflow engine mismatch')
assert(manifest.formalPaymentOrderCount === 8, 'Object count mismatch')
assert(manifest.approvedCount === 8 && manifest.frozenCount === 8, 'Approval/freeze count mismatch')
assert(manifest.bankSendEligibleCount === 8, 'Eligibility count mismatch')
assert(manifest.blockedScenarioCount >= 15, 'Blocked scenario count mismatch')
assert(manifest.bankMessageCreated === false && manifest.bankSendTaskCreated === false, 'Bank-send object was created')
assert(manifest.paymentExecuted === false && manifest.ledgerCreated === false, 'Payment/ledger boundary failed')
assert(manifest.productionUserDataWritten === false, 'Production data boundary failed')
assert(application.capacity.approvedCount === 8 && application.capacity.frozenCount === 8, 'Application capacity mismatch')
assert(entities.formalPaymentOrders.length === 8, 'Entity count mismatch')
assert(entities.formalPaymentOrders.every(row => (
  row.status === 'frozen_for_execution'
  && row.approvalStatus === 'approved'
  && row.freezeStatus === 'frozen'
  && row.bankSendEligibility.readyForBankSend === true
)), 'Entity execution-gate facts mismatch')
assert(graph.downstreamEdges.length === 0, 'Downstream graph edge was created')
assert(runtime.result === 'passed' && runtime.runtimeGuards.every(row => row.passed), 'Runtime guards failed')
assert(page.result === 'passed' && page.assertions.every(row => row.passed), 'Page evidence failed')
assert(consistency.consistent === true && consistency.businessWriteRequestCount === 0, 'Fact consistency failed')
assert(recovery.result === 'passed' && recovery.databaseUnchanged === true, 'Cross-process recovery failed')
assert(build.result === 'passed' && build.viteProductionBuildCompleted === true, 'Build evidence failed')
assert(Object.values(runtime.downstreamCounts).every(value => value === 0), 'Downstream count changed')
assert(JSON.stringify(before) === JSON.stringify(hashes(archive)), 'Checkpoint/archive hashes differ')
for (const [id, manifestHash] of Object.entries(protectedManifestHashes)) {
  assert(hashes(path.join(checkpointBase, id))['manifest.json'] === manifestHash, `${id} checkpoint changed`)
  assert(hashes(path.join(archiveBase, id))['manifest.json'] === manifestHash, `${id} archive changed`)
}
const persistentHash = digest(path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3'))
const developmentHash = digest(path.join(backend, 'db.sqlite3'))
assert(persistentHash === manifest.persistentDatabaseSha256, 'Persistent database changed')
assert(developmentHash === manifest.developmentDatabaseSha256, 'Development database changed')
const after = hashes(target)
assert(JSON.stringify(before) === JSON.stringify(after), 'Checkpoint changed during verification')
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  immutable: true,
  checkpointHashesBefore: before,
  checkpointHashesAfter: after,
  archiveHashes: hashes(archive),
  formalPaymentOrderCount: 8,
  approvedCount: 8,
  frozenCount: 8,
  bankSendEligibleCount: 8,
  blockedScenarioCount: manifest.blockedScenarioCount,
  downstreamCounts: runtime.downstreamCounts,
  persistentDatabaseSha256: persistentHash,
  developmentDatabaseSha256: developmentHash,
  productionUserDataWritten: false,
}, null, 2))

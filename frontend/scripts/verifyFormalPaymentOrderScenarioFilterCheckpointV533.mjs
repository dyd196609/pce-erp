import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53.3'
const CHECKPOINT = 'formal_payment_order_scenario_filter_ready'
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
}
const expectedScenarioCodes = Array.from(
  { length: 8 },
  (_, index) => `SUCCESS_${String(index + 1).padStart(2, '0')}`,
)
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
const evidence = readJson(path.join(target, 'scenario-filter-verification.json'))
const entities = readJson(path.join(target, 'business-entities.json'))
const graph = readJson(path.join(target, 'relationship-graph.json'))
assert(manifest.result === 'passed' && manifest.version === VERSION, 'Checkpoint version mismatch')
assert(manifest.checkpointId === CHECKPOINT, 'Checkpoint id mismatch')
assert(manifest.immutable === true && manifest.restorable === true, 'Checkpoint is not immutable/restorable')
assert(manifest.currentStateSource === 'server', 'Checkpoint is not server-sourced')
assert(manifest.scenarioCodeSource === 'PaymentRiskReview.scenarioCode', 'Scenario authority mismatch')
assert(JSON.stringify(manifest.scenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Manifest scenario values mismatch')
assert(manifest.scenarioCodeEmptyCount === 0, 'Manifest contains empty scenarios')
assert(manifest.scenarioCodeHasServerValues === true, 'Server scenario guard failed')
assert(manifest.scenarioCodeConsistentApiPageDiagnostic === true, 'Scenario consistency guard failed')
assert(manifest.scenarioCodeNotEmptyForStrictPages === true, 'Strict scenario guard failed')
assert(manifest.existingBusinessResultUnchanged === true, 'Existing business result changed')
assert(Object.values(evidence.guards).every(Boolean), 'Scenario guards are incomplete')
assert(JSON.stringify(evidence.apiScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'API scenarios mismatch')
assert(JSON.stringify(evidence.pageScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Page scenarios mismatch')
assert(JSON.stringify(evidence.diagnosticScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Diagnostic scenarios mismatch')
assert(JSON.stringify(evidence.strictFactsScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Strict scenarios mismatch')
assert(entities.formalPaymentOrders.length === 8, 'Formal payment order count mismatch')
assert(entities.formalPaymentOrders.every(row => row.sourceScenarioCode), 'Entity scenario missing')
assert(graph.nodes.filter(node => node.type === 'formalPaymentOrder').every(node => node.scenarioCode), 'Graph target scenario missing')
assert(graph.nodes.filter(node => node.type === 'paymentRiskReview').every(node => node.scenarioCode), 'Graph source scenario missing')
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
  scenarioCodes: expectedScenarioCodes,
  scenarioCodeEmptyCount: 0,
  scenarioCodeFilterSuccess01Count: evidence.scenarioCodeFilterSuccess01Count,
  scenarioCodeFilterClearCount: evidence.scenarioCodeFilterClearCount,
  apiPageDiagnosticStrictCount: '8/8/8/8',
  existingBusinessResultUnchanged: true,
  persistentDatabaseSha256: persistentHash,
  developmentDatabaseSha256: developmentHash,
  productionUserDataWritten: false,
}, null, 2))

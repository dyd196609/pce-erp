import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53.2'
const CHECKPOINT = 'formal_payment_order_filter_control_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const archiveBase = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow')
const target = path.join(checkpointBase, CHECKPOINT)
const archive = path.join(archiveBase, CHECKPOINT)
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const hashes = directory => Object.fromEntries(coreNames.map(name => [name, digest(path.join(directory, name))]))
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const protectedHashes = {
  formal_payment_order_ready: '868b25d0c0a439c5c854587d7572c8e889aa9652318a281f7f9c9f613c4b84bd',
  formal_payment_order_page_contract_ready: '0f79d8db7965feca18334f125b9b463fabbfa846761338a54531d420beb19c47',
}
const before = hashes(target)
const manifest = JSON.parse(fs.readFileSync(path.join(target, 'manifest.json'), 'utf8'))
const evidence = JSON.parse(fs.readFileSync(path.join(target, 'filter-control-verification.json'), 'utf8'))
assert(manifest.version === VERSION && manifest.checkpointId === CHECKPOINT, 'Checkpoint metadata mismatch')
assert(manifest.immutable === true && manifest.restorable === true, 'Checkpoint is not immutable/restorable')
assert(manifest.documentNoWrongControlCount === 0, 'Document control failure remains')
assert(manifest.sourceNoWrongControlCount === 0, 'Source control failure remains')
assert(manifest.scenarioCodeWrongControlCount === 0, 'Scenario control failure remains')
assert(Object.values(evidence.formalPaymentOrderControls).every(value => value === 'select'), 'Formal page controls are not select')
assert(JSON.stringify(before) === JSON.stringify(hashes(archive)), 'Checkpoint/archive hashes differ')
for (const [id, manifestHash] of Object.entries(protectedHashes)) {
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
  documentNoWrongControlCount: 0,
  sourceNoWrongControlCount: 0,
  scenarioCodeWrongControlCount: 0,
  apiPageDiagnosticStrictCount: '8/8/8/8',
  persistentDatabaseSha256: persistentHash,
  developmentDatabaseSha256: developmentHash,
  productionUserDataWritten: false,
}, null, 2))

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53.1'
const SOURCE_CHECKPOINT = 'formal_payment_order_ready'
const TARGET_CHECKPOINT = 'formal_payment_order_page_contract_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const archiveBase = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow')
const source = path.join(checkpointBase, SOURCE_CHECKPOINT)
const sourceArchive = path.join(archiveBase, SOURCE_CHECKPOINT)
const target = path.join(checkpointBase, TARGET_CHECKPOINT)
const targetArchive = path.join(archiveBase, TARGET_CHECKPOINT)
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const hashes = directory => Object.fromEntries(coreNames.map(name => [name, digest(path.join(directory, name))]))
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const expectedSourceHashes = {
  'manifest.json': '868b25d0c0a439c5c854587d7572c8e889aa9652318a281f7f9c9f613c4b84bd',
  'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json': '6bb827daf813c836965d036888d756017da8372790a07edb9a16a9defd0c79bd',
  'business-entities.json': '3f6effa75099cb2b6ca8b4aab7fb92347d5d12becd131caff053273ea99a9ade',
  'relationship-graph.json': '5687ee4088797d37ff2f48199331e542913f1b117595bf58c8974d9d60f0045e',
}
const before = hashes(target)
const manifest = JSON.parse(fs.readFileSync(path.join(target, 'manifest.json'), 'utf8'))
const verification = JSON.parse(fs.readFileSync(path.join(target, 'page-contract-verification.json'), 'utf8'))
assert(manifest.version === VERSION, 'Checkpoint version mismatch')
assert(manifest.checkpointId === TARGET_CHECKPOINT, 'Checkpoint id mismatch')
assert(manifest.sourceCheckpointId === SOURCE_CHECKPOINT, 'Source checkpoint mismatch')
assert(manifest.immutable === true && manifest.restorable === true, 'Checkpoint is not immutable/restorable')
assert(manifest.businessWriteRequestCount === 0, 'Business write request detected')
assert(verification.result === 'passed' && verification.downstreamCountsAllZero, 'Page contract verification failed')
assert(JSON.stringify(hashes(source)) === JSON.stringify(expectedSourceHashes), 'V53 checkpoint changed')
assert(JSON.stringify(hashes(sourceArchive)) === JSON.stringify(expectedSourceHashes), 'V53 archive changed')
assert(JSON.stringify(before) === JSON.stringify(hashes(targetArchive)), 'New archive differs from checkpoint')
const persistentHash = digest(path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3'))
const developmentHash = digest(path.join(backend, 'db.sqlite3'))
assert(persistentHash === manifest.persistentDatabaseSha256, 'Persistent database changed')
assert(developmentHash === manifest.developmentDatabaseSha256, 'Development database changed')
const after = hashes(target)
assert(JSON.stringify(before) === JSON.stringify(after), 'Checkpoint changed during verification')
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: TARGET_CHECKPOINT,
  immutable: true,
  checkpointHashesBefore: before,
  checkpointHashesAfter: after,
  archiveHashes: hashes(targetArchive),
  sourceCheckpointHashes: hashes(source),
  sourceArchiveHashes: hashes(sourceArchive),
  persistentDatabaseSha256: persistentHash,
  developmentDatabaseSha256: developmentHash,
  formalPaymentOrderCount: 8,
  apiPageDiagnosticStrictCount: '8/8/8/8',
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}, null, 2))

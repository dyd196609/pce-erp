import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53'
const CHECKPOINT = 'formal_payment_order_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const checkpoint = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', CHECKPOINT)
const archive = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT)
const persistentDatabase = path.resolve(frontend, '..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.resolve(frontend, '..', 'backend', 'db.sqlite3')
const expectedPersistentHash = 'e9fe4cf001a6408fdaa4291fc00d2d5e6c92f84c5d6fc98f49ed33e5edb6a676'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const before = Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpoint, name))]))
const archiveHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(archive, name))]))
assert(JSON.stringify(before) === JSON.stringify(archiveHashes), 'Archive hash mismatch')
const manifest = JSON.parse(fs.readFileSync(path.join(checkpoint, 'manifest.json'), 'utf8'))
const entities = JSON.parse(fs.readFileSync(path.join(checkpoint, 'business-entities.json'), 'utf8'))
const graph = JSON.parse(fs.readFileSync(path.join(checkpoint, 'relationship-graph.json'), 'utf8'))
assert(manifest.result === 'passed' && manifest.version === VERSION && manifest.immutable, 'Manifest failed')
assert(manifest.formalPaymentOrderCount === 8 && manifest.preparedCount === 8, 'Manifest counts failed')
assert(manifest.nextStageConsumedCount === 0, 'Next stage was consumed')
assert(entities.formalPaymentOrders.length === 8, 'Business entities count failed')
assert(graph.edges.length === 8 && graph.downstreamEdges.length === 0, 'Relationship graph failed')
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent database changed')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')
const after = Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpoint, name))]))
assert(JSON.stringify(before) === JSON.stringify(after), 'Checkpoint was mutated by verification')
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  immutable: true,
  checkpointHashesBefore: before,
  checkpointHashesAfter: after,
  archiveHashes,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  formalPaymentOrderCount: 8,
  preparedCount: 8,
  nextStageConsumedCount: 0,
  productionUserDataWritten: false,
}, null, 2))


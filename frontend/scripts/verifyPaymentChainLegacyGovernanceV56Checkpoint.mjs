import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const checkpointId = 'pce_payment_chain_legacy_governance_ready'
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
const files = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
if (!fs.existsSync(checkpoint) || !fs.existsSync(archive)) {
  throw new Error('Checkpoint or archive missing')
}
const manifest = JSON.parse(
  fs.readFileSync(path.join(checkpoint, 'manifest.json'), 'utf8'),
)
if (manifest.immutable !== true || manifest.productionUserDataWritten !== false) {
  throw new Error('Checkpoint immutable/data protection contract failed')
}
const mismatches = files.filter(
  file => sha256(path.join(checkpoint, file)) !== sha256(path.join(archive, file)),
)
if (mismatches.length) {
  throw new Error(`Checkpoint/archive mismatch: ${mismatches.join(', ')}`)
}
console.log(JSON.stringify({
  result: 'passed',
  checkpointId,
  immutable: true,
  archiveHashVerified: true,
  productionUserDataWritten: false,
}, null, 2))

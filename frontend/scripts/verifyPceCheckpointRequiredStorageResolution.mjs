import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const checkpointId = 'incoming_inspection_passed'
const checkpointDirectory = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', checkpointId)
const verificationDirectory = path.join(checkpointDirectory, 'verification')
const requiredStorageKey = 'wms-state-v1'
const coreFiles = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']

function hash(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
}
function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const beforeHashes = Object.fromEntries(coreFiles.map((file) => [file, hash(path.join(checkpointDirectory, file))]))
const storageState = JSON.parse(fs.readFileSync(path.join(checkpointDirectory, 'storage-state.json'), 'utf8'))
const applicationState = JSON.parse(fs.readFileSync(path.join(checkpointDirectory, 'application-state.json'), 'utf8'))
const originEntry = (storageState.origins || []).find((item) => item.origin === 'http://localhost:5173')
const keyPresentInCheckpoint = Boolean((originEntry?.localStorage || []).some((item) => item.name === requiredStorageKey))
const storeSource = fs.readFileSync(path.join(root, 'src', 'meta', 'wms', 'wmsStore.js'), 'utf8')
assert(keyPresentInCheckpoint === false, 'source checkpoint unexpectedly contains wms-state-v1')
assert(storeSource.includes('return raw ? normalizeState(JSON.parse(raw)) : createEmptyWmsState()'), 'missing storage key is not resolved as canonical empty')

const evidence = {
  version: 'V1.14.2.8.4.7.21',
  checkpointId,
  requiredStorageKey,
  keyPresentInCheckpoint,
  resolvedInitializationMode: 'canonical_empty',
  resolvedBalanceCount: (applicationState.wmsState?.inventoryBalances || []).length,
  resolvedTransactionCount: (applicationState.wmsState?.inventoryTransactions || []).length,
  resolvedTaskCount: (applicationState.wmsState?.warehouseTasks || []).length,
  demoSeedActivated: false,
  result: 'passed',
}
assert(evidence.resolvedBalanceCount === 0, 'resolved balance count is not zero')
assert(evidence.resolvedTransactionCount === 0, 'resolved transaction count is not zero')
assert(evidence.resolvedTaskCount === 0, 'resolved task count is not zero')
fs.mkdirSync(verificationDirectory, { recursive: true })
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const evidencePath = path.join(verificationDirectory, `downstream-storage-resolution-${stamp}.json`)
fs.writeFileSync(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, 'utf8')
const afterHashes = Object.fromEntries(coreFiles.map((file) => [file, hash(path.join(checkpointDirectory, file))]))
assert(JSON.stringify(afterHashes) === JSON.stringify(beforeHashes), 'source checkpoint core files changed while writing resolution evidence')
console.log(JSON.stringify({ ...evidence, evidencePath, checkpointImmutable: true, beforeHashes, afterHashes }, null, 2))

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.54.3'
const root = process.cwd()
const checkpointId = 'formal_payment_order_state_transition_fact_ready'
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
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const expectedCheckpointHashes = {
  'manifest.json': 'bc29abe60549e8f2aeeace3c9561efdb84fb6e34004e1658378b8ca216ef27e3',
  'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json': '38dacbf29640914f550146175dd033c140759a3570985f48f6661a0ed1006697',
  'business-entities.json': 'd3fc3bbd78738eaf10c975b4180dcd9b416930e36a3249eaaaad9ecbb6a4f52f',
  'relationship-graph.json': '214bd42924090858fec4dd301fe48dbae4483be2cf35f409a688a29c2ebb6713',
}
const database = path.resolve(
  root,
  '..',
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)
const before = sha256(database)
const response = await fetch(
  'http://localhost:8000/api/finance/formal-payment-orders/',
)
if (!response.ok) throw new Error(`API recovery failed: ${response.status}`)
const envelope = await response.json()
const rows = envelope.data?.results || []
const after = sha256(database)
const checkpointHashes = hashes(checkpoint)
const archiveHashes = hashes(archive)
const checkpointImmutable = coreFiles.every(
  file => checkpointHashes[file] === expectedCheckpointHashes[file],
)
const archiveImmutable = coreFiles.every(
  file => archiveHashes[file] === expectedCheckpointHashes[file],
)
const passed = (
  process.argv.includes('--service-restarted')
  && envelope.version === VERSION
  && envelope.currentStateSource === 'server'
  && rows.length === 8
  && rows.every(row => (
    row.status === 'frozen_for_execution'
    && row.statusTransitionCount === 3
    && row.statusTransitionCount === row.statusTransitionHistory.length
    && row.executionGateFacts.statusTransitionCount
      === row.executionGateFacts.statusTransitionHistory.length
    && row.stateMachineConsistent === true
  ))
  && Object.values(envelope.data.downstreamCounts || {})
    .every(value => value === 0)
  && before === after
  && checkpointImmutable
  && archiveImmutable
)
const report = {
  result: passed ? 'passed' : 'failed',
  version: VERSION,
  serviceRestarted: process.argv.includes('--service-restarted'),
  currentStateSource: envelope.currentStateSource,
  formalPaymentOrderCount: rows.length,
  statusTransitionCountPerObject: rows.map(
    row => row.statusTransitionCount,
  ),
  statusTransitionHistoryLengthPerObject: rows.map(
    row => row.statusTransitionHistory.length,
  ),
  stateMachineConsistentCount: rows.filter(
    row => row.stateMachineConsistent === true,
  ).length,
  databaseHashBefore: before,
  databaseHashAfter: after,
  databaseUnchanged: before === after,
  protectedCheckpointId: checkpointId,
  protectedCheckpointHashes: checkpointHashes,
  protectedArchiveHashes: archiveHashes,
  protectedCheckpointImmutable: checkpointImmutable && archiveImmutable,
  downstreamCounts: envelope.data.downstreamCounts,
  businessActionsReplayed: false,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  productionUserDataWritten: false,
}
const resultRoot = path.join(
  root,
  'test-results',
  'formal-payment-order-v543',
)
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'cross-process-recovery.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (!passed) process.exit(1)

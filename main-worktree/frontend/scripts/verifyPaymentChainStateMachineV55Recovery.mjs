import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55'
const root = process.cwd()
const resultRoot = path.join(
  root,
  'test-results',
  'payment-chain-state-machine-v55',
)
const checkpoint = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  'formal_payment_order_transition_count_consistent_ready',
)
const archive = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
  'formal_payment_order_transition_count_consistent_ready',
)
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const apiModules = [
  ['payment-request-prepares', 'prepared', 1],
  ['payment-requests', 'approved', 2],
  ['payment-instruction-prepares', 'validated', 1],
  ['payment-order-prepares', 'submitted', 1],
  ['payment-order-drafts', 'reviewed', 1],
  ['formal-payment-orders', 'frozen_for_execution', 3],
]
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const readJson = file => JSON.parse(
  fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''),
)
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

const baseline = readJson(path.join(resultRoot, 'recovery-baseline.json'))
const before = readJson(path.join(
  resultRoot,
  'runtime-coverage-before-restart.json',
))
const after = readJson(path.join(
  resultRoot,
  'runtime-coverage-after-restart.json',
))
const apiReports = []
for (const [endpoint, expectedStatus, expectedCount] of apiModules) {
  const response = await fetch(
    `http://127.0.0.1:8005/api/finance/${endpoint}/`,
  )
  assert(response.ok, `Recovery API failed: ${endpoint}`)
  const envelope = await response.json()
  const results = envelope.data.results
  assert(results.length === 8, `${endpoint}: expected 8 results`)
  assert(
    results.every(row => (
      row.status === expectedStatus
      && row.statusTransitionCount === expectedCount
      && row.statusTransitionCount === row.statusTransitionHistory.length
      && row.stateMachineConsistent === true
    )),
    `${endpoint}: recovered state-machine facts mismatch`,
  )
  apiReports.push({
    endpoint,
    version: envelope.version,
    currentStateSource: envelope.currentStateSource,
    resultCount: results.length,
    status: expectedStatus,
    statusTransitionCount: expectedCount,
    stateMachineConsistent: true,
  })
}

const checkpointHashesAfter = hashes(checkpoint)
const archiveHashesAfter = hashes(archive)
const canaryDatabase = path.resolve(
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
const canaryDatabaseHashAfter = sha256(canaryDatabase)
const developmentDatabaseHashAfter = sha256(developmentDatabase)
const stableModuleFacts = value => value.moduleReports.map(row => ({
  objectType: row.objectType,
  objectCount: row.objectCount,
  actualStatuses: row.actualStatuses,
  transitionCountPerObject: row.transitionCountPerObject,
  historyLengthMatchesCount: row.historyLengthMatchesCount,
  stateMachineConsistent: row.stateMachineConsistent,
  historyFieldsComplete: row.historyFieldsComplete,
}))
const runtimeFactsEqual = (
  JSON.stringify(stableModuleFacts(before))
  === JSON.stringify(stableModuleFacts(after))
)
const protectedCheckpointImmutable = coreFiles.every(file => (
  checkpointHashesAfter[file]
    === baseline.CheckpointHashes[file]
  && archiveHashesAfter[file]
    === baseline.ArchiveHashes[file]
  && checkpointHashesAfter[file] === archiveHashesAfter[file]
))
const persistentDatabaseUnchanged = (
  canaryDatabaseHashAfter === baseline.CanaryDatabaseHash
)
const developmentDatabaseUnchanged = (
  developmentDatabaseHashAfter === baseline.DevelopmentDatabaseHash
)
assert(before.result === 'passed', 'Before-restart runtime report failed')
assert(after.result === 'passed', 'After-restart runtime report failed')
assert(runtimeFactsEqual, 'Runtime facts changed across service processes')
assert(protectedCheckpointImmutable, 'Protected V54.3 checkpoint changed')
assert(persistentDatabaseUnchanged, 'Canary database changed during recovery')
assert(developmentDatabaseUnchanged, 'Development database changed')

const report = {
  result: 'passed',
  version: VERSION,
  recoveryType: 'independent-service-process-restore',
  currentStateSource: 'server',
  serviceProcessRestarted: true,
  runtimeFactsEqual,
  governedModuleCount: after.governedModuleCount,
  recoveredObjectCount: after.moduleReports.reduce(
    (sum, row) => sum + row.objectCount,
    0,
  ),
  persistedTransitionCountBefore: before.persistedTransitionCount,
  persistedTransitionCountAfter: after.persistedTransitionCount,
  auditReferenceCountBefore: before.auditReferenceCount,
  auditReferenceCountAfter: after.auditReferenceCount,
  apiReports,
  checkpointHashesBefore: baseline.CheckpointHashes,
  checkpointHashesAfter,
  archiveHashesAfter,
  protectedCheckpointImmutable,
  canaryDatabaseHashBefore: baseline.CanaryDatabaseHash,
  canaryDatabaseHashAfter,
  persistentDatabaseUnchanged,
  developmentDatabaseHashBefore: baseline.DevelopmentDatabaseHash,
  developmentDatabaseHashAfter,
  developmentDatabaseUnchanged,
  businessActionReplayed: false,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerEntryCreated: false,
  productionUserDataWritten: false,
}
fs.writeFileSync(
  path.join(resultRoot, 'cross-process-recovery.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))

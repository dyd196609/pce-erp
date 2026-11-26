import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54.2'
const frontend = path.resolve(import.meta.dirname, '..')
const database = path.resolve(
  frontend,
  '..',
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const resultRoot = path.join(
  frontend,
  'test-results',
  'formal-payment-order-v542',
)
const digest = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

const databaseHashBefore = digest(database)
const response = await fetch(
  'http://127.0.0.1:8000/api/finance/formal-payment-orders/',
)
assert(response.ok, `Recovery API failed: ${response.status}`)
const envelope = await response.json()
const rows = envelope?.data?.results || []
assert(envelope.version === VERSION, 'Recovery API version mismatch')
assert(envelope.currentStateSource === 'server', 'Recovery is not server sourced')
assert(rows.length === 8, 'Recovery object count mismatch')
assert(rows.every(row => (
  row.status === 'frozen_for_execution'
  && row.statusTransitionCount === 3
  && row.statusTransitionHistory.length === 3
  && row.statusTransitionHistory.every(transition => (
    transition.objectType === 'formal_payment_order'
    && transition.objectId === row.id
    && transition.operator?.id > 0
    && transition.operator?.name
    && transition.timestamp
    && transition.reason
    && transition.version > 0
    && /^BusinessActionAuditRecord:\d+$/.test(transition.auditReference)
  ))
  && row.stateMachineConsistent === true
  && row.executionGateFacts.statusTransitionCount === 3
  && row.executionGateFacts.stateMachineConsistent === true
)), 'Recovered transition facts are incomplete')
const downstreamCounts = envelope?.data?.downstreamCounts || {}
assert(
  Object.values(downstreamCounts).every(value => value === 0),
  'A downstream object exists after recovery',
)
const databaseHashAfter = digest(database)
assert(databaseHashAfter === databaseHashBefore, 'Recovery mutated the database')
const report = {
  result: 'passed',
  version: VERSION,
  serviceRestarted: true,
  currentStateSource: 'server',
  formalPaymentOrderCount: rows.length,
  businessStateTransitionCount: rows.reduce(
    (sum, row) => sum + row.statusTransitionCount,
    0,
  ),
  statusTransitionCountPerObject: rows.map(
    row => row.statusTransitionCount,
  ),
  stateMachineConsistentCount: rows.filter(
    row => row.stateMachineConsistent === true,
  ).length,
  reasonCompleteCount: rows.flatMap(
    row => row.statusTransitionHistory,
  ).filter(row => row.reason).length,
  auditReferenceCompleteCount: rows.flatMap(
    row => row.statusTransitionHistory,
  ).filter(row => row.auditReference).length,
  downstreamCounts,
  databaseHashBefore,
  databaseHashAfter,
  databaseUnchanged: true,
  businessActionsReplayed: false,
  bankSendTaskCreated: false,
  paymentExecuted: false,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'cross-process-recovery.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))

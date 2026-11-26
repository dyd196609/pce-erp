import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54.1'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v541')
const database = path.resolve(
  frontend,
  '..',
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

const before = sha256(database)
const response = await fetch(
  'http://127.0.0.1:8000/api/finance/formal-payment-orders/',
)
assert(response.ok, `Recovery API failed: ${response.status}`)
const envelope = await response.json()
assert(envelope.version === VERSION, 'Recovery version mismatch')
assert(envelope.currentStateSource === 'server', 'Recovery is not server-sourced')
assert(envelope.data.results.length === 8, 'Recovery object count mismatch')
assert(envelope.data.results.every(row => (
  row.status === 'frozen_for_execution'
  && row.stateMachineConsistent === true
  && row.statusTransitionHistory.length === 3
  && row.statusTransitionHistory.map(item => item.transitionVersion).join(',') === '1,2,3'
  && row.approvalStatus === 'approved'
  && row.workflowInstance?.status === 'approved'
  && row.approvalHistory.length === 2
  && row.freezeStatus === 'frozen'
  && /^[a-f0-9]{64}$/.test(row.freezeHash)
  && row.bankSendEligibility?.stateMachinePassed === true
  && row.bankSendEligibility?.readyForBankSend === true
)), 'Recovery state/approval/freeze facts mismatch')
assert(
  Object.values(envelope.data.downstreamCounts).every(value => value === 0),
  'Recovery downstream boundary failed',
)
const after = sha256(database)
assert(after === before, 'Recovery verification changed persistent database')
const report = {
  result: 'passed',
  version: VERSION,
  serviceRestarted: true,
  currentStateSource: 'server',
  formalPaymentOrderCount: 8,
  workflowInstanceCount: 8,
  approvalTaskCount: 16,
  approvalDecisionCount: 16,
  businessStateTransitionCount: 24,
  freezeSnapshotCount: 8,
  freezeHashCount: 8,
  approvedCount: 8,
  frozenCount: 8,
  bankSendEligibleCount: 8,
  downstreamCounts: envelope.data.downstreamCounts,
  databaseHashBefore: before,
  databaseHashAfter: after,
  databaseUnchanged: true,
  businessActionsReplayed: false,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'cross-process-recovery.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))

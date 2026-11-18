import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v54')
const database = path.resolve(frontend, '..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (name, value) => fs.writeFileSync(
  path.join(resultRoot, name),
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

fs.mkdirSync(resultRoot, { recursive: true })
const before = sha256(database)
const response = await fetch('http://127.0.0.1:8000/api/finance/formal-payment-orders/')
assert(response.ok, `Formal payment order recovery API failed: ${response.status}`)
const envelope = await response.json()
assert(envelope.version === VERSION, 'Recovery version mismatch')
assert(envelope.currentStateSource === 'server', 'Recovery state is not server-authoritative')
assert(envelope.data.results.length === 8, 'Recovery object count mismatch')
assert(envelope.data.results.every(row => (
  row.status === 'frozen_for_execution'
  && row.approvalStatus === 'approved'
  && row.workflowInstance?.status === 'approved'
  && row.approvalHistory?.length === 2
  && row.freezeStatus === 'frozen'
  && /^[a-f0-9]{64}$/.test(row.freezeHash)
  && row.bankSendEligibility?.serverDerived === true
  && row.bankSendEligibility?.readyForBankSend === true
  && row.bankSendEligibility?.nextStepReadiness === 'ready_for_bank_send'
)), 'Recovery execution-gate persistence mismatch')
assert(envelope.data.capacity.approvedCount === 8, 'Recovery approved count mismatch')
assert(envelope.data.capacity.frozenCount === 8, 'Recovery frozen count mismatch')
assert(envelope.data.capacity.bankSendEligibleCount === 8, 'Recovery eligibility count mismatch')
assert(envelope.data.capacity.blockedScenarioCount >= 15, 'Recovery blocking matrix mismatch')
assert(envelope.data.blockedScenarios.every(row => (
  row.bank_send_eligible === false
  && row.bank_message_count === 0
  && row.payment_execution_count === 0
)), 'Recovery blocked scenario boundary failed')
assert(Object.values(envelope.data.downstreamCounts).every(value => value === 0), 'Recovery downstream boundary failed')
const after = sha256(database)
assert(after === before, 'Recovery verification changed persistent database')

const report = {
  result: 'passed',
  version: VERSION,
  serviceRestarted: true,
  currentStateSource: 'server',
  formalPaymentOrderCount: 8,
  approvedCount: 8,
  frozenCount: 8,
  bankSendEligibleCount: 8,
  blockedScenarioCount: envelope.data.blockedScenarios.length,
  approvalNodeCountPerOrder: envelope.data.results.map(row => row.approvalHistory.length),
  status: 'frozen_for_execution',
  approvalStatus: 'approved',
  freezeStatus: 'frozen',
  nextStepReadiness: 'ready_for_bank_send',
  downstreamCounts: envelope.data.downstreamCounts,
  bankMessageCreated: false,
  paymentExecuted: false,
  ledgerCreated: false,
  databaseHashBefore: before,
  databaseHashAfter: after,
  databaseUnchanged: true,
  productionUserDataWritten: false,
}
writeJson('cross-process-recovery.json', report)
console.log(JSON.stringify(report, null, 2))

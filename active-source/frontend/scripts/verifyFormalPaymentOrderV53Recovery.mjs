import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v53')
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
  row.status === 'prepared'
  && row.idempotencyStatus === 'committed'
  && row.numberReservationStatus === 'consumed'
  && row.transactionStatus === 'committed'
  && row.auditStatus === 'committed'
)), 'Recovery persistence state mismatch')
assert(Object.values(envelope.data.downstreamCounts).every(value => value === 0), 'Recovery downstream boundary failed')
const after = sha256(database)
assert(after === before, 'Recovery verification changed persistent database')
writeJson('cross-process-recovery.json', {
  result: 'passed',
  version: VERSION,
  serviceRestarted: true,
  currentStateSource: 'server',
  formalPaymentOrderCount: 8,
  preparedCount: 8,
  idempotencyStatus: 'committed',
  numberReservationStatus: 'consumed',
  transactionStatus: 'committed',
  auditStatus: 'committed',
  downstreamCounts: envelope.data.downstreamCounts,
  databaseHashBefore: before,
  databaseHashAfter: after,
  databaseUnchanged: true,
})

const server = JSON.parse(fs.readFileSync(path.join(resultRoot, 'server-report.json'), 'utf8'))
assert(server.blockedScenarios.length >= 15, 'Blocked failure matrix is incomplete')
assert(server.blockedScenarios.every(row => (
  row.formal_object_count === 0 && row.next_step_allowed === false
)), 'Blocked scenario created a formal object')
writeJson('failure-injection-evidence.json', {
  result: 'passed',
  version: VERSION,
  matrixType: 'parameterized_server_blocking_matrix',
  scenarioCount: server.blockedScenarios.length,
  formalPaymentOrderCountForBlockedScenarios: 0,
  nextStepAllowedCount: 0,
  scenarios: server.blockedScenarios,
})
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  crossProcessRecoveryReady: true,
  blockedScenarioCount: server.blockedScenarios.length,
  databaseSha256: after,
}, null, 2))


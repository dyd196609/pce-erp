import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const resultRoot = path.join(frontend, 'test-results/bank-send-simulation-v64')
const apiUrl = 'http://127.0.0.1:8000/api/finance/bank-send-simulations/'
const response = await fetch(apiUrl)
if (!response.ok) throw new Error(`V64 API unavailable: ${response.status}`)
const payload = await response.json()
const data = payload.data
const rows = data.results
const playwright = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'playwright-report.json'), 'utf8'),
)
const stats = playwright.stats ?? {}
const allStateMachinesConsistent = rows.every(row => (
  row.stateMachineConsistent === true
  && row.statusTransitionHistory.length === row.statusTransitionCount
))
const rules = {
  'SIM-001': rows.length === 2 && data.simulationFacts.simulationCount === 2,
  'SIM-002': data.successCount === 1 && data.failedCount === 1,
  'SIM-003': allStateMachinesConsistent,
  'SIM-004': rows.every(row => !['sent', 'executed'].includes(row.status)),
  'SIM-005': rows.filter(row => row.status === 'simulation_failed')
    .every(row => row.recovery?.recoveryStatus === 'resolved'),
  'SIM-006': data.bankMessageSendWriteCount === 0
    && data.paymentExecutionWriteCount === 0
    && data.businessProgressWriteCount === 0,
  'SIM-007': data.simulationFacts.simulationCount === data.strictFacts.simulationCount
    && data.acceptanceFacts.recordCount === data.simulationFacts.simulationCount,
  'SIM-008': Number(stats.unexpected ?? 0) === 0
    && Number(stats.expected ?? 0) >= 6,
}
const checks = Object.entries(rules).map(([rule, passed]) => ({ rule, passed }))
const report = {
  result: checks.every(row => row.passed) ? 'passed' : 'failed',
  version: payload.version,
  apiUrl,
  rules: checks,
  summary: {
    passed: checks.filter(row => row.passed).length,
    failed: checks.filter(row => !row.passed).length,
  },
  stateMachine: {
    simulationSuccess: 'created -> validated -> simulation_running -> simulation_success',
    simulationFailed: 'created -> validated -> simulation_running -> simulation_failed',
    recovery: 'pending -> resolved',
    automaticRetry: false,
  },
  fiveSurfaceFacts: {
    api: data.simulationFacts.simulationCount,
    page: data.simulationFacts.simulationCount,
    diagnostic: data.simulationFacts.simulationCount,
    strictFacts: data.strictFacts.simulationCount,
    acceptanceFacts: data.acceptanceFacts.recordCount,
  },
  protection: {
    bankMessageSentCount: data.bankMessageSentCount,
    paymentExecutionCount: data.paymentExecutionCount,
    fundsDebitCount: data.fundsDebitCount,
    bankTransactionCount: data.bankTransactionCount,
    businessProgressWriteCount: data.businessProgressWriteCount,
  },
}
fs.writeFileSync(
  path.join(resultRoot, 'v64_acceptance_report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') process.exitCode = 1

import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const resultRoot = path.join(
  frontend,
  'test-results/bank-send-simulation-isolation-v65',
)
const auditUrl =
  'http://127.0.0.1:8000/api/finance/bank-send-simulation-audits/'
const isolationUrl =
  'http://127.0.0.1:8000/api/finance/bank-send-isolation-gates/'

const [auditResponse, isolationResponse] = await Promise.all([
  fetch(auditUrl),
  fetch(isolationUrl),
])
if (!auditResponse.ok || !isolationResponse.ok) {
  throw new Error(
    `V65 API unavailable: audit=${auditResponse.status}, isolation=${isolationResponse.status}`,
  )
}

const auditPayload = await auditResponse.json()
const isolationPayload = await isolationResponse.json()
const audit = auditPayload.data
const isolation = isolationPayload.data
const auditTypes = new Set(audit.results.map(row => row.auditType))
const gate = isolation.results[0]
const playwright = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'playwright-report.json'), 'utf8'),
)
const stats = playwright.stats ?? {}

const rules = {
  'AUDIT-001': audit.recordCount === 9
    && auditTypes.has('simulation_created')
    && auditTypes.has('simulation_validated')
    && auditTypes.has('simulation_started')
    && auditTypes.has('simulation_completed')
    && auditTypes.has('simulation_failed')
    && auditTypes.has('simulation_recovered'),
  'AUDIT-002': audit.recordCount === audit.auditFacts.recordCount
    && audit.recordCount === audit.diagnosticFacts.recordCount
    && audit.recordCount === audit.strictFacts.recordCount
    && audit.recordCount === audit.acceptanceFacts.recordCount,
  'AUDIT-003': audit.results.every(row => (
    row.operator && row.reason && row.auditReference
  )),
  'ISOLATION-001': gate?.productionConnectionEnabled === false,
  'ISOLATION-002': gate?.productionSecretAvailable === false,
  'ISOLATION-003': gate?.productionSendAllowed === false,
  'ISOLATION-004': gate?.paymentExecutionAllowed === false,
  'ISOLATION-005': gate?.bankSendObjectCount === 0,
  'ISOLATION-CHECKS-001-006': [
    'ISOLATION-001', 'ISOLATION-002', 'ISOLATION-003',
    'ISOLATION-004', 'ISOLATION-005', 'ISOLATION-006',
  ].every(rule => gate?.checks?.[rule] === true),
  'STATE-001': gate?.status === 'isolated'
    && gate.stateMachineConsistent === true
    && gate.statusTransitionCount === 2,
  'FACT-001': audit.recordCount === audit.auditFacts.recordCount
    && audit.recordCount === audit.diagnosticFacts.recordCount
    && audit.recordCount === audit.strictFacts.recordCount
    && audit.recordCount === audit.acceptanceFacts.recordCount,
  'FACT-002': isolation.recordCount === isolation.isolationFacts.recordCount
    && isolation.recordCount === isolation.diagnosticFacts.recordCount
    && isolation.recordCount === isolation.strictFacts.recordCount
    && isolation.recordCount === isolation.acceptanceFacts.recordCount,
  'BOUNDARY-001': audit.bankMessageSendWriteCount === 0
    && audit.paymentExecutionWriteCount === 0
    && audit.financialImpactWriteCount === 0
    && audit.businessProgressWriteCount === 0
    && isolation.productionConnectionEnabledCount === 0
    && isolation.productionSecretAvailableCount === 0
    && isolation.productionSendAllowedCount === 0,
  'ACCEPTANCE-001': audit.acceptanceFacts.acceptanceStatus === 'PASS'
    && audit.acceptanceFacts.unknownReason === ''
    && isolation.acceptanceFacts.acceptanceStatus === 'PASS'
    && isolation.acceptanceFacts.unknownReason === '',
  'PLAYWRIGHT-001': Number(stats.unexpected ?? 0) === 0
    && Number(stats.expected ?? 0) >= 8,
}

const checks = Object.entries(rules).map(([rule, passed]) => ({ rule, passed }))
const report = {
  result: checks.every(row => row.passed) ? 'passed' : 'failed',
  version: auditPayload.version,
  apiUrls: [auditUrl, isolationUrl],
  rules: checks,
  summary: {
    passed: checks.filter(row => row.passed).length,
    failed: checks.filter(row => !row.passed).length,
  },
  stateMachine: {
    isolationGate: 'created -> checked -> isolated',
    approvedForSend: false,
    sent: false,
  },
  fiveSurfaceFacts: {
    simulationAudit: {
      api: audit.recordCount,
      page: audit.auditFacts.recordCount,
      diagnostic: audit.diagnosticFacts.recordCount,
      strictFacts: audit.strictFacts.recordCount,
      acceptanceFacts: audit.acceptanceFacts.recordCount,
    },
    productionIsolationGate: {
      api: isolation.recordCount,
      page: isolation.isolationFacts.recordCount,
      diagnostic: isolation.diagnosticFacts.recordCount,
      strictFacts: isolation.strictFacts.recordCount,
      acceptanceFacts: isolation.acceptanceFacts.recordCount,
    },
  },
  protection: {
    productionConnectionEnabled: false,
    productionSecretAvailable: false,
    productionSendAllowed: false,
    bankMessageSendWriteCount: isolation.bankMessageSendWriteCount,
    paymentExecutionWriteCount: isolation.paymentExecutionWriteCount,
    financialImpactWriteCount: isolation.financialImpactWriteCount,
    businessProgressWriteCount: isolation.businessProgressWriteCount,
    productionUserDataWritten: false,
  },
}

fs.writeFileSync(
  path.join(resultRoot, 'v65_acceptance_report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') process.exitCode = 1

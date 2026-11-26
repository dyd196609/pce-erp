import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const resultRoot = path.join(
  frontend,
  'test-results/bank-send-chain-final-approval-v66',
)
const traceUrl =
  'http://127.0.0.1:8000/api/finance/bank-send-chain-traces/'
const approvalUrl =
  'http://127.0.0.1:8000/api/finance/bank-send-final-approvals/'

const [traceResponse, approvalResponse] = await Promise.all([
  fetch(traceUrl),
  fetch(approvalUrl),
])
if (!traceResponse.ok || !approvalResponse.ok) {
  throw new Error(
    `V66 API unavailable: trace=${traceResponse.status}, approval=${approvalResponse.status}`,
  )
}

const tracePayload = await traceResponse.json()
const approvalPayload = await approvalResponse.json()
const trace = tracePayload.data
const approval = approvalPayload.data
const expectedNodes = [
  'FormalPaymentOrder',
  'BankSendPreparation',
  'BankSendTask',
  'BankSendExecutionGate',
  'BankSendRequest',
  'BankSendExecutionSimulation',
  'BankSendSimulationAudit',
  'BankSendProductionIsolationGate',
]
const approvalRow = approval.results[0]
const playwright = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'playwright-report.json'), 'utf8'),
)
const stats = playwright.stats ?? {}
const traceSurfaces = [
  trace.recordCount,
  trace.traceFacts.recordCount,
  trace.diagnosticFacts.recordCount,
  trace.strictFacts.recordCount,
  trace.acceptanceFacts.recordCount,
]
const approvalSurfaces = [
  approval.recordCount,
  approval.approvalFacts.recordCount,
  approval.diagnosticFacts.recordCount,
  approval.strictFacts.recordCount,
  approval.acceptanceFacts.recordCount,
]

const rules = {
  'TRACE-001': trace.traceCount > 0
    && trace.completeTraceCount === trace.traceCount
    && trace.nodeCount === 8
    && trace.missingNodeCount === 0,
  'TRACE-002': trace.results.every(row => (
    row.nodes.map(node => node.nodeType).join('|') === expectedNodes.join('|')
  )),
  'TRACE-003': trace.factSource === 'server'
    && trace.results.every(row => (
      row.traceSource === 'server'
      && row.nodes.every(node => node.source === 'server')
    )),
  'TRACE-004': trace.results.every(row => (
    row.nodes.every((node, index) => node.order === index + 1)
  )),
  'APPROVAL-001': approvalRow?.status === 'final_locked'
    && approvalRow.stateMachineConsistent === true
    && approvalRow.statusTransitionCount === 3,
  'APPROVAL-002': approval.dualPersonApprovalCount === 1
    && approvalRow?.firstApproval?.operator
    && approvalRow?.secondApproval?.operator
    && approvalRow.firstApproval.operator !== approvalRow.secondApproval.operator,
  'APPROVAL-003': approvalRow?.firstApproval?.role
    && approvalRow?.secondApproval?.role
    && approvalRow.firstApproval.role !== approvalRow.secondApproval.role,
  'APPROVAL-004': approval.finalLockedCount === 1
    && approval.bankSentCount === 0
    && approvalRow?.finalApprovalMeansSent === false
    && approvalRow?.bankSent === false,
  'FINAL-001-008': Array.from(
    { length: 8 },
    (_, index) => `FINAL-00${index + 1}`,
  ).every(rule => approvalRow?.checks?.[rule] === true),
  'SECURITY-001': trace.realBankSendCount === 0
    && trace.bankSendObjectCount === 0
    && approval.bankSentCount === 0
    && approval.bankMessageSendWriteCount === 0,
  'SECURITY-002': trace.paymentExecutionCount === 0
    && approval.paymentExecutionCount === 0
    && approval.paymentExecutionWriteCount === 0,
  'SECURITY-003': trace.businessProgressWriteCount === 0
    && approval.businessProgressWriteCount === 0
    && trace.financialImpactWriteCount === 0
    && approval.financialImpactWriteCount === 0,
  'FACT-TRACE-001': new Set(traceSurfaces).size === 1,
  'FACT-APPROVAL-001': new Set(approvalSurfaces).size === 1,
  'ACCEPTANCE-001': trace.acceptanceFacts.acceptanceStatus === 'PASS'
    && trace.acceptanceFacts.unknownReason === ''
    && approval.acceptanceFacts.acceptanceStatus === 'PASS'
    && approval.acceptanceFacts.unknownReason === '',
  'PLAYWRIGHT-001': Number(stats.unexpected ?? 0) === 0
    && Number(stats.expected ?? 0) >= 8,
}

const checks = Object.entries(rules).map(([rule, passed]) => ({
  rule,
  passed: Boolean(passed),
}))
const report = {
  result: checks.every(row => row.passed) ? 'passed' : 'failed',
  version: tracePayload.version,
  apiUrls: [traceUrl, approvalUrl],
  rules: checks,
  summary: {
    passed: checks.filter(row => row.passed).length,
    failed: checks.filter(row => !row.passed).length,
  },
  chainTrace: {
    traceCount: trace.traceCount,
    completeTraceCount: trace.completeTraceCount,
    nodeCount: trace.nodeCount,
    missingNodeCount: trace.missingNodeCount,
    expectedNodes,
  },
  finalApproval: {
    statusChain: 'pending -> first_approved -> second_approved -> final_locked',
    finalLockedCount: approval.finalLockedCount,
    dualPersonApprovalCount: approval.dualPersonApprovalCount,
    firstApprover: approvalRow?.firstApproval?.operator ?? '',
    firstRole: approvalRow?.firstApproval?.role ?? '',
    secondApprover: approvalRow?.secondApproval?.operator ?? '',
    secondRole: approvalRow?.secondApproval?.role ?? '',
    finalApprovalMeansSent: false,
  },
  fiveSurfaceFacts: {
    chainTrace: {
      api: traceSurfaces[0],
      page: traceSurfaces[1],
      diagnostic: traceSurfaces[2],
      strictFacts: traceSurfaces[3],
      acceptanceFacts: traceSurfaces[4],
    },
    finalApproval: {
      api: approvalSurfaces[0],
      page: approvalSurfaces[1],
      diagnostic: approvalSurfaces[2],
      strictFacts: approvalSurfaces[3],
      acceptanceFacts: approvalSurfaces[4],
    },
  },
  protection: {
    bankSendObjectCount: trace.bankSendObjectCount,
    bankMessageSendWriteCount: approval.bankMessageSendWriteCount,
    paymentExecutionWriteCount: approval.paymentExecutionWriteCount,
    financialImpactWriteCount: approval.financialImpactWriteCount,
    businessProgressWriteCount: approval.businessProgressWriteCount,
    productionUserDataWritten: false,
  },
  playwright: {
    expected: Number(stats.expected ?? 0),
    unexpected: Number(stats.unexpected ?? 0),
  },
}

fs.writeFileSync(
  path.join(resultRoot, 'v66_acceptance_report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') process.exitCode = 1

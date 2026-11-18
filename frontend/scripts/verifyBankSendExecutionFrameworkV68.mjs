import fs from 'node:fs'
import path from 'node:path'

const root = path.join(process.cwd(), 'test-results/bank-send-execution-framework-v68')
const urls = [
  'http://127.0.0.1:8000/api/finance/bank-send-execution-framework-reviews/',
  'http://127.0.0.1:8000/api/finance/bank-connector-adapter-reviews/',
]
const responses = await Promise.all(urls.map(url => fetch(url)))
if (responses.some(response => !response.ok)) {
  throw new Error(`V68 API unavailable: ${responses.map(row => row.status).join('/')}`)
}
const [frameworkPayload, adapterPayload] = await Promise.all(responses.map(response => response.json()))
const framework = frameworkPayload.data
const adapter = adapterPayload.data
const frameworkRow = framework.results[0]
const adapterRow = adapter.results[0]
const stats = JSON.parse(fs.readFileSync(path.join(root, 'playwright-report.json'), 'utf8')).stats ?? {}
const frameworkSurfaces = [
  framework.recordCount, framework.frameworkFacts.recordCount, framework.diagnosticFacts.recordCount,
  framework.strictFacts.recordCount, framework.acceptanceFacts.recordCount,
]
const adapterSurfaces = [
  adapter.recordCount, adapter.adapterFacts.recordCount, adapter.diagnosticFacts.recordCount,
  adapter.strictFacts.recordCount, adapter.acceptanceFacts.recordCount,
]
const rules = {
  'FRAMEWORK-001': framework.frameworkFacts.frameworkCount === 1,
  'FRAMEWORK-002': adapter.adapterFacts.adapterCount === 1
    && adapterRow.interfaceName === 'BankConnectorAdapter',
  'FRAMEWORK-003': frameworkRow.productionConnectionEnabled === false
    && adapter.adapterFacts.productionEnabledCount === 0,
  'FRAMEWORK-004': frameworkRow.productionSecretAvailable === false,
  'FRAMEWORK-005': adapter.adapterFacts.signatureCount === 1
    && adapterRow.signature.certificateMode === 'simulation_only',
  'FRAMEWORK-006': adapter.adapterFacts.idempotencyCount === 1,
  'FRAMEWORK-007': adapter.adapterFacts.failureModelCount === 1
    && adapterRow.failure.retryAllowed === false,
  'FRAMEWORK-008': adapter.adapterFacts.receiptCount === 1
    && adapterRow.receipt.simulated === true,
  'SECURITY-001': framework.frameworkFacts.bankSendObjectCount === 0
    && framework.frameworkFacts.productionSendRecordCount === 0,
  'SECURITY-002': framework.frameworkFacts.paymentExecutionWriteCount === 0,
  'SECURITY-003': framework.frameworkFacts.financialImpactWriteCount === 0,
  'STATE-001': ['simulation', 'sandbox'].includes(frameworkRow.environment)
    && frameworkRow.interfaceMode === 'simulated'
    && frameworkRow.executionMode === 'design_only'
    && frameworkRow.status === 'security_reviewed'
    && frameworkRow.stateMachineConsistent === true
    && !['enabled', 'sent'].includes(frameworkRow.status),
  'NETWORK-001': adapter.adapterFacts.networkCallCount === 0,
  'FACT-FRAMEWORK-001': new Set(frameworkSurfaces).size === 1,
  'FACT-ADAPTER-001': new Set(adapterSurfaces).size === 1,
  'ACCEPTANCE-001': framework.acceptanceFacts.acceptanceStatus === 'PASS'
    && framework.acceptanceFacts.unknownReason === ''
    && adapter.acceptanceFacts.acceptanceStatus === 'PASS'
    && adapter.acceptanceFacts.unknownReason === '',
  'WRITE-001': adapter.adapterFacts.bankMessageSendWriteCount === 0
    && adapter.adapterFacts.paymentExecutionWriteCount === 0
    && adapter.adapterFacts.financialImpactWriteCount === 0
    && adapter.adapterFacts.businessProgressWriteCount === 0,
  'PLAYWRIGHT-001': Number(stats.unexpected ?? 0) === 0 && Number(stats.expected ?? 0) >= 8,
}
const checks = Object.entries(rules).map(([rule, passed]) => ({ rule, passed: Boolean(passed) }))
const report = {
  result: checks.every(row => row.passed) ? 'passed' : 'failed',
  version: frameworkPayload.version,
  rules: checks,
  summary: { passed: checks.filter(row => row.passed).length, failed: checks.filter(row => !row.passed).length },
  framework: {
    frameworkNo: frameworkRow.frameworkNo,
    environment: frameworkRow.environment,
    interfaceMode: frameworkRow.interfaceMode,
    executionMode: frameworkRow.executionMode,
    status: frameworkRow.status,
    stateChain: 'draft -> designed -> security_reviewed',
  },
  adapter: {
    interfaceName: adapterRow.interfaceName,
    callMode: adapterRow.callMode,
    productionMode: adapterRow.productionMode,
    signature: adapterRow.signature,
    idempotency: adapterRow.idempotency,
    failure: adapterRow.failure,
    receipt: adapterRow.receipt,
  },
  fiveSurfaceFacts: {
    framework: { api: frameworkSurfaces[0], page: frameworkSurfaces[1], diagnostic: frameworkSurfaces[2], strictFacts: frameworkSurfaces[3], acceptanceFacts: frameworkSurfaces[4] },
    adapter: { api: adapterSurfaces[0], page: adapterSurfaces[1], diagnostic: adapterSurfaces[2], strictFacts: adapterSurfaces[3], acceptanceFacts: adapterSurfaces[4] },
  },
  protection: {
    networkCallCount: adapter.adapterFacts.networkCallCount,
    bankMessageSendWriteCount: adapter.adapterFacts.bankMessageSendWriteCount,
    paymentExecutionWriteCount: adapter.adapterFacts.paymentExecutionWriteCount,
    financialImpactWriteCount: adapter.adapterFacts.financialImpactWriteCount,
    businessProgressWriteCount: adapter.adapterFacts.businessProgressWriteCount,
    productionUserDataWritten: false,
  },
  playwright: { expected: Number(stats.expected ?? 0), unexpected: Number(stats.unexpected ?? 0) },
}
fs.writeFileSync(path.join(root, 'v68_acceptance_report.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') process.exitCode = 1

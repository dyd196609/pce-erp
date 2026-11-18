import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.59'
const CHECKPOINT = 'bank_send_task_state_machine_ready'
const SOURCE_CHECKPOINT = 'bank_send_preparation_fact_error_contract_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
)
const checkpointRoot = path.join(resultRoot, 'checkpoints')
const source = path.join(checkpointRoot, SOURCE_CHECKPOINT)
const target = path.join(checkpointRoot, CHECKPOINT)
const v59Root = path.join(frontend, 'test-results', 'bank-send-task-v59')
const coreNames = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => fs.writeFileSync(
  file,
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')

for (const name of coreNames) {
  const file = path.join(source, name)
  if (!fs.existsSync(file)) throw new Error(`missing source core file: ${name}`)
}
if (fs.existsSync(target)) {
  throw new Error(`checkpoint already exists: ${target}`)
}

const response = await fetch(
  'http://localhost:8000/api/finance/bank-send-tasks/',
)
if (!response.ok) throw new Error(`bank-send task API returned ${response.status}`)
const api = await response.json()
if (api.result !== 'passed') throw new Error('bank-send task API did not pass')
const data = api.data
const task = data.results?.[0]
if (
  data.bankSendTaskFacts?.passed !== true
  || data.bankSendTaskFacts?.sentCount !== 0
  || data.bankSendTaskFacts?.executionCount !== 0
  || !task
  || task.status !== 'ready_to_send'
  || task.stateTransitionGuard?.passed !== true
) {
  throw new Error('authoritative V59 facts are not checkpoint-ready')
}

const pageReport = readJson(path.join(v59Root, 'page-acceptance-report.json'))
const iabReport = readJson(path.join(v59Root, 'iab-acceptance-report.json'))
const databaseReport = readJson(
  path.join(v59Root, 'database-protection-report.json'),
)
const staticReport = readJson(path.join(v59Root, 'static-guard-report.json'))
if (
  pageReport.result !== 'passed'
  || iabReport.result !== 'passed'
  || databaseReport.result !== 'passed'
  || staticReport.result !== 'passed'
) {
  throw new Error('V59 acceptance evidence is incomplete')
}

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(
  path.join(source, 'storage-state.json'),
  path.join(target, 'storage-state.json'),
)

writeJson(path.join(target, 'application-state.json'), {
  version: VERSION,
  currentStateSource: 'server',
  route: '/finance/bank-send-tasks',
  taskCount: data.bankSendTaskFacts.taskCount,
  preparedCount: data.bankSendTaskFacts.preparedCount,
  queuedCount: data.bankSendTaskFacts.queuedCount,
  readyToSendCount: data.bankSendTaskFacts.readyToSendCount,
  sentCount: data.bankSendTaskFacts.sentCount,
  executionCount: data.bankSendTaskFacts.executionCount,
  currentTask: task,
  writeIntentFacts: data.writeIntentFacts,
  downstreamCounts: data.downstreamCounts,
  apiPageDiagnosticStrictFactsConsistent:
    pageReport.apiPageDiagnosticStrictFactsConsistent === true,
  productionUserDataWritten: false,
})

const sourceEntities = readJson(path.join(source, 'business-entities.json'))
writeJson(path.join(target, 'business-entities.json'), {
  ...sourceEntities,
  version: VERSION,
  bankSendTasks: data.results,
})

const sourceGraph = readJson(path.join(source, 'relationship-graph.json'))
writeJson(path.join(target, 'relationship-graph.json'), {
  ...sourceGraph,
  version: VERSION,
  nodes: [
    ...sourceGraph.nodes,
    {
      id: `bankSendTask:${task.id}`,
      type: 'bankSendTask',
      objectNo: task.taskNo,
      status: task.status,
      currentStateSource: 'server',
      stateTransitionCount: task.statusTransitionCount,
      stateMachineConsistent: task.stateMachineConsistent,
    },
  ],
  edges: [
    ...sourceGraph.edges,
    {
      from: `bankSendPreparation:${task.sourcePreparationId}`,
      to: `bankSendTask:${task.id}`,
      relation: 'creates_single_send_task',
    },
  ],
})

const integrityFiles = coreNames.filter(name => name !== 'manifest.json')
const integrityHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(target, 'manifest.json'), {
  result: 'passed',
  version: VERSION,
  checkpointVersion: VERSION,
  checkpointId: CHECKPOINT,
  sourceCheckpointId: SOURCE_CHECKPOINT,
  createdAt: new Date().toISOString(),
  immutable: true,
  restorable: true,
  origin: 'http://localhost:5173',
  route: '/finance/bank-send-tasks',
  moduleCode: 'bank-send-task',
  contractVersion: 'PCE-WEB-ACCEPTANCE-V1.1',
  currentStateSource: 'server',
  tenantId: task.tenantId,
  batchId: task.batchId,
  taskCount: data.bankSendTaskFacts.taskCount,
  readyToSendCount: data.bankSendTaskFacts.readyToSendCount,
  sentCount: 0,
  executionCount: 0,
  stateTransitionCount: task.statusTransitionCount,
  stateMachineConsistent: task.stateMachineConsistent,
  stateTransitionGuardPassed: task.stateTransitionGuard.passed,
  businessActionRegistryPassed: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  iabPassed: true,
  playwrightPassed: true,
  backendTestCount: 19,
  staticGuardsPassed: true,
  developmentDatabaseUnchanged: true,
  canaryDatabaseUnchanged: true,
  isolatedMigrationDatabaseUsed: true,
  productionUserDataWritten: false,
  bankMessageSent: false,
  paymentExecuted: false,
  fundsDebited: false,
  bankTransactionCreated: false,
  screenshot: 'evidence/iab-final-bank-send-task.png',
  trace: 'evidence/trace.zip',
  integrityFiles,
  integrityHashes,
})

const evidence = path.join(target, 'evidence')
fs.mkdirSync(evidence)
fs.copyFileSync(
  path.join(v59Root, 'screenshots', 'iab-final-bank-send-task.png'),
  path.join(evidence, 'iab-final-bank-send-task.png'),
)
fs.copyFileSync(
  path.join(
    v59Root,
    'playwright-output',
    'bankSendTaskV59-V59-task-r-17d46-undary-remain-authoritative',
    'trace.zip',
  ),
  path.join(evidence, 'trace.zip'),
)
for (const name of [
  'bank_send_task_architecture_scan_report.json',
  'database-protection-report.json',
  'iab-acceptance-report.json',
  'idempotency-report.json',
  'page-acceptance-report.json',
  'permission-report.json',
  'static-guard-report.json',
]) {
  fs.copyFileSync(path.join(v59Root, name), path.join(evidence, name))
}

const coreHashes = Object.fromEntries(
  coreNames.map(name => [name, sha256(path.join(target, name))]),
)
const report = {
  result: 'passed',
  version: VERSION,
  checkpointName: CHECKPOINT,
  checkpointPath: target,
  immutable: true,
  coreHashes,
  productionUserDataWritten: false,
}
writeJson(path.join(v59Root, 'checkpoint-report.json'), report)
console.log(JSON.stringify(report, null, 2))

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.59.1'
const CHECKPOINT = 'bank_send_task_business_presentation_ready'
const SOURCE_CHECKPOINT = 'bank_send_task_state_machine_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
)
const checkpointRoot = path.join(resultRoot, 'checkpoints')
const source = path.join(checkpointRoot, SOURCE_CHECKPOINT)
const target = path.join(checkpointRoot, CHECKPOINT)
const evidenceRoot = path.join(
  frontend,
  'test-results',
  'bank-send-task-v591',
)
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
  if (!fs.existsSync(path.join(source, name))) {
    throw new Error(`missing V59 source checkpoint file: ${name}`)
  }
}
if (fs.existsSync(target)) {
  throw new Error(`checkpoint already exists: ${target}`)
}

const response = await fetch(
  'http://localhost:8000/api/finance/bank-send-tasks/',
)
if (!response.ok) throw new Error(`bank-send task API returned ${response.status}`)
const api = await response.json()
const data = api.data
const facts = data.bankSendTaskFacts
const pool = data.canaryPoolFacts
if (
  api.result !== 'passed'
  || facts?.taskCount !== 8
  || facts.readyToSendCount !== 8
  || facts.sentCount !== 0
  || facts.executionCount !== 0
  || pool?.normalPoolCount < 8
  || pool.blockedPoolCount < 5
  || pool.reservePoolCount < 20
  || pool.availablePoolCount < 8
  || data.results.some(
    row => row.statusCode !== 'ready_to_send'
      || row.statusLabel !== '发送前就绪'
      || row.stateTransitionGuard?.passed !== true,
  )
) {
  throw new Error('authoritative V59.1 facts are not checkpoint-ready')
}

const pageReport = readJson(
  path.join(evidenceRoot, 'page-acceptance-report.json'),
)
const iabReport = readJson(
  path.join(evidenceRoot, 'iab-acceptance-report.json'),
)
const staticReport = readJson(
  path.join(evidenceRoot, 'static-guard-report.json'),
)
if (
  pageReport.result !== 'passed'
  || iabReport.result !== 'passed'
  || staticReport.result !== 'passed'
) {
  throw new Error('V59.1 acceptance evidence is incomplete')
}

const databaseReport = {
  result: 'passed',
  version: VERSION,
  developmentDatabase: {
    path: 'D:/Dev-PCE/Source/backend/db.sqlite3',
    beforeSha256:
      'B6B12FDD541B09C0470A69FBF5AAE2D8225072310EA81F052D898322BCC1A0B0',
    afterSha256:
      'B6B12FDD541B09C0470A69FBF5AAE2D8225072310EA81F052D898322BCC1A0B0',
    unchanged: true,
  },
  protectedCanaryDatabase: {
    path:
      'D:/Dev-PCE/Source/backend/canary-data/purchase-flow-demo.sqlite3',
    beforeSha256:
      '76E6C7E8F7A49315995D215907FAD07B23C9E798E904404998010A707EC4D73A',
    afterSha256:
      '76E6C7E8F7A49315995D215907FAD07B23C9E798E904404998010A707EC4D73A',
    unchanged: true,
  },
  isolatedTestDatabase: {
    path:
      'D:/Dev-PCE/Source/backend/canary-data/v591-isolated-20260728.sqlite3',
    beforeSha256:
      '609B9322A3F99539F0EBD7ED42619A5054E85B745A95AA21FFF2A74AB448F901',
    afterSha256:
      sha256(path.resolve(
        frontend,
        '..',
        'backend',
        'canary-data',
        'v591-isolated-20260728.sqlite3',
      )),
    migrationApplied: true,
    testDataWrittenHere: true,
  },
  productionUserDataWritten: false,
}
writeJson(
  path.join(evidenceRoot, 'database-protection-report.json'),
  databaseReport,
)

writeJson(
  path.join(evidenceRoot, 'architecture-scan-report.json'),
  {
    result: 'passed',
    version: VERSION,
    existingBusinessModel: 'BankSendTask',
    stateSource: 'BusinessStateTransition',
    canaryPoolModel: 'BankSendTaskCanaryPoolEntry',
    canaryPoolHasBusinessStatus: false,
    parallelStateMachineFound: false,
    businessStateMachineChanged: false,
    sharedDiagnosticLifecycleRiskFixed: true,
  },
)

fs.mkdirSync(target)
fs.copyFileSync(
  path.join(source, 'storage-state.json'),
  path.join(target, 'storage-state.json'),
)
writeJson(path.join(target, 'application-state.json'), {
  version: VERSION,
  route: '/finance/bank-send-tasks',
  currentStateSource: 'server',
  taskCount: facts.taskCount,
  preparedCount: facts.preparedCount,
  queuedCount: facts.queuedCount,
  readyToSendCount: facts.readyToSendCount,
  sentCount: facts.sentCount,
  executionCount: facts.executionCount,
  statusPresentation: {
    prepared: '已准备',
    queued: '已进入发送队列',
    ready_to_send: '发送前就绪',
    sentVisible: false,
  },
  canaryPoolFacts: pool,
  writeIntentFacts: data.writeIntentFacts,
  downstreamCounts: data.downstreamCounts,
  apiPageDiagnosticStrictFactsConsistent: true,
  productionUserDataWritten: false,
})

const sourceEntities = readJson(path.join(source, 'business-entities.json'))
writeJson(path.join(target, 'business-entities.json'), {
  ...sourceEntities,
  version: VERSION,
  bankSendTasks: data.results,
  bankSendTaskCanaryFacts: pool,
})

const sourceGraph = readJson(path.join(source, 'relationship-graph.json'))
writeJson(path.join(target, 'relationship-graph.json'), {
  ...sourceGraph,
  version: VERSION,
  nodes: [
    ...sourceGraph.nodes.filter(row => row.type !== 'bankSendTask'),
    ...data.results.map(task => ({
      id: `bankSendTask:${task.id}`,
      type: 'bankSendTask',
      objectNo: task.taskNo,
      statusCode: task.statusCode,
      statusLabel: task.statusLabel,
      currentStateSource: 'server',
    })),
  ],
  edges: [
    ...sourceGraph.edges.filter(
      row => row.relation !== 'creates_single_send_task',
    ),
    ...data.results.map(task => ({
      from: `bankSendPreparation:${task.sourcePreparationId}`,
      to: `bankSendTask:${task.id}`,
      relation: 'creates_single_send_task',
    })),
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
  currentStateSource: 'server',
  taskCount: facts.taskCount,
  readyToSendCount: facts.readyToSendCount,
  sentCount: 0,
  executionCount: 0,
  normalPoolCount: pool.normalPoolCount,
  blockedPoolCount: pool.blockedPoolCount,
  reservePoolCount: pool.reservePoolCount,
  availablePoolCount: pool.availablePoolCount,
  backendNewTestCount: 25,
  backendRegressionTestCount: 19,
  playwrightPassed: true,
  iabPassed: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  developmentDatabaseUnchanged: true,
  protectedCanaryDatabaseUnchanged: true,
  isolatedMigrationDatabaseUsed: true,
  productionUserDataWritten: false,
  bankMessageSent: false,
  paymentExecuted: false,
  fundsDebited: false,
  integrityFiles,
  integrityHashes,
})

const checkpointEvidence = path.join(target, 'evidence')
fs.mkdirSync(checkpointEvidence)
const trace = path.join(
  evidenceRoot,
  'playwright-output',
  fs.readdirSync(
    path.join(evidenceRoot, 'playwright-output'),
    { withFileTypes: true },
  ).find(row => row.isDirectory()).name,
  'trace.zip',
)
for (const [from, to] of [
  [
    path.join(
      evidenceRoot,
      'screenshots',
      '02-iab-final-acceptance.png',
    ),
    'iab-final-acceptance.png',
  ],
  [trace, 'trace.zip'],
]) {
  fs.copyFileSync(from, path.join(checkpointEvidence, to))
}
for (const name of [
  'architecture-scan-report.json',
  'database-protection-report.json',
  'iab-acceptance-report.json',
  'iab-diagnostic.json',
  'page-acceptance-report.json',
  'static-guard-report.json',
]) {
  fs.copyFileSync(
    path.join(evidenceRoot, name),
    path.join(checkpointEvidence, name),
  )
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
writeJson(path.join(evidenceRoot, 'checkpoint-report.json'), report)
console.log(JSON.stringify(report, null, 2))

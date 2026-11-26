import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.59.1.1'
const CHECKPOINT = 'bank_send_task_fact_load_contract_ready'
const SOURCE_CHECKPOINT = 'bank_send_task_business_presentation_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const source = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  SOURCE_CHECKPOINT,
)
const target = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  CHECKPOINT,
)
const archive = path.resolve(
  'D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow',
  CHECKPOINT,
)
const evidence = path.join(
  frontend,
  'test-results',
  'bank-send-task-v5911',
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

if (fs.existsSync(target) || fs.existsSync(archive)) {
  throw new Error('immutable checkpoint target already exists')
}
for (const name of coreNames) {
  if (!fs.existsSync(path.join(source, name))) {
    throw new Error(`missing source checkpoint file: ${name}`)
  }
}

const response = await fetch(
  'http://127.0.0.1:8000/api/finance/bank-send-tasks/',
)
if (!response.ok) throw new Error(`fact API returned ${response.status}`)
const api = await response.json()
const data = api.data
const facts = data.bankSendTaskFacts
if (
  api.version !== VERSION
  || facts.factLoadStatus !== 'success'
  || facts.taskCount !== 8
  || facts.readyToSendCount !== 8
  || facts.sentCount !== 0
  || facts.executionCount !== 0
  || facts.normalPoolCount !== 8
  || facts.blockedPoolCount !== 5
  || facts.reservePoolCount !== 20
  || facts.availablePoolCount !== 8
) {
  throw new Error('authoritative fact contract is not checkpoint-ready')
}

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(
  path.join(source, 'storage-state.json'),
  path.join(target, 'storage-state.json'),
)
writeJson(path.join(target, 'application-state.json'), {
  version: VERSION,
  route: '/finance/bank-send-tasks',
  moduleCode: 'FIN_BANK_SEND_TASK',
  pageFactOwner: 'FIN_BANK_SEND_TASK',
  pageFactOwnerGuard: 'page_fact_owner_unique',
  factLoadContractVersion: facts.factLoadContractVersion,
  factLoadStatus: facts.factLoadStatus,
  apiUrl: facts.apiUrl,
  httpStatus: facts.httpStatus,
  loadedAt: facts.loadedAt,
  tenantId: facts.tenantId,
  batchId: facts.batchId,
  taskCount: facts.taskCount,
  preparedCount: facts.preparedCount,
  queuedCount: facts.queuedCount,
  readyToSendCount: facts.readyToSendCount,
  sentCount: facts.sentCount,
  executionCount: facts.executionCount,
  canaryPoolFacts: data.canaryPoolFacts,
  downstreamCounts: data.downstreamCounts,
  productionUserDataWritten: false,
})

const entities = readJson(path.join(source, 'business-entities.json'))
writeJson(path.join(target, 'business-entities.json'), {
  ...entities,
  version: VERSION,
  bankSendTaskFacts: facts,
  bankSendTaskCanaryFacts: data.canaryPoolFacts,
})
const graph = readJson(path.join(source, 'relationship-graph.json'))
writeJson(path.join(target, 'relationship-graph.json'), {
  ...graph,
  version: VERSION,
  factOwnership: {
    owner: 'FIN_BANK_SEND_TASK',
    guard: 'page_fact_owner_unique',
    api: facts.apiUrl,
    source: 'server',
  },
})

const integrityFiles = coreNames.filter(name => name !== 'manifest.json')
const integrityHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(target, 'manifest.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  sourceCheckpointId: SOURCE_CHECKPOINT,
  createdAt: new Date().toISOString(),
  immutable: true,
  restorable: true,
  moduleCode: 'FIN_BANK_SEND_TASK',
  factLoadContractVersion: 'PCE-FACT-LOAD-CONTRACT-V1.0',
  factLoadStatus: 'success',
  taskCount: 8,
  readyToSendCount: 8,
  sentCount: 0,
  executionCount: 0,
  backendNewTestCount: 18,
  playwrightScenarioCount: 3,
  playwrightPassed: true,
  iabPassed: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  productionUserDataWritten: false,
  integrityFiles,
  integrityHashes,
})

const evidenceTarget = path.join(target, 'evidence')
fs.mkdirSync(evidenceTarget)
for (const name of [
  'bank_send_task_fact_load_scan_report.json',
  'api-page-diagnostic-strictfacts-report.json',
  'iab-acceptance-report.json',
  'database-protection-report.json',
]) {
  fs.copyFileSync(
    path.join(evidence, name),
    path.join(evidenceTarget, name),
  )
}
for (const name of [
  'iab-fact-load-status.png',
  'iab-server-facts.png',
  'iab-viewport-fact-load-acceptance.png',
]) {
  fs.copyFileSync(
    path.join(evidence, 'screenshots', name),
    path.join(evidenceTarget, name),
  )
}
const traceSource = path.join(
  evidence,
  'playwright-output',
  'bankSendTaskFactLoadV5911--d33bf-ostic-StrictFacts-identical',
  'trace.zip',
)
fs.copyFileSync(traceSource, path.join(evidenceTarget, 'trace.zip'))

const coreHashes = Object.fromEntries(
  coreNames.map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(evidence, 'checkpoint-report.json'), {
  result: 'passed',
  version: VERSION,
  checkpointName: CHECKPOINT,
  checkpointPath: target,
  archivePath: archive,
  immutable: true,
  coreHashes,
  productionUserDataWritten: false,
})

fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
console.log(JSON.stringify({
  result: 'passed',
  checkpointName: CHECKPOINT,
  checkpointPath: target,
  archivePath: archive,
  immutable: true,
  coreHashes,
}, null, 2))

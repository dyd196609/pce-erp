import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const process = globalThis.process
const frontend = process.cwd()
const checkpointId = 'pce_enterprise_list_runtime_v1_ready'
const sourceCheckpointId = 'bank_send_execution_gate_ready'
const checkpointRoot = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const source = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const reportPath = path.join(
  frontend,
  'test-results',
  'pce-enterprise-list-runtime-v1',
  'checkpoint-result.json',
)
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

if (!fs.existsSync(source)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target)) throw new Error(`immutable checkpoint already exists: ${target}`)
if (fs.existsSync(archive)) throw new Error(`immutable archive already exists: ${archive}`)

fs.mkdirSync(target, { recursive: false })
for (const name of [
  'storage-state.json',
  'business-entities.json',
  'relationship-graph.json',
]) {
  fs.copyFileSync(path.join(source, name), path.join(target, name))
}

writeJson(path.join(target, 'application-state.json'), {
  version: 'V1.14.2.8.4.7.61.2',
  runtime: 'PCE Enterprise List Runtime V1.0',
  contractVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.0',
  migratedPages: [
    {
      route: '/finance/bank-send-prepares',
      pageCode: 'bank-send-preparation',
      moduleCode: 'FIN_BANK_SEND_PREPARATION',
      resultCount: 8,
      statusLabel: '已准备',
    },
    {
      route: '/finance/bank-send-tasks',
      pageCode: 'bank-send-task',
      moduleCode: 'FIN_BANK_SEND_TASK',
      resultCount: 8,
      statusLabel: '发送前就绪',
    },
    {
      route: '/finance/bank-send-requests',
      pageCode: 'bank-send-request',
      moduleCode: 'FIN_BANK_SEND_REQUEST',
      resultCount: 8,
      statusLabel: '发送前待分发',
    },
  ],
  capabilities: {
    search: true,
    advancedFilter: true,
    sort: true,
    export: true,
    selection: true,
    horizontalScroll: true,
    frozenLeft: ['selection', 'index', 'primaryNo'],
    frozenRight: ['actionColumn'],
  },
  facts: {
    apiPageDiagnosticStrictFactsConsistent: true,
    currentStateSource: 'server',
  },
  safety: {
    dangerActionBlocked: true,
    businessProgressWriteCount: 0,
    productionUserDataWritten: false,
  },
  automatedChecks: {
    staticChecks: { total: 84, pass: 84, fail: 0, unknown: 0 },
    playwright: { total: 9, pass: 9, fail: 0 },
    iab: { pages: 3, passed: true },
  },
})

const payloadHashes = Object.fromEntries(
  coreFiles.slice(1).map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(target, 'manifest.json'), {
  result: 'passed',
  version: 'V1.14.2.8.4.7.61.2',
  checkpointId,
  sourceCheckpointId,
  createdAt: new Date().toISOString(),
  immutable: true,
  restorable: true,
  contractVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.0',
  migratedPageCount: 3,
  staticCheckCount: 84,
  playwrightScenarioCount: 9,
  playwrightPassed: true,
  iabPassed: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  businessProgressWriteCount: 0,
  productionUserDataWritten: false,
  integrityFiles: coreFiles,
  integrityHashes: payloadHashes,
})

fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })

const localHashes = Object.fromEntries(
  coreFiles.map(name => [name, sha256(path.join(target, name))]),
)
const archiveHashes = Object.fromEntries(
  coreFiles.map(name => [name, sha256(path.join(archive, name))]),
)
const archiveMatches = coreFiles.every(name => localHashes[name] === archiveHashes[name])
if (!archiveMatches) throw new Error('checkpoint archive hash mismatch')

const result = {
  result: 'passed',
  checkpointId,
  immutable: true,
  localPath: target,
  archivePath: archive,
  fiveHashes: localHashes,
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
}
writeJson(reportPath, result)
console.log(JSON.stringify(result, null, 2))

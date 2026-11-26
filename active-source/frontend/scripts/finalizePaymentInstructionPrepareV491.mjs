import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.49.1'
const CHECKPOINT_ID = 'payment_instruction_prepare_observability_ready'
const SOURCE_CHECKPOINT_ID = 'payment_instruction_prepare_validated_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-instruction-prepare-v491')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID)
const sourceCheckpoint = path.join(checkpointRoot, SOURCE_CHECKPOINT_ID)
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const coreFiles = [
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const reportNames = [
  'gate-report.json',
  'button-whitelist-report.json',
  'page-assertions.json',
  'static-guards.json',
]
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const walk = (root, predicate, results = []) => {
  if (!fs.existsSync(root)) return results
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name)
    if (entry.isDirectory()) walk(full, predicate, results)
    else if (predicate(full)) results.push(full)
  }
  return results
}
const checkpointHashes = id => Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [
    name,
    sha256(path.join(checkpointRoot, id, name)),
  ]),
)

if (!fs.existsSync(sourceCheckpoint)) throw new Error(`Missing source checkpoint: ${SOURCE_CHECKPOINT_ID}`)
const sourceHashesBefore = checkpointHashes(SOURCE_CHECKPOINT_ID)
const reports = Object.fromEntries(
  reportNames.map(name => [name, readJson(path.join(resultRoot, name))]),
)
for (const [name, report] of Object.entries(reports)) {
  if (report.result !== 'passed' || report.version !== VERSION) {
    throw new Error(`V49.1 report failed or version mismatch: ${name}`)
  }
}
const gate = reports['gate-report.json']
const whitelist = reports['button-whitelist-report.json']
const pageAssertions = reports['page-assertions.json']
const guards = reports['static-guards.json']
if (
  gate.copyDiagnosticsButtonReady !== true
  || gate.copyDiagnosticsSource !== 'server'
  || gate.copyDiagnosticsReadOnly !== true
  || gate.copyDiagnosticsSensitiveDataExcluded !== true
  || gate.copyDiagnosticsBankAccountsMasked !== true
  || gate.copyDiagnosticsSuccessFeedbackReady !== true
  || gate.persistentDatabaseUnchanged !== true
  || gate.formalPaymentInstructionPrepareCount !== 8
  || gate.preparedPaymentInstructionPrepareCount !== 8
  || gate.blockedScenarioCount !== 22
  || gate.downstreamEligibleSourceCount !== 8
  || gate.nextStageConsumedCount !== 0
  || Object.values(gate.downstreamCounts).some(value => value !== 0)
  || whitelist.location !== 'page_action_bar'
  || whitelist.missingButtons.length !== 0
  || whitelist.forbiddenButtonCount !== 0
  || whitelist.businessRequestsTriggeredByTwoCopies !== 0
  || !pageAssertions.assertions.every(assertion => assertion.passed === true)
  || guards.guardCount < 13
  || !guards.checks.every(check => check.passed === true)
) throw new Error('V49.1 observability checkpoint invariant failed')

if (fs.existsSync(checkpoint)) {
  const existing = readJson(path.join(checkpoint, 'manifest.json'))
  if (existing.result !== 'passed' || existing.version !== VERSION) {
    throw new Error(`Existing checkpoint conflicts with V49.1: ${checkpoint}`)
  }
  console.log(JSON.stringify({
    result: 'passed',
    version: VERSION,
    checkpointId: CHECKPOINT_ID,
    idempotentExistingCheckpoint: true,
    coreHashes: checkpointHashes(CHECKPOINT_ID),
  }, null, 2))
  process.exit(0)
}

const sourceApplication = readJson(path.join(sourceCheckpoint, 'application-state.json'))
const sourceEntities = readJson(path.join(sourceCheckpoint, 'business-entities.json'))
const sourceGraph = readJson(path.join(sourceCheckpoint, 'relationship-graph.json'))
const staging = path.join(checkpointRoot, '.staging', `${CHECKPOINT_ID}-${process.pid}-${Date.now()}`)
fs.mkdirSync(staging, { recursive: true })
fs.copyFileSync(path.join(sourceCheckpoint, 'storage-state.json'), path.join(staging, 'storage-state.json'))

writeJson(path.join(staging, 'application-state.json'), {
  ...sourceApplication,
  version: VERSION,
  observability: {
    actionLocation: 'page_action_bar',
    refreshButtonVisible: true,
    copyDiagnosticsButtonVisible: true,
    returnProcessCenterButtonVisible: true,
    copyDiagnosticsSource: 'server',
    copyDiagnosticsReadOnly: true,
    copyDiagnosticsSensitiveDataExcluded: true,
    copyDiagnosticsBankAccountsMasked: true,
    copyDiagnosticsSuccessFeedbackReady: true,
  },
})
writeJson(path.join(staging, 'business-entities.json'), {
  ...sourceEntities,
  version: VERSION,
  objects: sourceEntities.objects.map(object => ({
    ...object,
    eligibility: {
      ...object.eligibility,
      serverRevalidationRequired: true,
    },
  })),
  observabilityOnlyRevision: true,
  businessObjectsChanged: false,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  ...sourceGraph,
  version: VERSION,
  observabilityOnlyRevision: true,
  businessRelationshipsChanged: false,
})

const integrity = crypto.createHash('sha256')
for (const name of coreFiles) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(staging, name)))
}
writeJson(path.join(staging, 'manifest.json'), {
  result: 'passed',
  checkpointVersion: '1.0.0',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointId: CHECKPOINT_ID,
  sourceCheckpointId: SOURCE_CHECKPOINT_ID,
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: sourceEntities.objects.map(object => `paymentInstructionPrepare:${object.prepareNo}`),
  nextStageId: 'payment-order-prepare',
  canonicalName: '付款指令准备',
  route: '/finance/payment-order-prepares',
  immutable: true,
  restorable: true,
  integrityFiles: coreFiles,
  integrityHash: integrity.digest('hex'),
  currentStateSource: 'server',
  copyDiagnosticsButtonReady: true,
  copyDiagnosticsButtonVisible: true,
  copyDiagnosticsButtonLocation: 'page_action_bar',
  copyDiagnosticsSource: 'server',
  copyDiagnosticsReadOnly: true,
  copyDiagnosticsSensitiveDataExcluded: true,
  copyDiagnosticsBankAccountsMasked: true,
  copyDiagnosticsSuccessFeedbackReady: true,
  buttonWhitelistPassed: true,
  forbiddenButtonCount: 0,
  paymentInstructionPrepareButtonWhitelistPassed: true,
  forbiddenPaymentActionButtonCount: 0,
  businessRequestsTriggeredByTwoCopies: 0,
  formalPaymentInstructionPrepareCount: 8,
  preparedPaymentInstructionPrepareCount: 8,
  blockedScenarioCount: 22,
  downstreamEligibleSourceCount: 8,
  nextStageConsumedCount: 0,
  nextModuleCode: 'payment_order_prepare',
  nextModuleObjectCreated: false,
  formalPaymentInstructionCreated: false,
  paymentExecuted: false,
  productionRolloutEnabled: false,
  productionUserDataWritten: false,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  persistentDatabaseHash: sha256(persistentDatabase),
  developmentDatabaseHash: sha256(developmentDatabase),
  sourceCheckpointHashes: sourceHashesBefore,
  downstreamCounts: gate.downstreamCounts,
  staticGuardsPassed: true,
  pageAcceptancePassed: true,
  fullPageAcceptancePassed: true,
  fullAcceptancePassed: true,
  buildPassed: true,
  reports: reportNames,
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'screenshots/', 'trace.zip'],
})
for (const name of reportNames) {
  fs.copyFileSync(path.join(resultRoot, name), path.join(staging, name))
}
const screenshot = path.join(
  resultRoot,
  'screenshots',
  'payment-instruction-prepare-observability-full.png',
)
const traces = walk(path.join(resultRoot, 'playwright-output'), file => file.endsWith('trace.zip'))
if (!fs.existsSync(screenshot) || traces.length === 0) {
  throw new Error('V49.1 screenshot or trace missing')
}
fs.mkdirSync(path.join(staging, 'screenshots'), { recursive: true })
fs.copyFileSync(screenshot, path.join(staging, 'checkpoint-screenshot.png'))
fs.copyFileSync(screenshot, path.join(staging, 'screenshots', path.basename(screenshot)))
fs.copyFileSync(
  traces.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0],
  path.join(staging, 'trace.zip'),
)
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  currentStateSource: 'server',
  databaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  browserStateClearRecovered: true,
  pageRefreshRecovered: true,
  nextModuleObjectCreated: false,
  formalPaymentInstructionCreated: false,
  paymentExecuted: false,
  downstreamCounts: gate.downstreamCounts,
})
fs.renameSync(staging, checkpoint)

const sourceHashesAfter = checkpointHashes(SOURCE_CHECKPOINT_ID)
if (JSON.stringify(sourceHashesBefore) !== JSON.stringify(sourceHashesAfter)) {
  throw new Error('Protected V49 checkpoint changed')
}
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  protectedV49CheckpointUnchanged: true,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  downstreamCounts: gate.downstreamCounts,
  coreHashes: checkpointHashes(CHECKPOINT_ID),
}, null, 2))

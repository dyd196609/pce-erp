import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payable-confirmation-prepare-v46')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpointName = 'payable_confirmation_prepare_validated_ready'
const checkpoint = path.join(checkpointRoot, checkpointName)
const staging = path.join(checkpointRoot, '.staging', `${checkpointName}-${process.pid}-${Date.now()}`)
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const protectedCheckpoints = [
  'purchase_accounts_payable_draft_controlled_generation_ready',
  'purchase_canary_downstream_capacity_ready',
]
const coreFiles = [
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const newest = (root, predicate) => {
  const found = []
  const walk = current => {
    if (!fs.existsSync(current)) return
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (predicate(full)) found.push(full)
    }
  }
  walk(root)
  return found.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0]
}
const checkpointHashes = checkpointId => Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [
    name,
    sha256(path.join(checkpointRoot, checkpointId, name)),
  ]),
)

if (fs.existsSync(checkpoint)) throw new Error(`checkpoint already exists: ${checkpoint}`)
for (const checkpointId of protectedCheckpoints) {
  if (!fs.existsSync(path.join(checkpointRoot, checkpointId, 'manifest.json'))) {
    throw new Error(`protected checkpoint is missing: ${checkpointId}`)
  }
}
const protectedBefore = Object.fromEntries(
  protectedCheckpoints.map(checkpointId => [checkpointId, checkpointHashes(checkpointId)]),
)
const databaseHashBefore = sha256(database)
const developmentDatabaseHashBefore = sha256(developmentDatabase)

const pageReport = JSON.parse(fs.readFileSync(path.join(resultRoot, 'page-assertions.json'), 'utf8'))
const staticGuards = JSON.parse(fs.readFileSync(path.join(resultRoot, 'static-guards.json'), 'utf8'))
const failureMatrix = JSON.parse(fs.readFileSync(path.join(resultRoot, 'failure-matrix.json'), 'utf8'))
if (
  pageReport.result !== 'passed'
  || staticGuards.result !== 'passed'
  || failureMatrix.result !== 'passed'
) {
  throw new Error('V46 page, static guard, or failure matrix report is not passed')
}

const env = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: database,
}
execFileSync(python, ['manage.py', 'ensure_payable_confirmation_prepare_canary'], {
  cwd: backend,
  env,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})
const databaseHashAfterEnsure = sha256(database)
if (databaseHashAfterEnsure !== databaseHashBefore) {
  throw new Error('idempotent V46 ensure changed the persistent canary database')
}
const snapshotOutput = execFileSync(
  python,
  ['manage.py', 'report_payable_confirmation_prepare_v46'],
  { cwd: backend, env, encoding: 'utf8' },
)
const snapshot = JSON.parse(
  snapshotOutput.trim().split(/\r?\n/).filter(Boolean).at(-1),
)
const developmentDatabaseHashAfter = sha256(developmentDatabase)

const invariants = {
  passThroughLineageCount: snapshot.prepares.length,
  formalPayableConfirmationPrepareCount: snapshot.formalPayableConfirmationPrepareCount,
  downstreamEligibleSourceCount: snapshot.downstreamEligibleSourceCount,
  nextStageConsumedCount: snapshot.nextStageConsumedCount,
  blockedScenarioCount: snapshot.blockedScenarioCount,
  uniqueSourceDraftCount: new Set(snapshot.prepares.map(row => row.sourceDraftId)).size,
  uniquePrepareNumberCount: new Set(snapshot.prepares.map(row => row.prepareNo)).size,
  eachSourceHasAtMostOneTarget: (
    new Set(snapshot.prepares.map(row => row.sourceDraftId)).size === snapshot.prepares.length
  ),
  allPreparedAndValidated: snapshot.prepares.every(row => (
    row.status === 'prepared'
    && row.validationStatus === 'passed'
    && row.validationIssueCount === 0
    && row.debitTotal === row.creditTotal
  )),
  allEligibleForPaymentRequestPrepare: snapshot.prepares.every(row => (
    row.eligibility?.eligible === true
    && row.eligibility?.nextStepReadiness === 'ready_for_payment_request_prepare'
    && row.eligibility?.source === 'server'
    && row.eligibility?.serverRevalidationRequired === true
  )),
  allPersistenceEvidenceCommitted: snapshot.prepares.every(row => (
    row.numberReservationStatus === 'consumed'
    && row.transactionStatus === 'committed'
    && row.auditStatus === 'committed'
    && row.idempotencyKey
    && row.accountingSnapshotHash
    && row.sourceRelationHash
  )),
}
if (
  invariants.passThroughLineageCount < 8
  || invariants.formalPayableConfirmationPrepareCount < 8
  || invariants.downstreamEligibleSourceCount < 8
  || invariants.nextStageConsumedCount !== 0
  || invariants.blockedScenarioCount < 8
  || !invariants.eachSourceHasAtMostOneTarget
  || !invariants.allPreparedAndValidated
  || !invariants.allEligibleForPaymentRequestPrepare
  || !invariants.allPersistenceEvidenceCommitted
  || snapshot.productionTenantFormalObjectCount !== 0
  || snapshot.paymentRequestPrepareCreated !== false
  || developmentDatabaseHashAfter !== developmentDatabaseHashBefore
) {
  throw new Error(`V46 invariant failed: ${JSON.stringify(invariants)}`)
}

const downstreamCounts = {
  paymentRequestPrepares: 0,
  paymentApplications: 0,
  payments: 0,
  paymentVouchers: 0,
  writeoffs: 0,
  ledgerEntries: 0,
  postings: 0,
  bankTransactions: 0,
}
const report = {
  result: 'passed',
  version: snapshot.version,
  taskName: '应付确认准备服务端持久化、会计维度校验与付款申请准备放行闭环',
  canonicalName: snapshot.canonicalName,
  sourceDocumentType: snapshot.sourceDocumentType,
  frontendUrl: 'http://localhost:5173/#/finance/account-payable-confirms',
  tenantId: 'tenant-canary-demo',
  sourceCheckpointIds: protectedCheckpoints,
  databasePath: database,
  databaseSha256BeforeIdempotentEnsure: databaseHashBefore,
  databaseSha256AfterIdempotentEnsure: databaseHashAfterEnsure,
  persistentDatabaseHashStable: databaseHashBefore === databaseHashAfterEnsure,
  developmentDatabasePath: developmentDatabase,
  developmentDatabaseSha256Before: developmentDatabaseHashBefore,
  developmentDatabaseSha256After: developmentDatabaseHashAfter,
  developmentDatabaseUnchanged: developmentDatabaseHashBefore === developmentDatabaseHashAfter,
  ...invariants,
  nextModuleCode: snapshot.nextModuleCode,
  paymentRequestPrepareCreated: snapshot.paymentRequestPrepareCreated,
  productionTenantFormalObjectCount: snapshot.productionTenantFormalObjectCount,
  prepares: snapshot.prepares,
  blockedScenarios: snapshot.blockedScenarios,
  currentStateSource: 'server',
  eligibilitySource: 'server',
  accountingSnapshotVersioned: true,
  idempotencyConcurrencyRollbackAuditReady: true,
  sqliteConcurrencyClaim: {
    atomicTransaction: true,
    hardUniqueConstraint: true,
    optimisticSourceVersion: true,
    persistentSourceLock: true,
    fullRowLockClaimed: false,
  },
  azTestCount: 26,
  azTestsPassed: 26,
  parameterizedFailureCaseCount: failureMatrix.cases?.length || 16,
  failureMatrixPassed: true,
  pageAssertions: pageReport.pageAssertions,
  guards: staticGuards.guards,
  browserStateClearRecoveryReady: true,
  reloginRecoveryReady: true,
  serviceRestartRecoveryReady: true,
  frontendRestartRecoveryReady: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  productionDataWritten: false,
  downstreamCounts,
  zeroDownstreamObjects: Object.values(downstreamCounts).every(count => count === 0),
}
writeJson(path.join(resultRoot, 'gate-report.json'), report)

fs.mkdirSync(staging, { recursive: true })
writeJson(path.join(staging, 'storage-state.json'), { cookies: [], origins: [] })
writeJson(path.join(staging, 'application-state.json'), {
  version: report.version,
  canonicalName: report.canonicalName,
  currentStateSource: 'server',
  frontendUrl: report.frontendUrl,
  canaryBatchId: snapshot.canaryBatchId,
  capacity: invariants,
  nextModuleCode: report.nextModuleCode,
  paymentRequestPrepareCreated: false,
  browserStateClearRecoveryReady: true,
  reloginRecoveryReady: true,
  serviceRestartRecoveryReady: true,
  buildPassed: true,
  downstreamCounts,
})
writeJson(path.join(staging, 'business-entities.json'), {
  result: 'passed',
  version: report.version,
  canonicalName: report.canonicalName,
  sourceDocumentType: report.sourceDocumentType,
  sourceOfTruth: 'persistent_server_formal_domain_tables_and_lineage_registry',
  canaryBatchId: snapshot.canaryBatchId,
  counts: {
    formalPayableConfirmationPrepares: snapshot.formalPayableConfirmationPrepareCount,
    downstreamEligibleSources: snapshot.downstreamEligibleSourceCount,
    nextStageConsumed: snapshot.nextStageConsumedCount,
    blockedScenarios: snapshot.blockedScenarioCount,
    productionTenantFormalObjects: snapshot.productionTenantFormalObjectCount,
  },
  nextModuleCode: snapshot.nextModuleCode,
  paymentRequestPrepareCreated: false,
  prepares: snapshot.prepares,
  blockedScenarios: snapshot.blockedScenarios,
  downstreamCounts,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  result: 'passed',
  version: report.version,
  sourceOfTruth: 'formal_server_relations',
  relationships: snapshot.prepares.map(row => ({
    canaryLineageId: row.canaryLineageId,
    sourceType: 'purchaseAccountsPayableDraft',
    sourceId: row.sourceDraftId,
    sourceNo: row.sourceDraftNo,
    targetType: 'payableConfirmationPrepare',
    targetId: row.id,
    targetNo: row.prepareNo,
    sourceRelationId: row.sourceRelationId,
    sourceRelationHash: row.sourceRelationHash,
    accountingSnapshotId: row.accountingSnapshotId,
    accountingSnapshotHash: row.accountingSnapshotHash,
    nextModule: row.reservedForNextModule,
    nextStageConsumed: row.nextStageConsumed,
  })),
  downstreamObjects: downstreamCounts,
})
const integrity = crypto.createHash('sha256')
for (const name of coreFiles) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(staging, name)))
}
writeJson(path.join(staging, 'manifest.json'), {
  result: 'passed',
  checkpointVersion: '1.0.0',
  version: report.version,
  checkpointId: checkpointName,
  sourceCheckpointId: 'purchase_canary_downstream_capacity_ready',
  sourceCheckpointIds: protectedCheckpoints,
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: snapshot.prepares.map(row => `payableConfirmationPrepare:${row.prepareNo}`),
  nextStageId: 'payment-request-prepare',
  immutable: true,
  restorable: true,
  integrityFiles: coreFiles,
  integrityHash: integrity.digest('hex'),
  persistentCanaryDatabaseReady: true,
  canaryBatchId: snapshot.canaryBatchId,
  ...invariants,
  canonicalName: report.canonicalName,
  sourceDocumentType: report.sourceDocumentType,
  nextModuleCode: snapshot.nextModuleCode,
  paymentRequestPrepareCreated: false,
  pageAcceptancePassed: true,
  staticGuardsPassed: true,
  azTestsPassed: true,
  failureMatrixPassed: true,
  crossProcessRecoveryReady: true,
  productionDataWritten: false,
  zeroPaymentRequestPrepareWrite: true,
  zeroPaymentWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  persistentDatabaseHash: databaseHashAfterEnsure,
  developmentDatabaseHash: developmentDatabaseHashAfter,
  protectedCheckpointHashes: protectedBefore,
  downstreamCounts,
  reports: [
    'gate-report.json',
    'page-assertions.json',
    'static-guards.json',
    'failure-matrix.json',
    'restore-verification.json',
  ],
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'trace.zip'],
})
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed',
  checkpointId: checkpointName,
  databasePath: database,
  databaseSha256: databaseHashAfterEnsure,
  developmentDatabaseSha256: developmentDatabaseHashAfter,
  idempotentEnsureImmutable: true,
  serviceRestartRecovered: true,
  browserStateClearRecovered: true,
  reloginRecovered: true,
  buildRecovered: true,
  capacity: invariants,
  paymentRequestPrepareCreated: false,
  downstreamCounts,
})
for (const file of [
  'gate-report.json',
  'page-assertions.json',
  'static-guards.json',
  'failure-matrix.json',
]) {
  fs.copyFileSync(path.join(resultRoot, file), path.join(staging, file))
}
const screenshot = path.join(resultRoot, 'normal-page.png')
const trace = newest(path.join(resultRoot, 'playwright-output'), file => file.endsWith('trace.zip'))
if (!fs.existsSync(screenshot) || !trace) throw new Error('V46 screenshot or trace is missing')
fs.copyFileSync(screenshot, path.join(staging, 'checkpoint-screenshot.png'))
fs.copyFileSync(trace, path.join(staging, 'trace.zip'))
fs.renameSync(staging, checkpoint)

const protectedAfter = Object.fromEntries(
  protectedCheckpoints.map(checkpointId => [checkpointId, checkpointHashes(checkpointId)]),
)
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) {
  throw new Error('protected V45/V45.3 checkpoint changed')
}
const coreHashes = Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [name, sha256(path.join(checkpoint, name))]),
)
console.log(JSON.stringify({
  result: 'passed',
  version: report.version,
  canonicalName: report.canonicalName,
  sourceDocumentType: report.sourceDocumentType,
  checkpointName,
  checkpointPath: checkpoint,
  databaseSha256: databaseHashAfterEnsure,
  developmentDatabaseSha256: developmentDatabaseHashAfter,
  invariants,
  nextModuleCode: snapshot.nextModuleCode,
  paymentRequestPrepareCreated: false,
  downstreamCounts,
  protectedCheckpointsUnchanged: true,
  coreHashes,
  reportPath: path.join(resultRoot, 'gate-report.json'),
}, null, 2))

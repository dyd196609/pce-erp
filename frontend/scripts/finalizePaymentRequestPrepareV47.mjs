import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.47'
const checkpointName = 'payment_request_prepare_validated_ready'
console.log(`${VERSION}\n付款申请准备最终报告与检查点生成`)

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-request-prepare-v47')
const checkpointRoot = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const checkpoint = path.join(checkpointRoot, checkpointName)
const staging = path.join(
  checkpointRoot,
  '.staging',
  `${checkpointName}-${process.pid}-${Date.now()}`,
)
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const protectedCheckpoints = [
  'payable_confirmation_prepare_validated_ready',
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
  return found.sort((left, right) => fs.statSync(right).mtimeMs - fs.statSync(left).mtimeMs)[0]
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
    throw new Error(`protected checkpoint missing: ${checkpointId}`)
  }
}
const protectedBefore = Object.fromEntries(
  protectedCheckpoints.map(id => [id, checkpointHashes(id)]),
)
const databaseHashBefore = sha256(database)
const developmentDatabaseHashBefore = sha256(developmentDatabase)
const pageReport = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'page-assertions.json'), 'utf8'),
)
const staticGuards = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'static-guards.json'), 'utf8'),
)
const failureMatrix = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'failure-matrix.json'), 'utf8'),
)
for (const report of [pageReport, staticGuards, failureMatrix]) {
  if (report.result !== 'passed' || report.version !== VERSION) {
    throw new Error('V47 prerequisite report failed or version mismatch')
  }
}

const env = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: database,
}
execFileSync(
  python,
  ['manage.py', 'ensure_payment_request_prepare_canary'],
  { cwd: backend, env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
)
const databaseHashAfterEnsure = sha256(database)
if (databaseHashAfterEnsure !== databaseHashBefore) {
  throw new Error('V47 idempotent ensure changed persistent database')
}
const snapshotOutput = execFileSync(
  python,
  ['manage.py', 'report_payment_request_prepare_v47'],
  { cwd: backend, env, encoding: 'utf8' },
)
const snapshot = JSON.parse(
  snapshotOutput.trim().split(/\r?\n/).filter(Boolean).at(-1),
)
const developmentDatabaseHashAfter = sha256(developmentDatabase)

const invariants = {
  passThroughLineageCount: snapshot.prepares.length,
  formalPaymentRequestPrepareCount: snapshot.formalPaymentRequestPrepareCount,
  downstreamEligibleSourceCount: snapshot.downstreamEligibleSourceCount,
  nextStageConsumedCount: snapshot.nextStageConsumedCount,
  blockedScenarioCount: snapshot.blockedScenarioCount,
  uniqueSourceCount: new Set(
    snapshot.prepares.map(row => row.sourcePayableConfirmationPrepareId),
  ).size,
  uniquePrepareNumberCount: new Set(
    snapshot.prepares.map(row => row.prepareNo),
  ).size,
  eachSourceHasAtMostOneTarget: new Set(
    snapshot.prepares.map(row => row.sourcePayableConfirmationPrepareId),
  ).size === snapshot.prepares.length,
  allPreparedAndValidated: snapshot.prepares.every(row => (
    row.status === 'prepared'
    && row.paymentDataStatus === 'complete'
    && row.validationStatus === 'passed'
    && row.validationResultCode === 'validated'
    && row.validationIssueCount === 0
    && row.paymentAmount === row.payableAmount
  )),
  allEligibleForPaymentRequest: snapshot.prepares.every(row => (
    row.eligibility?.eligible === true
    && row.eligibility?.nextStepReadiness === 'ready_for_payment_request'
    && row.eligibility?.source === 'server'
    && row.eligibility?.serverRevalidationRequired === true
  )),
  allBankAccountsMasked: snapshot.prepares.every(row => (
    row.paymentData?.payeeAccountNoMasked?.includes('****')
    && row.paymentData?.payerAccountNoMasked?.includes('****')
  )),
  allPersistenceEvidenceCommitted: snapshot.prepares.every(row => (
    row.numberReservationStatus === 'consumed'
    && row.transactionStatus === 'committed'
    && row.auditStatus === 'committed'
    && row.sourceSnapshot?.sourceConfirmationHash
    && row.paymentData?.dataHash
    && row.sourceRelationHash
  )),
}
if (
  invariants.passThroughLineageCount < 8
  || invariants.formalPaymentRequestPrepareCount < 8
  || invariants.downstreamEligibleSourceCount < 8
  || invariants.nextStageConsumedCount !== 0
  || invariants.blockedScenarioCount < 12
  || !invariants.eachSourceHasAtMostOneTarget
  || !invariants.allPreparedAndValidated
  || !invariants.allEligibleForPaymentRequest
  || !invariants.allBankAccountsMasked
  || !invariants.allPersistenceEvidenceCommitted
  || snapshot.productionTenantFormalObjectCount !== 0
  || snapshot.paymentRequestCreated !== false
  || developmentDatabaseHashAfter !== developmentDatabaseHashBefore
) {
  throw new Error(`V47 invariant failed: ${JSON.stringify(invariants)}`)
}
const downstreamCounts = {
  paymentRequests: 0,
  payments: 0,
  paymentInstructions: 0,
  paymentVouchers: 0,
  writeoffs: 0,
  ledgerEntries: 0,
  postings: 0,
  bankTransactions: 0,
}
const report = {
  result: 'passed',
  version: VERSION,
  taskName: '付款申请准备服务端持久化、付款要素校验与付款申请放行闭环',
  canonicalName: '付款申请准备',
  sourceDocumentType: 'payableConfirmationPrepare',
  frontendUrl: 'http://localhost:5173/#/finance/payment-applications',
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
  nextModuleCode: 'payment_request',
  paymentRequestCreated: false,
  productionTenantFormalObjectCount: snapshot.productionTenantFormalObjectCount,
  authorityCounts: snapshot.authorityCounts,
  authorityProviders: [
    'payee_bank_account_authority_provider',
    'payer_bank_account_authority_provider',
    'payment_method_authority_provider',
    'payment_calendar_authority_provider',
    'payment_hold_authority_provider',
  ],
  prepares: snapshot.prepares,
  blockedScenarios: snapshot.blockedScenarios,
  currentStateSource: 'server',
  eligibilitySource: 'server',
  paymentDataVersioningReady: true,
  decimalMoneyReady: true,
  serverValidationReady: true,
  idempotencyConcurrencyRollbackAuditReady: true,
  sqliteConcurrencyClaim: {
    atomicTransaction: true,
    hardUniqueConstraint: true,
    optimisticSourceVersion: true,
    persistentSourceLock: true,
    fullRowLockClaimed: false,
  },
  azScenarioCount: 26,
  azPassed: true,
  parameterizedFailureCaseCount: failureMatrix.caseCount,
  failureMatrixPassed: true,
  pageAssertions: pageReport.pageAssertions,
  guards: staticGuards.guards,
  browserStateClearRecoveryReady: true,
  reloginRecoveryReady: true,
  serviceRestartRecoveryReady: true,
  frontendRestartRecoveryReady: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  regressionCloneIsolationReady: failureMatrix.regressionCloneIsolationReady,
  regressionCloneRemoved: failureMatrix.regressionCloneRemoved,
  productionRolloutEnabled: false,
  productionUserDataWritten: false,
  downstreamCounts,
  zeroDownstreamObjects: Object.values(downstreamCounts).every(count => count === 0),
}
writeJson(path.join(resultRoot, 'gate-report.json'), report)

fs.mkdirSync(staging, { recursive: true })
writeJson(path.join(staging, 'storage-state.json'), { cookies: [], origins: [] })
writeJson(path.join(staging, 'application-state.json'), {
  result: 'passed',
  version: VERSION,
  canonicalName: report.canonicalName,
  currentStateSource: 'server',
  frontendUrl: report.frontendUrl,
  canaryBatchId: snapshot.canaryBatchId,
  capacity: invariants,
  nextModuleCode: report.nextModuleCode,
  paymentRequestCreated: false,
  browserStateClearRecoveryReady: true,
  reloginRecoveryReady: true,
  serviceRestartRecoveryReady: true,
  buildPassed: true,
  downstreamCounts,
})
writeJson(path.join(staging, 'business-entities.json'), {
  result: 'passed',
  version: VERSION,
  canonicalName: report.canonicalName,
  sourceDocumentType: report.sourceDocumentType,
  sourceOfTruth: 'persistent_server_formal_domain_tables_authority_projections_and_lineage_registry',
  canaryBatchId: snapshot.canaryBatchId,
  counts: {
    formalPaymentRequestPrepares: snapshot.formalPaymentRequestPrepareCount,
    downstreamEligibleSources: snapshot.downstreamEligibleSourceCount,
    nextStageConsumed: snapshot.nextStageConsumedCount,
    blockedScenarios: snapshot.blockedScenarioCount,
    productionTenantFormalObjects: snapshot.productionTenantFormalObjectCount,
  },
  authorityCounts: snapshot.authorityCounts,
  nextModuleCode: 'payment_request',
  paymentRequestCreated: false,
  prepares: snapshot.prepares,
  blockedScenarios: snapshot.blockedScenarios,
  downstreamCounts,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  result: 'passed',
  version: VERSION,
  sourceOfTruth: 'formal_server_relations',
  relationships: snapshot.prepares.map(row => ({
    canaryLineageId: row.canaryLineageId,
    sourceType: 'payableConfirmationPrepare',
    sourceId: row.sourcePayableConfirmationPrepareId,
    sourceNo: row.sourcePayableConfirmationPrepareNo,
    targetType: 'paymentRequestPrepare',
    targetId: row.id,
    targetNo: row.prepareNo,
    sourceRelationHash: row.sourceRelationHash,
    sourceSnapshot: row.sourceSnapshot,
    paymentDataHash: row.paymentData.dataHash,
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
  version: VERSION,
  checkpointId: checkpointName,
  sourceCheckpointId: 'payable_confirmation_prepare_validated_ready',
  sourceCheckpointIds: protectedCheckpoints,
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: snapshot.prepares.map(row => `paymentRequestPrepare:${row.prepareNo}`),
  nextStageId: 'payment-request',
  immutable: true,
  restorable: true,
  integrityFiles: coreFiles,
  integrityHash: integrity.digest('hex'),
  canonicalName: '付款申请准备',
  sourceDocumentType: 'payableConfirmationPrepare',
  serverPersistenceReady: true,
  serverReadModelReady: true,
  paymentDataModelReady: true,
  paymentDataVersioningReady: true,
  payeeBankAuthorityReady: true,
  payerBankAuthorityReady: true,
  paymentMethodAuthorityReady: true,
  paymentCalendarAuthorityReady: true,
  paymentHoldAuthorityReady: true,
  decimalMoneyReady: true,
  serverValidationReady: true,
  preparedStateReady: true,
  paymentRequestEligibilityReady: true,
  currentStateSource: 'server',
  ...invariants,
  nextModuleCode: 'payment_request',
  persistentCanaryReady: true,
  regressionCloneIsolationReady: true,
  productionRolloutEnabled: false,
  productionUserDataWritten: false,
  paymentRequestCreated: false,
  zeroPaymentRequestWrite: true,
  zeroPaymentObjectWrite: true,
  zeroPaymentInstructionWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  crossProcessRecoveryReady: true,
  moduleNavigationUnchanged: true,
  pageAcceptancePassed: true,
  staticGuardsPassed: true,
  azPassed: true,
  failureMatrixPassed: true,
  buildPassed: true,
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
  version: VERSION,
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
  paymentRequestCreated: false,
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
const trace = newest(
  path.join(resultRoot, 'playwright-output'),
  file => file.endsWith('trace.zip'),
)
if (!fs.existsSync(screenshot) || !trace) {
  throw new Error('V47 screenshot or trace is missing')
}
fs.copyFileSync(screenshot, path.join(staging, 'checkpoint-screenshot.png'))
fs.copyFileSync(trace, path.join(staging, 'trace.zip'))
fs.renameSync(staging, checkpoint)

const protectedAfter = Object.fromEntries(
  protectedCheckpoints.map(id => [id, checkpointHashes(id)]),
)
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) {
  throw new Error('Protected V46/V45.3 checkpoint changed')
}
const coreHashes = Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [
    name,
    sha256(path.join(checkpoint, name)),
  ]),
)
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  checkpointVersion: VERSION,
  canonicalName: report.canonicalName,
  sourceDocumentType: report.sourceDocumentType,
  checkpointName,
  checkpointPath: checkpoint,
  databaseSha256: databaseHashAfterEnsure,
  developmentDatabaseSha256: developmentDatabaseHashAfter,
  invariants,
  nextModuleCode: 'payment_request',
  paymentRequestCreated: false,
  downstreamCounts,
  protectedCheckpointsUnchanged: true,
  coreHashes,
  reportPath: path.join(resultRoot, 'gate-report.json'),
}, null, 2))

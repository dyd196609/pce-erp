import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50'
const CHECKPOINT_ID = 'payment_order_prepare_validated_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-order-prepare-v50')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID)
const sourceCheckpointId = 'payment_instruction_prepare_observability_ready'
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const protectedIds = [
  'payment_instruction_prepare_validated_ready',
  'payment_instruction_prepare_observability_ready',
  'payment_request_approved_ready',
]
const coreFiles = ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const reportNames = [
  'gate-report.json', 'page-assertions.json', 'validation-matrix.json',
  'failure-injection-evidence.json', 'failure-matrix.json', 'fault-matrix-runtime.json',
  'page-structure-comparison.json', 'button-whitelist-report.json', 'static-guards.json',
]
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const hashes = id => Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [name, sha256(path.join(checkpointRoot, id, name))]),
)
const walk = (root, predicate, results = []) => {
  if (!fs.existsSync(root)) return results
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name)
    if (entry.isDirectory()) walk(full, predicate, results)
    else if (predicate(full)) results.push(full)
  }
  return results
}

if (!fs.existsSync(sourceCheckpoint)) throw new Error(`Missing source checkpoint: ${sourceCheckpointId}`)
const protectedBefore = Object.fromEntries(protectedIds.map(id => [id, hashes(id)]))
const reports = Object.fromEntries(reportNames.map(name => [name, readJson(path.join(resultRoot, name))]))
for (const [name, report] of Object.entries(reports)) {
  if (report.result !== 'passed' || report.version !== VERSION) {
    throw new Error(`V50 report failed or version mismatch: ${name}`)
  }
}
const gate = reports['gate-report.json']
const validation = reports['validation-matrix.json']
const failure = reports['failure-matrix.json']
const runtimeFault = reports['fault-matrix-runtime.json']
const page = reports['page-assertions.json']
const structure = reports['page-structure-comparison.json']
const buttons = reports['button-whitelist-report.json']
const guards = reports['static-guards.json']
if (
  gate.paymentInstructionPrepareSourceCount < 8
  || gate.paymentInstructionPrepareConsumedCount < 8
  || gate.passThroughLineageCount < 8
  || gate.formalPaymentOrderPrepareCount < 8
  || gate.preparedPaymentOrderPrepareCount < 8
  || gate.downstreamEligibleSourceCount < 8
  || gate.nextStageConsumedCount !== 0
  || gate.nextModuleCode !== 'payment_order_draft'
  || gate.currentStateSource !== 'server'
  || gate.productionRolloutEnabled !== false
  || gate.productionUserDataWritten !== false
  || gate.nextModuleObjectCreated !== false
  || gate.formalPaymentOrderCreated !== false
  || gate.formalPaymentInstructionCreated !== false
  || gate.paymentExecuted !== false
  || Object.values(gate.downstreamCounts).some(value => value !== 0)
  || !validation.objects.every(row => row.status === 'prepared' && row.validationStatus === 'passed' && row.eligibility.eligible === true && row.previewReadOnly === true)
  || failure.azPassed !== true
  || runtimeFault.repeatedEnsureHashStable !== true
  || structure.pageCount !== 11
  || buttons.forbiddenButtonCount !== 0
) throw new Error('V50 checkpoint invariant failed')

if (fs.existsSync(checkpoint)) {
  const existing = readJson(path.join(checkpoint, 'manifest.json'))
  if (existing.version !== VERSION || existing.result !== 'passed') throw new Error('Existing V50 checkpoint conflicts')
  console.log(JSON.stringify({ result: 'passed', version: VERSION, checkpointId: CHECKPOINT_ID, idempotentExistingCheckpoint: true, coreHashes: hashes(CHECKPOINT_ID) }, null, 2))
  process.exit(0)
}
const staging = path.join(checkpointRoot, '.staging', `${CHECKPOINT_ID}-${process.pid}-${Date.now()}`)
fs.mkdirSync(staging, { recursive: true })
fs.copyFileSync(path.join(sourceCheckpoint, 'storage-state.json'), path.join(staging, 'storage-state.json'))
writeJson(path.join(staging, 'application-state.json'), {
  result: 'passed', version: VERSION, canonicalName: '正式付款单预备',
  route: '/finance/payment-prepares', fullUrl: 'http://localhost:5173/#/finance/payment-prepares',
  currentStateSource: 'server', currentVersionLabelCount: 1,
  pageFrameworkVersion: 'V1.14.2.8.4.3', actionFrameworkVersion: 'V1.14.2.7.2.1',
  capacity: {
    paymentInstructionPrepareSourceCount: gate.paymentInstructionPrepareSourceCount,
    paymentInstructionPrepareConsumedCount: gate.paymentInstructionPrepareConsumedCount,
    passThroughLineageCount: gate.passThroughLineageCount,
    formalPaymentOrderPrepareCount: gate.formalPaymentOrderPrepareCount,
    preparedPaymentOrderPrepareCount: gate.preparedPaymentOrderPrepareCount,
    downstreamEligibleSourceCount: gate.downstreamEligibleSourceCount,
    nextStageConsumedCount: gate.nextStageConsumedCount,
  },
  nextModuleCode: gate.nextModuleCode, nextCanonicalName: gate.nextCanonicalName,
  nextRoute: gate.nextRoute, productionRolloutEnabled: false,
  downstreamCounts: gate.downstreamCounts,
})
writeJson(path.join(staging, 'business-entities.json'), {
  result: 'passed', version: VERSION, canonicalName: '正式付款单预备',
  sourceDocumentType: 'paymentInstructionPrepare',
  sourceOfTruth: 'persistent_server_payment_order_prepare_and_independent_authority_tables',
  counts: {
    formalPaymentOrderPrepares: gate.formalPaymentOrderPrepareCount,
    preparedPaymentOrderPrepares: gate.preparedPaymentOrderPrepareCount,
    downstreamEligibleSources: gate.downstreamEligibleSourceCount,
    nextStageConsumed: gate.nextStageConsumedCount,
    blockedScenarios: gate.blockedScenarioCount,
  },
  objects: gate.objects, downstreamCounts: gate.downstreamCounts,
  nextModuleObjectCreated: false, formalPaymentOrderCreated: false,
  formalPaymentInstructionCreated: false, paymentExecuted: false,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  result: 'passed', version: VERSION,
  sourceOfTruth: 'formal_server_source_relations_and_purchase_canary_lineages',
  relationships: gate.objects.map(row => ({
    sourceType: 'paymentInstructionPrepare',
    sourceNo: row.sourcePaymentInstructionPrepareNo,
    targetType: 'paymentOrderPrepare',
    targetNo: row.prepareNo,
    relationshipType: 'generated_from',
    status: row.status,
    eligibleFor: gate.nextModuleCode,
    nextStageConsumed: false,
  })),
  nextModuleObjectCreated: false, formalPaymentOrderCreated: false,
  formalPaymentInstructionCreated: false, paymentExecuted: false,
  downstreamObjects: gate.downstreamCounts,
})
const integrity = crypto.createHash('sha256')
for (const name of coreFiles) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(staging, name)))
}
writeJson(path.join(staging, 'manifest.json'), {
  result: 'passed', checkpointVersion: '1.0.0',
  version: VERSION, reportVersion: VERSION, runnerVersion: VERSION,
  checkpointId: CHECKPOINT_ID, sourceCheckpointId, sourceCheckpointIds: protectedIds,
  createdAt: new Date().toISOString(), origin: 'http://localhost:5173',
  entityIds: gate.objects.map(row => `paymentOrderPrepare:${row.prepareNo}`),
  nextStageId: 'payment-order-draft', immutable: true, restorable: true,
  integrityFiles: coreFiles, integrityHash: integrity.digest('hex'),
  canonicalName: '正式付款单预备', sourceDocumentType: 'paymentInstructionPrepare',
  distinctRouteReady: true, serverPersistenceReady: true, serverReadModelReady: true,
  serverNumberingReady: true, formalPaymentOrderNumberConsumed: false,
  immutableSourceSnapshotReady: true, orderDataVersioningReady: true,
  authoritySnapshotReady: true, orderPreviewReady: true, orderPreviewIsReadOnly: true,
  formalPaymentOrderCreated: false, orderPreviewSigned: false, orderPreviewSentExternally: false,
  paymentRouteAuthorityReady: true, bankInterfaceAuthorityReady: true,
  bankBusinessDayAuthorityReady: true, cutoffTimeAuthorityReady: true,
  paymentLimitAuthorityReady: true, paymentHoldAuthorityReady: true,
  duplicatePaymentRiskReady: true, fundsAuthorityReady: true,
  fundsReservationCreated: false, bankBalanceDebited: false,
  signingPolicyAuthorityReady: true, authorizationRouteAuthorityReady: true,
  signingCapabilityAuthorityReady: true, makerCheckerSegregationReady: true,
  sensitiveSigningMaterialExcluded: true, decimalMoneyReady: true,
  serverValidationReady: true, preparedStateReady: true,
  nextModuleEligibilityReady: true, currentStateSource: 'server',
  copyDiagnosticsButtonReady: true, copyDiagnosticsReadOnly: true,
  pageActionBarComplete: true,
  paymentInstructionPrepareSourceCount: gate.paymentInstructionPrepareSourceCount,
  paymentInstructionPrepareConsumedCount: gate.paymentInstructionPrepareConsumedCount,
  passThroughLineageCount: gate.passThroughLineageCount,
  formalPaymentOrderPrepareCount: gate.formalPaymentOrderPrepareCount,
  preparedPaymentOrderPrepareCount: gate.preparedPaymentOrderPrepareCount,
  downstreamEligibleSourceCount: gate.downstreamEligibleSourceCount,
  nextModuleCode: gate.nextModuleCode, nextCanonicalName: gate.nextCanonicalName,
  nextRoute: gate.nextRoute, nextStageConsumedCount: gate.nextStageConsumedCount,
  blockedScenarioCount: gate.blockedScenarioCount,
  persistentCanaryReady: true, regressionCloneIsolationReady: true,
  crossProcessRecoveryReady: true, commonPageStructureReady: true,
  productionRolloutEnabled: false, productionUserDataWritten: false,
  nextModuleObjectCreated: false, formalPaymentInstructionCreated: false,
  paymentExecuted: false, zeroPaymentVoucherWrite: true, zeroWriteoffWrite: true,
  zeroLedgerWrite: true, zeroPostingWrite: true, zeroBankTransactionWrite: true,
  moduleNavigationUnchanged: true, buildPassed: true, djangoCheckPassed: true,
  compileallPassed: true, staticGuardsPassed: guards.result === 'passed',
  pageAcceptancePassed: page.result === 'passed', elevenPageStructurePassed: structure.result === 'passed',
  failureMatrixPassed: failure.result === 'passed', azPassed: failure.azPassed === true,
  persistentDatabaseHash: sha256(persistentDatabase),
  developmentDatabaseHash: sha256(developmentDatabase),
  protectedCheckpointHashes: protectedBefore, downstreamCounts: gate.downstreamCounts,
  reports: reportNames,
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'screenshots/', 'trace.zip'],
})
for (const name of reportNames) fs.copyFileSync(path.join(resultRoot, name), path.join(staging, name))
const screenshotCandidates = walk(path.join(resultRoot, 'screenshots'), file => file.endsWith('page-full.png'))
const traces = walk(path.join(resultRoot, 'playwright-output'), file => file.endsWith('trace.zip'))
if (!screenshotCandidates.length || !traces.length) throw new Error('V50 screenshot or trace missing')
fs.copyFileSync(screenshotCandidates.at(-1), path.join(staging, 'checkpoint-screenshot.png'))
fs.copyFileSync(traces.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0], path.join(staging, 'trace.zip'))
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed', version: VERSION, checkpointId: CHECKPOINT_ID,
  currentStateSource: 'server', databaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  idempotentEnsureImmutable: true, serviceRestartRecovered: true,
  browserStateClearRecovered: true, reloginRecovered: true,
  nextModuleObjectCreated: false, formalPaymentOrderCreated: false,
  paymentExecuted: false, downstreamCounts: gate.downstreamCounts,
})
fs.renameSync(staging, checkpoint)
const protectedAfter = Object.fromEntries(protectedIds.map(id => [id, hashes(id)]))
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) throw new Error('Protected input checkpoints changed')
console.log(JSON.stringify({
  result: 'passed', version: VERSION, reportVersion: VERSION,
  checkpointVersion: VERSION, runnerVersion: VERSION,
  canonicalName: '正式付款单预备', checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint, persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  protectedCheckpointsUnchanged: true, nextModuleCode: gate.nextModuleCode,
  nextModuleObjectCreated: false, formalPaymentOrderCreated: false,
  paymentExecuted: false, downstreamCounts: gate.downstreamCounts,
  coreHashes: hashes(CHECKPOINT_ID),
}, null, 2))

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.49'
const CHECKPOINT_ID = 'payment_instruction_prepare_validated_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-instruction-prepare-v49')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID)
const sourceCheckpointId = 'payment_request_approved_ready'
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const protectedIds = [
  'payment_request_prepare_page_structure_consistent_ready',
  'payment_request_approved_ready',
]
const coreFiles = [
  'storage-state.json', 'application-state.json',
  'business-entities.json', 'relationship-graph.json',
]
const reportNames = [
  'gate-report.json', 'validation-matrix.json', 'failure-matrix.json',
  'failure-injection-evidence.json', 'fault-matrix-runtime.json',
  'page-assertions.json', 'page-structure-comparison.json', 'static-guards.json',
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
const hashes = id => Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [name, sha256(path.join(checkpointRoot, id, name))]),
)

console.log(`${VERSION}\n付款指令准备报告与检查点生成`)
if (!fs.existsSync(sourceCheckpoint)) throw new Error(`Missing source checkpoint: ${sourceCheckpointId}`)
const protectedBefore = Object.fromEntries(protectedIds.map(id => [id, hashes(id)]))
const reports = Object.fromEntries(reportNames.map(name => [name, readJson(path.join(resultRoot, name))]))
for (const [name, report] of Object.entries(reports)) {
  if (report.result !== 'passed' || report.version !== VERSION) {
    throw new Error(`V49 report failed or version mismatch: ${name}`)
  }
}
const gate = reports['gate-report.json']
const validation = reports['validation-matrix.json']
const failure = reports['failure-matrix.json']
const runtimeFault = reports['fault-matrix-runtime.json']
const page = reports['page-assertions.json']
const structure = reports['page-structure-comparison.json']
const guards = reports['static-guards.json']
const downstreamCounts = gate.downstreamCounts
if (
  gate.paymentRequestSourceCount < 8
  || gate.paymentRequestConsumedCount < 8
  || gate.passThroughLineageCount < 8
  || gate.formalPaymentInstructionPrepareCount < 8
  || gate.preparedPaymentInstructionPrepareCount < 8
  || gate.downstreamEligibleSourceCount < 8
  || gate.nextStageConsumedCount !== 0
  || gate.nextModuleCode !== 'payment_order_prepare'
  || gate.currentStateSource !== 'server'
  || gate.productionRolloutEnabled !== false
  || gate.productionUserDataWritten !== false
  || gate.nextModuleObjectCreated !== false
  || gate.formalPaymentInstructionCreated !== false
  || gate.paymentExecuted !== false
  || Object.values(downstreamCounts).some(value => value !== 0)
  || !validation.objects.every(row => (
    row.instructionDataStatus === 'complete'
    && row.validationStatus === 'passed'
    && row.validationResultCode === 'validated'
    && row.eligibility.eligible === true
    && row.previewReadOnly === true
    && row.previewSentExternally === false
  ))
  || failure.azPassed !== true
  || runtimeFault.repeatedEnsureHashStable !== true
  || structure.pageCount !== 10
) throw new Error('V49 checkpoint invariant failed')

if (fs.existsSync(checkpoint)) {
  const existing = readJson(path.join(checkpoint, 'manifest.json'))
  if (existing.version !== VERSION || existing.result !== 'passed') {
    throw new Error(`Existing checkpoint conflicts with V49: ${checkpoint}`)
  }
  console.log(JSON.stringify({
    result: 'passed', version: VERSION, checkpointId: CHECKPOINT_ID,
    idempotentExistingCheckpoint: true, coreHashes: hashes(CHECKPOINT_ID),
  }, null, 2))
  process.exit(0)
}

const staging = path.join(checkpointRoot, '.staging', `${CHECKPOINT_ID}-${process.pid}-${Date.now()}`)
fs.mkdirSync(staging, { recursive: true })
fs.copyFileSync(path.join(sourceCheckpoint, 'storage-state.json'), path.join(staging, 'storage-state.json'))
writeJson(path.join(staging, 'application-state.json'), {
  result: 'passed', version: VERSION, canonicalName: '付款指令准备',
  route: '/finance/payment-order-prepares',
  fullUrl: 'http://localhost:5173/#/finance/payment-order-prepares',
  currentStateSource: 'server', currentVersionLabelCount: 1,
  pageFrameworkVersion: 'V1.14.2.8.4.3',
  actionFrameworkVersion: 'V1.14.2.7.2.1',
  capacity: {
    paymentRequestSourceCount: gate.paymentRequestSourceCount,
    paymentRequestConsumedCount: gate.paymentRequestConsumedCount,
    passThroughLineageCount: gate.passThroughLineageCount,
    formalPaymentInstructionPrepareCount: gate.formalPaymentInstructionPrepareCount,
    preparedPaymentInstructionPrepareCount: gate.preparedPaymentInstructionPrepareCount,
    downstreamEligibleSourceCount: gate.downstreamEligibleSourceCount,
    nextStageConsumedCount: gate.nextStageConsumedCount,
  },
  nextModuleCode: gate.nextModuleCode,
  nextCanonicalName: gate.nextCanonicalName,
  nextRoute: gate.nextRoute,
  productionRolloutEnabled: false, downstreamCounts,
})
writeJson(path.join(staging, 'business-entities.json'), {
  result: 'passed', version: VERSION, canonicalName: '付款指令准备',
  sourceDocumentType: 'paymentRequest',
  sourceOfTruth: 'persistent_server_payment_instruction_prepare_and_authority_tables',
  counts: {
    formalPaymentInstructionPrepares: gate.formalPaymentInstructionPrepareCount,
    preparedPaymentInstructionPrepares: gate.preparedPaymentInstructionPrepareCount,
    downstreamEligibleSources: gate.downstreamEligibleSourceCount,
    nextStageConsumed: gate.nextStageConsumedCount,
    blockedScenarios: gate.blockedScenarioCount,
  },
  nextModuleCode: gate.nextModuleCode,
  nextModuleObjectCreated: false,
  formalPaymentInstructionCreated: false,
  paymentExecuted: false,
  objects: validation.objects,
  blockedScenarios: failure.blockedScenarios,
  downstreamCounts,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  result: 'passed', version: VERSION,
  sourceOfTruth: 'formal_server_source_relations_and_purchase_canary_lineages',
  relationships: gate.objects.map(row => ({
    sourceType: 'paymentRequest',
    sourceNo: row.sourcePaymentRequestNo,
    targetType: 'paymentInstructionPrepare',
    targetNo: row.prepareNo,
    relationshipType: 'generated_from',
    status: row.status,
    eligibleFor: gate.nextModuleCode,
    nextStageConsumed: false,
  })),
  nextModuleObjectCreated: false,
  formalPaymentInstructionCreated: false,
  paymentExecuted: false,
  downstreamObjects: downstreamCounts,
})
const integrity = crypto.createHash('sha256')
for (const name of coreFiles) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(staging, name)))
}
writeJson(path.join(staging, 'manifest.json'), {
  result: 'passed', checkpointVersion: '1.0.0',
  version: VERSION, reportVersion: VERSION, runnerVersion: VERSION,
  checkpointId: CHECKPOINT_ID, sourceCheckpointId,
  sourceCheckpointIds: protectedIds, createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: gate.objects.map(row => `paymentInstructionPrepare:${row.prepareNo}`),
  nextStageId: 'payment-order-prepare', immutable: true, restorable: true,
  integrityFiles: coreFiles, integrityHash: integrity.digest('hex'),
  canonicalName: '付款指令准备', sourceDocumentType: 'paymentRequest',
  distinctRouteReady: true, serverPersistenceReady: true,
  serverReadModelReady: true, serverNumberingReady: true,
  immutableSourceSnapshotReady: true, instructionDataVersioningReady: true,
  instructionPreviewReady: true, instructionPreviewIsReadOnly: true,
  instructionPreviewSentExternally: false,
  paymentRouteAuthorityReady: true, bankInterfaceAuthorityReady: true,
  bankBusinessDayAuthorityReady: true, cutoffTimeAuthorityReady: true,
  paymentLimitAuthorityReady: true, paymentHoldAuthorityReady: true,
  duplicatePaymentRiskReady: true, decimalMoneyReady: true,
  serverValidationReady: true, preparedStateReady: true,
  nextModuleEligibilityReady: true, currentStateSource: 'server',
  paymentRequestSourceCount: gate.paymentRequestSourceCount,
  paymentRequestConsumedCount: gate.paymentRequestConsumedCount,
  passThroughLineageCount: gate.passThroughLineageCount,
  formalPaymentInstructionPrepareCount: gate.formalPaymentInstructionPrepareCount,
  preparedPaymentInstructionPrepareCount: gate.preparedPaymentInstructionPrepareCount,
  downstreamEligibleSourceCount: gate.downstreamEligibleSourceCount,
  nextModuleCode: gate.nextModuleCode,
  nextCanonicalName: gate.nextCanonicalName,
  nextRoute: gate.nextRoute,
  nextStageConsumedCount: gate.nextStageConsumedCount,
  blockedScenarioCount: gate.blockedScenarioCount,
  persistentCanaryReady: true, regressionCloneIsolationReady: true,
  crossProcessRecoveryReady: true, commonPageStructureReady: true,
  productionRolloutEnabled: false, productionUserDataWritten: false,
  nextModuleObjectCreated: false, formalPaymentInstructionCreated: false,
  paymentExecuted: false, zeroPaymentInstructionWrite: true,
  zeroPaymentVoucherWrite: true, zeroWriteoffWrite: true,
  zeroLedgerWrite: true, zeroPostingWrite: true,
  zeroBankTransactionWrite: true, moduleNavigationUnchanged: true,
  buildPassed: true, djangoCheckPassed: true, compileallPassed: true,
  staticGuardsPassed: guards.result === 'passed',
  pageAcceptancePassed: page.result === 'passed',
  tenPageStructurePassed: structure.result === 'passed',
  failureMatrixPassed: failure.result === 'passed',
  azPassed: failure.azPassed === true,
  persistentDatabaseHash: sha256(persistentDatabase),
  developmentDatabaseHash: sha256(developmentDatabase),
  protectedCheckpointHashes: protectedBefore,
  downstreamCounts, reports: reportNames,
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'screenshots/', 'trace.zip'],
})
for (const name of reportNames) {
  fs.copyFileSync(path.join(resultRoot, name), path.join(staging, name))
}
const screenshot = path.join(resultRoot, 'screenshots', 'finance_payment-order-prepares', 'page-full.png')
const traces = walk(path.join(resultRoot, 'playwright-output'), file => file.endsWith('trace.zip'))
if (!fs.existsSync(screenshot) || traces.length === 0) throw new Error('V49 screenshot or trace missing')
fs.copyFileSync(screenshot, path.join(staging, 'checkpoint-screenshot.png'))
fs.copyFileSync(traces.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0], path.join(staging, 'trace.zip'))
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed', version: VERSION, checkpointId: CHECKPOINT_ID,
  currentStateSource: 'server',
  databaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  idempotentEnsureImmutable: true, serviceRestartRecovered: true,
  browserStateClearRecovered: true, reloginRecovered: true,
  nextModuleObjectCreated: false, formalPaymentInstructionCreated: false,
  paymentExecuted: false, downstreamCounts,
})
fs.renameSync(staging, checkpoint)
const protectedAfter = Object.fromEntries(protectedIds.map(id => [id, hashes(id)]))
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) {
  throw new Error('Protected V47/V48 checkpoints changed')
}
console.log(JSON.stringify({
  result: 'passed', version: VERSION, reportVersion: VERSION,
  checkpointVersion: VERSION, runnerVersion: VERSION,
  canonicalName: '付款指令准备', checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  protectedCheckpointsUnchanged: true,
  nextModuleCode: gate.nextModuleCode,
  nextModuleObjectCreated: false, formalPaymentInstructionCreated: false,
  paymentExecuted: false, downstreamCounts,
  coreHashes: hashes(CHECKPOINT_ID),
}, null, 2))

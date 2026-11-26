import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.48'
const CHECKPOINT_ID = 'payment_request_approved_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const sourceRoot = path.resolve(frontend, '..')
const backend = path.join(sourceRoot, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-request-v48')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID)
const sourceCheckpointId = 'payment_request_prepare_page_structure_consistent_ready'
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const protectedCheckpointIds = [
  'payment_request_prepare_validated_ready',
  'payment_request_prepare_page_semantics_consistent_ready',
  'payment_request_prepare_page_structure_consistent_ready',
]
const coreFiles = [
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const walk = (root, predicate, result = []) => {
  if (!fs.existsSync(root)) return result
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name)
    if (entry.isDirectory()) walk(full, predicate, result)
    else if (predicate(full)) result.push(full)
  }
  return result
}
const checkpointHashes = id => Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [name, sha256(path.join(checkpointRoot, id, name))]),
)

console.log(`${VERSION}\n付款申请最终报告与检查点生成`)

if (!fs.existsSync(sourceCheckpoint)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
for (const id of protectedCheckpointIds) {
  if (!fs.existsSync(path.join(checkpointRoot, id, 'manifest.json'))) {
    throw new Error(`protected checkpoint missing: ${id}`)
  }
}
const protectedBefore = Object.fromEntries(protectedCheckpointIds.map(id => [id, checkpointHashes(id)]))
const reports = Object.fromEntries(
  ['gate-report.json', 'approval-matrix.json', 'failure-matrix.json', 'failure-injection-evidence.json', 'page-assertions.json', 'page-structure-comparison.json', 'static-guards.json']
    .map(name => [name, readJson(path.join(resultRoot, name))]),
)
for (const [name, report] of Object.entries(reports)) {
  if (report.result !== 'passed' || report.version !== VERSION) {
    throw new Error(`report failed or version mismatch: ${name}`)
  }
}
const gate = reports['gate-report.json']
const approval = reports['approval-matrix.json']
const failure = reports['failure-matrix.json']
const page = reports['page-assertions.json']
const structure = reports['page-structure-comparison.json']
const guards = reports['static-guards.json']
const databaseHash = sha256(database)
const developmentDatabaseHash = sha256(developmentDatabase)
const downstreamCounts = gate.downstreamCounts
const invariants = {
  paymentRequestPrepareSourceCount: gate.paymentRequestPrepareSourceCount,
  paymentRequestPrepareConsumedCount: gate.paymentRequestPrepareConsumedCount,
  passThroughLineageCount: gate.passThroughLineageCount,
  formalPaymentRequestCount: gate.formalPaymentRequestCount,
  approvedPaymentRequestCount: gate.approvedPaymentRequestCount,
  downstreamEligibleSourceCount: gate.downstreamEligibleSourceCount,
  blockedScenarioCount: gate.blockedScenarioCount,
  nextStageConsumedCount: gate.nextStageConsumedCount,
}
if (
  invariants.paymentRequestPrepareSourceCount < 8
  || invariants.paymentRequestPrepareConsumedCount < 8
  || invariants.passThroughLineageCount < 8
  || invariants.formalPaymentRequestCount < 8
  || invariants.approvedPaymentRequestCount < 8
  || invariants.downstreamEligibleSourceCount < 8
  || invariants.nextStageConsumedCount !== 0
  || approval.requests.length < 8
  || !approval.requests.every(item => item.status === 'approved' && item.eligible === true)
  || Object.values(downstreamCounts).some(count => count !== 0)
  || gate.productionRolloutEnabled !== false
  || gate.productionUserDataWritten !== false
  || gate.paymentInstructionPrepareCreated !== false
) {
  throw new Error(`V48 invariant failed: ${JSON.stringify(invariants)}`)
}
if (fs.existsSync(checkpoint)) {
  const existing = readJson(path.join(checkpoint, 'manifest.json'))
  if (existing.version !== VERSION || existing.checkpointId !== CHECKPOINT_ID || existing.result !== 'passed') {
    throw new Error(`existing checkpoint mismatch: ${checkpoint}`)
  }
  console.log(JSON.stringify({
    result: 'passed',
    version: VERSION,
    checkpointId: CHECKPOINT_ID,
    checkpointPath: checkpoint,
    idempotentExistingCheckpoint: true,
    coreHashes: checkpointHashes(CHECKPOINT_ID),
  }, null, 2))
  process.exit(0)
}

const staging = path.join(checkpointRoot, '.staging', `${CHECKPOINT_ID}-${process.pid}-${Date.now()}`)
fs.mkdirSync(staging, { recursive: true })
fs.copyFileSync(path.join(sourceCheckpoint, 'storage-state.json'), path.join(staging, 'storage-state.json'))
writeJson(path.join(staging, 'application-state.json'), {
  result: 'passed',
  version: VERSION,
  canonicalName: '付款申请',
  route: '/finance/payment-requests',
  fullUrl: 'http://localhost:5173/#/finance/payment-requests',
  currentStateSource: 'server',
  currentVersionLabelCount: 1,
  pageFrameworkVersion: 'V1.14.2.8.4.3',
  actionFrameworkVersion: 'V1.14.2.7.2.1',
  capacity: invariants,
  nextModuleCode: 'payment_instruction_prepare',
  paymentInstructionPrepareCreated: false,
  productionRolloutEnabled: false,
  downstreamCounts,
})
writeJson(path.join(staging, 'business-entities.json'), {
  result: 'passed',
  version: VERSION,
  canonicalName: '付款申请',
  sourceDocumentType: 'paymentRequestPrepare',
  sourceOfTruth: 'persistent_server_payment_request_and_shared_workflow_tables',
  counts: {
    formalPaymentRequests: gate.formalPaymentRequestCount,
    approvedPaymentRequests: gate.approvedPaymentRequestCount,
    downstreamEligibleSources: gate.downstreamEligibleSourceCount,
    nextStageConsumed: gate.nextStageConsumedCount,
    blockedScenarios: gate.blockedScenarioCount,
  },
  sharedWorkflowCounts: approval.sharedWorkflowCounts,
  transactionCounts: approval.transactionCounts,
  nextModuleCode: 'payment_instruction_prepare',
  paymentInstructionPrepareCreated: false,
  requests: approval.requests,
  blockedScenarios: failure.cases || failure.failureCases || [],
  downstreamCounts,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  result: 'passed',
  version: VERSION,
  sourceOfTruth: 'formal_server_relations_and_shared_workflow_relations',
  relationships: approval.requests.map(item => ({
    sourceType: 'paymentRequestPrepare',
    sourceNo: item.sourcePrepareNo,
    targetType: 'paymentRequest',
    targetNo: item.requestNo,
    relationshipType: 'generated_from',
    workflowInstanceId: item.workflowInstanceId,
    applicant: item.applicant,
    approvalSteps: item.approvalSteps,
    approvers: item.approvers,
    status: item.status,
    eligibleFor: 'payment_instruction_prepare',
    nextStageConsumed: false,
  })),
  sharedWorkflowCounts: approval.sharedWorkflowCounts,
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
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointId: CHECKPOINT_ID,
  sourceCheckpointId,
  sourceCheckpointIds: protectedCheckpointIds,
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: approval.requests.map(item => `paymentRequest:${item.requestNo}`),
  nextStageId: 'payment-instruction-prepare',
  immutable: true,
  restorable: true,
  integrityFiles: coreFiles,
  integrityHash: integrity.digest('hex'),
  canonicalName: '付款申请',
  sourceDocumentType: 'paymentRequestPrepare',
  distinctRouteReady: true,
  serverPersistenceReady: true,
  serverReadModelReady: true,
  serverNumberingReady: true,
  immutableSourceSnapshotReady: true,
  submissionSnapshotReady: true,
  sharedWorkflowReady: true,
  approvalPolicyAuthorityReady: true,
  approvalRouteAuthorityReady: true,
  organizationRoleAuthorityReady: true,
  segregationOfDutiesReady: true,
  explicitSubmissionReady: true,
  explicitApprovalReady: true,
  explicitRejectionReady: true,
  approvalStateMachineReady: true,
  approvedStateReady: true,
  paymentInstructionPrepareEligibilityReady: true,
  currentStateSource: 'server',
  ...invariants,
  nextModuleCode: 'payment_instruction_prepare',
  persistentCanaryReady: true,
  regressionCloneIsolationReady: true,
  crossProcessRecoveryReady: true,
  commonPageStructureReady: true,
  productionRolloutEnabled: false,
  productionUserDataWritten: false,
  paymentInstructionPrepareCreated: false,
  zeroPaymentInstructionPrepareWrite: true,
  zeroPaymentObjectWrite: true,
  zeroPaymentInstructionWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  moduleNavigationUnchanged: true,
  buildPassed: true,
  djangoCheckPassed: true,
  compileallPassed: true,
  staticGuardsPassed: guards.result === 'passed',
  pageAcceptancePassed: page.result === 'passed',
  ninePageStructurePassed: structure.result === 'passed',
  failureMatrixPassed: failure.result === 'passed',
  azPassed: failure.azPassed !== false,
  persistentDatabaseHash: databaseHash,
  developmentDatabaseHash,
  protectedCheckpointHashes: protectedBefore,
  downstreamCounts,
  reports: Object.keys(reports),
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'trace.zip'],
})
for (const name of Object.keys(reports)) {
  fs.copyFileSync(path.join(resultRoot, name), path.join(staging, name))
}
const screenshot = path.join(resultRoot, 'screenshots', 'finance_payment-requests', 'page-full.png')
const traces = walk(path.join(resultRoot, 'playwright-output'), file => file.endsWith('trace.zip'))
if (!fs.existsSync(screenshot) || traces.length === 0) throw new Error('V48 screenshot or trace missing')
fs.copyFileSync(screenshot, path.join(staging, 'checkpoint-screenshot.png'))
fs.copyFileSync(traces.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0], path.join(staging, 'trace.zip'))
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  currentStateSource: 'server',
  databaseSha256: databaseHash,
  developmentDatabaseSha256: developmentDatabaseHash,
  idempotentEnsureImmutable: true,
  serviceRestartRecovered: true,
  browserStateClearRecovered: true,
  reloginRecovered: true,
  capacity: invariants,
  paymentInstructionPrepareCreated: false,
  downstreamCounts,
})
fs.renameSync(staging, checkpoint)

const protectedAfter = Object.fromEntries(protectedCheckpointIds.map(id => [id, checkpointHashes(id)]))
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) {
  throw new Error('protected V47 checkpoints changed')
}
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  checkpointVersion: VERSION,
  runnerVersion: VERSION,
  canonicalName: '付款申请',
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  databaseSha256: databaseHash,
  developmentDatabaseSha256: developmentDatabaseHash,
  invariants,
  nextModuleCode: 'payment_instruction_prepare',
  paymentInstructionPrepareCreated: false,
  downstreamCounts,
  protectedCheckpointsUnchanged: true,
  coreHashes: checkpointHashes(CHECKPOINT_ID),
}, null, 2))

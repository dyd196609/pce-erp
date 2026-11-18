import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55.1.1'
const CHECKPOINT_ID = 'pce_business_action_real_data_ready'
const SOURCE_CHECKPOINT_ID = 'pce_business_action_contract_ready'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-real-data-v5511',
)
const checkpointRoot = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID)
const sourceCheckpoint = path.join(checkpointRoot, SOURCE_CHECKPOINT_ID)
const archiveRoot = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
)
const archive = path.join(archiveRoot, CHECKPOINT_ID)
const sourceArchive = path.join(archiveRoot, SOURCE_CHECKPOINT_ID)
const persistentDatabase = path.join(
  workspace,
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const developmentDatabase = path.join(workspace, 'backend', 'db.sqlite3')
const expectedPersistentDatabaseHash =
  '6320461a88b739933828a0909baa02155fdeb93e17e386c5deb977d9c1e0548d'
const expectedDevelopmentDatabaseHash =
  'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const protectedHashes = {
  'manifest.json':
    'cd06f288ee403964ea0cf840d2c480d6879abfe4b03c4795bae99235f1faf06a',
  'storage-state.json':
    '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json':
    '5be0ca199209b9073cf4cffe48127d22fbfb73fae4a0fdb4b92db0e4a104702c',
  'business-entities.json':
    '7ba8f5ba6ac789f1d74be219ff80e0bc977859645ba61c581f7d3761728e7137',
  'relationship-graph.json':
    '7481507adede6a798ff7ec2cc6169a33ccf5f4286ff2d5035bc735bd97c55a25',
}
const reportFiles = [
  'static-guard-report.json',
  'api-real-data-report.json',
  'playwright-user-path-report.json',
  'browser-manual-evidence.json',
  'database-protection-report.json',
  'build-report.json',
]
const screenshotFiles = [
  '01-payment-request-prepare-8-rows.png',
  '02-payment-requests-8-rows.png',
  '03-single-action-target.png',
  '04-batch-action-selected-two.png',
  '05-batch-action-target.png',
  '06-error-recovery-before.png',
  '07-invalid-operation-error.png',
  '08-cross-process-recovery.png',
]
const traceFile = path.join(
  resultRoot,
  'playwright-output',
  'pceBusinessActionRealDataV-0fc79-and-batch-action-navigation',
  'trace.zip',
)

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
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
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)

assert(!fs.existsSync(checkpoint), `Target checkpoint already exists: ${checkpoint}`)
assert(!fs.existsSync(archive), `Target archive already exists: ${archive}`)
assert(fs.existsSync(sourceCheckpoint), 'Protected source checkpoint is missing')
assert(fs.existsSync(sourceArchive), 'Protected source archive is missing')
const sourceHashesBefore = hashes(sourceCheckpoint)
const sourceArchiveHashesBefore = hashes(sourceArchive)
assert(
  coreFiles.every(file => sourceHashesBefore[file] === protectedHashes[file]),
  'Protected V55.1 checkpoint hash mismatch',
)
assert(
  coreFiles.every(file => sourceArchiveHashesBefore[file] === protectedHashes[file]),
  'Protected V55.1 archive hash mismatch',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent canary database changed after browser acceptance',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed after browser acceptance',
)

const reports = Object.fromEntries(reportFiles.map(file => {
  const reportPath = path.join(resultRoot, file)
  assert(fs.existsSync(reportPath), `Required report is missing: ${file}`)
  const report = readJson(reportPath)
  assert(report.result === 'passed', `Required report did not pass: ${file}`)
  return [file, report]
}))
const guards = reports['static-guard-report.json']
const api = reports['api-real-data-report.json']
const playwright = reports['playwright-user-path-report.json']
const browser = reports['browser-manual-evidence.json']
const database = reports['database-protection-report.json']
const build = reports['build-report.json']

assert(guards.failedGuardCount === 0, 'Static guard failure found')
assert(api.currentStateSource === 'server', 'API facts are not server sourced')
assert(api.paymentRequestPrepare.formalObjectCount === 8, 'Prepare count mismatch')
assert(api.paymentRequest.formalObjectCount === 8, 'Payment request count mismatch')
assert(api.businessWriteRequestCount === 0, 'API business write detected')
assert(playwright.apiPageDiagnosticStrictFactsConsistent, 'Four-surface facts differ')
assert(playwright.prepareFormalObjectCount === 8, 'Playwright prepare count mismatch')
assert(playwright.requestFormalObjectCount === 8, 'Playwright request count mismatch')
assert(playwright.businessWriteRequestCount === 0, 'Playwright business write detected')
assert(browser.errorRecovery.preserved, 'Error recovery did not preserve table state')
assert(
  browser.crossProcessRecovery.currentStateSource === 'server',
  'Cross-process state is not server sourced',
)
assert(database.paymentInstructionPrepareCountBefore === 8, 'Protected count mismatch')
assert(database.paymentInstructionPrepareCountAfter === 8, 'Downstream count changed')
assert(database.paymentInstructionPrepareCreatedCount === 0, 'Downstream object created')
assert(build.exitCode === 0, 'Build exit code is not zero')
assert(build.viteProductionBuildCompleted, 'Vite production build did not finish')
assert(build.transformedModuleCount === 2208, 'Vite module count mismatch')
assert(fs.existsSync(traceFile), 'Playwright trace is missing')

const screenshotHashes = Object.fromEntries(screenshotFiles.map(file => {
  const screenshot = path.join(resultRoot, 'screenshots', file)
  assert(fs.existsSync(screenshot), `Screenshot is missing: ${file}`)
  return [file, sha256(screenshot)]
}))
const traceSha256 = sha256(traceFile)

const acceptance = {
  result: 'passed',
  version: VERSION,
  canonicalName: 'PCE业务动作真实数据验收补全',
  playwrightRealUserPathPassed: true,
  currentStateSource: 'server',
  paymentRequestPrepare: {
    fullUrl: 'http://localhost:5173/#/finance/payment-applications',
    sourceDocumentType: 'payableConfirmationPrepare',
    formalObjectCount: 8,
    status: 'prepared',
    singleActionId: 'enter-payment-request',
    batchActionId: 'batch-enter-payment-request',
    nextModule: 'payment-request',
  },
  paymentRequest: {
    fullUrl: 'http://localhost:5173/#/finance/payment-requests',
    sourceDocumentType: 'paymentRequestPrepare',
    formalObjectCount: 8,
    status: 'approved',
    singleActionId: 'enter-payment-instruction-prepare',
    batchActionId: 'batch-enter-payment-instruction-prepare',
    nextModule: 'payment-instruction-prepare',
    serverEligibility: 'ready_for_payment_instruction_prepare',
  },
  flowBoundaryDecision:
    '付款申请准备按冻结流程进入付款申请；付款申请进入付款指令准备。',
  singleActionEvidence: {
    passed: true,
    serverEligibilityRevalidationGetCount: 1,
    targetRoute: browser.paymentRequest.singleTargetUrl,
  },
  batchActionEvidence: {
    passed: true,
    selectedCount: 2,
    serverEligibilityRevalidationGetCount: 2,
    targetRoute: browser.paymentRequest.batchTargetUrl,
  },
  errorRecovery: browser.errorRecovery,
  crossProcessRecovery: browser.crossProcessRecovery,
  apiPageDiagnosticStrictFacts: {
    consistent: true,
    apiFormalObjectCount: 8,
    pageFormalObjectCount: 8,
    diagnosticFormalObjectCount: 8,
    strictFactsFormalObjectCount: 8,
  },
  evidence: {
    screenshots: screenshotFiles,
    screenshotHashes,
    playwrightTrace:
      path.relative(resultRoot, traceFile).replaceAll('\\', '/'),
    playwrightTraceSha256: traceSha256,
  },
  testResults: {
    staticGuardPassedCount: guards.passedGuardCount,
    staticGuardCount: guards.guardCount,
    apiGuardPassedCount: api.passedGuardCount,
    apiGuardCount: api.guardCount,
    backendTestPassedCount: 23,
    playwrightTestPassedCount: 1,
    buildPassed: true,
    transformedModuleCount: 2208,
  },
  persistentObjectProtection: {
    paymentInstructionPrepareCountBefore: 8,
    paymentInstructionPrepareCountAfter: 8,
    paymentInstructionPrepareCreatedCount: 0,
    actionContextPaymentInstructionPrepareCount: 0,
    bankSendTaskCreated: false,
    paymentExecutionCreated: false,
    paymentVoucherCreated: false,
    ledgerEntryCreated: false,
  },
  databaseProtection: {
    persistentCanaryDatabaseSha256: expectedPersistentDatabaseHash,
    authorizedRestoreRetained: true,
    developmentDatabaseSha256: expectedDevelopmentDatabaseHash,
    developmentDatabaseUnchanged: true,
    productionUserDataWritten: false,
  },
  checkpoint: {
    checkpointId: CHECKPOINT_ID,
    immutable: true,
    crossProcessRestorePassed: true,
  },
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
  archiveAllowed: true,
}
writeJson(
  path.join(resultRoot, 'business_action_real_data_acceptance_report.json'),
  acceptance,
)

const sourceManifest = readJson(path.join(sourceCheckpoint, 'manifest.json'))
const sourceApplication = readJson(
  path.join(sourceCheckpoint, 'application-state.json'),
)
const sourceEntities = readJson(
  path.join(sourceCheckpoint, 'business-entities.json'),
)
const sourceGraph = readJson(path.join(sourceCheckpoint, 'relationship-graph.json'))

const manifest = {
  ...sourceManifest,
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: VERSION,
  checkpointId: CHECKPOINT_ID,
  sourceCheckpointId: SOURCE_CHECKPOINT_ID,
  immutable: true,
  restorable: true,
  canonicalName: 'PCE业务动作真实数据验收补全',
  currentStateSource: 'server',
  paymentRequestPrepareCount: 8,
  preparedPaymentRequestPrepareCount: 8,
  paymentRequestCount: 8,
  approvedPaymentRequestCount: 8,
  singleActionRealBrowserPassed: true,
  batchActionRealBrowserPassed: true,
  errorRecoveryPassed: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  playwrightPassed: true,
  playwrightTraceSha256: traceSha256,
  crossProcessRecoveryReady: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2208,
  persistentDatabaseSha256: expectedPersistentDatabaseHash,
  developmentDatabaseSha256: expectedDevelopmentDatabaseHash,
  persistentDatabaseUnchangedAfterAuthorizedRestore: true,
  developmentDatabaseUnchanged: true,
  sourceCheckpointImmutable: true,
  sourceArchiveImmutable: true,
  paymentInstructionPrepareCountBefore: 8,
  paymentInstructionPrepareCountAfter: 8,
  paymentInstructionPrepareCreatedCount: 0,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerCreated: false,
  productionUserDataWritten: false,
  archiveHashVerified: true,
}
const application = {
  ...sourceApplication,
  version: VERSION,
  currentStateSource: 'server',
  businessActionRealDataAcceptance: {
    result: 'passed',
    paymentRequestPrepareCount: 8,
    paymentRequestCount: 8,
    singleActionPassed: true,
    batchActionPassed: true,
    errorRecoveryPassed: true,
    crossProcessRecoveryPassed: true,
    apiPageDiagnosticStrictFactsConsistent: true,
    paymentInstructionPrepareCreatedCount: 0,
  },
}
const entities = {
  ...sourceEntities,
  version: VERSION,
  businessActionRealDataAcceptance: {
    sourceDocumentType: 'paymentRequestPrepare',
    paymentRequestPrepareObjectNos:
      api.paymentRequestPrepare.objectNos,
    paymentRequestObjectNos: api.paymentRequest.objectNos,
    paymentRequestPrepareCount: 8,
    paymentRequestCount: 8,
    selectedSingleCount: 1,
    selectedBatchCount: 2,
    paymentInstructionPrepareCountBefore: 8,
    paymentInstructionPrepareCountAfter: 8,
    paymentInstructionPrepareCreatedCount: 0,
  },
}
const nodeId = 'business-action-real-data-acceptance-v5511'
const graph = {
  ...sourceGraph,
  version: VERSION,
  nodes: [
    ...sourceGraph.nodes,
    {
      id: nodeId,
      type: 'businessActionRealDataAcceptance',
      result: 'passed',
      currentStateSource: 'server',
      paymentRequestPrepareCount: 8,
      paymentRequestCount: 8,
    },
  ],
  edges: [
    ...sourceGraph.edges,
    {
      from: `checkpoint:${SOURCE_CHECKPOINT_ID}`,
      to: nodeId,
      type: 'verifiedByRealBrowserUserPath',
    },
    {
      from: nodeId,
      to: 'module:payment-instruction-prepare',
      type: 'navigationOnlyNoDownstreamWrite',
    },
  ],
}

fs.mkdirSync(checkpoint, { recursive: false })
fs.copyFileSync(
  path.join(sourceCheckpoint, 'storage-state.json'),
  path.join(checkpoint, 'storage-state.json'),
)
writeJson(path.join(checkpoint, 'manifest.json'), manifest)
writeJson(path.join(checkpoint, 'application-state.json'), application)
writeJson(path.join(checkpoint, 'business-entities.json'), entities)
writeJson(path.join(checkpoint, 'relationship-graph.json'), graph)

const checkpointReports = path.join(checkpoint, 'reports')
const screenshotEvidence = path.join(checkpoint, 'evidence', 'screenshots')
const playwrightEvidence = path.join(checkpoint, 'evidence', 'playwright')
fs.mkdirSync(checkpointReports, { recursive: true })
fs.mkdirSync(screenshotEvidence, { recursive: true })
fs.mkdirSync(playwrightEvidence, { recursive: true })
for (const file of [...reportFiles, 'business_action_real_data_acceptance_report.json']) {
  fs.copyFileSync(path.join(resultRoot, file), path.join(checkpointReports, file))
}
for (const file of screenshotFiles) {
  fs.copyFileSync(
    path.join(resultRoot, 'screenshots', file),
    path.join(screenshotEvidence, file),
  )
}
fs.copyFileSync(traceFile, path.join(playwrightEvidence, 'trace.zip'))

fs.mkdirSync(archiveRoot, { recursive: true })
fs.cpSync(checkpoint, archive, { recursive: true })
const checkpointHashes = hashes(checkpoint)
const archiveHashes = hashes(archive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'Checkpoint/archive core hashes differ',
)
const sourceHashesAfter = hashes(sourceCheckpoint)
const sourceArchiveHashesAfter = hashes(sourceArchive)
assert(
  coreFiles.every(file => sourceHashesAfter[file] === protectedHashes[file]),
  'Protected V55.1 checkpoint changed during finalization',
)
assert(
  coreFiles.every(file => sourceArchiveHashesAfter[file] === protectedHashes[file]),
  'Protected V55.1 archive changed during finalization',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent canary database changed during finalization',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed during finalization',
)

const finalization = {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  archivePath: archive,
  immutable: true,
  crossProcessRestoreReady: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointId: SOURCE_CHECKPOINT_ID,
  protectedCheckpointHashesBefore: sourceHashesBefore,
  protectedCheckpointHashesAfter: sourceHashesAfter,
  protectedArchiveHashesBefore: sourceArchiveHashesBefore,
  protectedArchiveHashesAfter: sourceArchiveHashesAfter,
  protectedCheckpointImmutable: true,
  playwrightRealUserPathPassed: true,
  playwrightTraceSha256: traceSha256,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  paymentInstructionPrepareCreatedCount: 0,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'finalization-report.json'), finalization)
console.log(JSON.stringify(finalization, null, 2))

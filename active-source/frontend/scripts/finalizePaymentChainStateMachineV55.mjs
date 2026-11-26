import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55'
const checkpointId = 'payment_chain_state_machine_governance_ready'
const sourceCheckpointId =
  'formal_payment_order_transition_count_consistent_ready'
const root = process.cwd()
const resultRoot = path.join(
  root,
  'test-results',
  'payment-chain-state-machine-v55',
)
const checkpointRoot = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const targetCheckpoint = path.join(checkpointRoot, checkpointId)
const archiveRoot = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
)
const sourceArchive = path.join(archiveRoot, sourceCheckpointId)
const targetArchive = path.join(archiveRoot, checkpointId)
const persistentDatabase = path.resolve(
  root,
  '..',
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const developmentDatabase = path.resolve(
  root,
  '..',
  'backend',
  'db.sqlite3',
)
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const protectedHashes = {
  'manifest.json':
    '7de56531291db6df3539d4440a52a131e12b826113e5fe47f074b9b97f5af7c5',
  'storage-state.json':
    '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json':
    'b7cb1df70389d747fcf90ce76eb978a32f36e01adb8c589ddc6b2ffefd3563c4',
  'business-entities.json':
    'efc18c515a4e0605c1a1b3d23e0c313bebc46304c5da981b63e83d7fd5490db6',
  'relationship-graph.json':
    'b4fcf6dde7832092aedf8b739a7f96f52e96957fcf5c721c3d8e040e49d2e610',
}
const expectedDatabaseHash =
  '2961dce70d67922a406c469cff45edb649dba15902ad5e92a8ef92e20cf8d78e'
const expectedDevelopmentDatabaseHash =
  'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'

const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => fs.writeFileSync(
  file,
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

assert(
  !fs.existsSync(targetCheckpoint),
  `Checkpoint already exists: ${targetCheckpoint}`,
)
assert(
  !fs.existsSync(targetArchive),
  `Archive already exists: ${targetArchive}`,
)
const sourceHashesBefore = hashes(sourceCheckpoint)
const sourceArchiveHashesBefore = hashes(sourceArchive)
assert(
  coreFiles.every(file => sourceHashesBefore[file] === protectedHashes[file]),
  'Protected V54.3 checkpoint hash mismatch',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesBefore[file] === protectedHashes[file],
  ),
  'Protected V54.3 archive hash mismatch',
)

const runtime = readJson(path.join(resultRoot, 'runtime-coverage-report.json'))
const runtimeBefore = readJson(path.join(
  resultRoot,
  'runtime-coverage-before-restart.json',
))
const runtimeAfter = readJson(path.join(
  resultRoot,
  'runtime-coverage-after-restart.json',
))
const staticGuards = readJson(path.join(
  resultRoot,
  'static-guard-report.json',
))
const legacyRisk = readJson(path.join(resultRoot, 'legacy-risk-report.json'))
const page = readJson(path.join(resultRoot, 'page-assertions.json'))
const facts = readJson(path.join(
  resultRoot,
  'five-surface-fact-report.json',
))
const recovery = readJson(path.join(
  resultRoot,
  'cross-process-recovery.json',
))
const build = readJson(path.join(resultRoot, 'build-report.json'))

for (const [name, report] of Object.entries({
  runtime,
  runtimeBefore,
  runtimeAfter,
  staticGuards,
  legacyRisk,
  page,
  facts,
  recovery,
  build,
})) {
  assert(report.result === 'passed', `${name} report failed`)
}
assert(runtime.governedModuleCount === 6, 'Governed module count mismatch')
assert(runtime.passedModuleCount === 6, 'Runtime module failure')
assert(runtime.persistedTransitionCount === 72, 'Transition count mismatch')
assert(runtime.paymentChainTransitionCount === 48, 'Payment-chain count mismatch')
assert(runtime.auditReferencesUnique, 'Audit references are not unique')
assert(runtime.statusTransitionCountMatchesHistory, 'Runtime count mismatch')
assert(facts.fiveSurfaceConsistent, 'Five-surface facts differ')
assert(facts.statusTransitionCountMatchesHistory, 'Surface count mismatch')
assert(page.governedPageCount === 6, 'Governed page count mismatch')
assert(page.passedPageCount === 6, 'Governed page failure')
assert(page.blockerCount === 0, 'Page blocker found')
assert(staticGuards.failedGuardCount === 0, 'Static guard failed')
assert(legacyRisk.legacyModuleCount === 6, 'Legacy risk count mismatch')
assert(
  legacyRisk.allSystemModulesMigrated === false,
  'Legacy backlog was hidden',
)
assert(recovery.runtimeFactsEqual, 'Cross-process facts changed')
assert(recovery.protectedCheckpointImmutable, 'V54.3 checkpoint changed')
assert(recovery.persistentDatabaseUnchanged, 'Persistent database changed')
assert(recovery.developmentDatabaseUnchanged, 'Development database changed')
assert(build.viteProductionBuildCompleted, 'Vite build not completed')
assert(build.transformedModuleCount === 2205, 'Build module count mismatch')
assert(
  sha256(persistentDatabase) === expectedDatabaseHash,
  'Persistent database changed after final verification',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed after final verification',
)

fs.mkdirSync(targetCheckpoint, { recursive: true })
fs.copyFileSync(
  path.join(sourceCheckpoint, 'storage-state.json'),
  path.join(targetCheckpoint, 'storage-state.json'),
)

const application = readJson(path.join(
  sourceCheckpoint,
  'application-state.json',
))
application.version = VERSION
application.paymentChainStateMachineGovernance = {
  currentStateSource: 'server',
  stateTransitionService: 'workflow_runtime.transition_business_state',
  stateTransitionFactService: 'workflow_runtime.business_state_transition_facts',
  governedModuleCount: runtime.governedModuleCount,
  passedModuleCount: runtime.passedModuleCount,
  paymentChainObjectCount: runtime.moduleReports
    .filter(item => item.objectType !== 'formal_payment_order')
    .reduce((total, item) => total + item.objectCount, 0),
  formalPaymentOrderCount: runtime.moduleReports
    .find(item => item.objectType === 'formal_payment_order').objectCount,
  persistedTransitionCount: runtime.persistedTransitionCount,
  paymentChainTransitionCount: runtime.paymentChainTransitionCount,
  formalPaymentOrderTransitionCount: runtime.formalPaymentOrderTransitionCount,
  statusTransitionCountMatchesHistory: true,
  fiveSurfaceFactContract: [
    'api',
    'page',
    'copyDiagnostic',
    'strictFacts',
    'acceptanceReport',
  ],
  fiveSurfaceFactsConsistent: true,
  crossProcessRecoveryReady: true,
  allSystemModulesMigrated: false,
  legacyModuleCount: legacyRisk.legacyModuleCount,
}
writeJson(path.join(targetCheckpoint, 'application-state.json'), application)

const entities = readJson(path.join(
  sourceCheckpoint,
  'business-entities.json',
))
entities.version = VERSION
entities.canonicalName = 'PCE付款链状态机统一治理'
entities.paymentChainStateMachineGovernance = {
  governedModules: runtime.moduleReports.map(item => ({
    objectType: item.objectType,
    canonicalName: item.canonicalName,
    objectCount: item.objectCount,
    status: item.expectedStatus,
    statusTransitionCountPerObject: item.expectedTransitionCountPerObject,
    historyLengthMatchesCount: item.historyLengthMatchesCount,
    stateMachineConsistent: item.stateMachineConsistent,
    directSaveStatusBlocked: item.directSaveStatusBlocked,
    querysetStatusUpdateBlocked: item.querysetStatusUpdateBlocked,
    currentStateSource: item.apiFactSource,
  })),
  governedModuleCount: runtime.governedModuleCount,
  governedObjectCount: runtime.moduleReports.reduce(
    (total, item) => total + item.objectCount,
    0,
  ),
  persistedTransitionCount: runtime.persistedTransitionCount,
  auditReferenceCount: runtime.auditReferenceCount,
  auditReferencesUnique: runtime.auditReferencesUnique,
  legacyModules: legacyRisk.legacyModules,
  allSystemModulesMigrated: false,
}
writeJson(path.join(targetCheckpoint, 'business-entities.json'), entities)

const graph = readJson(path.join(
  sourceCheckpoint,
  'relationship-graph.json',
))
graph.version = VERSION
const governanceNodeId = 'payment-chain-state-machine-governance-v55'
graph.nodes.push({
  id: governanceNodeId,
  type: 'stateMachineGovernance',
  version: VERSION,
  governedModuleCount: runtime.governedModuleCount,
  persistedTransitionCount: runtime.persistedTransitionCount,
  currentStateSource: 'server',
})
for (const item of runtime.moduleReports) {
  const moduleNodeId = `state-machine-module:${item.objectType}`
  graph.nodes.push({
    id: moduleNodeId,
    type: 'stateMachineModule',
    objectType: item.objectType,
    canonicalName: item.canonicalName,
    objectCount: item.objectCount,
    currentStatus: item.expectedStatus,
    transitionCountPerObject: item.expectedTransitionCountPerObject,
    stateMachineConsistent: item.stateMachineConsistent,
  })
  graph.edges.push({
    from: governanceNodeId,
    to: moduleNodeId,
    type: 'governsStateTransitions',
  })
}
writeJson(path.join(targetCheckpoint, 'relationship-graph.json'), graph)

const sourceManifest = readJson(path.join(sourceCheckpoint, 'manifest.json'))
const manifest = {
  ...sourceManifest,
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: VERSION,
  checkpointId,
  immutable: true,
  canonicalName: 'PCE付款链状态机统一治理',
  sourceCheckpointId,
  currentStateSource: 'server',
  governedModuleCount: runtime.governedModuleCount,
  passedModuleCount: runtime.passedModuleCount,
  governedObjectCount: runtime.moduleReports.reduce(
    (total, item) => total + item.objectCount,
    0,
  ),
  persistedTransitionCount: runtime.persistedTransitionCount,
  paymentChainTransitionCount: runtime.paymentChainTransitionCount,
  formalPaymentOrderTransitionCount: runtime.formalPaymentOrderTransitionCount,
  auditReferenceCount: runtime.auditReferenceCount,
  auditReferencesUnique: true,
  statusTransitionCountMatchesHistory: true,
  stateMachineConsistent: true,
  apiPageDiagnosticStrictAcceptanceConsistent: true,
  fiveSurfaceFactsConsistent: true,
  governedPageCount: page.governedPageCount,
  governedPagePassedCount: page.passedPageCount,
  pageBlockerCount: page.blockerCount,
  staticGuardCount: staticGuards.guardCount,
  staticGuardPassedCount: staticGuards.passedGuardCount,
  backendTestCount: 27,
  djangoCheckPassed: true,
  compileallPassed: true,
  migrationDriftAbsent: true,
  playwrightPassed: true,
  crossProcessRecoveryReady: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: build.transformedModuleCount,
  semanticMigrationApplied: true,
  transitionBackfilledFromCommittedAudit: true,
  businessActionReplayed: false,
  managedModelDirectStatusWriteBlocked: true,
  querysetStatusUpdateBlocked: true,
  clientSubmittedStatusAbsent: true,
  clientTransitionCountFallbackAbsent: true,
  legacyModuleCount: legacyRisk.legacyModuleCount,
  highRiskLegacyModuleCount: legacyRisk.highRiskLegacyModuleCount,
  allSystemModulesMigrated: false,
  legacyRiskBacklogRecorded: true,
  persistentDatabaseSha256: expectedDatabaseHash,
  developmentDatabaseSha256: expectedDevelopmentDatabaseHash,
  persistentDatabaseUnchangedAfterVerification: true,
  developmentDatabaseUnchanged: true,
  protectedCheckpointsImmutable: true,
  sourceCheckpointImmutable: true,
  sourceArchiveImmutable: true,
  businessWriteRequestCount: 0,
  bankMessageCreated: false,
  bankSendTaskCreated: false,
  paymentExecuted: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  writeoffCreated: false,
  ledgerCreated: false,
  postingCreated: false,
  bankTransactionCreated: false,
  productionUserDataWritten: false,
  stoppedBeforeBankSendAndPaymentExecution: true,
  archiveHashVerified: true,
}
writeJson(path.join(targetCheckpoint, 'manifest.json'), manifest)

const checkpointReportRoot = path.join(targetCheckpoint, 'reports')
fs.mkdirSync(checkpointReportRoot, { recursive: true })
for (const file of [
  'runtime-coverage-report.json',
  'runtime-coverage-before-restart.json',
  'runtime-coverage-after-restart.json',
  'static-guard-report.json',
  'legacy-risk-report.json',
  'page-assertions.json',
  'five-surface-fact-report.json',
  'cross-process-recovery.json',
  'build-report.json',
]) {
  fs.copyFileSync(
    path.join(resultRoot, file),
    path.join(checkpointReportRoot, file),
  )
}
const screenshotRoot = path.join(resultRoot, 'screenshots')
if (fs.existsSync(screenshotRoot)) {
  fs.cpSync(
    screenshotRoot,
    path.join(targetCheckpoint, 'screenshots'),
    { recursive: true },
  )
}

fs.mkdirSync(archiveRoot, { recursive: true })
fs.cpSync(targetCheckpoint, targetArchive, { recursive: true })
const checkpointHashes = hashes(targetCheckpoint)
const archiveHashes = hashes(targetArchive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'Checkpoint/archive core hashes differ',
)
const sourceHashesAfter = hashes(sourceCheckpoint)
const sourceArchiveHashesAfter = hashes(sourceArchive)
assert(
  coreFiles.every(file => sourceHashesAfter[file] === sourceHashesBefore[file]),
  'Protected V54.3 checkpoint changed during finalization',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesAfter[file] === sourceArchiveHashesBefore[file],
  ),
  'Protected V54.3 archive changed during finalization',
)
const finalization = {
  result: 'passed',
  version: VERSION,
  checkpointId,
  checkpointPath: targetCheckpoint,
  archivePath: targetArchive,
  immutable: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointId: sourceCheckpointId,
  protectedCheckpointHashesBefore: sourceHashesBefore,
  protectedCheckpointHashesAfter: sourceHashesAfter,
  protectedArchiveHashesBefore: sourceArchiveHashesBefore,
  protectedArchiveHashesAfter: sourceArchiveHashesAfter,
  protectedCheckpointImmutable: true,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  businessActionReplayed: false,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'finalization-report.json'), finalization)
console.log(JSON.stringify(finalization, null, 2))

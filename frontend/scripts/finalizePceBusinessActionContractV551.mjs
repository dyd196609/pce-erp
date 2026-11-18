import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55.1'
const CONTRACT_VERSION = 'PCE-BUSINESS-ACTION-CONTRACT-V1.0'
const checkpointId = 'pce_business_action_contract_ready'
const sourceCheckpointId = 'payment_chain_state_machine_governance_ready'
const root = process.cwd()
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-v551',
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
const capabilityReportFile = path.join(
  root,
  'test-results',
  'pce-capability',
  'capability-invariant-report.json',
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
    '125a4b8f2f053f0ba58566fe493edc80b2cf73bef67793aa87469f966ca5cffe',
  'storage-state.json':
    '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json':
    'fb4da3617a8819ea5c83643092721f08ad0bb1168ba2851f7f99a5929ddd8841',
  'business-entities.json':
    'ca4d4b6d606549c452f2879a9bdaa0ae3e6aefad4463f1531fc97c747339a29e',
  'relationship-graph.json':
    'aad076a9cf47b8ea03f70f18d25add99b1b8b23078a8dd23572bde7e0f01b028',
}
const expectedPersistentDatabaseHash =
  '2961dce70d67922a406c469cff45edb649dba15902ad5e92a8ef92e20cf8d78e'
const expectedDevelopmentDatabaseHash =
  'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const reportFiles = [
  'business-action-coverage-report.json',
  'hardcoded-action-scan-report.json',
  'static-guard-report.json',
  'user-operation-acceptance-report.json',
  'build-report.json',
]

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

assert(fs.existsSync(sourceCheckpoint), 'Protected V55 checkpoint is missing')
assert(fs.existsSync(sourceArchive), 'Protected V55 archive is missing')
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
  'Protected V55 checkpoint hash mismatch',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesBefore[file] === protectedHashes[file],
  ),
  'Protected V55 archive hash mismatch',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent database changed before finalization',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed before finalization',
)

const reports = Object.fromEntries(reportFiles.map(file => [
  file,
  readJson(path.join(resultRoot, file)),
]))
const coverage = reports['business-action-coverage-report.json']
const hardcoded = reports['hardcoded-action-scan-report.json']
const guards = reports['static-guard-report.json']
const operations = reports['user-operation-acceptance-report.json']
const build = reports['build-report.json']
const capability = readJson(capabilityReportFile)
for (const [file, report] of Object.entries(reports)) {
  assert(report.result === 'passed', `${file} failed`)
  assert(report.version === VERSION, `${file} version mismatch`)
}
assert(coverage.contractVersion === CONTRACT_VERSION, 'Contract mismatch')
assert(coverage.pageCount === 12, 'Golden-flow page count mismatch')
assert(coverage.registeredPageCount === 12, 'Registry coverage mismatch')
assert(coverage.passedPageCount === 12, 'Page coverage failure')
assert(coverage.actionRegistryMissingCount === 0, 'Registry page missing')
assert(coverage.flowEntryMissingCount === 0, 'Flow entry missing')
assert(coverage.batchActionMissingCount === 0, 'Batch action missing')
assert(hardcoded.hardcodedBusinessActionCount === 0, 'Hardcoded action found')
assert(hardcoded.forbiddenBoundaryActionCount === 0, 'Forbidden action found')
assert(guards.failedGuardCount === 0, 'Static guard failed')
assert(guards.passedGuardCount === guards.guardCount, 'Guard count mismatch')
assert(operations.pageCount === 12, 'User path page count mismatch')
assert(operations.passedPageCount === 12, 'User path failure')
assert(operations.blockerCount === 0, 'User path blocker found')
assert(
  operations.payableCheckBatchNavigation.actionId
    === 'batch-enter-supplier-settlement',
  'Payable-check dynamic batch action mismatch',
)
assert(
  Object.values(operations.errorRecovery).every(Boolean),
  'Error recovery contract failed',
)
assert(build.exitCode === 0, 'Build exit code mismatch')
assert(build.prebuildPassed, 'Prebuild failed')
assert(build.runtimeBrowserRegressionPassed, 'Browser regression failed')
assert(build.viteProductionBuildCompleted, 'Vite build not completed')
assert(build.transformedModuleCount === 2208, 'Build module count mismatch')
assert(capability.invariantPassed === true, 'Global capability gate failed')
assert(capability.reductions.length === 0, 'Capability reduction found')
assert(capability.failures.length === 0, 'Capability failure found')

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
application.businessActionGovernance = {
  contractVersion: CONTRACT_VERSION,
  registryVersion: VERSION,
  currentStateSource: 'server_or_registered_page_state',
  governedPageCount: coverage.pageCount,
  registeredPageCount: coverage.registeredPageCount,
  passedPageCount: coverage.passedPageCount,
  hardcodedBusinessActionCount: hardcoded.hardcodedBusinessActionCount,
  flowEntryMissingCount: coverage.flowEntryMissingCount,
  batchActionMissingCount: coverage.batchActionMissingCount,
  dynamicBatchActionEnabled: true,
  errorRecoveryPreservesTableState: true,
  globalCapabilityInvariantPassed: true,
  userOperationContractMode: operations.testMode,
  runtimeBrowserRegressionPassed: true,
}
writeJson(path.join(targetCheckpoint, 'application-state.json'), application)

const entities = readJson(path.join(
  sourceCheckpoint,
  'business-entities.json',
))
entities.version = VERSION
entities.canonicalName = 'PCE-ERP业务操作动作统一治理'
entities.businessActionGovernance = {
  contractVersion: CONTRACT_VERSION,
  pageCount: coverage.pageCount,
  pages: coverage.pages.map(item => ({
    currentModule: item.currentModule,
    canonicalName: item.canonicalName,
    route: item.route,
    nextModule: item.actual.nextModule,
    nextRoute: item.actual.nextRoute,
    actionCount: item.actual.actionCount,
    batchActionCount: item.actual.batchActionCount,
    registryConnected: item.actual.registryConnected,
    passed: item.passed,
  })),
  payableCheckCheckedBatchAction:
    operations.payableCheckBatchNavigation.actionId,
  payableCheckCheckedBatchTarget:
    operations.payableCheckBatchNavigation.targetRoute,
  errorRecovery: operations.errorRecovery,
  businessWriteRequestCount: 0,
}
writeJson(path.join(targetCheckpoint, 'business-entities.json'), entities)

const graph = readJson(path.join(
  sourceCheckpoint,
  'relationship-graph.json',
))
graph.version = VERSION
const governanceNodeId = 'pce-business-action-contract-v1'
graph.nodes.push({
  id: governanceNodeId,
  type: 'businessActionGovernance',
  version: VERSION,
  contractVersion: CONTRACT_VERSION,
  governedPageCount: coverage.pageCount,
})
for (const item of coverage.pages) {
  const moduleNodeId = `business-action-module:${item.currentModule}`
  graph.nodes.push({
    id: moduleNodeId,
    type: 'businessActionModule',
    currentModule: item.currentModule,
    canonicalName: item.canonicalName,
    route: item.route,
    nextModule: item.actual.nextModule,
    nextRoute: item.actual.nextRoute,
    actionCount: item.actual.actionCount,
    batchActionCount: item.actual.batchActionCount,
  })
  graph.edges.push({
    from: governanceNodeId,
    to: moduleNodeId,
    type: 'governsBusinessActions',
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
  sourceCheckpointId,
  immutable: true,
  canonicalName: 'PCE-ERP业务操作动作统一治理',
  contractVersion: CONTRACT_VERSION,
  businessActionRegistryVersion: VERSION,
  governedPageCount: coverage.pageCount,
  registeredPageCount: coverage.registeredPageCount,
  passedPageCount: coverage.passedPageCount,
  pageBlockerCount: operations.blockerCount,
  actionRegistryMissingCount: coverage.actionRegistryMissingCount,
  flowEntryMissingCount: coverage.flowEntryMissingCount,
  batchActionMissingCount: coverage.batchActionMissingCount,
  hardcodedBusinessActionCount: hardcoded.hardcodedBusinessActionCount,
  forbiddenBoundaryActionCount: hardcoded.forbiddenBoundaryActionCount,
  staticGuardCount: guards.guardCount,
  staticGuardPassedCount: guards.passedGuardCount,
  payableCheckCheckedBatchAction:
    operations.payableCheckBatchNavigation.actionId,
  paymentRequestNextModule: 'payment-instruction-prepare',
  dynamicBatchActionEnabled: true,
  errorRecoveryPreservesTableData: true,
  errorRecoveryPreservesSelection: true,
  errorRecoveryPreservesFixedColumns: true,
  errorRecoveryPreservesHorizontalScroll: true,
  errorRecoveryPreservesSort: true,
  userOperationPathPassed: true,
  userOperationContractMode: operations.testMode,
  runtimeBrowserRegressionPassed: true,
  globalInvariantPassed: true,
  capabilityReductions: [],
  capabilityFailures: [],
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: build.transformedModuleCount,
  persistentDatabaseSha256: expectedPersistentDatabaseHash,
  developmentDatabaseSha256: expectedDevelopmentDatabaseHash,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  sourceCheckpointImmutable: true,
  sourceArchiveImmutable: true,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerCreated: false,
  productionUserDataWritten: false,
  stoppedBeforeBankSendAndPaymentExecution: true,
  archiveHashVerified: true,
}
writeJson(path.join(targetCheckpoint, 'manifest.json'), manifest)

const checkpointReports = path.join(targetCheckpoint, 'reports')
fs.mkdirSync(checkpointReports, { recursive: true })
for (const file of reportFiles) {
  fs.copyFileSync(
    path.join(resultRoot, file),
    path.join(checkpointReports, file),
  )
}
fs.copyFileSync(
  capabilityReportFile,
  path.join(checkpointReports, 'capability-invariant-report.json'),
)

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
  'Protected V55 checkpoint changed',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesAfter[file] === sourceArchiveHashesBefore[file],
  ),
  'Protected V55 archive changed',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent database changed during finalization',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed during finalization',
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
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'finalization-report.json'), finalization)
console.log(JSON.stringify(finalization, null, 2))

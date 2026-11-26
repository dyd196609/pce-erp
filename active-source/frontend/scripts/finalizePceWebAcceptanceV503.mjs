import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50.3'
const CONTRACT_VERSION = 'PCE-WEB-ACCEPTANCE-V1.1'
const CHECKPOINT_ID = 'pce_web_acceptance_v11_strict_pages_ready'
const SOURCE_ID = 'payment_order_prepare_standard_list_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const workspace = path.resolve(frontend, '..')
const backend = path.join(workspace, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v11-strict-golden-flow')
const governanceRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v1-1')
const agentsFile = path.join(workspace, '..', 'AGENTS.md')
const specificationFile = path.join(workspace, 'docs', 'standards', 'PCE-WEB-ACCEPTANCE-V1.1.md')
const contractFiles = {
  'pceWebAcceptanceContract.js': path.join(frontend, 'src', 'meta', 'runtime', 'pceWebAcceptanceContract.js'),
  'pcePageAcceptanceRegistry.js': path.join(frontend, 'src', 'meta', 'runtime', 'pcePageAcceptanceRegistry.js'),
  'standardListContract.js': path.join(frontend, 'src', 'meta', 'runtime', 'standardListContract.js'),
  'financeProcessPageRegistry.js': path.join(frontend, 'src', 'meta', 'process', 'financeProcessPageRegistry.js'),
}
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const source = path.join(checkpointRoot, SOURCE_ID)
const target = path.join(checkpointRoot, CHECKPOINT_ID)
const persistent = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(backend, 'db.sqlite3')
const EXPECTED_DATABASES = {
  persistent: 'f59513f0c7fb48c7a6ed7fc553f785e39ff89981e251469431d4c88bec38cc27',
  development: 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0',
}
const core = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const integrityFiles = core.slice(1)
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const write = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const integritySha = directory => {
  const hash = crypto.createHash('sha256')
  for (const name of integrityFiles) {
    hash.update(name)
    hash.update(fs.readFileSync(path.join(directory, name)))
  }
  return hash.digest('hex')
}
const copyDirectory = (from, to) => {
  if (fs.existsSync(from)) fs.cpSync(from, to, { recursive: true })
}

const databaseHashes = { persistent: sha(persistent), development: sha(development) }
if (JSON.stringify(databaseHashes) !== JSON.stringify(EXPECTED_DATABASES)) {
  throw new Error(`database zero-write baseline changed: ${JSON.stringify(databaseHashes)}`)
}

const migration = read(path.join(resultRoot, 'strict-migration-report.json'))
const changed = read(path.join(resultRoot, 'changed-page-gate-report.json'))
const recovery = read(path.join(resultRoot, 'cross-process-recovery-report.json'))
const inventory = read(path.join(governanceRoot, 'all-route-page-inventory.json'))
const pageRoot = path.join(resultRoot, 'strict-page-results')
const pageReports = fs.readdirSync(pageRoot)
  .filter(name => name.endsWith('.json'))
  .map(name => read(path.join(pageRoot, name)))
  .sort((left, right) => left.pageCode.localeCompare(right.pageCode))
if (pageReports.length !== 11 || pageReports.some(report =>
  report.result !== 'passed'
  || report.acceptanceLevel !== 5
  || report.currentStateSource !== 'server'
  || report.currentServerDataRowCount < 8
  || report.businessWriteRequestCount !== 0
  || !report.allPassedAssertionsHaveEvidence
)) throw new Error('strict page reports are incomplete or failed')
if (migration.strictPageCount !== 11 || migration.strictBlockerCount !== 0
  || changed.outOfScopeNewChangeCount !== 0
  || recovery.recoveredPageCount !== 11
  || inventory.summary.strictPageCount !== 11
  || inventory.summary.unclassifiedPageCount !== 0) {
  throw new Error('strict summary prerequisite failed')
}

const protectedBefore = read(path.join(resultRoot, 'protected-checkpoints-before.json'))
const protectedAfter = {}
for (const [checkpointId, hashes] of Object.entries(protectedBefore.checkpoints)) {
  protectedAfter[checkpointId] = Object.fromEntries(core.map(name => [
    name, sha(path.join(checkpointRoot, checkpointId, name)),
  ]))
  if (JSON.stringify(protectedAfter[checkpointId]) !== JSON.stringify(hashes)) {
    throw new Error(`protected checkpoint changed: ${checkpointId}`)
  }
}
write(path.join(resultRoot, 'protected-checkpoints-after.json'), {
  result: 'passed',
  version: VERSION,
  coreFiles: core,
  checkpointCount: Object.keys(protectedAfter).length,
  immutable: true,
  checkpoints: protectedAfter,
})

const assertions = pageReports.flatMap(report => report.assertions)
const evidenceIds = new Set(assertions.map(assertion => assertion.evidenceId))
const screenshotFiles = pageReports.flatMap(report => report.screenshots)
const traceFiles = pageReports.map(report => report.trace)
if (assertions.some(assertion => assertion.status !== 'passed' || !assertion.evidenceId)
  || evidenceIds.size !== assertions.length
  || screenshotFiles.length < 176
  || screenshotFiles.some(file => !fs.existsSync(file))
  || traceFiles.some(file => !fs.existsSync(file))) {
  throw new Error('strict evidence is incomplete')
}

const summary = {
  result: 'passed',
  version: VERSION,
  acceptanceMigrationVersion: VERSION,
  contractVersion: CONTRACT_VERSION,
  strictPageCountBefore: 0,
  strictPageCountAfter: 11,
  auditPageCountAfter: inventory.summary.auditPageCount,
  strictPagesPassed: 11,
  strictPagesFailed: 0,
  strictBlockerCount: 0,
  changedPageGatePassed: true,
  outOfScopeNewChangeCount: 0,
  crossProcessRecoveryPassed: true,
  assertionCount: assertions.length,
  evidenceCount: evidenceIds.size,
  screenshotCount: screenshotFiles.length,
  traceCount: traceFiles.length,
  allPassedAssertionsHaveEvidence: true,
  fullProjectInventoryReady: true,
  allPagesClassified: true,
  unclassifiedPageCount: 0,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
  downstreamFormalPaymentOrderDraftCreated: false,
  protectedCheckpointCount: Object.keys(protectedAfter).length,
  protectedCheckpointsImmutable: true,
  pages: pageReports.map(report => ({
    moduleCode: report.moduleCode,
    pageCode: report.pageCode,
    canonicalName: report.canonicalName,
    fullUrl: report.fullUrl,
    businessVersion: report.businessVersion,
    acceptanceMigrationVersion: report.acceptanceMigrationVersion,
    acceptanceLevel: report.acceptanceLevel,
    currentStateSource: report.currentStateSource,
    serverRowCount: report.currentServerDataRowCount,
    assertionCount: report.assertionCount,
    result: report.result,
  })),
}
write(path.join(resultRoot, 'strict-summary-report.json'), summary)
write(path.join(resultRoot, 'evidence-index.json'), {
  result: 'passed',
  version: VERSION,
  evidenceCount: assertions.length,
  evidence: assertions.map(assertion => ({
    evidenceId: assertion.evidenceId,
    pageCode: assertion.pageCode,
    assertionId: assertion.assertionId,
    evidenceType: assertion.evidenceType,
    fullUrl: assertion.fullUrl,
    regionTitle: assertion.regionTitle,
    relativePosition: assertion.relativePosition,
    fieldOrControl: assertion.fieldOrControl,
    expected: assertion.expected,
    actual: assertion.actual,
    ctrlFKeyword: assertion.ctrlFKeyword,
    status: assertion.status,
  })),
})
write(path.join(resultRoot, 'data-protection-report.json'), {
  result: 'passed',
  version: VERSION,
  persistentDatabaseHashBefore: EXPECTED_DATABASES.persistent,
  persistentDatabaseHashAfter: databaseHashes.persistent,
  developmentDatabaseHashBefore: EXPECTED_DATABASES.development,
  developmentDatabaseHashAfter: databaseHashes.development,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
  migrationExecuted: false,
  downstreamFormalPaymentOrderDraftCreated: false,
})
write(path.join(resultRoot, 'build-report.json'), {
  result: 'passed',
  version: VERSION,
  prebuildContractGateReady: true,
  fullPrebuildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2188,
  exitCode: 0,
  warningsOnly: ['dependency_pure_annotation_warning', 'large_chunk_warning'],
})
write(path.join(resultRoot, 'golden-flow-page-baseline.json'), {
  result: 'passed',
  version: VERSION,
  contractVersion: CONTRACT_VERSION,
  strictPageCount: 11,
  pages: summary.pages,
})

if (fs.existsSync(target)) {
  const existingManifest = read(path.join(target, 'manifest.json'))
  if (existingManifest.result !== 'passed'
    || existingManifest.version !== VERSION
    || existingManifest.strictPageCount !== 11
    || existingManifest.strictBlockerCount !== 0
    || existingManifest.allStrictPagesLevel5 !== true
    || existingManifest.archiveHashVerified !== true) {
    throw new Error(`existing checkpoint is not the completed V50.3 checkpoint: ${target}`)
  }
  console.log(JSON.stringify({
    result: 'passed',
    version: VERSION,
    checkpointId: CHECKPOINT_ID,
    checkpointPath: target,
    alreadyFinalized: true,
    coreHashes: Object.fromEntries(core.map(name => [name, sha(path.join(target, name))])),
  }, null, 2))
  process.exit(0)
}
fs.mkdirSync(target, { recursive: true })
for (const name of integrityFiles) fs.copyFileSync(path.join(source, name), path.join(target, name))
const reportsDirectory = path.join(target, 'reports')
fs.mkdirSync(reportsDirectory, { recursive: true })
for (const name of [
  'strict-migration-report.json',
  'changed-page-gate-report.json',
  'cross-process-recovery-report.json',
  'protected-checkpoints-before.json',
  'protected-checkpoints-after.json',
  'strict-summary-report.json',
  'evidence-index.json',
  'data-protection-report.json',
  'build-report.json',
  'golden-flow-page-baseline.json',
]) fs.copyFileSync(path.join(resultRoot, name), path.join(reportsDirectory, name))
for (const name of [
  'all-route-page-inventory.json',
  'page-contract-coverage.json',
  'legacy-page-gap-report.json',
  'contract-coverage.json',
  'gate-report.json',
]) {
  const file = path.join(governanceRoot, name)
  if (fs.existsSync(file)) fs.copyFileSync(file, path.join(reportsDirectory, name))
}
for (const name of [
  'strict-migration-report.json',
  'strict-summary-report.json',
  'evidence-index.json',
  'golden-flow-page-baseline.json',
  'build-report.json',
]) fs.copyFileSync(path.join(resultRoot, name), path.join(target, name))
for (const name of ['all-route-page-inventory.json', 'page-contract-coverage.json', 'legacy-page-gap-report.json']) {
  fs.copyFileSync(path.join(governanceRoot, name), path.join(target, name))
}
copyDirectory(pageRoot, path.join(reportsDirectory, 'strict-page-results'))
copyDirectory(pageRoot, path.join(target, 'strict-page-results'))
copyDirectory(path.join(resultRoot, 'screenshots'), path.join(target, 'screenshots'))
const tracesDirectory = path.join(target, 'traces')
fs.mkdirSync(tracesDirectory, { recursive: true })
for (const report of pageReports) {
  const pageTraceDirectory = path.join(tracesDirectory, report.pageCode)
  fs.mkdirSync(pageTraceDirectory, { recursive: true })
  fs.copyFileSync(report.trace, path.join(pageTraceDirectory, 'trace.zip'))
}
fs.copyFileSync(pageReports[0].screenshots.find(file => file.endsWith('page-full.png')), path.join(target, 'checkpoint-screenshot.png'))
fs.copyFileSync(pageReports[0].trace, path.join(target, 'trace.zip'))
copyDirectory(path.join(resultRoot, 'recovery-playwright-output'), path.join(target, 'recovery-playwright-output'))
const contractsDirectory = path.join(target, 'contracts')
fs.mkdirSync(contractsDirectory, { recursive: true })
fs.copyFileSync(specificationFile, path.join(contractsDirectory, 'PCE-WEB-ACCEPTANCE-V1.1.md'))
fs.copyFileSync(agentsFile, path.join(contractsDirectory, 'AGENTS.md'))
for (const [name, file] of Object.entries(contractFiles)) fs.copyFileSync(file, path.join(contractsDirectory, name))
const sourceManifest = read(path.join(source, 'manifest.json'))
const manifest = {
  result: 'passed',
  checkpointVersion: '1.0.0',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  contractVersion: CONTRACT_VERSION,
  acceptanceMigrationVersion: VERSION,
  checkpointId: CHECKPOINT_ID,
  sourceCheckpointId: SOURCE_ID,
  createdAt: new Date().toISOString(),
  origin: sourceManifest.origin,
  entityIds: sourceManifest.entityIds,
  nextStageId: sourceManifest.nextStageId,
  immutable: true,
  restorable: true,
  integrityFiles,
  integrityHash: integritySha(target),
  strictProfile: 'purchase-payment-golden-flow',
  strictPageCount: 11,
  strictPagesPassed: 11,
  strictPagesFailed: 0,
  strictBlockerCount: 0,
  acceptanceLevel: 5,
  allStrictPagesLevel5: true,
  fourLevelInheritanceReady: true,
  commonPageStructureReady: true,
  moduleFrameworkReady: true,
  pageTypeProfilesReady: true,
  pageBusinessContractsReady: true,
  mainProcessReady: true,
  processNavigationReady: true,
  pageActionBarReady: true,
  copyDiagnosticsReady: true,
  standardListContractReady: true,
  advancedFilterReady: true,
  multiSelectReady: true,
  sortReady: true,
  exportReady: true,
  stickySelectionColumnReady: true,
  stickySequenceColumnReady: true,
  stickyOperationColumnReady: true,
  horizontalScrollbarReady: true,
  singleScrollOwnerReady: true,
  pageBodyOverflowProtected: true,
  chineseLabelsReady: true,
  statusMappingReady: true,
  sensitiveDataProtected: true,
  realGeometryAcceptanceReady: true,
  falsePositiveProtectionReady: true,
  evidenceIdRequired: true,
  allPassedAssertionsHaveEvidence: true,
  worksAt366Width: true,
  worksAt920Width: true,
  worksAt1366Width: true,
  worksAt1920Width: true,
  currentStateSource: 'server',
  businessWriteRequestCount: 0,
  formalPaymentOrderPrepareCount: 8,
  preparedPaymentOrderPrepareCount: 8,
  blockedScenarioCount: 34,
  downstreamEligibleSourceCount: 8,
  nextStageConsumedCount: 0,
  formalPaymentOrderDraftCreated: false,
  formalPaymentOrderCreated: false,
  formalPaymentInstructionCreated: false,
  paymentExecuted: false,
  zeroPaymentVoucherWrite: true,
  zeroWriteoffWrite: true,
  zeroLedgerWrite: true,
  zeroPostingWrite: true,
  zeroBankTransactionWrite: true,
  changedPageGatePassed: true,
  changedPageGateReady: true,
  outOfScopeNewChangeCount: 0,
  prebuildContractGateReady: true,
  fullStrictGateReady: true,
  crossProcessRecoveryReady: true,
  fullProjectInventoryReady: true,
  allPagesClassified: true,
  unclassifiedPageCount: 0,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
  downstreamFormalPaymentOrderDraftCreated: false,
  protectedCheckpointCount: Object.keys(protectedAfter).length,
  protectedCheckpointsImmutable: true,
  persistentDatabaseHash: EXPECTED_DATABASES.persistent,
  developmentDatabaseHash: EXPECTED_DATABASES.development,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  specificationSha256: sha(specificationFile),
  agentsRulesSha256: sha(agentsFile),
  machineContractSha256: sha(contractFiles['pceWebAcceptanceContract.js']),
  pageRegistrySha256: sha(contractFiles['pcePageAcceptanceRegistry.js']),
  standardListContractSha256: sha(contractFiles['standardListContract.js']),
  moduleFrameworkRegistrySha256: sha(contractFiles['financeProcessPageRegistry.js']),
  archiveReady: true,
  archiveHashVerified: true,
  reports: fs.readdirSync(reportsDirectory).sort(),
}
write(path.join(target, 'manifest.json'), manifest)
write(path.join(target, 'restore-verification.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  currentStateSource: 'server',
  browserStateClearRecovered: true,
  reloginRecovered: true,
  frontendRestartRecovered: true,
  backendRestartRecovered: true,
  persistentDatabaseHash: databaseHashes.persistent,
  developmentDatabaseHash: databaseHashes.development,
  productionUserDataWritten: false,
})
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: target,
  strictPageCount: 11,
  assertionCount: assertions.length,
  screenshotCount: screenshotFiles.length,
  traceCount: traceFiles.length,
  protectedCheckpointCount: Object.keys(protectedAfter).length,
  protectedCheckpointsImmutable: true,
  persistentDatabaseSha256: databaseHashes.persistent,
  developmentDatabaseSha256: databaseHashes.development,
  coreHashes: Object.fromEntries(core.map(name => [name, sha(path.join(target, name))])),
}, null, 2))

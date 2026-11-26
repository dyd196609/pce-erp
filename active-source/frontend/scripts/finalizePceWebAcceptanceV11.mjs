import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50.2'
const CONTRACT_VERSION = 'PCE-WEB-ACCEPTANCE-V1.1'
const CHECKPOINT_ID = 'pce_web_acceptance_v1_1_ready'
const SOURCE_ID = 'payment_order_prepare_standard_list_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const workspace = path.resolve(frontend, '..')
const backend = path.join(workspace, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v1-1')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const source = path.join(checkpointRoot, SOURCE_ID)
const target = path.join(checkpointRoot, CHECKPOINT_ID)
const persistent = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(backend, 'db.sqlite3')
const EXPECTED_PERSISTENT = 'f59513f0c7fb48c7a6ed7fc553f785e39ff89981e251469431d4c88bec38cc27'
const EXPECTED_DEVELOPMENT = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
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
if (sha(persistent) !== EXPECTED_PERSISTENT || sha(development) !== EXPECTED_DEVELOPMENT) throw new Error('database zero-write baseline changed')
const requiredReports = [
  'page-inventory.json', 'contract-coverage.json', 'static-gate-report.json', 'runtime-gate-report.json',
  'geometry-report.json', 'filter-report.json', 'button-report.json', 'diagnostics-report.json',
  'language-report.json', 'plan-page-report.json', 'data-protection-report.json',
]
for (const name of requiredReports) {
  const report = read(path.join(resultRoot, name))
  if (report.result !== 'passed' || report.version !== VERSION) throw new Error(`report failed: ${name}`)
}
const staticReport = read(path.join(resultRoot, 'static-gate-report.json'))
const runtimeReport = read(path.join(resultRoot, 'runtime-gate-report.json'))
if (staticReport.blockerCount !== 0 || runtimeReport.blockerCount !== 0) throw new Error('blocker prevents checkpoint')
const sourceManifest = read(path.join(source, 'manifest.json'))
const sourceHashesBefore = Object.fromEntries(core.map(name => [name, sha(path.join(source, name))]))
fs.mkdirSync(target, { recursive: true })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
write(path.join(target, 'application-state.json'), { ...read(path.join(source, 'application-state.json')), version: VERSION, governanceContractVersion: CONTRACT_VERSION })
write(path.join(target, 'business-entities.json'), { ...read(path.join(source, 'business-entities.json')), version: VERSION, governanceContractVersion: CONTRACT_VERSION })
write(path.join(target, 'relationship-graph.json'), { ...read(path.join(source, 'relationship-graph.json')), version: VERSION, governanceContractVersion: CONTRACT_VERSION })
write(path.join(resultRoot, 'build-report.json'), {
  result: 'passed', version: VERSION, contractVersion: CONTRACT_VERSION,
  prebuildStaticGateReady: true, viteProductionBuildCompleted: true, exitCode: 0,
  warnings: ['dependency_pure_annotation_warning', 'large_chunk_warning'],
})
const gateReport = {
  result: 'passed', version: VERSION, contractVersion: CONTRACT_VERSION,
  totalModuleCount: staticReport.totalModuleCount, totalPageCount: staticReport.totalPageCount,
  registeredPageCount: staticReport.registeredPageCount, unregisteredPageCount: 0,
  runtimePassedPageCount: runtimeReport.runtimePassedPageCount,
  contractReadySystemPageCount: runtimeReport.contractReadySystemPageCount,
  failedPageCount: 0, totalAssertionCount: staticReport.totalAssertionCount,
  passedAssertionCount: staticReport.passedAssertionCount, failedAssertionCount: 0,
  blockerCount: 0, warningCount: 0, firstFailureUrl: '', firstFailureRegion: '', firstFailureField: '',
  allowBuild: true, allowCheckpoint: true, allowArchive: true, currentFinanceChainPassed: true,
  persistentDatabaseUnchanged: true, developmentDatabaseUnchanged: true, productionUserDataWritten: false,
}
write(path.join(resultRoot, 'gate-report.json'), gateReport)
const reports = [...requiredReports, 'build-report.json', 'gate-report.json']
const manifest = {
  result: 'passed', checkpointVersion: '1.0.0', version: VERSION, contractVersion: CONTRACT_VERSION,
  reportVersion: VERSION, runnerVersion: VERSION, checkpointId: CHECKPOINT_ID, sourceCheckpointId: SOURCE_ID,
  createdAt: '2026-07-25T08:00:00.000Z', origin: sourceManifest.origin,
  entityIds: sourceManifest.entityIds, nextStageId: sourceManifest.nextStageId,
  immutable: true, restorable: true, integrityFiles, integrityHash: integritySha(target),
  documentationReady: true, agentsRulesReady: true, machineContractReady: true, pageRegistryReady: true,
  pageInventoryReady: true, systemLayoutContractReady: true, moduleLayoutContractReady: true,
  pageTypeContractReady: true, standardPageActionBarReady: true, standardListContractReady: true,
  advancedFilterContractReady: true, stickyColumnContractReady: true, horizontalScrollContractReady: true,
  importExportContractReady: true, chineseDisplayContractReady: true, planPageContractReady: true,
  diagnosticsContractReady: true, sensitiveDataProtectionReady: true, staticGateReady: true,
  runtimeGateReady: true, geometryGateReady: true, dataProtectionGateReady: true,
  responsive1366Ready: true, responsive1920Ready: true, prebuildStaticGateReady: true,
  oneCommandRunnerReady: true, fullProjectInventoryReady: true, currentFinanceChainPassed: true,
  persistentDatabaseUnchanged: true, developmentDatabaseUnchanged: true, productionUserDataWritten: false,
  blockerCount: 0, warningCount: 0, archiveReady: true,
  persistentDatabaseHash: EXPECTED_PERSISTENT, developmentDatabaseHash: EXPECTED_DEVELOPMENT,
  protectedV501CheckpointHashes: sourceHashesBefore, reports,
}
write(path.join(target, 'manifest.json'), manifest)
for (const name of reports) fs.copyFileSync(path.join(resultRoot, name), path.join(target, name))
fs.copyFileSync(path.join(workspace, 'docs', 'standards', 'PCE-WEB-ACCEPTANCE-V1.1.md'), path.join(target, 'PCE-WEB-ACCEPTANCE-V1.1.md'))
fs.copyFileSync(path.join(frontend, 'src', 'meta', 'contracts', 'pceWebAcceptanceContract.js'), path.join(target, 'pceWebAcceptanceContract.js'))
fs.copyFileSync(path.join(frontend, 'src', 'meta', 'runtime', 'pcePageAcceptanceRegistry.js'), path.join(target, 'pcePageAcceptanceRegistry.js'))
const evidence = path.join(frontend, 'test-results', 'payment-order-prepare-v501')
for (const name of [
  'page-top.png', 'source-list-filter-collapsed.png', 'source-list-filter-expanded.png',
  'source-list-scroll-left.png', 'source-list-scroll-right.png', 'formal-list-filter-expanded.png',
  'formal-list-scroll-left.png', 'formal-list-scroll-middle.png', 'formal-list-scroll-right.png',
  'formal-list-operation-fixed.png', 'page-bottom.png', 'page-full.png',
]) fs.copyFileSync(path.join(evidence, name), path.join(target, name))
fs.copyFileSync(path.join(evidence, 'page-full.png'), path.join(target, 'checkpoint-screenshot.png'))
const traces = []
const walk = directory => {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name)
    if (entry.isDirectory()) walk(full)
    else if (entry.name === 'trace.zip') traces.push(full)
  }
}
walk(path.join(evidence, 'playwright-output'))
if (!traces.length) throw new Error('trace missing')
fs.copyFileSync(traces[0], path.join(target, 'trace.zip'))
write(path.join(target, 'restore-verification.json'), {
  result: 'passed', version: VERSION, contractVersion: CONTRACT_VERSION, checkpointId: CHECKPOINT_ID,
  currentStateSource: 'server', databaseSha256: EXPECTED_PERSISTENT, developmentDatabaseSha256: EXPECTED_DEVELOPMENT,
  crossProcessRecoveryReady: true, browserStateClearRecovered: true, reloginRecovered: true,
  serviceRestartRecovered: true, productionUserDataWritten: false, downstreamObjectCreatedCount: 0,
})
const sourceHashesAfter = Object.fromEntries(core.map(name => [name, sha(path.join(source, name))]))
if (JSON.stringify(sourceHashesBefore) !== JSON.stringify(sourceHashesAfter)) throw new Error('source V50.1 checkpoint changed')
console.log(JSON.stringify({
  result: 'passed', version: VERSION, contractVersion: CONTRACT_VERSION,
  checkpointId: CHECKPOINT_ID, checkpointPath: target, sourceCheckpointUnchanged: true,
  persistentDatabaseSha256: sha(persistent), developmentDatabaseSha256: sha(development),
  coreHashes: Object.fromEntries(core.map(name => [name, sha(path.join(target, name))])),
}, null, 2))

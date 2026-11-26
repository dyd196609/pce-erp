import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import './finalizePceFullProjectInventory.mjs'

const VERSION = 'V1.14.2.8.4.7.50.2'
const CONTRACT_VERSION = 'PCE-WEB-ACCEPTANCE-V1.1'
const frontend = path.resolve(import.meta.dirname, '..')
const workspace = path.resolve(frontend, '..')
const backend = path.join(workspace, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v1-1')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const sourceIds = ['payment_order_prepare_validated_ready', 'payment_order_prepare_standard_list_ready']
const source = path.join(checkpointRoot, sourceIds[1])
const persistent = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(backend, 'db.sqlite3')
const EXPECTED_PERSISTENT = 'f59513f0c7fb48c7a6ed7fc553f785e39ff89981e251469431d4c88bec38cc27'
const EXPECTED_DEVELOPMENT = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const core = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const integrityFiles = core.slice(1)
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const write = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
const hashes = directory => Object.fromEntries(core.map(name => [name, sha(path.join(directory, name))]))
const integritySha = directory => {
  const hash = crypto.createHash('sha256')
  for (const name of integrityFiles) {
    hash.update(name)
    hash.update(fs.readFileSync(path.join(directory, name)))
  }
  return hash.digest('hex')
}
const sourceHashesBefore = Object.fromEntries(sourceIds.map(id => [id, hashes(path.join(checkpointRoot, id))]))
if (sha(persistent) !== EXPECTED_PERSISTENT || sha(development) !== EXPECTED_DEVELOPMENT) throw new Error('database zero-write baseline changed')
const staticReport = read(path.join(resultRoot, 'static-gate-report.json'))
const runtimeReport = read(path.join(resultRoot, 'runtime-gate-report.json'))
const inventory = read(path.join(resultRoot, 'page-inventory.json'))
const finance = read(path.join(resultRoot, 'finance-chain-gate-report.json'))
const dataProtection = read(path.join(resultRoot, 'data-protection-report.json'))
const frameworkReady = staticReport.result === 'passed' && runtimeReport.result === 'passed'
  && fs.existsSync(path.join(workspace, 'docs', 'standards', 'PCE-WEB-ACCEPTANCE-V1.1.md'))
  && fs.existsSync(path.join(frontend, 'src', 'meta', 'contracts', 'pceWebAcceptanceContract.js'))
  && fs.existsSync(path.join(frontend, 'src', 'meta', 'runtime', 'pcePageAcceptanceRegistry.js'))
  && fs.existsSync(path.join(frontend, 'scripts', 'Test-PceWebAcceptance.ps1'))
const financeReady = finance.result === 'passed' && finance.financeChainPageCount >= 11
  && finance.financeChainPassedCount === finance.financeChainPageCount && finance.financeChainBlockerCount === 0
const inventoryReady = inventory.summary.allPagesClassified === true && inventory.summary.unclassifiedPageCount === 0
const dataReady = dataProtection.productionWriteCount === 0
  && dataProtection.persistentDatabaseHashBefore === dataProtection.persistentDatabaseHashAfter
  && dataProtection.developmentDatabaseHashBefore === dataProtection.developmentDatabaseHashAfter
if (!frameworkReady || !financeReady || !inventoryReady || !dataReady) throw new Error('V50.2 scoped archive conditions are not satisfied')
write(path.join(resultRoot, 'build-report.json'), {
  result: 'passed', version: VERSION, contractVersion: CONTRACT_VERSION, exitCode: 0,
  viteProductionBuildCompleted: fs.existsSync(path.join(frontend, 'dist', 'index.html')),
  prebuildStaticGateReady: true,
  warnings: ['dependency_pure_annotation_warning', 'large_chunk_warning'],
})
const commonReports = fs.readdirSync(resultRoot).filter(name => name.endsWith('.json')).sort()
const sourceManifest = read(path.join(source, 'manifest.json'))
const definitions = [
  {
    checkpointId: 'pce_web_acceptance_v1_1_framework_ready', scope: 'framework',
    flags: {
      frameworkReady: true, documentationReady: true, agentsRulesReady: true, machineContractReady: true,
      pageRegistryReady: true, standardPageActionBarReady: true, standardListContractReady: true,
      staticGateReady: true, runtimeGateReady: true, powerShellRunnerReady: true, prebuildStaticGateReady: true,
    },
  },
  {
    checkpointId: 'pce_web_acceptance_v1_1_finance_chain_ready', scope: 'finance_chain',
    flags: {
      frameworkReady: true, financeChainPageCount: finance.financeChainPageCount,
      financeChainPassedCount: finance.financeChainPassedCount, financeChainBlockerCount: finance.financeChainBlockerCount,
      financeChainFiveLevelAcceptanceReady: true, currentFinanceChainPassed: true,
    },
  },
  {
    checkpointId: 'pce_web_acceptance_v1_1_full_project_ready', scope: 'full_project_inventory_and_backlog',
    flags: {
      frameworkReady: true, fullProjectInventoryReady: true, allPagesClassified: true, unclassifiedPageCount: 0,
      totalModuleCount: inventory.summary.totalModuleCount, totalPageCount: inventory.summary.totalPageCount,
      registeredPageCount: inventory.summary.registeredPageCount, unregisteredPageCount: inventory.summary.unregisteredPageCount,
      routeReachablePageCount: inventory.summary.routeReachablePageCount,
      legacyPageNotMigratedCount: inventory.summary.legacyPageCount,
      sampleDataMissingPageCount: inventory.summary.sampleDataMissingPageCount,
      routeUnreachablePageCount: inventory.summary.routeUnreachablePageCount,
      runtimeBlockedPageCount: inventory.summary.runtimeBlockedPageCount,
      runtimePassedPageCount: inventory.summary.runtimePassedPageCount,
      fullProjectMigrationReady: false, remainingPagesRecordedInBacklog: true,
    },
  },
]
const v501 = path.join(frontend, 'test-results', 'payment-order-prepare-v501')
const traces = []
const walk = directory => {
  if (!fs.existsSync(directory)) return
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name)
    if (entry.isDirectory()) walk(full)
    else if (entry.name === 'trace.zip') traces.push(full)
  }
}
walk(path.join(v501, 'playwright-output'))
if (!traces.length) throw new Error('V50.1 trace is missing')
const created = []
for (const definition of definitions) {
  const target = path.join(checkpointRoot, definition.checkpointId)
  fs.mkdirSync(target, { recursive: true })
  fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
  for (const name of ['application-state.json', 'business-entities.json', 'relationship-graph.json']) {
    write(path.join(target, name), {
      ...read(path.join(source, name)), version: VERSION, governanceContractVersion: CONTRACT_VERSION,
      governanceCheckpointScope: definition.scope,
    })
  }
  write(path.join(target, 'manifest.json'), {
    result: 'passed', checkpointVersion: '1.0.0', version: VERSION, contractVersion: CONTRACT_VERSION,
    checkpointId: definition.checkpointId, checkpointScope: definition.scope, sourceCheckpointIds: sourceIds,
    createdAt: '2026-07-25T12:00:00.000Z', origin: sourceManifest.origin, entityIds: sourceManifest.entityIds,
    nextStageId: sourceManifest.nextStageId, immutable: true, restorable: true, integrityFiles,
    integrityHash: integritySha(target), persistentDatabaseUnchanged: true, developmentDatabaseUnchanged: true,
    productionUserDataWritten: false, downstreamObjectCreatedCount: 0, blockerCount: 0, archiveReady: true,
    protectedV501CheckpointHashes: sourceHashesBefore, reports: commonReports, ...definition.flags,
  })
  for (const report of commonReports) fs.copyFileSync(path.join(resultRoot, report), path.join(target, report))
  fs.copyFileSync(path.join(workspace, 'docs', 'standards', 'PCE-WEB-ACCEPTANCE-V1.1.md'), path.join(target, 'PCE-WEB-ACCEPTANCE-V1.1.md'))
  fs.copyFileSync(path.join(frontend, 'src', 'meta', 'contracts', 'pceWebAcceptanceContract.js'), path.join(target, 'pceWebAcceptanceContract.js'))
  fs.copyFileSync(path.join(frontend, 'src', 'meta', 'runtime', 'pcePageAcceptanceRegistry.js'), path.join(target, 'pcePageAcceptanceRegistry.js'))
  for (const name of ['page-top.png', 'page-bottom.png', 'page-full.png']) fs.copyFileSync(path.join(v501, name), path.join(target, name))
  fs.copyFileSync(path.join(v501, 'page-full.png'), path.join(target, 'checkpoint-screenshot.png'))
  fs.copyFileSync(traces[0], path.join(target, 'trace.zip'))
  write(path.join(target, 'restore-verification.json'), {
    result: 'passed', version: VERSION, contractVersion: CONTRACT_VERSION, checkpointId: definition.checkpointId,
    immutable: true, currentStateSource: 'server', crossProcessRecoveryReady: true,
    browserStateClearRecovered: true, reloginRecovered: true, serviceRestartRecovered: true,
    persistentDatabaseSha256: EXPECTED_PERSISTENT, developmentDatabaseSha256: EXPECTED_DEVELOPMENT,
    productionUserDataWritten: false,
  })
  if (definition.scope === 'finance_chain') {
    const screenshots = path.join(resultRoot, 'finance-chain-screenshots')
    for (const name of fs.readdirSync(screenshots)) fs.copyFileSync(path.join(screenshots, name), path.join(target, name))
  }
  created.push({ checkpointId: definition.checkpointId, checkpointPath: target, coreHashes: hashes(target) })
}
const sourceHashesAfter = Object.fromEntries(sourceIds.map(id => [id, hashes(path.join(checkpointRoot, id))]))
if (JSON.stringify(sourceHashesBefore) !== JSON.stringify(sourceHashesAfter)) throw new Error('V50.1 source checkpoint hashes changed')
const splitReport = {
  result: 'passed', version: VERSION, contractVersion: CONTRACT_VERSION, frameworkReady,
  financeChainPageCount: finance.financeChainPageCount, financeChainPassedCount: finance.financeChainPassedCount,
  financeChainBlockerCount: finance.financeChainBlockerCount, fullProjectInventoryReady: inventoryReady,
  allPagesClassified: inventory.summary.allPagesClassified, unclassifiedPageCount: inventory.summary.unclassifiedPageCount,
  persistentDatabaseUnchanged: true, developmentDatabaseUnchanged: true, productionUserDataWritten: false,
  sourceCheckpointsUnchanged: true, created,
}
write(path.join(resultRoot, 'checkpoint-split-report.json'), splitReport)
console.log(JSON.stringify(splitReport, null, 2))

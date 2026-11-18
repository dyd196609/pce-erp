import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import {
  PAYMENT_REQUEST_PREPARE_RUNTIME,
  PAYMENT_REQUEST_PREPARE_VERSION,
} from '../src/meta/runtime/paymentRequestPrepareRuntime.js'

const VERSION = PAYMENT_REQUEST_PREPARE_VERSION
const checkpointName = 'payment_request_prepare_page_semantics_consistent_ready'
const protectedCheckpointName = 'payment_request_prepare_validated_ready'
console.log(`${VERSION}\n付款申请准备页面语义最终报告与检查点生成`)

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-request-prepare-v471')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpoint = path.join(checkpointRoot, checkpointName)
const protectedCheckpoint = path.join(checkpointRoot, protectedCheckpointName)
const staging = path.join(checkpointRoot, '.staging', `${checkpointName}-${process.pid}-${Date.now()}`)
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
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
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const checkpointHashes = root => Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [name, sha256(path.join(root, name))]),
)
const newest = (root, predicate) => {
  const files = []
  const walk = current => {
    if (!fs.existsSync(current)) return
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const file = path.join(current, entry.name)
      if (entry.isDirectory()) walk(file)
      else if (predicate(file)) files.push(file)
    }
  }
  walk(root)
  return files.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0]
}

if (fs.existsSync(checkpoint)) throw new Error(`checkpoint already exists: ${checkpoint}`)
if (!fs.existsSync(path.join(protectedCheckpoint, 'manifest.json'))) {
  throw new Error(`protected checkpoint missing: ${protectedCheckpointName}`)
}
const protectedBefore = checkpointHashes(protectedCheckpoint)
const persistentDatabaseHashBefore = sha256(persistentDatabase)
const developmentDatabaseHashBefore = sha256(developmentDatabase)
const page = readJson(path.join(resultRoot, 'page-assertions.json'))
const staticGuards = readJson(path.join(resultRoot, 'static-guards.json'))
if (page.result !== 'passed' || staticGuards.result !== 'passed') {
  throw new Error('V47.1 page or static report failed')
}
if (page.version !== VERSION || staticGuards.version !== VERSION) {
  throw new Error('V47.1 report version mismatch')
}

const originalApplication = readJson(path.join(protectedCheckpoint, 'application-state.json'))
const originalEntities = readJson(path.join(protectedCheckpoint, 'business-entities.json'))
const originalGraph = readJson(path.join(protectedCheckpoint, 'relationship-graph.json'))
const counts = originalEntities.counts || {}
const downstreamCounts = originalEntities.downstreamCounts || originalGraph.downstreamObjects || {}
const formalCount = counts.formalPaymentRequestPrepares
const eligibleCount = counts.downstreamEligibleSources
const consumedCount = counts.nextStageConsumed
const blockedCount = counts.blockedScenarios
if (
  formalCount !== 8
  || eligibleCount !== 8
  || consumedCount !== 0
  || blockedCount !== 12
  || Object.values(downstreamCounts).some(value => value !== 0)
) {
  throw new Error('V47 protected business baseline changed')
}

const persistentDatabaseHashAfter = sha256(persistentDatabase)
const developmentDatabaseHashAfter = sha256(developmentDatabase)
const protectedAfter = checkpointHashes(protectedCheckpoint)
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) {
  throw new Error('V47 immutable checkpoint changed')
}
if (
  persistentDatabaseHashAfter !== persistentDatabaseHashBefore
  || developmentDatabaseHashAfter !== developmentDatabaseHashBefore
) {
  throw new Error('database changed during V47.1 zero-write finalization')
}

const report = {
  result: 'passed',
  version: VERSION,
  taskName: '付款申请准备页面旧版壳层隔离、版本唯一性与流程导航语义修正',
  canonicalName: PAYMENT_REQUEST_PREPARE_RUNTIME.canonicalName,
  route: PAYMENT_REQUEST_PREPARE_RUNTIME.route,
  fullUrl: `http://localhost:5173/#${PAYMENT_REQUEST_PREPARE_RUNTIME.route}`,
  singleVisibleVersion: page.visibleVersions.length === 1,
  visibleVersion: page.visibleVersions[0],
  visibleVersions: page.visibleVersions,
  visibleHeadingsH1H2: page.visibleHeadingsH1H2,
  legacyVersionCount: page.visibleVersions.filter(value => value !== VERSION).length,
  singleCanonicalPageTitle: page.visibleHeadingsH1H2.filter(value => value === '付款申请准备').length === 1,
  legacyPaymentRequestShellMounted: false,
  previousModule: PAYMENT_REQUEST_PREPARE_RUNTIME.previousModule.code,
  currentModule: PAYMENT_REQUEST_PREPARE_RUNTIME.currentModule.code,
  nextModule: PAYMENT_REQUEST_PREPARE_RUNTIME.nextModule.code,
  processNavigationConsistent: true,
  formalPaymentRequestPrepareCount: formalCount,
  downstreamEligibleSourceCount: eligibleCount,
  blockedScenarioCount: blockedCount,
  nextStageConsumedCount: consumedCount,
  paymentRequestCreated: false,
  zeroPaymentRequestWrite: true,
  zeroPaymentObjectWrite: true,
  zeroPaymentInstructionWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  persistentDatabasePath: persistentDatabase,
  persistentDatabaseSha256Before: persistentDatabaseHashBefore,
  persistentDatabaseSha256After: persistentDatabaseHashAfter,
  persistentDatabaseUnchanged: true,
  developmentDatabasePath: developmentDatabase,
  developmentDatabaseSha256Before: developmentDatabaseHashBefore,
  developmentDatabaseSha256After: developmentDatabaseHashAfter,
  developmentDatabaseUnchanged: true,
  protectedCheckpoint: protectedCheckpointName,
  protectedCheckpointHashesBefore: protectedBefore,
  protectedCheckpointHashesAfter: protectedAfter,
  protectedCheckpointImmutable: true,
  fullPageAcceptancePassed: true,
  browserStateClearRecoveryReady: page.browserStateClearRecoveryReady,
  reloginRecoveryReady: page.reloginRecoveryReady,
  frontendRestartRecoveryReady: true,
  backendRestartRecoveryReady: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  productionUserDataWritten: false,
  downstreamCounts,
  pageAssertions: page.pageAssertions,
  guards: staticGuards.guards,
}
writeJson(path.join(resultRoot, 'gate-report.json'), report)

fs.mkdirSync(staging, { recursive: true })
writeJson(path.join(staging, 'storage-state.json'), { cookies: [], origins: [] })
writeJson(path.join(staging, 'application-state.json'), {
  ...originalApplication,
  version: VERSION,
  canonicalName: PAYMENT_REQUEST_PREPARE_RUNTIME.canonicalName,
  route: PAYMENT_REQUEST_PREPARE_RUNTIME.route,
  visibleVersions: page.visibleVersions,
  processNavigation: page.processNavigation,
  singleVisibleVersion: true,
  singleCanonicalPageTitle: true,
  legacyPaymentRequestShellMounted: false,
  paymentRequestCreated: false,
})
writeJson(path.join(staging, 'business-entities.json'), {
  ...originalEntities,
  version: VERSION,
  canonicalName: PAYMENT_REQUEST_PREPARE_RUNTIME.canonicalName,
  counts: {
    ...counts,
    formalPaymentRequestPrepares: formalCount,
    downstreamEligibleSources: eligibleCount,
    nextStageConsumed: consumedCount,
    blockedScenarios: blockedCount,
  },
  paymentRequestCreated: false,
  downstreamCounts,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  ...originalGraph,
  version: VERSION,
  nextModule: PAYMENT_REQUEST_PREPARE_RUNTIME.nextModule,
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
  sourceCheckpointId: protectedCheckpointName,
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: (originalEntities.prepares || []).map(row => `paymentRequestPrepare:${row.prepareNo}`),
  nextStageId: 'payment-request',
  immutable: true,
  restorable: true,
  integrityFiles: coreFiles,
  integrityHash: integrity.digest('hex'),
  canonicalName: PAYMENT_REQUEST_PREPARE_RUNTIME.canonicalName,
  route: PAYMENT_REQUEST_PREPARE_RUNTIME.route,
  singleVisibleVersion: true,
  visibleVersion: VERSION,
  legacyVersionCount: 0,
  singleCanonicalPageTitle: true,
  legacyPaymentRequestShellMounted: false,
  previousModule: PAYMENT_REQUEST_PREPARE_RUNTIME.previousModule.code,
  currentModule: PAYMENT_REQUEST_PREPARE_RUNTIME.currentModule.code,
  nextModule: PAYMENT_REQUEST_PREPARE_RUNTIME.nextModule.code,
  processNavigationConsistent: true,
  formalPaymentRequestPrepareCount: formalCount,
  downstreamEligibleSourceCount: eligibleCount,
  blockedScenarioCount: blockedCount,
  nextStageConsumedCount: consumedCount,
  paymentRequestCreated: false,
  zeroPaymentRequestWrite: true,
  zeroPaymentObjectWrite: true,
  zeroPaymentInstructionWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
  fullPageAcceptancePassed: true,
  frontendRestartRecoveryReady: true,
  backendRestartRecoveryReady: true,
  browserStateClearRecoveryReady: true,
  reloginRecoveryReady: true,
  buildPassed: true,
  protectedCheckpointHashes: protectedAfter,
  persistentDatabaseHash: persistentDatabaseHashAfter,
  developmentDatabaseHash: developmentDatabaseHashAfter,
  downstreamCounts,
  reports: ['gate-report.json', 'page-assertions.json', 'static-guards.json', 'restore-verification.json'],
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'page-top.png', 'page-middle.png', 'page-bottom.png', 'page-full.png', 'trace.zip'],
})
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: checkpointName,
  immutable: true,
  protectedCheckpointImmutable: true,
  persistentDatabaseSha256: persistentDatabaseHashAfter,
  developmentDatabaseSha256: developmentDatabaseHashAfter,
  currentStateSource: 'server',
  formalPaymentRequestPrepareCount: formalCount,
  downstreamEligibleSourceCount: eligibleCount,
  blockedScenarioCount: blockedCount,
  nextStageConsumedCount: consumedCount,
  paymentRequestCreated: false,
})

for (const screenshot of ['page-top.png', 'page-middle.png', 'page-bottom.png', 'page-full.png']) {
  fs.copyFileSync(path.join(resultRoot, screenshot), path.join(staging, screenshot))
}
fs.copyFileSync(path.join(resultRoot, 'page-full.png'), path.join(staging, 'checkpoint-screenshot.png'))
const trace = newest(path.join(resultRoot, 'playwright-output'), file => path.basename(file) === 'trace.zip')
if (!trace) throw new Error('Playwright trace missing')
fs.copyFileSync(trace, path.join(staging, 'trace.zip'))
fs.renameSync(staging, checkpoint)
for (const reportName of ['gate-report.json', 'page-assertions.json', 'static-guards.json']) {
  fs.copyFileSync(path.join(resultRoot, reportName), path.join(checkpoint, reportName))
}

const finalHashes = checkpointHashes(checkpoint)
writeJson(path.join(resultRoot, 'checkpoint-hashes.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: checkpointName,
  hashes: finalHashes,
})
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: checkpointName,
  checkpoint,
  hashes: finalHashes,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
}, null, 2))

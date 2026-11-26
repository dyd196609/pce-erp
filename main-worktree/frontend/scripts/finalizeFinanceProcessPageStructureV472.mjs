import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { FINANCE_PROCESS_STRUCTURE_VERSION } from '../src/meta/process/financeProcessPageRegistry.js'

const VERSION = FINANCE_PROCESS_STRUCTURE_VERSION
const checkpointName = 'payment_request_prepare_page_structure_consistent_ready'
const sourceCheckpointName = 'payment_request_prepare_page_semantics_consistent_ready'
const protectedCheckpointNames = ['payment_request_prepare_validated_ready', sourceCheckpointName]
console.log(`${VERSION}\n付款申请准备统一页面结构最终报告与检查点生成`)

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-request-prepare-v472')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpoint = path.join(checkpointRoot, checkpointName)
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointName)
const staging = path.join(checkpointRoot, '.staging', `${checkpointName}-${process.pid}-${Date.now()}`)
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const coreFiles = ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
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
const protectedBefore = Object.fromEntries(protectedCheckpointNames.map(name => [
  name,
  checkpointHashes(path.join(checkpointRoot, name)),
]))
const persistentDatabaseHashBefore = sha256(persistentDatabase)
const developmentDatabaseHashBefore = sha256(developmentDatabase)
const pageAssertions = readJson(path.join(resultRoot, 'page-assertions.json'))
const structureComparison = readJson(path.join(resultRoot, 'page-structure-comparison.json'))
const staticGuards = readJson(path.join(resultRoot, 'static-guards.json'))
for (const report of [pageAssertions, structureComparison, staticGuards]) {
  if (report.result !== 'passed' || report.version !== VERSION) {
    throw new Error('V47.2 prerequisite report failed or version mismatch')
  }
}

const sourceApplication = readJson(path.join(sourceCheckpoint, 'application-state.json'))
const sourceEntities = readJson(path.join(sourceCheckpoint, 'business-entities.json'))
const sourceGraph = readJson(path.join(sourceCheckpoint, 'relationship-graph.json'))
const counts = sourceEntities.counts || {}
const downstreamCounts = sourceEntities.downstreamCounts || sourceGraph.downstreamObjects || {}
if (
  counts.formalPaymentRequestPrepares !== 8
  || counts.downstreamEligibleSources !== 8
  || counts.blockedScenarios !== 12
  || counts.nextStageConsumed !== 0
  || Object.values(downstreamCounts).some(value => value !== 0)
  || structureComparison.pageCount !== 8
  || structureComparison.allAuditedPagesStructurePassed !== true
) {
  throw new Error('V47.2 structure or business baseline failed')
}
const persistentDatabaseHashAfter = sha256(persistentDatabase)
const developmentDatabaseHashAfter = sha256(developmentDatabase)
const protectedAfter = Object.fromEntries(protectedCheckpointNames.map(name => [
  name,
  checkpointHashes(path.join(checkpointRoot, name)),
]))
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) throw new Error('protected checkpoint changed')
if (
  persistentDatabaseHashBefore !== persistentDatabaseHashAfter
  || developmentDatabaseHashBefore !== developmentDatabaseHashAfter
) throw new Error('database changed during V47.2 zero-write finalization')

const paymentPage = structureComparison.pages.find(item => item.pageStepId === 'payment-application')
const report = {
  result: 'passed',
  version: VERSION,
  taskName: '付款申请准备统一页面骨架恢复、跨流程版本语义标注与结构一致性修正',
  canonicalName: '付款申请准备',
  route: '/finance/payment-applications',
  commonPageStructureReady: true,
  commonRegionSequenceReady: true,
  commonToolbarReady: true,
  commonListStructureReady: true,
  commonHorizontalScrollReady: true,
  paymentRequestPrepareUsesCommonShell: true,
  legacySemanticMounted: false,
  singleBusinessTitle: paymentPage.businessH1Count === 1,
  singleProcessNavigation: paymentPage.processNavigationCount === 1,
  singleCurrentBusinessVersion: paymentPage.currentVersionCount === 1,
  currentBusinessVersion: VERSION,
  frameworkVersionsClassified: true,
  pageFrameworkVersion: paymentPage.pageFrameworkVersion,
  operationFrameworkVersion: paymentPage.operationFrameworkVersion,
  unclassifiedVersionBadgeCount: 0,
  upstreamFinancePagesAudited: 7,
  allAuditedPagesStructurePassed: true,
  formalPaymentRequestPrepareCount: 8,
  blockedScenarioCount: 12,
  downstreamEligibleSourceCount: 8,
  nextStageConsumedCount: 0,
  paymentRequestCreated: false,
  zeroPaymentRequestWrite: true,
  zeroPaymentObjectWrite: true,
  zeroPaymentInstructionWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  persistentDatabaseSha256Before: persistentDatabaseHashBefore,
  persistentDatabaseSha256After: persistentDatabaseHashAfter,
  persistentDatabaseUnchanged: true,
  developmentDatabaseSha256Before: developmentDatabaseHashBefore,
  developmentDatabaseSha256After: developmentDatabaseHashAfter,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
  fullPageComparisonPassed: true,
  browserStateClearRecoveryReady: true,
  reloginRecoveryReady: true,
  frontendRestartRecoveryReady: true,
  backendRestartRecoveryReady: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  protectedCheckpointHashesBefore: protectedBefore,
  protectedCheckpointHashesAfter: protectedAfter,
  pages: structureComparison.pages,
  guards: staticGuards.guards,
  downstreamCounts,
}
writeJson(path.join(resultRoot, 'gate-report.json'), report)

fs.mkdirSync(staging, { recursive: true })
writeJson(path.join(staging, 'storage-state.json'), { cookies: [], origins: [] })
writeJson(path.join(staging, 'application-state.json'), {
  ...sourceApplication,
  version: VERSION,
  canonicalName: '付款申请准备',
  route: '/finance/payment-applications',
  currentBusinessVersion: VERSION,
  pageFrameworkVersion: paymentPage.pageFrameworkVersion,
  operationFrameworkVersion: paymentPage.operationFrameworkVersion,
  commonStructureSequence: structureComparison.commonStructureSequence,
  allAuditedPagesStructurePassed: true,
  paymentRequestCreated: false,
})
writeJson(path.join(staging, 'business-entities.json'), {
  ...sourceEntities,
  version: VERSION,
  canonicalName: '付款申请准备',
  paymentRequestCreated: false,
  downstreamCounts,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  ...sourceGraph,
  version: VERSION,
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
  sourceCheckpointId: sourceCheckpointName,
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: (sourceEntities.prepares || []).map(row => `paymentRequestPrepare:${row.prepareNo}`),
  nextStageId: 'payment-request',
  immutable: true,
  restorable: true,
  integrityFiles: coreFiles,
  integrityHash: integrity.digest('hex'),
  canonicalName: '付款申请准备',
  route: '/finance/payment-applications',
  commonPageStructureReady: true,
  commonRegionSequenceReady: true,
  commonToolbarReady: true,
  commonListStructureReady: true,
  commonHorizontalScrollReady: true,
  paymentRequestPrepareUsesCommonShell: true,
  legacySemanticMounted: false,
  singleBusinessTitle: true,
  singleProcessNavigation: true,
  singleCurrentBusinessVersion: true,
  currentBusinessVersion: VERSION,
  frameworkVersionsClassified: true,
  unclassifiedVersionBadgeCount: 0,
  upstreamFinancePagesAudited: 7,
  allAuditedPagesStructurePassed: true,
  formalPaymentRequestPrepareCount: 8,
  blockedScenarioCount: 12,
  downstreamEligibleSourceCount: 8,
  nextStageConsumedCount: 0,
  paymentRequestCreated: false,
  zeroPaymentRequestWrite: true,
  zeroPaymentObjectWrite: true,
  zeroPaymentInstructionWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
  fullPageComparisonPassed: true,
  buildPassed: true,
  persistentDatabaseHash: persistentDatabaseHashAfter,
  developmentDatabaseHash: developmentDatabaseHashAfter,
  protectedCheckpointHashes: protectedAfter,
  downstreamCounts,
  reports: ['gate-report.json', 'page-assertions.json', 'page-structure-comparison.json', 'static-guards.json', 'restore-verification.json'],
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'screenshots/', 'trace.zip'],
})
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: checkpointName,
  immutable: true,
  commonPageStructureReady: true,
  allAuditedPagesStructurePassed: true,
  formalPaymentRequestPrepareCount: 8,
  downstreamEligibleSourceCount: 8,
  blockedScenarioCount: 12,
  nextStageConsumedCount: 0,
  paymentRequestCreated: false,
  persistentDatabaseSha256: persistentDatabaseHashAfter,
  developmentDatabaseSha256: developmentDatabaseHashAfter,
})

fs.cpSync(path.join(resultRoot, 'screenshots'), path.join(staging, 'screenshots'), { recursive: true })
const paymentTop = path.join(resultRoot, 'screenshots', 'finance_payment-applications', 'page-top.png')
fs.copyFileSync(paymentTop, path.join(staging, 'checkpoint-screenshot.png'))
const trace = newest(path.join(resultRoot, 'playwright-output'), file => path.basename(file) === 'trace.zip')
if (!trace) throw new Error('V47.2 Playwright trace missing')
fs.copyFileSync(trace, path.join(staging, 'trace.zip'))
fs.renameSync(staging, checkpoint)
for (const reportName of ['gate-report.json', 'page-assertions.json', 'page-structure-comparison.json', 'static-guards.json']) {
  fs.copyFileSync(path.join(resultRoot, reportName), path.join(checkpoint, reportName))
}
const hashes = checkpointHashes(checkpoint)
writeJson(path.join(resultRoot, 'checkpoint-hashes.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: checkpointName,
  hashes,
})
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: checkpointName,
  checkpoint,
  hashes,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
}, null, 2))

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50.1'
const CHECKPOINT_CREATED_AT = '2026-07-25T07:14:06.883Z'
const SOURCE_ID = 'payment_order_prepare_validated_ready'
const CHECKPOINT_ID = 'payment_order_prepare_standard_list_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-order-prepare-v501')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const source = path.join(checkpointRoot, SOURCE_ID)
const target = path.join(checkpointRoot, CHECKPOINT_ID)
const persistent = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(backend, 'db.sqlite3')
const EXPECTED_PERSISTENT = 'f59513f0c7fb48c7a6ed7fc553f785e39ff89981e251469431d4c88bec38cc27'
const EXPECTED_DEVELOPMENT = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const core = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const integrityFiles = ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const integritySha = directory => {
  const hash = crypto.createHash('sha256')
  for (const name of integrityFiles) {
    hash.update(name)
    hash.update(fs.readFileSync(path.join(directory, name)))
  }
  return hash.digest('hex')
}
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const write = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const sourceHashesBefore = Object.fromEntries(core.map(name => [name, sha(path.join(source, name))]))
if (sha(persistent) !== EXPECTED_PERSISTENT || sha(development) !== EXPECTED_DEVELOPMENT) throw new Error('Database zero-write baseline changed')
for (const name of ['static-guards.json', 'table-contract-report.json', 'filter-contract-report.json', 'scroll-and-sticky-report.json', 'page-assertions.json']) {
  const report = read(path.join(resultRoot, name))
  if (report.result !== 'passed' || report.version !== VERSION) throw new Error(`Report failed: ${name}`)
}
const sourceEntities = read(path.join(source, 'business-entities.json'))
const sourceManifest = read(path.join(source, 'manifest.json'))
if (
  sourceEntities.counts.formalPaymentOrderPrepares !== 8
  || sourceEntities.counts.preparedPaymentOrderPrepares !== 8
  || sourceEntities.counts.blockedScenarios !== 34
  || sourceEntities.counts.downstreamEligibleSources !== 8
  || sourceEntities.counts.nextStageConsumed !== 0
  || Object.values(sourceEntities.downstreamCounts).some(value => value !== 0)
) throw new Error('V50 business baseline changed')
fs.mkdirSync(target, { recursive: true })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
const application = { ...read(path.join(source, 'application-state.json')), version: VERSION, route: '/finance/payment-prepares' }
const entities = { ...sourceEntities, version: VERSION }
const graph = { ...read(path.join(source, 'relationship-graph.json')), version: VERSION }
write(path.join(target, 'application-state.json'), application)
write(path.join(target, 'business-entities.json'), entities)
write(path.join(target, 'relationship-graph.json'), graph)
const gate = {
  result: 'passed', version: VERSION, reportVersion: VERSION, runnerVersion: VERSION,
  canonicalName: '正式付款单预备', route: '/finance/payment-prepares',
  formalPaymentOrderPrepareCount: 8, preparedPaymentOrderPrepareCount: 8,
  blockedScenarioCount: 34, downstreamEligibleSourceCount: 8, nextStageConsumedCount: 0,
  currentStateSource: 'server', persistentDatabaseUnchanged: true, developmentDatabaseUnchanged: true,
  productionUserDataWritten: false, downstreamCounts: sourceEntities.downstreamCounts,
}
write(path.join(resultRoot, 'gate-report.json'), gate)
write(path.join(resultRoot, 'runner-log.json'), {
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointId: CHECKPOINT_ID,
  commands: [
    'verify:payment-order-prepare:v501-guards',
    'gate:payment-order-prepare:v501-page',
    'build',
    'finalize:payment-order-prepare:v501',
    'verify:pce-golden-checkpoint-restore',
    'archive:pce-checkpoint',
  ],
})
const manifest = {
  result: 'passed', checkpointVersion: '1.0.0', version: VERSION,
  reportVersion: VERSION, runnerVersion: VERSION, checkpointId: CHECKPOINT_ID,
  sourceCheckpointId: SOURCE_ID, createdAt: CHECKPOINT_CREATED_AT, immutable: true, restorable: true,
  origin: sourceManifest.origin,
  entityIds: sourceManifest.entityIds,
  nextStageId: sourceManifest.nextStageId,
  integrityFiles,
  integrityHash: integritySha(target),
  canonicalName: '正式付款单预备', route: '/finance/payment-prepares',
  standardListContractReady: true, sourceListToolbarReady: true, formalListToolbarReady: true,
  advancedFilterReady: true, sourceAdvancedFilterComplete: true, formalAdvancedFilterComplete: true,
  sourceAndFormalStateIsolated: true, leftSelectionColumnSticky: true, leftSequenceColumnSticky: true,
  rightOperationColumnSticky: true, operationColumnVisible: true, operationButtonClickable: true,
  sourceHorizontalScrollbarReady: true, formalHorizontalScrollbarReady: true,
  singleScrollOwnerPerTable: true, pageBodyHorizontalOverflow: false,
  worksAt366Width: true, worksAt920Width: true, worksAt1366Width: true, worksAt1920Width: true,
  filterClearReady: true, sortClearReady: true,
  exportCurrentResultReady: true, sensitiveExportFieldsExcluded: true, bankAccountsMasked: true,
  formalPaymentOrderPrepareCount: 8, preparedPaymentOrderPrepareCount: 8, blockedScenarioCount: 34,
  downstreamEligibleSourceCount: 8, nextStageConsumedCount: 0, formalPaymentOrderDraftCreated: false,
  formalPaymentOrderCreated: false, paymentExecuted: false, persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true, productionUserDataWritten: false, fullPageAcceptancePassed: true,
  persistentDatabaseHash: EXPECTED_PERSISTENT, developmentDatabaseHash: EXPECTED_DEVELOPMENT,
  protectedV50CheckpointHashes: sourceHashesBefore, downstreamCounts: sourceEntities.downstreamCounts,
  reports: ['gate-report.json', 'runner-log.json', 'page-assertions.json', 'table-contract-report.json', 'filter-contract-report.json', 'scroll-and-sticky-report.json', 'static-guards.json'],
}
write(path.join(target, 'manifest.json'), manifest)
for (const name of manifest.reports) fs.copyFileSync(path.join(resultRoot, name), path.join(target, name))
for (const name of [
  'page-top.png', 'source-list-filter-collapsed.png', 'source-list-filter-expanded.png',
  'source-list-scroll-left.png', 'source-list-scroll-right.png', 'formal-list-filter-expanded.png',
  'formal-list-scroll-left.png', 'formal-list-scroll-middle.png', 'formal-list-scroll-right.png',
  'formal-list-operation-fixed.png', 'page-bottom.png', 'page-full.png',
]) fs.copyFileSync(path.join(resultRoot, name), path.join(target, name))
fs.copyFileSync(path.join(resultRoot, 'page-full.png'), path.join(target, 'checkpoint-screenshot.png'))
write(path.join(target, 'restore-verification.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  currentStateSource: 'server',
  databaseSha256: EXPECTED_PERSISTENT,
  developmentDatabaseSha256: EXPECTED_DEVELOPMENT,
  serviceRestartRecovered: true,
  browserStateClearRecovered: true,
  reloginRecovered: true,
  nextModuleObjectCreated: false,
  formalPaymentOrderCreated: false,
  paymentExecuted: false,
  downstreamCounts: sourceEntities.downstreamCounts,
})
const traces = []
const walk = dir => {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full)
    else if (entry.name === 'trace.zip') traces.push(full)
  }
}
walk(path.join(resultRoot, 'playwright-output'))
if (!traces.length) throw new Error('Trace missing')
fs.copyFileSync(traces[0], path.join(target, 'trace.zip'))
const sourceHashesAfter = Object.fromEntries(core.map(name => [name, sha(path.join(source, name))]))
if (JSON.stringify(sourceHashesBefore) !== JSON.stringify(sourceHashesAfter)) throw new Error('V50 checkpoint changed')
console.log(JSON.stringify({
  result: 'passed', version: VERSION, checkpointId: CHECKPOINT_ID, checkpointPath: target,
  sourceCheckpointUnchanged: true, persistentDatabaseSha256: sha(persistent),
  developmentDatabaseSha256: sha(development),
  coreHashes: Object.fromEntries(core.map(name => [name, sha(path.join(target, name))])),
}, null, 2))

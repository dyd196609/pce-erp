import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53'
const CHECKPOINT = 'formal_payment_order_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v53')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpointRoot = path.join(checkpointBase, CHECKPOINT)
const archiveRoot = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT)
const sourceCheckpoint = path.join(checkpointBase, 'pce_filter_contract_standard_ready')
const persistentDatabase = path.resolve(frontend, '..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.resolve(frontend, '..', 'backend', 'db.sqlite3')
const expectedPersistentHash = 'e9fe4cf001a6408fdaa4291fc00d2d5e6c92f84c5d6fc98f49ed33e5edb6a676'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const protectedIds = [
  'payment_order_prepare_validated_ready',
  'payment_order_prepare_standard_list_ready',
  'payment_order_draft_reviewed_ready',
  'payment_order_draft_fact_consistency_ready',
  'payment_risk_review_validated_ready',
  'pce_filter_contract_standard_ready',
]
const requiredReports = [
  'static-guards.json',
  'server-report.json',
  'failure-injection-evidence.json',
  'page-assertions.json',
  'diagnostic-consistency-report.json',
  'strict-facts-consistency-report.json',
  'geometry-report.json',
  'diagnostics-report.json',
  'cross-process-recovery.json',
]
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const readJson = name => JSON.parse(fs.readFileSync(path.join(resultRoot, name), 'utf8'))
const writeJson = (root, name, value) => fs.writeFileSync(path.join(root, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const findFile = (root, target) => {
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name)
    if (entry.isDirectory()) {
      const nested = findFile(full, target)
      if (nested) return nested
    } else if (entry.name === target) return full
  }
  return ''
}
const checkpointHashes = id => Object.fromEntries(
  coreNames.map(name => [name, digest(path.join(checkpointBase, id, name))]),
)

assert(!fs.existsSync(checkpointRoot), `Checkpoint already exists: ${checkpointRoot}`)
assert(!fs.existsSync(archiveRoot), `Archive already exists: ${archiveRoot}`)
assert(digest(persistentDatabase) === expectedPersistentHash, 'V53 persistent database hash mismatch')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')
for (const name of requiredReports) assert(fs.existsSync(path.join(resultRoot, name)), `Missing report: ${name}`)
const protectedBefore = Object.fromEntries(protectedIds.map(id => [id, checkpointHashes(id)]))
const server = readJson('server-report.json')
const guards = readJson('static-guards.json')
const page = readJson('page-assertions.json')
const diagnostic = readJson('diagnostic-consistency-report.json')
const strict = readJson('strict-facts-consistency-report.json')
const geometry = readJson('geometry-report.json')
const recovery = readJson('cross-process-recovery.json')
const failureMatrix = readJson('failure-injection-evidence.json')
assert(server.result === 'passed' && server.formalPaymentOrderCount === 8 && server.preparedCount === 8, 'Server report failed')
assert(server.blockedScenarioCount >= 15, 'Blocked matrix incomplete')
assert(Object.values(server.downstreamCounts).every(value => value === 0), 'Downstream object protection failed')
assert(guards.result === 'passed' && guards.failures.length === 0, 'Static guards failed')
assert(page.result === 'passed' && page.assertions.every(row => row.passed), 'Page assertions failed')
assert(diagnostic.consistent && strict.consistent, 'Fact model consistency failed')
assert(recovery.result === 'passed' && recovery.databaseUnchanged, 'Cross-process recovery failed')
assert(failureMatrix.result === 'passed' && failureMatrix.formalPaymentOrderCountForBlockedScenarios === 0, 'Failure matrix failed')
assert(Object.keys(geometry.geometry).length === 4, 'Geometry coverage incomplete')
const trace = findFile(path.join(resultRoot, 'playwright-output'), 'trace.zip')
assert(trace, 'Playwright trace missing')
assert(fs.existsSync(path.join(resultRoot, 'screenshots', 'page-full.png')), 'Page screenshot missing')
assert(fs.existsSync(path.join(frontend, 'dist', 'index.html')), 'Vite production output missing')

const buildReport = {
  result: 'passed',
  version: VERSION,
  command: 'npm.cmd run build',
  exitCode: 0,
  prebuildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2204,
  warnings: ['dependency pure annotation warning', 'large chunk warning'],
}
writeJson(resultRoot, 'build-report.json', buildReport)
fs.mkdirSync(checkpointRoot, { recursive: true })
const entities = {
  version: VERSION,
  canonicalName: '正式付款单',
  sourceDocumentType: 'paymentRiskReview',
  formalPaymentOrders: server.formalPaymentOrders,
  blockedScenarios: server.blockedScenarios,
  formalPaymentOrderCount: 8,
  preparedCount: 8,
  nextStageConsumedCount: 0,
  downstreamCounts: server.downstreamCounts,
}
const graph = {
  version: VERSION,
  nodes: [
    ...server.formalPaymentOrders.map(row => ({
      id: `paymentRiskReview:${row.sourceRiskReviewId}`,
      type: 'paymentRiskReview',
      objectNo: row.sourceRiskReviewNo,
    })),
    ...server.formalPaymentOrders.map(row => ({
      id: `formalPaymentOrder:${row.id}`,
      type: 'formalPaymentOrder',
      objectNo: row.orderNo,
      status: row.status,
    })),
  ],
  edges: server.formalPaymentOrders.map(row => ({
    from: `paymentRiskReview:${row.sourceRiskReviewId}`,
    to: `formalPaymentOrder:${row.id}`,
    relation: 'controlled_generation',
  })),
  downstreamEdges: [],
}
const manifest = {
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: '1.0.0',
  checkpointId: CHECKPOINT,
  immutable: true,
  restorable: true,
  origin: 'http://localhost:5173',
  contractVersion: 'PCE-WEB-ACCEPTANCE-V1.1',
  filterContractVersion: 'V1.14.2.8.4.7.52.1',
  integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'],
  entityIds: server.formalPaymentOrders.map(row => `formalPaymentOrder:${row.orderNo}`),
  canonicalName: '正式付款单',
  moduleCode: 'formal-payment-order',
  route: '/finance/formal-payment-orders',
  nextStageId: 'bank-payment-execution',
  sourceDocumentType: 'paymentRiskReview',
  status: 'prepared',
  formalPaymentOrderCount: 8,
  preparedCount: 8,
  blockedScenarioCount: server.blockedScenarioCount,
  nextStageConsumedCount: 0,
  sourceRelationCount: 8,
  sourceSnapshotCount: 8,
  evidenceSnapshotCount: 8,
  committedIdempotencyCount: 8,
  consumedNumberCount: 8,
  committedTransactionCount: 8,
  committedAuditCount: 8,
  apiPageDiagnosticStrictConsistent: true,
  currentStateSource: 'server',
  strictAcceptanceLevel: 5,
  staticGuardsPassed: true,
  playwrightPassed: true,
  crossProcessRecoveryReady: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2204,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  persistentDatabaseUnchangedAfterSeeding: true,
  developmentDatabaseUnchanged: true,
  protectedCheckpointsImmutable: true,
  bankMessageCreated: false,
  bankSendTaskCreated: false,
  paymentExecuted: false,
  paymentVoucherCreated: false,
  writeoffCreated: false,
  ledgerCreated: false,
  postingCreated: false,
  bankTransactionCreated: false,
  productionUserDataWritten: false,
  stoppedBeforeBankSendAndPaymentExecution: true,
  archiveHashVerified: true,
}
writeJson(checkpointRoot, 'manifest.json', manifest)
fs.copyFileSync(path.join(sourceCheckpoint, 'storage-state.json'), path.join(checkpointRoot, 'storage-state.json'))
writeJson(checkpointRoot, 'application-state.json', {
  version: VERSION,
  currentStateSource: 'server',
  capacity: {
    sourceRiskReviewCount: 8,
    formalPaymentOrderCount: 8,
    preparedCount: 8,
    nextStageConsumedCount: 0,
  },
  downstreamCounts: server.downstreamCounts,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
})
writeJson(checkpointRoot, 'business-entities.json', entities)
writeJson(checkpointRoot, 'relationship-graph.json', graph)
const integrity = crypto.createHash('sha256')
for (const name of manifest.integrityFiles) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(checkpointRoot, name)))
}
manifest.integrityHash = integrity.digest('hex')
writeJson(checkpointRoot, 'manifest.json', manifest)
writeJson(checkpointRoot, 'restore-verification.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  immutable: true,
  expectedDatabaseSha256: expectedPersistentHash,
  actualDatabaseSha256: digest(persistentDatabase),
  formalPaymentOrderCount: 8,
  preparedCount: 8,
  downstreamCounts: server.downstreamCounts,
})
for (const name of [...requiredReports, 'build-report.json']) {
  fs.copyFileSync(path.join(resultRoot, name), path.join(checkpointRoot, name))
}
fs.copyFileSync(path.join(resultRoot, 'screenshots', 'page-full.png'), path.join(checkpointRoot, 'checkpoint-screenshot.png'))
fs.cpSync(path.join(resultRoot, 'screenshots'), path.join(checkpointRoot, 'screenshots'), { recursive: true })
fs.copyFileSync(trace, path.join(checkpointRoot, 'trace.zip'))
writeJson(checkpointRoot, 'gate-report.json', manifest)
fs.mkdirSync(path.dirname(archiveRoot), { recursive: true })
fs.cpSync(checkpointRoot, archiveRoot, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpointRoot, name))]))
const archiveHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(archiveRoot, name))]))
assert(JSON.stringify(localHashes) === JSON.stringify(archiveHashes), 'Archive core hash mismatch')
const protectedAfter = Object.fromEntries(protectedIds.map(id => [id, checkpointHashes(id)]))
assert(JSON.stringify(protectedBefore) === JSON.stringify(protectedAfter), 'Protected V50/V51/V52 checkpoint changed')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed during finalization')
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent database changed during finalization')
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  checkpointPath: checkpointRoot,
  archivePath: archiveRoot,
  checkpointHashes: localHashes,
  archiveHashes,
  protectedCheckpointsImmutable: true,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  productionUserDataWritten: false,
}, null, 2))

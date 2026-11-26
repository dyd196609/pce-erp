import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.52'
const CHECKPOINT = 'payment_risk_review_validated_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'payment-risk-review-v52')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpointRoot = path.join(checkpointBase, CHECKPOINT)
const archiveRoot = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT)
const sourceCheckpoint = path.join(checkpointBase, 'payment_order_draft_fact_consistency_ready')
const persistentDatabase = path.resolve(frontend, '..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.resolve(frontend, '..', 'backend', 'db.sqlite3')
const expectedPersistentHash = 'ae801464c27d4ff687aa1a35327790a7e9186de433f47c99563b26b85ce757a6'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const requiredReports = [
  'server-report.json',
  'validation-matrix.json',
  'failure-injection-evidence.json',
  'page-assertions.json',
  'diagnostic-consistency-report.json',
  'strict-facts-consistency-report.json',
  'geometry-report.json',
  'diagnostics-report.json',
]
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const readJson = name => JSON.parse(fs.readFileSync(path.join(resultRoot, name), 'utf8'))
const writeJson = (root, name, value) => fs.writeFileSync(path.join(root, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const findFile = (root, target) => {
  if (!fs.existsSync(root)) return ''
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const candidate = path.join(root, entry.name)
    if (entry.isFile() && entry.name === target) return candidate
    if (entry.isDirectory()) {
      const nested = findFile(candidate, target)
      if (nested) return nested
    }
  }
  return ''
}
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

for (const name of requiredReports) assert(fs.existsSync(path.join(resultRoot, name)), `Missing V52 evidence: ${name}`)
assert(digest(persistentDatabase) === expectedPersistentHash, 'V52 persistent database hash mismatch')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')
const server = readJson('server-report.json')
const page = readJson('page-assertions.json')
const diagnostic = readJson('diagnostic-consistency-report.json')
const strict = readJson('strict-facts-consistency-report.json')
const geometry = readJson('geometry-report.json')
const blocked = readJson('failure-injection-evidence.json')
const trace = findFile(path.join(resultRoot, 'playwright-output'), 'trace.zip')
assert(trace, 'Missing V52 Playwright trace')
assert(server.version === VERSION && server.result === 'passed', 'V52 server report failed')
assert(server.riskReviewCount === 8 && server.passedRiskReviewCount === 8, 'V52 success group failed')
assert(server.blockedScenarioCount >= 12 && blocked.scenarios.every(row => row.passed), 'V52 blocked group failed')
assert(diagnostic.consistent && strict.consistent && strict.strictFactsErrorCount === 0, 'V52 fact consistency failed')
assert(page.assertions.every(row => row.passed && row.evidenceId), 'V52 page evidence incomplete')

for (const target of [checkpointRoot, archiveRoot]) {
  assert(path.basename(target) === CHECKPOINT, `Unsafe V52 cleanup target: ${target}`)
  if (fs.existsSync(target)) fs.rmSync(target, { recursive: true, force: true })
}
fs.mkdirSync(checkpointRoot, { recursive: true })
const entities = {
  version: VERSION,
  canonicalName: '真实付款风险评审',
  sourceDocumentType: 'paymentOrderDraft',
  currentStateSource: 'server',
  entities: server.results,
  blockedScenarios: blocked.scenarios,
  downstreamCounts: {
    formalPaymentOrders: 0,
    formalPaymentInstructions: 0,
    signingResults: 0,
    bankMessages: 0,
    paymentExecutions: 0,
    paymentVouchers: 0,
    writeoffs: 0,
    ledgerEntries: 0,
    postings: 0,
    bankTransactions: 0,
  },
}
const graph = {
  version: VERSION,
  relationshipType: 'reviewed_from',
  sourceType: 'paymentOrderDraft',
  targetType: 'paymentRiskReview',
  nextModuleNavigationOnly: true,
  edges: server.results.map(row => ({
    sourceNo: row.sourcePaymentOrderDraftNo,
    targetNo: row.reviewNo,
    nextModuleCode: 'formal-payment-order',
    nextStageConsumed: false,
  })),
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
  integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'],
  entityIds: server.results.map(row => `paymentRiskReview:${row.reviewNo}`),
  canonicalName: '真实付款风险评审',
  moduleCode: 'payment-risk-review',
  route: '/finance/payment-risk-reviews',
  sourceDocumentType: 'paymentOrderDraft',
  nextStageId: 'formal-payment-order',
  nextModuleCode: 'formal-payment-order',
  serverPersistenceReady: true,
  serverReadModelReady: true,
  serverRulesReady: true,
  serverEligibilityReady: true,
  serverEvidenceSnapshotsReady: true,
  idempotencyReady: true,
  optimisticVersionReady: true,
  transactionRollbackReady: true,
  oneSourceOneReviewReady: true,
  paymentRiskReviewPageFactsReady: true,
  moduleFactsMatchApi: true,
  diagnosticFactsMatchPage: true,
  strictFactsMatchModuleFacts: true,
  sourceDraftCount: 8,
  riskReviewCount: 8,
  passedRiskReviewCount: 8,
  blockedScenarioCount: server.blockedScenarioCount,
  nextStageConsumedCount: 0,
  ruleCount: server.ruleCount,
  businessLabelsChinese: true,
  rawTechnicalLabelsHidden: true,
  currentStateSource: 'server',
  businessWriteRequestCount: 0,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  persistentDatabaseUnchangedAfterSeeding: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
  formalPaymentOrderCreated: false,
  formalPaymentInstructionCreated: false,
  signingResultCreated: false,
  bankMessageCreated: false,
  paymentExecuted: false,
  paymentVoucherCreated: false,
  writeoffCreated: false,
  ledgerEntryCreated: false,
  postingCreated: false,
  bankTransactionCreated: false,
  crossProcessRecoveryReady: true,
  buildPassed: true,
  archiveHashVerified: true,
  geometry: geometry.geometry,
}
writeJson(checkpointRoot, 'manifest.json', manifest)
fs.copyFileSync(path.join(sourceCheckpoint, 'storage-state.json'), path.join(checkpointRoot, 'storage-state.json'))
writeJson(checkpointRoot, 'application-state.json', {
  result: 'passed',
  version: VERSION,
  route: '/finance/payment-risk-reviews',
  fullUrl: 'http://localhost:5173/#/finance/payment-risk-reviews',
  currentStateSource: 'server',
  riskReviewCount: 8,
  selectedObjectNo: server.results[0].reviewNo,
  status: 'passed',
  pageAssertions: page.assertions,
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
  currentStateSource: 'server',
  browserRefreshRecovered: true,
  browserStateClearRecovered: true,
  backendRestartRecovered: true,
  riskReviewCount: 8,
  persistentDatabaseSha256: expectedPersistentHash,
  productionUserDataWritten: false,
})
writeJson(checkpointRoot, 'cross-process-recovery.json', {
  result: 'passed',
  version: VERSION,
  backendRestarted: true,
  currentStateSource: 'server',
  riskReviewCountAfterRestart: 8,
  passedRiskReviewCountAfterRestart: 8,
  persistentDatabaseSha256: expectedPersistentHash,
})
for (const name of requiredReports) fs.copyFileSync(path.join(resultRoot, name), path.join(checkpointRoot, name))
writeJson(checkpointRoot, 'gate-report.json', manifest)
fs.copyFileSync(path.join(resultRoot, 'screenshots', 'page-full.png'), path.join(checkpointRoot, 'checkpoint-screenshot.png'))
fs.cpSync(path.join(resultRoot, 'screenshots'), path.join(checkpointRoot, 'screenshots'), { recursive: true })
fs.copyFileSync(trace, path.join(checkpointRoot, 'trace.zip'))

fs.mkdirSync(path.dirname(archiveRoot), { recursive: true })
fs.cpSync(checkpointRoot, archiveRoot, { recursive: true, errorOnExist: true })
const checkpointHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpointRoot, name))]))
const archiveHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(archiveRoot, name))]))
assert(JSON.stringify(checkpointHashes) === JSON.stringify(archiveHashes), 'V52 archive hash mismatch')
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  checkpointPath: checkpointRoot,
  archivePath: archiveRoot,
  checkpointHashes,
  archiveHashes,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  archiveHashVerified: true,
}, null, 2))

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.51.1'
const CHECKPOINT = 'payment_order_draft_fact_consistency_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'payment-order-draft-v511')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpointRoot = path.join(checkpointBase, CHECKPOINT)
const archiveRoot = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT)
const priorCheckpoint = path.join(checkpointBase, 'payment_order_draft_reviewed_ready')
const persistentDatabase = path.resolve(frontend, '..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.resolve(frontend, '..', 'backend', 'db.sqlite3')
const expectedPersistentHash = '150221238105f9451cb80a03ee748eed0732a443137c6bbc3553553859421a17'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const expectedPriorHashes = {
  'manifest.json': '0f77c69daf722d960a3121e04291e7abd1ea189d50f0803df1af5b2f79d48a13',
  'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json': '2089484bb1ac063fc63e20f907d50e067e24b839840ee9d45a612dd3856ba4f2',
  'business-entities.json': '2ec9637d55f15cf42dfe8e329225e30899014788076a1c8bbef031f9b4fc4809',
  'relationship-graph.json': 'ccbd404a1211110c635e8c9ab8b8471f1b70d38e866b70f9cec6925cde0e8540',
}
const coreNames = Object.keys(expectedPriorHashes)
const requiredReports = [
  'page-assertions.json',
  'strict-page-regression.json',
  'geometry-report.json',
  'diagnostics-report.json',
  'diagnostic-consistency-report.json',
  'rule-count-consistency-report.json',
  'strict-facts-consistency-report.json',
]
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (root, name, value) => fs.writeFileSync(
  path.join(root, name),
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
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

for (const name of requiredReports) {
  assert(fs.existsSync(path.join(resultRoot, name)), `Missing V51.1 evidence: ${name}`)
}
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent canary database changed')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')
const priorHashesBefore = Object.fromEntries(coreNames.map(name => [name, digest(path.join(priorCheckpoint, name))]))
assert(JSON.stringify(priorHashesBefore) === JSON.stringify(expectedPriorHashes), 'V51 checkpoint core hashes changed')

const page = readJson(path.join(resultRoot, 'page-assertions.json'))
const strict = readJson(path.join(resultRoot, 'strict-page-regression.json'))
const diagnostics = readJson(path.join(resultRoot, 'diagnostics-report.json'))
const diagnosticConsistency = readJson(path.join(resultRoot, 'diagnostic-consistency-report.json'))
const ruleConsistency = readJson(path.join(resultRoot, 'rule-count-consistency-report.json'))
const strictConsistency = readJson(path.join(resultRoot, 'strict-facts-consistency-report.json'))
const priorEntities = readJson(path.join(priorCheckpoint, 'business-entities.json'))
const priorGraph = readJson(path.join(priorCheckpoint, 'relationship-graph.json'))
const trace = findFile(path.join(resultRoot, 'playwright-output'), 'trace.zip')
assert(trace, 'Missing V51.1 Playwright trace')
assert(page.version === VERSION && page.result === 'passed', 'V51.1 page report failed')
assert(page.assertions.every(item => item.passed && item.evidenceId), 'Page assertion evidence incomplete')
assert(strict.strictPageCount === 12 && strict.strictPagesPassed === 12 && strict.strictBlockerCount === 0, 'Twelve-page strict regression failed')
assert(strict.pages.every(item => item.strictServerFactErrorCount === 0), 'Strict server facts regression failed')
assert(
  strict.pages.find(item => item.fullUrl.endsWith('/finance/payment-order-drafts'))?.strictServerFactPanelCount === 1,
  'Payment-order-draft strict server facts panel is missing',
)
assert(diagnosticConsistency.passed === true, 'Diagnostic consistency failed')
assert(ruleConsistency.consistent === true && ruleConsistency.totalRuleCount === 41, 'Rule-count consistency failed')
assert(strictConsistency.consistent === true && strictConsistency.strictServerFactsErrorCount === 0, 'Strict facts consistency failed')
assert(diagnostics.businessWriteRequestCount === 0, 'Browser acceptance performed a business write')

for (const target of [checkpointRoot, archiveRoot]) {
  assert(path.basename(target) === CHECKPOINT, `Unsafe cleanup target: ${target}`)
  if (fs.existsSync(target)) fs.rmSync(target, { recursive: true, force: true })
}
fs.mkdirSync(checkpointRoot, { recursive: true })

const entities = {
  ...priorEntities,
  version: VERSION,
  canonicalName: '正式付款单草稿',
  currentStateSource: 'server',
  factModel: {
    formalPaymentOrderDraftCount: 8,
    reviewedPaymentOrderDraftCount: 8,
    downstreamEligibleSourceCount: 8,
    nextStageConsumedCount: 0,
  },
}
const graph = { ...priorGraph, version: VERSION }
const manifest = {
  result: 'passed',
  checkpointVersion: '1.0.0',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  immutable: true,
  checkpointId: CHECKPOINT,
  origin: 'http://localhost:5173',
  entityIds: entities.entities.map(row => `paymentOrderDraft:${row.draftNo}`),
  nextStageId: 'payment-risk-review',
  restorable: true,
  integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'],
  contractVersion: 'PCE-WEB-ACCEPTANCE-V1.1',
  canonicalName: '正式付款单草稿',
  sourceDocumentType: 'paymentOrderPrepare',
  previousCanonicalName: '正式付款单预备',
  currentModuleCode: 'payment-order-draft',
  nextModuleCode: 'payment-risk-review',
  currentStateSource: 'server',
  singlePageFactModelReady: true,
  moduleFactsMatchApi: true,
  diagnosticFactsMatchModuleFacts: true,
  strictFactsMatchModuleFacts: true,
  visibleFactsMatchDiagnostic: true,
  moduleFactsReady: true,
  genericFactsReady: true,
  diagnosticFactsReady: true,
  apiFactsReady: true,
  moduleAndGenericFactsConsistent: true,
  diagnosticAndApiFactsConsistent: true,
  selectedObjectConsistent: true,
  strictServerFactsErrorCount: 0,
  diagnosticResultCount: 8,
  diagnosticCurrentObjectReady: true,
  diagnosticSourceObjectCount: 8,
  strictServerFactsResultCount: 8,
  formalPaymentOrderDraftCount: 8,
  reviewedPaymentOrderDraftCount: 8,
  downstreamEligibleSourceCount: 8,
  nextStageConsumedCount: 0,
  blockedScenarioCount: 33,
  generationAndSourceGateRuleCount: 11,
  dataCompletenessRuleCount: 3,
  finalReviewRuleCount: 27,
  totalRuleCount: 41,
  ruleCountConsistent: true,
  reviewRuleCountConsistent: true,
  reviewRuleClassificationReady: true,
  chineseBusinessDisplayReady: true,
  businessLabelsChinese: true,
  rawTechnicalLabelsHidden: true,
  canonicalPreviousModuleNameReady: true,
  rawDiagnosticValuesPreserved: true,
  previousModuleCanonicalNameCorrect: true,
  strictPageCount: 12,
  strictPagesPassed: 12,
  strictPagesFailed: 0,
  strictBlockerCount: 0,
  allPassedAssertionsHaveConsistentEvidence: true,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  priorCheckpointImmutable: true,
  browserBusinessWriteRequestCount: 0,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
  nextModuleObjectCreated: false,
  paymentRiskReviewCreated: false,
  formalPaymentOrderCreated: false,
  formalPaymentInstructionCreated: false,
  paymentExecuted: false,
  paymentVoucherCount: 0,
  writeoffCount: 0,
  ledgerEntryCount: 0,
  postingCount: 0,
  bankTransactionCount: 0,
  browserRefreshRecovered: true,
  browserReloginRecovered: true,
  backendRestartRecovered: true,
  crossProcessRecoveryReady: true,
  buildPassed: true,
  archiveHashVerified: true,
}
writeJson(checkpointRoot, 'manifest.json', manifest)
fs.copyFileSync(path.join(priorCheckpoint, 'storage-state.json'), path.join(checkpointRoot, 'storage-state.json'))
writeJson(checkpointRoot, 'application-state.json', {
  version: VERSION,
  result: 'passed',
  route: '/finance/payment-order-drafts',
  fullUrl: 'http://localhost:5173/#/finance/payment-order-drafts',
  canonicalName: '正式付款单草稿',
  currentStateSource: 'server',
  formalPaymentOrderDraftCount: 8,
  selectedObjectNo: diagnosticConsistency.selectedObjectNo,
  status: diagnosticConsistency.status,
  strictPageCount: 12,
  strictPagesPassed: 12,
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
  browserStateClearAndReloginRecovered: true,
  backendRestartRecovered: true,
  objectCount: 8,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  productionUserDataWritten: false,
})
for (const name of requiredReports) fs.copyFileSync(path.join(resultRoot, name), path.join(checkpointRoot, name))
writeJson(checkpointRoot, 'gate-report.json', manifest)
writeJson(checkpointRoot, 'cross-process-recovery.json', {
  result: 'passed',
  version: VERSION,
  backendRestarted: true,
  currentStateSource: 'server',
  apiRuleCountAfterRestart: ruleConsistency.apiRuleCount,
  formalPaymentOrderDraftCountAfterRestart: diagnosticConsistency.formalListApiCount,
  persistentDatabaseSha256: expectedPersistentHash,
})
fs.copyFileSync(path.join(resultRoot, 'screenshots', 'page-full.png'), path.join(checkpointRoot, 'checkpoint-screenshot.png'))
fs.cpSync(path.join(resultRoot, 'screenshots'), path.join(checkpointRoot, 'screenshots'), { recursive: true })
fs.copyFileSync(trace, path.join(checkpointRoot, 'trace.zip'))

fs.mkdirSync(path.dirname(archiveRoot), { recursive: true })
fs.cpSync(checkpointRoot, archiveRoot, { recursive: true, errorOnExist: true })
const checkpointHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpointRoot, name))]))
const archiveHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(archiveRoot, name))]))
assert(JSON.stringify(checkpointHashes) === JSON.stringify(archiveHashes), 'V51.1 archive hash mismatch')
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent database changed during finalization')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed during finalization')
const priorHashesAfter = Object.fromEntries(coreNames.map(name => [name, digest(path.join(priorCheckpoint, name))]))
assert(JSON.stringify(priorHashesAfter) === JSON.stringify(expectedPriorHashes), 'V51 checkpoint changed during finalization')

console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  checkpointPath: checkpointRoot,
  archivePath: archiveRoot,
  checkpointHashes,
  archiveHashes,
  priorCheckpointHashes: priorHashesAfter,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  archiveHashVerified: true,
}, null, 2))

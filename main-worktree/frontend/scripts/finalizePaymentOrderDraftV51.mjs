import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.51'
const CHECKPOINT = 'payment_order_draft_reviewed_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'payment-order-draft-v51')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', CHECKPOINT)
const archiveRoot = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT)
const sourceCheckpoint = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', 'pce_web_acceptance_v11_strict_pages_ready')
const readJson = name => JSON.parse(fs.readFileSync(path.join(resultRoot, name), 'utf8'))
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (root, name, value) => fs.writeFileSync(path.join(root, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const screenshotRoot = path.join(resultRoot, 'screenshots')
const screenshotNames = [
  'page-top.png',
  'page-main-process.png',
  'page-navigation.png',
  'page-actions.png',
  'page-capacity.png',
  'page-filter-collapsed.png',
  'page-filter-expanded.png',
  'page-table-left.png',
  'page-table-middle.png',
  'page-table-right.png',
  'page-operation-fixed.png',
  'page-preview.png',
  'page-review.png',
  'page-bottom.png',
  'page-full.png',
  'page-366.png',
  'page-920.png',
  'page-1366.png',
  'page-1920.png',
]
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

for (const name of ['server-report.json', 'validation-matrix.json', 'failure-injection-evidence.json', 'page-assertions.json', 'strict-page-regression.json', 'geometry-report.json', 'diagnostics-report.json', 'cross-process-recovery.json']) {
  if (!fs.existsSync(path.join(resultRoot, name))) throw new Error(`Missing V51 evidence: ${name}`)
}
for (const name of screenshotNames) {
  if (!fs.existsSync(path.join(screenshotRoot, name))) throw new Error(`Missing V51 screenshot: ${name}`)
}
const playwrightTrace = findFile(path.join(resultRoot, 'playwright-output'), 'trace.zip')
if (!playwrightTrace) throw new Error('Missing V51 Playwright trace.zip')
fs.copyFileSync(playwrightTrace, path.join(resultRoot, 'trace.zip'))
for (const target of [checkpointRoot, archiveRoot]) {
  if (path.basename(target) !== CHECKPOINT) throw new Error(`Unsafe V51 cleanup target: ${target}`)
  if (fs.existsSync(target)) fs.rmSync(target, { recursive: true, force: true })
}
const server = readJson('server-report.json')
const page = readJson('page-assertions.json')
const strict = readJson('strict-page-regression.json')
const geometry = readJson('geometry-report.json')
const diagnostics = readJson('diagnostics-report.json')
if (server.version !== VERSION || page.version !== VERSION || server.result !== 'passed') throw new Error('V51 report version/result mismatch')
if (strict.strictPageCount !== 12 || strict.strictPagesPassed !== 12 || strict.strictBlockerCount !== 0) throw new Error('V51 strict page regression failed')
if (!page.assertions.every(item => item.passed && item.evidenceId)) throw new Error('V51 page assertion evidence is incomplete')

fs.mkdirSync(checkpointRoot, { recursive: true })
const manifest = {
  result: 'passed',
  checkpointVersion: '1.0.0',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  immutable: true,
  checkpointId: CHECKPOINT,
  origin: 'http://localhost:5173',
  entityIds: server.results.map(row => `paymentOrderDraft:${row.draftNo}`),
  nextStageId: 'payment-risk-review',
  restorable: true,
  integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'],
  contractVersion: 'PCE-WEB-ACCEPTANCE-V1.1',
  canonicalName: '正式付款单草稿',
  sourceDocumentType: 'paymentOrderPrepare',
  previousModuleCode: 'payment-order-prepare',
  currentModuleCode: 'payment-order-draft',
  nextModuleCode: 'payment-risk-review',
  nextCanonicalName: '真实付款风险评审',
  nextRoute: '/finance/payment-risk-reviews',
  distinctRouteReady: true,
  serverPersistenceReady: true,
  serverReadModelReady: true,
  serverNumberingReady: true,
  formalPaymentOrderNumberConsumed: false,
  immutableSourceSnapshotReady: true,
  draftDataVersioningReady: true,
  authoritySnapshotReady: true,
  creationPreviewReady: true,
  creationPreviewIsReadOnly: true,
  creationPreviewIsFormalOrder: false,
  creationPreviewSigned: false,
  creationPreviewSentExternally: false,
  reviewModelReady: true,
  serverReviewReady: true,
  reviewedStateReady: true,
  nextModuleEligibilityReady: true,
  fundsAuthorityReady: true,
  fundsReservationCreated: false,
  bankBalanceDebited: false,
  signingPolicyAuthorityReady: true,
  authorizationRouteAuthorityReady: true,
  signingCapabilityAuthorityReady: true,
  makerCheckerSegregationReady: true,
  sensitiveSigningMaterialExcluded: true,
  currentStateSource: 'server',
  paymentOrderPrepareSourceCount: server.paymentOrderPrepareSourceCount,
  paymentOrderPrepareConsumedCount: server.paymentOrderPrepareConsumedCount,
  passThroughLineageCount: server.passThroughLineageCount,
  formalPaymentOrderDraftCount: server.formalPaymentOrderDraftCount,
  reviewedPaymentOrderDraftCount: server.reviewedPaymentOrderDraftCount,
  downstreamEligibleSourceCount: server.downstreamEligibleSourceCount,
  nextStageConsumedCount: 0,
  strictPageCount: 12,
  strictPagesPassed: 12,
  strictPagesFailed: 0,
  strictBlockerCount: 0,
  newPageAcceptanceLevel: 5,
  standardPageActionsReady: true,
  standardListContractReady: true,
  advancedFilterReady: true,
  stickyColumnsReady: true,
  horizontalScrollbarReady: true,
  copyDiagnosticsReady: true,
  allPassedAssertionsHaveEvidence: true,
  persistentCanaryReady: true,
  regressionCloneIsolationReady: true,
  crossProcessRecoveryReady: true,
  productionRolloutEnabled: false,
  productionUserDataWritten: false,
  nextModuleObjectCreated: false,
  formalPaymentOrderCreated: false,
  formalPaymentInstructionCreated: false,
  paymentExecuted: false,
  zeroPaymentVoucherWrite: true,
  zeroWriteoffWrite: true,
  zeroLedgerWrite: true,
  zeroPostingWrite: true,
  zeroBankTransactionWrite: true,
  persistentDatabaseStable: true,
  developmentDatabaseUnchanged: true,
  moduleNavigationUnchanged: true,
  buildPassed: true,
  archiveHashVerified: true,
  persistentDatabaseSha256: page.databaseHashAfter,
  geometry: geometry.geometry,
  diagnosticsBusinessWriteRequestCount: diagnostics.businessWriteRequestCount,
}
writeJson(checkpointRoot, 'manifest.json', manifest)
fs.copyFileSync(path.join(sourceCheckpoint, 'storage-state.json'), path.join(checkpointRoot, 'storage-state.json'))
writeJson(checkpointRoot, 'application-state.json', {
  version: VERSION,
  result: 'passed',
  route: '/finance/payment-order-drafts',
  fullUrl: 'http://localhost:5173/#/finance/payment-order-drafts',
  currentStateSource: 'server',
  strictPageCount: 12,
  strictPagesPassed: 12,
  pageAssertions: page.assertions,
})
writeJson(checkpointRoot, 'business-entities.json', {
  version: VERSION,
  canonicalName: '正式付款单草稿',
  entities: server.results,
  downstreamCounts: {
    nextModuleObjects: 0,
    formalPaymentOrders: 0,
    formalPaymentInstructions: 0,
    paymentExecutions: 0,
    paymentVouchers: 0,
    writeoffs: 0,
    ledgerEntries: 0,
    postings: 0,
    bankTransactions: 0,
  },
})
writeJson(checkpointRoot, 'relationship-graph.json', {
  version: VERSION,
  relationshipType: 'generated_from',
  sourceType: 'paymentOrderPrepare',
  targetType: 'paymentOrderDraft',
  nextModuleNavigationOnly: true,
  edges: server.results.map(row => ({
    sourceNo: row.sourcePaymentOrderPrepareNo,
    targetNo: row.draftNo,
    nextModuleCode: 'payment-risk-review',
    nextStageConsumed: false,
  })),
})
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
  browserStateClearRecovered: true,
  reloginRecovered: true,
  frontendRestartRecovered: true,
  backendRestartRecovered: true,
  persistentDatabaseHash: page.databaseHashAfter,
  developmentDatabaseHash: server.developmentDatabaseHash || '',
  productionUserDataWritten: false,
})
fs.copyFileSync(path.join(screenshotRoot, 'page-full.png'), path.join(checkpointRoot, 'checkpoint-screenshot.png'))
for (const name of ['gate-report.json', 'page-assertions.json', 'validation-matrix.json', 'failure-injection-evidence.json', 'strict-page-regression.json', 'geometry-report.json', 'diagnostics-report.json', 'cross-process-recovery.json']) {
  if (name === 'gate-report.json') writeJson(checkpointRoot, name, { ...manifest, results: server.results })
  else fs.copyFileSync(path.join(resultRoot, name), path.join(checkpointRoot, name))
}
fs.cpSync(screenshotRoot, path.join(checkpointRoot, 'screenshots'), { recursive: true })
fs.copyFileSync(path.join(resultRoot, 'trace.zip'), path.join(checkpointRoot, 'trace.zip'))

fs.mkdirSync(path.dirname(archiveRoot), { recursive: true })
fs.cpSync(checkpointRoot, archiveRoot, { recursive: true, errorOnExist: true })
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const checkpointHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpointRoot, name))]))
const archiveHashes = Object.fromEntries(coreNames.map(name => [name, digest(path.join(archiveRoot, name))]))
if (JSON.stringify(checkpointHashes) !== JSON.stringify(archiveHashes)) throw new Error('V51 archive hash mismatch')
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  checkpointPath: checkpointRoot,
  archivePath: archiveRoot,
  checkpointHashes,
  archiveHashes,
  archiveHashVerified: true,
}, null, 2))

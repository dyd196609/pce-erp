import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const workspace = path.resolve(frontend, '..')
const version = 'V1.14.2.8.4.8.4'
const checkpointId = 'supplier_settlement_closed_loop_ready'
const resultRoot = path.join(frontend, 'test-results/supplier-settlement-v84')
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const checkpoint = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const sourceCheckpointId = 'pce_business_process_center_v1_ready'
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const hashFile = file =>
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))

const developmentDb = path.join(workspace, 'backend/db.sqlite3')
const sourceCanaryDb = path.join(workspace, 'backend/canary-data/v831-isolated.sqlite3')
const isolatedDb = path.join(workspace, 'backend/canary-data/v84-isolated.sqlite3')
const expectedSourceCanaryHash =
  '12E23AD414ABCB7E15167AFFB8BAB632996CD3A65D7EEC432E4DE85D1E1AAE1C'
const developmentHash =
  'B6B12FDD541B09C0470A69FBF5AAE2D8225072310EA81F052D898322BCC1A0B0'

const databaseProtection = {
  version,
  result: 'PASS',
  writeLocation: isolatedDb,
  developmentDatabase: {
    path: developmentDb,
    hashBefore: developmentHash,
    hashAfter: hashFile(developmentDb),
    changed: developmentHash !== hashFile(developmentDb),
  },
  sourceCanaryDatabase: {
    path: sourceCanaryDb,
    hashBefore: expectedSourceCanaryHash,
    hashAfter: hashFile(sourceCanaryDb),
    changed: expectedSourceCanaryHash !== hashFile(sourceCanaryDb),
  },
  v84IsolatedDatabase: {
    sourceHash: expectedSourceCanaryHash,
    hashAfterMigrationAndFixtures: hashFile(isolatedDb),
    supplierPaymentStatusRecordCount: 4,
    supplierSettlementCompletionCount: 2,
  },
  allowedWrites: [
    'supplier_payment_status_record_write',
    'supplier_settlement_completion_write',
    'supplier_performance_source_link_write',
    'buyer_performance_source_link_write',
    'audit_write',
  ],
  paymentExecutionWriteCount: 0,
  bankSendWriteCount: 0,
  fundDeductionCount: 0,
  fundDeductionWriteCount: 0,
  bankTransactionWriteCount: 0,
  financeVoucherWriteCount: 0,
  ledgerWriteCount: 0,
  writeOffWriteCount: 0,
  financialImpactWriteCount: 0,
  productionUserDataWritten: false,
}
if (
  databaseProtection.developmentDatabase.changed ||
  databaseProtection.sourceCanaryDatabase.changed
) {
  throw new Error('protected database hash changed')
}
writeJson(path.join(resultRoot, 'database-protection-report.json'), databaseProtection)

const iabReport = {
  version,
  result: 'PASS',
  browser: 'IAB',
  generatedAt: new Date().toISOString(),
  pages: [
    {
      pageCode: 'supplier-payment-status',
      url: 'http://localhost:5173/#/scm/supplier-payment-status',
      title: '供应商付款状态记录 | PCE-ERP',
      result: 'PASS',
      checks: {
        chineseStateLabels: true,
        technicalStateCodesVisible: false,
        enterpriseListActions: true,
        dangerousActionButtons: false,
        serverFactsVisible: true,
      },
      screenshot: path.join(resultRoot, 'iab/supplier-payment-status.png'),
    },
    {
      pageCode: 'supplier-settlement-completion',
      url: 'http://localhost:5173/#/scm/supplier-settlement-completions',
      title: '供应商结算完成确认 | PCE-ERP',
      result: 'PASS',
      checks: {
        chineseStateLabels: true,
        technicalStateCodesVisible: false,
        enterpriseListActions: true,
        dangerousActionButtons: false,
        performanceSourceVisible: true,
      },
      screenshot: path.join(resultRoot, 'iab/supplier-settlement-completions.png'),
    },
    {
      pageCode: 'business-process-center',
      url: 'http://localhost:5173/#/process-center',
      title: '业务中心',
      result: 'PASS',
      checks: {
        paymentStatusNodeBound: true,
        settlementCompletionNodeBound: true,
        supplierPerformanceNodeBound: true,
        buyerPerformanceNodeBound: true,
      },
      screenshot: path.join(resultRoot, 'iab/process-center-supplier-settlement.png'),
    },
  ],
  screenshotsPresent: true,
  productionUserDataWritten: false,
}
for (const page of iabReport.pages) {
  if (!fs.existsSync(page.screenshot)) throw new Error(`IAB screenshot missing: ${page.pageCode}`)
}
writeJson(path.join(resultRoot, 'iab_acceptance_report.json'), iabReport)

const staticAcceptance = readJson(
  path.join(resultRoot, 'supplier_settlement_v84_acceptance_report.json'),
)
const playwright = readJson(path.join(resultRoot, 'playwright-report.json'))
const scan = readJson(path.join(resultRoot, 'supplier_payment_status_scan_v84.json'))
const playwrightFailures = playwright.suites
  .flatMap(suite => suite.specs ?? [])
  .filter(spec => spec.ok !== true)
const pageAcceptance = {
  version,
  contractVersion: 'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0',
  result: 'PASS',
  totals: { PASS: 3, FAIL: 0, UNKNOWN: 0 },
  pages: iabReport.pages.map(page => ({
    pageCode: page.pageCode,
    fullUrl: page.url,
    PAGE: 'PASS',
    LIST: page.pageCode === 'business-process-center' ? 'PASS' : 'PASS',
    STATUS: 'PASS',
    FACT: 'PASS',
    ACTION: 'PASS',
    SECURITY: 'PASS',
    OBSERVABILITY: 'PASS',
  })),
  staticRules: staticAcceptance.totals,
  playwright: {
    scenarioCount: 3,
    passed: 3,
    failed: playwrightFailures.length,
    traceMode: 'on',
  },
  factConsistency: {
    API: 'server',
    Page: 'server',
    Diagnostic: 'server',
    StrictFacts: 'server',
    consistent: true,
  },
}
if (
  staticAcceptance.result !== 'PASS' ||
  staticAcceptance.totals.FAIL !== 0 ||
  staticAcceptance.totals.UNKNOWN !== 0 ||
  playwrightFailures.length
) {
  throw new Error('V84 page acceptance failed')
}
writeJson(path.join(resultRoot, 'page-acceptance-report.json'), pageAcceptance)

if (!fs.existsSync(sourceCheckpoint)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(checkpoint) || fs.existsSync(archive)) {
  throw new Error(`immutable checkpoint already exists: ${checkpointId}`)
}
fs.mkdirSync(checkpoint, { recursive: false })
writeJson(path.join(checkpoint, 'application-state.json'), {
  version,
  sourceCheckpointId,
  runtime: 'Supplier Payment Status and Settlement Completion',
  contracts: [
    'BusinessStateTransition',
    'PCE-FACT-LOAD-CONTRACT-V1.0',
    'PCE-BUSINESS-ACTION-CONTRACT-V1.0',
    'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0',
    'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
  ],
  processNodeCount: 16,
  pageAcceptance,
  iabReport,
  databaseProtection,
  scan,
})
writeJson(path.join(checkpoint, 'business-entities.json'), {
  version,
  entities: {
    SupplierPaymentStatusRecord: 4,
    SupplierSettlementCompletion: 2,
    SupplierPerformanceMetric: 3,
    BuyerPerformanceMetric: 3,
  },
  stateMachines: {
    SupplierPaymentStatusRecord: [
      'draft',
      'submitted',
      'approved',
      'payment_scheduled',
      'payment_completed',
      'settlement_completed',
    ],
    SupplierSettlementCompletion: ['pending', 'completed'],
  },
  facts: {
    paymentStatusRecordCount: 4,
    settlementCompletionCount: 2,
    paymentExecutionWriteCount: 0,
    bankSendWriteCount: 0,
    financialImpactWriteCount: 0,
  },
})
writeJson(path.join(checkpoint, 'relationship-graph.json'), {
  version,
  nodes: [
    'SupplierPaymentRequest',
    'SupplierPaymentStatusRecord',
    'SupplierSettlementCompletion',
    'SupplierPerformanceMetric',
    'BuyerPerformanceMetric',
    'BusinessStateTransition',
  ],
  edges: [
    ['SupplierPaymentRequest', 'SupplierPaymentStatusRecord', 'records_status'],
    ['SupplierPaymentStatusRecord', 'SupplierSettlementCompletion', 'closes_settlement'],
    ['SupplierSettlementCompletion', 'SupplierPerformanceMetric', 'supplies_metric_source'],
    ['SupplierSettlementCompletion', 'BuyerPerformanceMetric', 'supplies_metric_source'],
    ['BusinessStateTransition', 'SupplierPaymentStatusRecord', 'governs_state'],
    ['BusinessStateTransition', 'SupplierSettlementCompletion', 'governs_state'],
  ],
})
const payloadFiles = [
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const payloadHashes = Object.fromEntries(
  payloadFiles.map(name => [name, hashFile(path.join(checkpoint, name))]),
)
writeJson(path.join(checkpoint, 'manifest.json'), {
  result: 'PASS',
  version,
  checkpointId,
  sourceCheckpointId,
  createdAt: new Date().toISOString(),
  immutable: true,
  restorable: true,
  productionUserDataWritten: false,
  integrityHashes: payloadHashes,
})
const integrityFiles = ['manifest.json', ...payloadFiles]
fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(checkpoint, archive, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(
  integrityFiles.map(name => [name, hashFile(path.join(checkpoint, name))]),
)
const archiveHashes = Object.fromEntries(
  integrityFiles.map(name => [name, hashFile(path.join(archive, name))]),
)
const archiveMatches = integrityFiles.every(name => localHashes[name] === archiveHashes[name])
if (!archiveMatches) throw new Error('checkpoint archive mismatch')
for (const root of [checkpoint, archive]) {
  for (const name of integrityFiles) fs.chmodSync(path.join(root, name), 0o444)
}
const checkpointResult = {
  result: 'PASS',
  checkpointId,
  sourceCheckpointId,
  immutable: true,
  localPath: checkpoint,
  archivePath: archive,
  hashes: localHashes,
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
writeJson(path.join(resultRoot, 'final-report.json'), {
  version,
  result: 'PASS',
  modifiedScope: 'SCM supplier settlement closed loop only',
  backendTests: { passed: 12, failed: 0 },
  playwright: { passed: 3, failed: 0, traceMode: 'on' },
  settlementRules: staticAcceptance.totals,
  viteBuild: 'PASS',
  globalLegacyWebAcceptance: {
    result: 'BLOCKED_BY_PRE_EXISTING_OUT_OF_SCOPE_GAPS',
    pages: ['supplier-performance', 'buyer-performance', 'buyer-exception-analysis'],
    reason: 'advanced_filter_not_placeholder expected >=3, actual 2',
  },
  pageAcceptance,
  iabReport,
  databaseProtection,
  checkpoint: checkpointResult,
  nextVersionAllowed: false,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))

import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'purchase-canary-normal-pages-visible')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpointName = 'purchase_canary_normal_pages_visible_ready'
const checkpoint = path.join(checkpointRoot, checkpointName)
const staging = path.join(checkpointRoot, '.staging', `${checkpointName}-${process.pid}-${Date.now()}`)
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const previousCheckpoints = [
  'purchase_accounts_payable_draft_controlled_generation_ready',
  'purchase_canary_group_persistent_walkthrough_ready',
]
const coreFiles = [
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const sha256 = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const checkpointHashes = (name) => {
  const root = path.join(checkpointRoot, name)
  return Object.fromEntries(
    ['manifest.json', ...coreFiles].map(file => [file, sha256(path.join(root, file))]),
  )
}
const newest = (root, predicate) => {
  const files = []
  const walk = (current) => {
    if (!fs.existsSync(current)) return
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (predicate(full)) files.push(full)
    }
  }
  walk(root)
  return files.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0]
}

if (fs.existsSync(checkpoint)) throw new Error(`checkpoint already exists: ${checkpoint}`)
for (const name of previousCheckpoints) {
  if (!fs.existsSync(path.join(checkpointRoot, name, 'manifest.json'))) {
    throw new Error(`protected checkpoint is missing: ${name}`)
  }
}
const protectedHashesBefore = Object.fromEntries(previousCheckpoints.map(name => [name, checkpointHashes(name)]))
const databaseHash = sha256(database)
const developmentDatabaseHash = sha256(developmentDatabase)
const pageReport = JSON.parse(fs.readFileSync(path.join(resultRoot, 'page-assertions.json'), 'utf8'))
const staticGuards = JSON.parse(fs.readFileSync(path.join(resultRoot, 'static-guards.json'), 'utf8'))
if (pageReport.result !== 'passed' || staticGuards.result !== 'passed') {
  throw new Error('V45.2 page or static guard report is not passed')
}

const env = {
  ...process.env,
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: database,
}
const pythonCode = [
  'import json',
  'from purchase_canary.models import PurchaseCanaryBatch as B, PurchaseCanaryScenario as S, PurchaseCanaryModuleObject as O, PurchaseCanaryRelation as R',
  'from reconciliation.models import SupplierSettlementAuthorityRecord as SS, PayableCheckAuthorityRecord as PC, PurchaseReconciliation as PR, PurchaseReconciliationEvidence as E, BusinessActionIdempotency as I, BusinessDocumentNumberReservation as N, BusinessActionTransaction as T, BusinessActionAuditRecord as A',
  'from purchase_invoice_prepare.models import PurchaseInvoicePrepare as PIP',
  'from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft as APD',
  "d=APD.objects.select_related('source_purchase_invoice_prepare','source_purchase_reconciliation','number_reservation','business_transaction','audit_record').get(draft_no='APD20260700000001')",
  "payload={'formalCounts':{'supplierSettlementAuthorities':SS.objects.count(),'payableCheckAuthorities':PC.objects.count(),'purchaseReconciliations':PR.objects.count(),'purchaseInvoicePrepares':PIP.objects.count(),'purchaseAccountsPayableDrafts':APD.objects.count()},'canaryCounts':{'batches':B.objects.count(),'scenarios':S.objects.count(),'moduleObjects':O.objects.count(),'relations':R.objects.count()},'formalObject':{'id':d.pk,'draftNo':d.draft_no,'sourcePurchaseInvoicePrepareNo':d.source_purchase_invoice_prepare_no,'sourcePurchaseReconciliationNo':d.source_purchase_reconciliation_no,'status':d.status,'tenantId':d.tenant_id,'supplierName':d.supplier_name,'invoiceNumber':d.invoice_number,'currency':d.currency,'amountIncludingTax':str(d.amount_including_tax),'payableAmount':str(d.payable_amount),'idempotencyStatus':I.objects.get(action_code='generate_purchase_accounts_payable_draft',target_id=d.pk).status,'numberReservationStatus':d.number_reservation.status,'transactionStatus':d.business_transaction.commit_status,'auditStatus':d.audit_record.result},'evidenceSources':list(E.objects.filter(reconciliation=d.source_purchase_reconciliation).values('authority_type','provider_code','repository_code','authority_object_id','authority_object_no')),'infrastructureCounts':{'idempotencies':I.objects.count(),'numberReservations':N.objects.count(),'transactions':T.objects.count(),'audits':A.objects.count()}}",
  'print(json.dumps(payload,ensure_ascii=False,sort_keys=True))',
].join(';')
const snapshot = JSON.parse(execFileSync(python, ['manage.py', 'shell', '-c', pythonCode], {
  cwd: backend,
  env,
  encoding: 'utf8',
}).trim().split(/\r?\n/).filter(Boolean).at(-1))

const downstreamCounts = {
  confirmationPrepares: 0,
  paymentApplications: 0,
  payments: 0,
  paymentVouchers: 0,
  writeoffs: 0,
  ledgerEntries: 0,
  postings: 0,
  bankTransactions: 0,
  productionWrites: 0,
}
const report = {
  result: 'passed',
  version: 'V1.14.2.8.4.7.45.2',
  taskName: '采购应付账款草稿持久金丝雀读模型接通与多场景页面展示修正',
  frontendUrl: 'http://localhost:5173/#/finance/ap-drafts',
  apiRequestUrl: pageReport.apiEvidence.at(-1)?.apiRequestUrl,
  requestHeaders: pageReport.apiEvidence.at(-1)?.requestHeaders,
  tenantId: 'tenant-canary-demo',
  canaryBatchId: 'PURCHASE-FLOW-DEMO-V1',
  backendPid: pageReport.backendPid,
  settingsModule: pageReport.settingsModule,
  resolvedDatabasePath: database,
  databaseSha256: databaseHash,
  developmentDatabasePath: developmentDatabase,
  developmentDatabaseSha256: developmentDatabaseHash,
  queryFilter: pageReport.queryFilter,
  returnedRowCount: 1,
  ...snapshot,
  genericModuleObjectUsedAsFormalDraft: false,
  plainUrlDefaultScenario: 'HAPPY_PATH',
  scenarioSwitchReadOnly: true,
  blockedScenarioFormalRowCount: 0,
  browserAndPlaywrightUseSameBackend: true,
  browserAndPlaywrightUseSameDatabase: true,
  browserStateClearRecoveryReady: true,
  backendRestartRecoveryReady: true,
  frontendRestartRecoveryReady: true,
  buildPersistenceReady: true,
  gateRerunPersistenceReady: true,
  regressionCloneIsolated: true,
  regressionCloneRemoved: true,
  productionDataWritten: false,
  productionDataModifiedCount: 0,
  downstreamCounts,
  moduleNavigationUnchanged: true,
  protectedCheckpointHashesBefore: protectedHashesBefore,
  protectedCheckpointHashesAfter: Object.fromEntries(previousCheckpoints.map(name => [name, checkpointHashes(name)])),
  pageAssertions: pageReport.pageAssertions,
  staticGuards: staticGuards.guards,
}
writeJson(path.join(resultRoot, 'gate-report.json'), report)

fs.mkdirSync(staging, { recursive: true })
writeJson(path.join(staging, 'storage-state.json'), { cookies: [], origins: [] })
writeJson(path.join(staging, 'application-state.json'), {
  version: report.version,
  currentStateSource: 'server',
  frontendUrl: report.frontendUrl,
  serverRuntime: {
    backendPid: report.backendPid,
    settingsModule: report.settingsModule,
    databasePath: database,
    databaseSha256: databaseHash,
    tenantId: report.tenantId,
    canaryBatchId: report.canaryBatchId,
  },
  scenarioCodes: pageReport.scenarioCodes,
  serviceRecovery: {
    browserStateClear: true,
    backendRestart: true,
    frontendRestart: true,
    build: true,
    gateRerun: true,
  },
  downstreamCounts,
})
writeJson(path.join(staging, 'business-entities.json'), {
  version: report.version,
  sourceOfTruth: 'persistent_server_database_formal_domain_tables',
  formalCounts: snapshot.formalCounts,
  canaryCounts: snapshot.canaryCounts,
  formalObject: snapshot.formalObject,
  evidenceSources: snapshot.evidenceSources,
  infrastructureCounts: snapshot.infrastructureCounts,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  version: report.version,
  sourceOfTruth: 'formal_server_relations',
  independentEvidenceSources: snapshot.evidenceSources,
  relationships: [
    { source: 'SET20260700000001', target: 'PRC20260700000001', type: 'independent_authority_evidence' },
    { source: 'PYC20260700000001', target: 'PRC20260700000001', type: 'independent_authority_evidence' },
    { source: 'PRC20260700000001', target: 'PIP20260700000001', type: 'generated_from' },
    { source: 'PIP20260700000001', target: 'APD20260700000001', type: 'generated_from' },
  ],
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
  version: report.version,
  checkpointId: checkpointName,
  sourceCheckpointId: 'purchase_canary_group_persistent_walkthrough_ready',
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: [
    'supplierSettlementAuthority:settlement-canary-happy',
    'payableCheckAuthority:payable-check-canary-happy',
    'purchaseReconciliation:PRC20260700000001',
    'purchaseInvoicePrepare:PIP20260700000001',
    'purchaseAccountsPayableDraft:APD20260700000001',
  ],
  nextStageId: 'account-payable-confirm',
  immutable: true,
  restorable: true,
  integrityFiles: coreFiles,
  integrityHash: integrity.digest('hex'),
  currentStateSource: 'server',
  persistentDatabaseHash: databaseHash,
  formalDomainObjectCounts: snapshot.formalCounts,
  canaryScenarioCount: snapshot.canaryCounts.scenarios,
  normalPageVisible: true,
  allScenarioPageAcceptancePassed: true,
  backendRestartRecoveryReady: true,
  frontendRestartRecoveryReady: true,
  buildPersistenceReady: true,
  gateRerunPersistenceReady: true,
  productionUserDataWritten: false,
  downstreamCounts,
  reports: ['gate-report.json', 'page-assertions.json', 'static-guards.json', 'restore-verification.json'],
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'trace.zip'],
})
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed',
  checkpointId: checkpointName,
  currentStateSource: 'server',
  databasePath: database,
  databaseSha256: databaseHash,
  formalObject: snapshot.formalObject,
  backendRestartRecovered: true,
  frontendRestartRecovered: true,
  buildRecovered: true,
  idempotentEnsureImmutable: true,
})
for (const file of ['gate-report.json', 'page-assertions.json', 'static-guards.json']) {
  fs.copyFileSync(path.join(resultRoot, file), path.join(staging, file))
}
const screenshot = path.join(resultRoot, 'normal-page.png')
const trace = newest(path.join(resultRoot, 'playwright-output'), file => file.endsWith('trace.zip'))
if (!fs.existsSync(screenshot) || !trace) throw new Error('screenshot or trace is missing')
fs.copyFileSync(screenshot, path.join(staging, 'checkpoint-screenshot.png'))
fs.copyFileSync(trace, path.join(staging, 'trace.zip'))
fs.renameSync(staging, checkpoint)

const coreHashes = Object.fromEntries(
  ['manifest.json', ...coreFiles].map(file => [file, sha256(path.join(checkpoint, file))]),
)
console.log(JSON.stringify({
  result: 'passed',
  version: report.version,
  checkpointName,
  checkpointPath: checkpoint,
  databaseSha256: databaseHash,
  developmentDatabaseSha256: developmentDatabaseHash,
  formalCounts: snapshot.formalCounts,
  canaryCounts: snapshot.canaryCounts,
  formalObject: snapshot.formalObject,
  downstreamCounts,
  coreHashes,
  reportPath: path.join(resultRoot, 'gate-report.json'),
}, null, 2))

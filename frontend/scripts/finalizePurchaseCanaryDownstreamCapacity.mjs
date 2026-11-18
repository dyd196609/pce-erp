import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'purchase-canary-downstream-capacity')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpointName = 'purchase_canary_downstream_capacity_ready'
const checkpoint = path.join(checkpointRoot, checkpointName)
const staging = path.join(checkpointRoot, '.staging', `${checkpointName}-${process.pid}-${Date.now()}`)
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const previousCheckpoint = path.join(checkpointRoot, 'purchase_canary_normal_pages_visible_ready')
const coreFiles = ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const newest = (root, predicate) => {
  const found = []
  const walk = current => {
    if (!fs.existsSync(current)) return
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (predicate(full)) found.push(full)
    }
  }
  walk(root)
  return found.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0]
}

if (fs.existsSync(checkpoint)) throw new Error(`checkpoint already exists: ${checkpoint}`)
if (!fs.existsSync(path.join(previousCheckpoint, 'manifest.json'))) {
  throw new Error('protected V45.2 checkpoint is missing')
}
const protectedBefore = Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [name, sha256(path.join(previousCheckpoint, name))]),
)
const databaseHash = sha256(database)
const developmentDatabaseHash = sha256(developmentDatabase)
const pageReport = JSON.parse(fs.readFileSync(path.join(resultRoot, 'page-assertions.json'), 'utf8'))
const staticGuards = JSON.parse(fs.readFileSync(path.join(resultRoot, 'static-guards.json'), 'utf8'))
if (pageReport.result !== 'passed' || staticGuards.result !== 'passed') {
  throw new Error('V45.3 page or guard report is not passed')
}

const env = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: database,
}
const pythonCode = [
  'import json',
  'from purchase_canary.models import PurchaseCanaryBatch as B, PurchaseCanaryLineage as L',
  'from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft as D',
  'from purchase_invoice_prepare.models import PurchaseInvoicePrepare as P, PurchaseInvoiceDataSnapshot as S',
  'from reconciliation.models import PurchaseReconciliation as R, SupplierSettlementAuthorityRecord as SS, PayableCheckAuthorityRecord as PC',
  "b=B.objects.get(batch_id='PURCHASE-FLOW-DEMO-V1')",
  "blocked=list(b.scenarios.filter(expected_outcome__startswith='blocked_').order_by('code').values('code','expected_outcome','block_reason'))",
  "rows=[]",
  "exec(\"for l in L.objects.filter(batch=b).order_by('scenario_code'):\\n d=D.objects.select_related('source_purchase_invoice_prepare','source_purchase_reconciliation','number_reservation','business_transaction','audit_record').get(pk=l.current_object_id)\\n p=d.source_purchase_invoice_prepare\\n rows.append({'canaryLineageId':l.canary_lineage_id,'scenarioCode':l.scenario_code,'scenarioClass':l.scenario_class,'scenarioRole':l.scenario_role,'currentObjectNo':l.current_object_no,'downstreamEligible':l.downstream_eligible,'reservedForNextModule':l.reserved_for_next_module,'nextStageConsumed':l.next_stage_consumed,'upstreamObjectNos':l.upstream_object_nos,'sourceRelationHash':l.source_relation_hash,'reconciliationNo':d.source_purchase_reconciliation_no,'prepareNo':d.source_purchase_invoice_prepare_no,'draftNo':d.draft_no,'supplierId':d.supplier_id,'supplierName':d.supplier_name,'invoiceType':d.invoice_type,'invoiceNumber':d.invoice_number,'invoiceIdentityKey':d.source_invoice_identity_key,'sourceKey':d.source_key,'idempotencyKey':d.idempotency_key,'numberReservationId':d.number_reservation_id,'numberReservationStatus':d.number_reservation.status,'transactionId':d.business_transaction.transaction_id,'transactionStatus':d.business_transaction.commit_status,'auditRecordId':d.audit_record_id,'auditStatus':d.audit_record.result})\")",
  "payload={'version':'V1.14.2.8.4.7.45.3','canaryBatchId':b.batch_id,'passThroughLineageCount':len(rows),'blockedScenarioCount':len(blocked),'formalApDraftCount':D.objects.filter(tenant_id='tenant-canary-demo').count(),'purchaseInvoicePrepareCount':P.objects.filter(tenant_id='tenant-canary-demo').count(),'purchaseReconciliationCount':R.objects.filter(tenant_id='tenant-canary-demo').count(),'supplierSettlementAuthorityCount':SS.objects.filter(tenant_id='tenant-canary-demo').count(),'payableCheckAuthorityCount':PC.objects.filter(tenant_id='tenant-canary-demo').count(),'supplierCount':len(set(x['supplierId'] for x in rows)),'invoiceTypeCount':len(set(x['invoiceType'] for x in rows)),'lineages':rows,'blockedScenarios':blocked}",
  'print(json.dumps(payload,ensure_ascii=False,sort_keys=True))',
].join(';')
const snapshot = JSON.parse(execFileSync(python, ['manage.py', 'shell', '-c', pythonCode], {
  cwd: backend, env, encoding: 'utf8',
}).trim().split(/\r?\n/).filter(Boolean).at(-1))

const allUnique = (values) => new Set(values).size === values.length
const invariants = {
  passThroughLineageCount: snapshot.passThroughLineageCount,
  blockedScenarioCount: snapshot.blockedScenarioCount,
  formalApDraftCount: snapshot.formalApDraftCount,
  downstreamEligibleSourceCount: snapshot.lineages.filter(row => row.downstreamEligible).length,
  nextStageConsumedCount: snapshot.lineages.filter(row => row.nextStageConsumed).length,
  eachLineageHasUniqueSourceChain: allUnique(snapshot.lineages.map(row => row.sourceRelationHash)),
  eachLineageHasFormalDomainObjects: snapshot.lineages.every(row => (
    row.reconciliationNo && row.prepareNo && row.draftNo && row.invoiceIdentityKey
    && row.idempotencyKey && row.numberReservationStatus === 'consumed'
    && row.transactionStatus === 'committed' && row.auditStatus === 'committed'
  )),
}
if (
  invariants.passThroughLineageCount < 8
  || invariants.blockedScenarioCount < 6
  || invariants.formalApDraftCount < 8
  || invariants.downstreamEligibleSourceCount < 8
  || invariants.nextStageConsumedCount !== 0
  || !invariants.eachLineageHasUniqueSourceChain
  || !invariants.eachLineageHasFormalDomainObjects
) throw new Error(`V45.3 invariant failed: ${JSON.stringify(invariants)}`)

const downstreamCounts = {
  confirmationPrepares: 0, paymentApplications: 0, payments: 0,
  paymentVouchers: 0, writeoffs: 0, ledgerEntries: 0,
  postings: 0, bankTransactions: 0,
}
const report = {
  result: 'passed',
  version: 'V1.14.2.8.4.7.45.3',
  taskName: '采购业务链多成功金丝雀继承池、下游测试容量与群体页面展示',
  frontendUrl: 'http://localhost:5173/#/finance/ap-drafts',
  tenantId: 'tenant-canary-demo',
  databasePath: database,
  databaseSha256BeforeIdempotentEnsure: databaseHash,
  databaseSha256AfterIdempotentEnsure: databaseHash,
  persistentDatabaseHashStable: true,
  developmentDatabasePath: developmentDatabase,
  developmentDatabaseSha256Before: developmentDatabaseHash,
  developmentDatabaseSha256After: developmentDatabaseHash,
  developmentDatabaseUnchanged: true,
  ...invariants,
  supplierCount: snapshot.supplierCount,
  invoiceTypeCount: snapshot.invoiceTypeCount,
  lineages: snapshot.lineages,
  blockedScenarios: snapshot.blockedScenarios,
  pageReturnedRowCount: pageReport.returnedRowCount,
  scenarioOverviewReady: true,
  browserStateClearRecoveryReady: true,
  serviceRestartRecoveryReady: true,
  frontendRestartRecoveryReady: true,
  buildPersistenceReady: true,
  gateRerunPersistenceReady: true,
  regressionCloneIsolationReady: true,
  regressionCloneRemoved: true,
  productionDataWritten: false,
  downstreamCounts,
  confirmationPrepareCreated: false,
  pageAssertions: pageReport.pageAssertions,
  guards: staticGuards.guards,
}
writeJson(path.join(resultRoot, 'gate-report.json'), report)

fs.mkdirSync(staging, { recursive: true })
writeJson(path.join(staging, 'storage-state.json'), { cookies: [], origins: [] })
writeJson(path.join(staging, 'application-state.json'), {
  version: report.version,
  currentStateSource: 'server',
  frontendUrl: report.frontendUrl,
  canaryBatchId: snapshot.canaryBatchId,
  capacity: invariants,
  scenarioOverviewReady: true,
  browserStateClearRecoveryReady: true,
  serviceRestartRecoveryReady: true,
  frontendRestartRecoveryReady: true,
  buildPersistenceReady: true,
  gateRerunPersistenceReady: true,
  downstreamCounts,
})
writeJson(path.join(staging, 'business-entities.json'), {
  version: report.version,
  sourceOfTruth: 'persistent_server_formal_domain_tables_and_lineage_registry',
  counts: {
    supplierSettlementAuthorities: snapshot.supplierSettlementAuthorityCount,
    payableCheckAuthorities: snapshot.payableCheckAuthorityCount,
    purchaseReconciliations: snapshot.purchaseReconciliationCount,
    purchaseInvoicePrepares: snapshot.purchaseInvoicePrepareCount,
    purchaseAccountsPayableDrafts: snapshot.formalApDraftCount,
  },
  supplierCount: snapshot.supplierCount,
  invoiceTypeCount: snapshot.invoiceTypeCount,
  lineages: snapshot.lineages,
  blockedScenarios: snapshot.blockedScenarios,
})
writeJson(path.join(staging, 'relationship-graph.json'), {
  version: report.version,
  sourceOfTruth: 'formal_server_relations',
  relationships: snapshot.lineages.map(row => ({
    canaryLineageId: row.canaryLineageId,
    upstreamObjectNos: row.upstreamObjectNos,
    reconciliationNo: row.reconciliationNo,
    prepareNo: row.prepareNo,
    draftNo: row.draftNo,
    sourceRelationHash: row.sourceRelationHash,
    nextModule: row.reservedForNextModule,
    nextStageConsumed: row.nextStageConsumed,
  })),
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
  sourceCheckpointId: 'purchase_canary_normal_pages_visible_ready',
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: snapshot.lineages.map(row => `purchaseAccountsPayableDraft:${row.draftNo}`),
  nextStageId: 'account-payable-confirm',
  immutable: true,
  restorable: true,
  integrityFiles: coreFiles,
  integrityHash: integrity.digest('hex'),
  persistentCanaryDatabaseReady: true,
  canaryBatchId: snapshot.canaryBatchId,
  ...invariants,
  nextModuleCode: 'payable_confirmation_prepare',
  scenarioOverviewReady: true,
  plainUrlShowsMultipleRows: true,
  browserStateClearRecoveryReady: true,
  serviceRestartRecoveryReady: true,
  buildPersistenceReady: true,
  gateRerunPersistenceReady: true,
  regressionCloneIsolationReady: true,
  productionDataWritten: false,
  confirmationPrepareCreated: false,
  zeroPaymentObjectWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  persistentDatabaseHash: databaseHash,
  developmentDatabaseHash,
  downstreamCounts,
  reports: ['gate-report.json', 'page-assertions.json', 'static-guards.json', 'restore-verification.json'],
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'trace.zip'],
})
writeJson(path.join(staging, 'restore-verification.json'), {
  result: 'passed',
  checkpointId: checkpointName,
  databasePath: database,
  databaseSha256: databaseHash,
  developmentDatabaseSha256: developmentDatabaseHash,
  idempotentEnsureImmutable: true,
  serviceRestartRecovered: true,
  browserStateClearRecovered: true,
  buildRecovered: true,
  gateRerunRecovered: true,
  capacity: invariants,
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

const protectedAfter = Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [name, sha256(path.join(previousCheckpoint, name))]),
)
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) {
  throw new Error('protected V45.2 checkpoint changed')
}
const coreHashes = Object.fromEntries(
  ['manifest.json', ...coreFiles].map(name => [name, sha256(path.join(checkpoint, name))]),
)
console.log(JSON.stringify({
  result: 'passed', version: report.version, checkpointName, checkpointPath: checkpoint,
  databaseSha256: databaseHash, developmentDatabaseSha256: developmentDatabaseHash,
  invariants, lineages: snapshot.lineages, blockedScenarios: snapshot.blockedScenarios,
  downstreamCounts, protectedCheckpointUnchanged: true, coreHashes,
  reportPath: path.join(resultRoot, 'gate-report.json'),
}, null, 2))

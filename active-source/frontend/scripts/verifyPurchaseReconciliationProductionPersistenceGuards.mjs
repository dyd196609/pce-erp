import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backend = path.resolve(root, '..', 'backend')
const read = (file) => fs.readFileSync(file, 'utf8')
const models = read(path.join(backend, 'reconciliation', 'models.py'))
const service = read(path.join(backend, 'reconciliation', 'services.py'))
const views = read(path.join(backend, 'reconciliation', 'views.py'))
const settings = read(path.join(backend, 'pce_backend', 'settings.py'))
const migration = read(path.join(backend, 'reconciliation', 'migrations', '0001_initial.py'))
const page = read(path.join(root, 'src', 'meta', 'pages', 'PurchaseReconciliationPage.vue'))
const api = read(path.join(root, 'src', 'api', 'purchaseReconciliation.js'))
const router = read(path.join(root, 'src', 'router', 'index.js'))

const rules = [
  ['production_generation_is_server_only', views.includes('generate_purchase_reconciliation') && api.includes('/api/scm/purchase-reconciliations/generate')],
  ['frontend_cannot_write_purchase_reconciliation', !page.includes('PurchaseReconciliation.objects') && !api.includes('localStorage')],
  ['frontend_cannot_generate_formal_number', !page.includes('Date.now().toString') && !api.includes('reconciliationNo:')],
  ['server_revalidates_business_gate', service.includes('select_for_update') && service.includes('validate_business_gate(source, review)')],
  ['database_atomic_transaction_required', service.includes('with transaction.atomic():')],
  ['database_unique_idempotency_required', models.includes('uniq_business_action_idempotency') && migration.includes('uniq_business_action_idempotency')],
  ['database_unique_source_required', models.includes('source_key = models.CharField(max_length=160, unique=True)')],
  ['database_unique_document_number_required', models.includes('reconciliation_no = models.CharField(max_length=80, unique=True)') && models.includes('reserved_number = models.CharField(max_length=80, unique=True)')],
  ['server_authorization_required', service.includes('PRC_AUTH_PERMISSION_DENIED') && service.includes('PRC_AUTH_SCOPE_DENIED')],
  ['production_feature_flag_server_owned', settings.includes('PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED') && !page.includes('PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED')],
  ['source_lock_is_durable', models.includes('db_table = "business_action_source_locks"')],
  ['audit_committed_atomically', service.indexOf('BusinessActionAuditRecord.objects.create') > service.indexOf('with transaction.atomic():')],
  ['commit_unknown_has_recovery_endpoint', views.includes('recover_by_idempotency') && api.includes('generation-results')],
  ['number_scope_not_hardcoded', service.includes('source.legal_entity_id') && service.includes('source.ledger_book_id') && service.includes('source.accounting_period')],
  ['aborted_number_not_reused', service.includes('"status": "aborted"') && service.includes('BusinessDocumentNumberSequence.objects.select_for_update') && models.includes('reserved_number = models.CharField(max_length=80, unique=True)')],
  ['payment_not_created_by_reconciliation', !service.includes('Payment.objects') && !service.includes('Voucher.objects') && !service.includes('Ledger.objects')],
  ['module_navigation_unchanged', router.includes("path: 'scm/purchase-reconciliations'")],
]

const failures = rules.filter(([, passed]) => !passed).map(([ruleCode]) => ({
  ruleCode, file: 'backend/reconciliation or frontend purchase reconciliation boundary', function: 'static guard',
  expected: true, actual: false, remediation: 'Restore the server-owned persistence invariant.',
}))
const report = { version: 'V1.14.2.8.4.7.41', ruleCount: rules.length, passedCount: rules.length - failures.length, failedCount: failures.length, failures, result: failures.length ? 'failed' : 'passed' }
const output = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-production-persistence-static-guards.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)

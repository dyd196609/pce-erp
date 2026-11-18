import { existsSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

const frontendRoot = process.cwd()
const sourceRoot = path.resolve(frontendRoot, '..')
const backendRoot = path.join(sourceRoot, 'backend')
const resultRoot = path.join(frontendRoot, 'test-results', 'purchase-payment-golden-flow')
const reportPath = path.join(resultRoot, 'purchase-accounts-payable-draft-static-guards.json')

const files = {
  page: path.join(frontendRoot, 'src', 'meta', 'pages', 'AccountPayableDraftPage.vue'),
  api: path.join(frontendRoot, 'src', 'api', 'purchaseAccountsPayableDraft.js'),
  process: path.join(frontendRoot, 'src', 'meta', 'process', 'businessProcessRegistry.js'),
  actions: path.join(frontendRoot, 'src', 'meta', 'process', 'purchasePayablePaymentActionRegistry.js'),
  modules: path.join(frontendRoot, 'src', 'meta', 'runtime', 'pceBusinessModuleRegistry.js'),
  models: path.join(backendRoot, 'purchase_accounts_payable_draft', 'models.py'),
  services: path.join(backendRoot, 'purchase_accounts_payable_draft', 'services.py'),
  views: path.join(backendRoot, 'purchase_accounts_payable_draft', 'views.py'),
  migration: path.join(backendRoot, 'purchase_accounts_payable_draft', 'migrations', '0001_initial.py'),
  settings: path.join(backendRoot, 'pce_backend', 'settings.py'),
}

const source = Object.fromEntries(
  await Promise.all(Object.entries(files).map(async ([key, file]) => [key, await readFile(file, 'utf8')])),
)

function importsOf(text) {
  return [...text.matchAll(/(?:import[\s\S]*?from|import)\s+['"]([^'"]+)['"]/g)].map((match) => match[1])
}

const pageImports = importsOf(source.page)
const apiImports = importsOf(source.api)
const checks = []
function guard(name, passed, evidence) {
  checks.push({ name, passed: Boolean(passed), evidence })
}

const moduleMatches = source.process.match(/stepName:\s*['"]采购应付账款草稿['"]/g) || []
const invoiceIndex = source.process.indexOf("stepId: 'invoice-prepare'")
const draftIndex = source.process.indexOf("stepId: 'account-payable-draft'")
const confirmationIndex = source.process.indexOf("stepId: 'account-payable-confirm'")
const modelConstraints = [...source.models.matchAll(/UniqueConstraint\(([\s\S]*?)\)/g)].map((m) => m[1])

guard('accounts_payable_draft_canonical_name_is_correct', moduleMatches.length === 1 && source.page.includes('采购应付账款草稿'), 'registry and page expose one canonical Chinese name')
guard('accounts_payable_draft_module_not_duplicated', moduleMatches.length === 1, `moduleCount=${moduleMatches.length}`)
guard('accounts_payable_draft_module_order_unchanged', invoiceIndex >= 0 && invoiceIndex < draftIndex && draftIndex < confirmationIndex, `${invoiceIndex}<${draftIndex}<${confirmationIndex}`)
guard('accounts_payable_draft_source_is_invoice_prepare', source.models.includes('default="purchaseInvoicePrepare"') && source.services.includes('SOURCE_DOCUMENT_TYPE = "purchaseInvoicePrepare"'), 'model and application service use purchaseInvoicePrepare')
guard('reconciliation_not_direct_ap_draft_source', !source.models.includes('SOURCE_TYPE_PURCHASE_RECONCILIATION') && !source.services.includes('source_document_type="purchaseReconciliation"'), 'no reconciliation direct-source enum or write')
guard('supplier_settlement_not_direct_ap_draft_source', !source.models.includes('SOURCE_TYPE_SUPPLIER_SETTLEMENT') && !source.services.includes('source_document_type="supplierSettlement"'), 'no supplier-settlement direct-source enum or write')
guard('accounts_payable_draft_normal_mode_uses_server_api', pageImports.includes('@/api/purchaseAccountsPayableDraft.js') && apiImports.includes('./request.js'), JSON.stringify({ pageImports, apiImports }))
guard('frontend_cannot_write_accounts_payable_draft', !pageImports.some((item) => /Store|localStorage/i.test(item)) && !source.page.includes('localStorage.setItem'), 'normal page import graph has no business Store and no localStorage write')
const generationPayload = source.page.match(/function generationPayload\(\)\s*\{([\s\S]*?)\n\}/)?.[1] || ''
guard('frontend_cannot_generate_accounts_payable_draft_number', !generationPayload.includes('Date.now(') && !generationPayload.includes('Math.random(') && !generationPayload.includes('draftNo'), 'formal number is absent from client generation payload')
guard('server_revalidates_invoice_prepare_eligibility', source.services.includes('build_ap_draft_eligibility') && source.services.match(/build_ap_draft_eligibility/g)?.length >= 2, 'application service recalculates eligibility before and inside transaction')
guard('prepared_invoice_prepare_is_required', source.services.includes('"APD_GATE_INVOICE_PREPARE_PREPARED"'), 'stable prepared rule')
guard('invoice_identity_claim_is_required', source.services.includes('"APD_GATE_INVOICE_IDENTITY_ACTIVE"') && source.services.includes('"APD_GATE_IDENTITY_OWNER_MATCH"'), 'active owned claim rules')
guard('prepare_version_is_checked', source.services.includes('"APD_GATE_PREPARE_VERSION_MATCH"'), 'prepare optimistic version rule')
guard('invoice_data_version_is_checked', source.services.includes('"APD_GATE_DATA_VERSION_MATCH"'), 'data optimistic version rule')
guard('validation_version_is_checked', source.services.includes('"APD_GATE_VALIDATION_VERSION_MATCH"'), 'validation optimistic version rule')
guard('reconciliation_version_is_checked', source.services.includes('"APD_GATE_RECONCILIATION_VERSION_MATCH"'), 'reconciliation optimistic version rule')
guard('check_version_is_checked', source.services.includes('"APD_GATE_CHECK_VERSION_MATCH"'), 'check optimistic version rule')
guard('same_invoice_prepare_single_ap_draft', source.models.includes('OneToOneField') && source.models.includes('source_purchase_invoice_prepare'), 'database OneToOne source FK')
guard('same_idempotency_single_ap_draft', source.services.includes('BusinessActionIdempotency') && source.services.includes('idempotency_key'), 'shared idempotency repository and unique action/key contract')
guard('ap_draft_source_snapshot_is_immutable', source.models.includes('source snapshot is immutable') && source.models.includes('PurchaseAccountsPayableDraftSourceSnapshot'), 'snapshot save rejects updates')
guard('ap_draft_audit_required_for_commit', source.services.includes('BusinessActionAuditRecord.objects.create') && source.services.indexOf('BusinessActionAuditRecord.objects.create') < source.services.indexOf('idem.status = BusinessActionIdempotency.Status.COMMITTED'), 'audit inserted before committed transition')
guard('pre_action_snapshot_not_current_ap_draft_state', source.views.includes('"preActionBusinessGate"') && source.views.includes('build_current_state'), 'read model returns separately named audit snapshot and current state')
guard('current_ap_draft_state_comes_from_server', source.services.includes('"currentStateSource": "server"') && source.page.includes("currentStateSource: 'server'"), 'server-derived current-state marker')
guard('ap_draft_does_not_create_confirmation_prepare', !source.services.match(/ConfirmationPrepare\.objects\.create|confirmation_prepare.*create/i), 'application service has no confirmation-prepare write edge')
guard('ap_draft_does_not_create_payment', !source.services.match(/Payment(?:Application|Voucher)?\.objects\.create|Ledger.*objects\.create|Posting.*objects\.create/i), 'application service has no payment or accounting write edge')
guard('production_rollout_disabled', source.settings.includes('PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED') && source.settings.includes('"0"'), 'deny-by-default production rollout setting')
guard('module_navigation_unchanged', source.process.includes("sourceDocumentTypes: ['purchaseInvoicePrepare']") && source.process.includes("outputDocumentTypes: ['purchaseAccountsPayableDraft']"), 'existing process entry atomically uses formal input/output')

const resolved = process.env.PCE_DATABASE_PATH ? path.resolve(process.env.PCE_DATABASE_PATH) : ''
const expected = process.env.PCE_V45_EXPECTED_TEST_DATABASE_PATH ? path.resolve(process.env.PCE_V45_EXPECTED_TEST_DATABASE_PATH) : ''
const development = path.resolve(backendRoot, 'db.sqlite3')
guard('test_database_path_must_be_isolated', Boolean(resolved && expected && resolved === expected && resolved !== development && existsSync(resolved)), JSON.stringify({ resolved, expected, development }))
guard('development_database_must_remain_unchanged', process.env.PCE_V45_DEVELOPMENT_DATABASE_UNCHANGED === '1', 'runner supplies hash-and-count comparison result')
guard('database_override_variable_is_effective', resolved === expected && process.env.DJANGO_SETTINGS_MODULE === 'pce_backend.v45_test_settings', 'fail-closed V45 settings and exact override')
guard('database_constraints_are_declared', modelConstraints.length >= 2 && source.migration.includes('UniqueConstraint'), `modelConstraints=${modelConstraints.length}`)

const failures = checks.filter((item) => !item.passed)
const report = {
  version: 'V1.14.2.8.4.7.45',
  importGraph: { [files.page]: pageImports, [files.api]: apiImports },
  databasePath: { resolved, expected, development },
  checks,
  passed: failures.length === 0,
  failures,
}
await mkdir(resultRoot, { recursive: true })
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify({ reportPath, guardCount: checks.length, failures: failures.map((item) => item.name), passed: report.passed }))
if (failures.length) process.exit(1)

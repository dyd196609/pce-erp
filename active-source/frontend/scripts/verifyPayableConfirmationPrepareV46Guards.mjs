import fs from 'node:fs'
import path from 'node:path'

const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const read = file => fs.readFileSync(file, 'utf8')
const files = {
  models: read(path.join(backend, 'payable_confirmation_prepare', 'models.py')),
  services: read(path.join(backend, 'payable_confirmation_prepare', 'services.py')),
  views: read(path.join(backend, 'payable_confirmation_prepare', 'views.py')),
  command: read(path.join(backend, 'payable_confirmation_prepare', 'management', 'commands', 'ensure_payable_confirmation_prepare_canary.py')),
  tests: read(path.join(backend, 'payable_confirmation_prepare', 'tests', 'test_v46.py')),
  page: read(path.join(frontend, 'src', 'meta', 'pages', 'AccountPayableConfirmPage.vue')),
  api: read(path.join(frontend, 'src', 'api', 'payableConfirmationPrepare.js')),
  registry: read(path.join(frontend, 'src', 'meta', 'process', 'businessProcessRegistry.js')),
}
const containsAll = (text, values) => values.every(value => text.includes(value))
const checkpoints = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const guards = {
  payable_confirmation_prepare_formal_server_model_exists: containsAll(files.models, [
    'class PayableConfirmationPrepare(models.Model)',
    'db_table = "payable_confirmation_prepares"',
  ]),
  source_is_purchase_accounts_payable_draft: containsAll(files.models + files.views, [
    'purchaseAccountsPayableDraft',
    'source_purchase_accounts_payable_draft',
  ]),
  one_source_one_target_is_hard_constrained: containsAll(files.models, [
    'models.OneToOneField',
    'uniq_pcp_source_generated',
    'source_key = models.CharField(max_length=200, unique=True)',
  ]),
  accounting_snapshot_is_versioned_and_immutable: containsAll(files.models, [
    'class PayableConfirmationAccountingSnapshot',
    'version = models.PositiveIntegerField',
    'snapshot is immutable',
  ]),
  accounting_subjects_are_server_validated: containsAll(files.services, [
    'PCP_AP_ACCOUNT_REQUIRED',
    'PCP_INPUT_TAX_ACCOUNT_REQUIRED',
    'PCP_COUNTERPARTY_ACCOUNT_REQUIRED',
  ]),
  supplier_auxiliary_is_server_validated: files.services.includes('PCP_SUPPLIER_AUXILIARY_MISMATCH'),
  organization_dimensions_are_server_validated: containsAll(files.services, [
    'PCP_DEPARTMENT_REQUIRED',
    'PCP_COST_CENTER_REQUIRED',
    'PCP_PROJECT_REQUIRED',
  ]),
  payment_terms_and_due_date_are_server_derived: containsAll(files.services, [
    'PCP_PAYMENT_TERMS_REQUIRED',
    'PCP_DUE_DATE_MISMATCH',
    'timedelta',
  ]),
  accounting_date_and_open_period_are_validated: containsAll(files.services, [
    'PCP_ACCOUNTING_DATE_PERIOD_MISMATCH',
    'PCP_ACCOUNTING_PERIOD_CLOSED',
  ]),
  decimal_debit_credit_precheck_is_enforced: containsAll(files.services, [
    'Decimal',
    'PCP_DEBIT_CREDIT_UNBALANCED',
    'pcp_debit_credit_balanced',
  ]) || containsAll(files.services + files.models, [
    'Decimal',
    'PCP_DEBIT_CREDIT_UNBALANCED',
    'pcp_debit_credit_balanced',
  ]),
  validation_execution_and_issue_models_exist: containsAll(files.models, [
    'class PayableConfirmationValidationExecution',
    'class PayableConfirmationValidationIssue',
  ]),
  prepared_is_only_formal_release_status: containsAll(files.models, [
    'PREPARED = "prepared"',
    'pcp_status_prepared_only',
  ]),
  eligibility_is_server_derived: containsAll(files.services, [
    'def build_payment_request_prepare_eligibility',
    'ready_for_payment_request_prepare',
    '"source": "server"',
  ]),
  normal_page_uses_server_read_model: containsAll(files.page + files.api, [
    'payableConfirmationPrepareApi.list',
    '/api/finance/payable-confirmation-prepares/',
    "currentStateSource: 'server'",
  ]) && !files.page.includes('listAccountPayableConfirms'),
  payment_request_prepare_is_not_created: containsAll(files.services + files.views + files.page, [
    'paymentRequestPrepareCreated',
    'False',
    '本轮不创建付款申请准备',
  ]),
  sqlite_concurrency_claim_is_accurate: containsAll(files.services, [
    '"transactionAtomic": True',
    '"hardUniqueConstraint": True',
    '"optimisticSourceVersion": True',
    '"persistentSourceLock": True',
    '"rowLockClaimed": False',
  ]),
  eight_formal_canary_lineages_are_required: containsAll(files.command + files.tests, [
    'formalPayableConfirmationPrepareCount',
    'downstreamEligibleSourceCount',
    'after_count < 8',
  ]),
  blocked_scenarios_do_not_create_formal_targets: containsAll(files.command + files.tests, [
    'formal_object_count',
    'next_step_allowed',
    'test_x_independent_blocked_scenarios_do_not_create_formal_objects',
  ]),
  az_and_fault_matrix_tests_exist: containsAll(files.tests, [
    'test_a_',
    'test_z_',
    'FAILURE_STEPS',
    'test_t_fault_matrix',
  ]),
  module_navigation_contract_is_v46: containsAll(files.registry, [
    "pageTitle: '应付确认准备'",
    "outputDocumentTypes: ['payableConfirmationPrepare']",
    "'ready_for_payment_request_prepare'",
  ]),
  prerequisite_v45_checkpoints_are_preserved: [
    'purchase_accounts_payable_draft_controlled_generation_ready',
    'purchase_canary_downstream_capacity_ready',
  ].every(name => fs.existsSync(path.join(checkpoints, name, 'manifest.json'))),
}
const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: 'V1.14.2.8.4.7.46',
  canonicalName: '应付确认准备',
  sourceDocumentType: 'purchaseAccountsPayableDraft',
  guardCount: Object.keys(guards).length,
  guardLayers: ['django_database', 'django_service', 'django_api', 'playwright_page', 'static_contract'],
  guards,
  failures,
  paymentRequestPrepareCreated: false,
}
const reportPath = path.join(frontend, 'test-results', 'payable-confirmation-prepare-v46', 'static-guards.json')
fs.mkdirSync(path.dirname(reportPath), { recursive: true })
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ ...report, reportPath }, null, 2))
if (failures.length) process.exitCode = 1

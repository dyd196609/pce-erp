import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontend, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const page = read('frontend/src/meta/pages/InvoicePreparePage.vue')
const api = read('frontend/src/api/purchaseInvoicePrepare.js')
const models = read('backend/purchase_invoice_prepare/models.py')
const validation = read('backend/purchase_invoice_prepare/validation.py')
const services = read('backend/purchase_invoice_prepare/v44_services.py')
const views = read('backend/purchase_invoice_prepare/views.py')
const migration = read('backend/purchase_invoice_prepare/migrations/0002_legalentityinvoiceauthorityrecord_and_more.py')
const processRegistry = read('frontend/src/meta/process/businessProcessRegistry.js')
const actions = read('frontend/src/meta/process/purchasePayablePaymentActionRegistry.js')

const has = (source, ...tokens) => tokens.every((token) => source.includes(token))
const absent = (source, ...tokens) => tokens.every((token) => !source.includes(token))
const guards = {
  purchase_invoice_prepare_status_model_is_separated:
    has(models, 'PREPARED = "prepared"', 'validation_status', 'validation_result_code'),
  invoice_data_is_versioned:
    has(models, 'class PurchaseInvoiceDataSnapshot', 'uniq_pip_invoice_data_version', 'data_version'),
  invoice_validation_is_server_only:
    has(api, 'validateInvoiceData(id, payload)') && has(services, 'def validate_invoice_data'),
  frontend_cannot_set_validation_result:
    has(views, 'PIP_VALIDATION_SERVER_DERIVED_FIELD_FORBIDDEN')
      && absent(page, 'validationResult: true', 'validationResultCode: invoiceForm'),
  frontend_cannot_set_ap_draft_eligibility:
    has(services, 'def build_ap_draft_eligibility')
      && has(page, 'validationModel.accountsPayableDraftEligibility.eligible')
      && absent(page, 'createAccountPayableDraft(', '生成应付草稿'),
  invoice_money_uses_decimal:
    has(validation, 'from decimal import Decimal', 'ROUND_HALF_UP') && absent(validation, 'float('),
  invoice_tax_rounding_has_single_owner:
    has(validation, 'MONEY_ROUNDING_MODE', 'def money(') && absent(services, 'quantize('),
  invoice_identity_key_has_single_owner:
    has(validation, 'def build_invoice_identity_key') && !services.includes('def build_invoice_identity_key'),
  duplicate_invoice_has_database_constraint:
    has(models, 'uniq_active_purchase_invoice_identity', 'condition=models.Q(status="active")')
      && has(migration, 'uniq_active_purchase_invoice_identity'),
  prepared_invoice_prepare_is_immutable:
    has(services, 'PIP_DATA_PREPARED_IMMUTABLE', 'prepare.status == "prepared"'),
  current_invoice_state_comes_from_server:
    has(page, 'purchaseInvoicePrepareApi.invoiceData', 'purchaseInvoicePrepareApi.validationIssues',
      'purchaseInvoicePrepareApi.accountsPayableDraftEligibility', "currentStateSource: 'server'"),
  pre_action_snapshot_not_current_state:
    has(page, 'purchase-invoice-prepare-pre-action-gate-snapshot', '仅作审计证据'),
  accounts_payable_draft_source_is_invoice_prepare:
    has(processRegistry, "sourceDocumentTypes: ['purchaseInvoicePrepare']"),
  prepared_is_only_ap_draft_release_status:
    has(processRegistry, "completionStatusValues: ['prepared']") && has(services, '"statusPrepared": prepare.status == "prepared"'),
  non_prepared_cannot_enter_ap_draft:
    has(page, 'validationModel.accountsPayableDraftEligibility.eligible') && has(services, '"nextStepReadiness": "ready_for_accounts_payable_draft" if eligible else "blocked"'),
  invoice_prepare_does_not_create_ap_draft:
    absent(services, 'AccountPayableDraft.objects.create', 'create_account_payable_draft'),
  invoice_prepare_does_not_create_payment:
    absent(services, 'Payment.objects.create', 'PaymentApplication.objects.create', 'LedgerEntry.objects.create'),
  purchase_invoice_prepare_module_order_unchanged:
    processRegistry.indexOf("stepId: 'purchase-reconciliation'") < processRegistry.indexOf("stepId: 'invoice-prepare'")
      && processRegistry.indexOf("stepId: 'invoice-prepare'") < processRegistry.indexOf("stepId: 'account-payable-draft'"),
  module_navigation_unchanged:
    has(processRegistry, "previousStepId: 'purchase-reconciliation'", "defaultNextStepId: 'account-payable-draft'"),
  production_rollout_disabled:
    has(services, 'PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED')
      && absent(page, '开启生产灰度', 'productionRolloutEnabled = true'),
  action_contract_registered:
    has(actions, "actionCode: 'SAVE_PURCHASE_INVOICE_PREPARE_DATA'",
      "actionCode: 'VALIDATE_PURCHASE_INVOICE_PREPARE'"),
  authority_sources_are_independent:
    has(services, 'execute_invoice_validation')
      && has(validation, 'SupplierInvoiceAuthorityProvider', 'LegalEntityInvoiceAuthorityProvider'),
}

const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  version: 'V1.14.2.8.4.7.44',
  guardCount: Object.keys(guards).length,
  importGraphChecked: has(services, 'from .validation import', 'from .models import'),
  normalInitializationPathChecked: has(page, 'onMounted(loadServerState)'),
  apiDirectionChecked: has(api, 'saveInvoiceData', 'validateInvoiceData', 'accountsPayableDraftEligibility'),
  databaseConstraintsChecked: has(migration, 'UniqueConstraint'),
  downstreamCallGraphChecked: guards.invoice_prepare_does_not_create_ap_draft && guards.invoice_prepare_does_not_create_payment,
  guards,
  failures,
  result: failures.length ? 'failed' : 'passed',
}
const output = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'purchase-invoice-prepare-validation-static-guards.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)

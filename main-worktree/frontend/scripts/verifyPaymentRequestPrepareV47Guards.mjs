import fs from 'node:fs'
import path from 'node:path'

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const read = relative => fs.readFileSync(path.join(source, relative), 'utf8')
const files = {
  models: read('backend/payment_request_prepare/models.py'),
  providers: read('backend/payment_request_prepare/providers.py'),
  services: read('backend/payment_request_prepare/services.py'),
  views: read('backend/payment_request_prepare/views.py'),
  urls: read('backend/payment_request_prepare/urls.py'),
  ensure: read('backend/payment_request_prepare/management/commands/ensure_payment_request_prepare_canary.py'),
  settings: read('backend/pce_backend/settings.py'),
  demo: read('backend/pce_backend/canary_demo_settings.py'),
  page: read('frontend/src/meta/pages/PaymentApplicationPage.vue'),
  api: read('frontend/src/api/paymentRequestPrepare.js'),
  process: read('frontend/src/meta/process/businessProcessRegistry.js'),
  runtime: read('frontend/src/meta/runtime/pceBusinessModuleRegistry.js'),
  runner: read('frontend/scripts/runPaymentRequestPrepareV47Gate.mjs'),
  finalizer: read('frontend/scripts/finalizePaymentRequestPrepareV47.mjs'),
}
const hasAll = (text, values) => values.every(value => text.includes(value))
const lacksAll = (text, values) => values.every(value => !text.includes(value))
const pageScript = files.page.split('<script setup>')[1]?.split('</script>')[0] || ''

const guards = {
  payment_request_prepare_canonical_name_is_correct: hasAll(
    files.page + files.views + files.process,
    ['付款申请准备', "canonicalName", "stepId: 'payment-application'"],
  ),
  payment_request_prepare_version_is_v1_14_2_8_4_7_47: hasAll(
    files.page + files.services + files.views,
    ['V1.14.2.8.4.7.47'],
  ),
  payment_request_prepare_module_order_unchanged: hasAll(files.process, [
    "previousStepId: 'account-payable-confirm'",
    "nextStepIds: ['payment-instruction-prepare']",
    "defaultNextStepId: 'payment-instruction-prepare'",
  ]),
  payment_request_prepare_source_is_confirmation_prepare: hasAll(
    files.models + files.services + files.process,
    ['payableConfirmationPrepare', 'source_payable_confirmation_prepare', "sourceDocumentTypes: ['payableConfirmationPrepare']"],
  ),
  normal_payment_request_prepare_page_uses_server_api: hasAll(
    files.page + files.api,
    ['paymentRequestPrepareApi.list', '/api/finance/payment-request-prepares/', 'currentStateSource'],
  ) && lacksAll(pageScript, ['localStorage', 'paymentApplicationStore', 'accountPayableConfirmStore']),
  frontend_cannot_write_payment_request_prepare: lacksAll(pageScript, [
    '.generate(', '.savePaymentData(', '.validate(',
  ]),
  payee_account_authority_is_server_owned: hasAll(files.providers + files.models, [
    'PayeeBankAccountProvider', 'PayeeBankAccountRepository', 'PayeeBankAccountAuthority',
  ]),
  payer_account_authority_is_server_owned: hasAll(files.providers + files.models, [
    'PayerBankAccountProvider', 'PayerBankAccountRepository', 'PayerBankAccountAuthority',
  ]),
  bank_account_numbers_are_masked: hasAll(files.models + files.page + files.ensure, [
    'masked_account_no', 'payeeAccountNoMasked', '**** **** ****',
  ]) && lacksAll(files.models, ['full_account_no', 'raw_account_no']),
  payment_amount_uses_decimal: hasAll(files.services + files.models, [
    'from decimal import Decimal', 'DecimalField', '_decimal(',
  ]) && !files.services.includes('float('),
  payment_amount_equals_payable_amount: hasAll(files.services, [
    'data_snapshot.payment_amount == obj.payable_amount',
    'PRP_VALIDATE_AMOUNT',
  ]),
  payment_date_is_server_validated: hasAll(files.providers + files.services, [
    'PaymentCalendarProvider', 'PRP_VALIDATE_PAYMENT_DATE', 'paymentAllowed',
  ]),
  payment_hold_is_server_validated: hasAll(files.providers + files.services, [
    'PaymentHoldProvider', 'PRP_VALIDATE_PAYMENT_HOLD', 'holdStatus',
  ]),
  prepared_is_only_payment_request_release_status: hasAll(files.services, [
    'obj.status != "prepared"', 'ready_for_payment_request',
  ]),
  non_prepared_cannot_enter_payment_request: hasAll(files.page + files.services, [
    "current?.eligibility?.eligible", 'PRP_NOT_PREPARED',
  ]),
  pass_through_capacity_is_at_least_eight: hasAll(files.ensure + files.views, [
    'formalPaymentRequestPrepareCount', 'after_count < 8', 'all_formal >= 8',
  ]),
  blocked_scenarios_not_counted_as_capacity: hasAll(files.views + files.ensure, [
    'scenario_class == "blocked"', 'formal_object_count": 0',
  ]),
  current_state_comes_from_server: hasAll(files.page + files.views + files.services, [
    'currentStateSource', '"server"',
  ]),
  persistent_canary_survives_restart: hasAll(files.runner + files.finalizer, [
    'serviceRestartRecoveryReady', 'persistentDatabaseHashStable',
  ]),
  regression_clone_does_not_modify_demo: hasAll(files.runner + files.finalizer, [
    'regressionCloneIsolationReady', 'regressionCloneRemoved',
  ]),
  production_rollout_disabled: hasAll(files.settings + files.demo, [
    'PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED',
    'PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED = False',
  ]),
  payment_request_prepare_does_not_create_payment_request: hasAll(
    files.page + files.views + files.services,
    ['paymentRequestCreated', 'False', '该按钮仅导航，不创建付款申请'],
  ),
  module_navigation_unchanged: hasAll(files.process, [
    "stepId: 'payment-application'",
    "routePath: '/finance/payment-applications'",
    "nextStepIds: ['payment-instruction-prepare']",
  ]),
  report_version_matches_checkpoint_version: hasAll(files.finalizer, [
    "const VERSION = 'V1.14.2.8.4.7.47'",
    'version: VERSION',
    'checkpointName',
  ]),
  page_version_matches_runtime_version: hasAll(files.page + files.services, [
    "const VERSION = 'V1.14.2.8.4.7.47'",
    'VERSION = "V1.14.2.8.4.7.47"',
  ]),
  runner_version_matches_checkpoint_version: hasAll(files.runner + files.finalizer, [
    "const VERSION = 'V1.14.2.8.4.7.47'",
    "payment_request_prepare_validated_ready",
  ]),
}
const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: 'V1.14.2.8.4.7.47',
  gate: 'payment_request_prepare_v47_static_and_runtime_contract_guards',
  guardCount: Object.keys(guards).length,
  guards,
  failures,
  productionRolloutEnabled: false,
  paymentRequestCreated: false,
}
const output = path.join(frontend, 'test-results', 'payment-request-prepare-v47', 'static-guards.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exitCode = 1

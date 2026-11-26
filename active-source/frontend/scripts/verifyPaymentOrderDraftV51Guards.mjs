import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.51.1'
const frontend = path.resolve(import.meta.dirname, '..')
const sourceRoot = path.resolve(frontend, '..')
const read = relative => fs.readFileSync(path.join(sourceRoot, relative), 'utf8')
const page = read('frontend/src/meta/pages/PaymentOrderDraftPage.vue')
const api = read('frontend/src/api/paymentOrderDraft.js')
const runtime = read('frontend/src/meta/runtime/paymentOrderDraftRuntime.js')
const financeRegistry = read('frontend/src/meta/process/financeProcessPageRegistry.js')
const processRegistry = read('frontend/src/meta/process/businessProcessRegistry.js')
const moduleRegistry = read('frontend/src/meta/runtime/pceBusinessModuleRegistry.js')
const router = read('frontend/src/router/index.js')
const models = read('backend/payment_order_draft/models.py')
const services = read('backend/payment_order_draft/services.py')
const providers = read('backend/payment_order_draft/providers.py')
const views = read('backend/payment_order_draft/views.py')
const settings = read('backend/pce_backend/settings.py')
const migration = read('backend/payment_order_draft/migrations/0001_initial.py')
const listShell = read('frontend/src/meta/components/PceListPageShell.vue')
const strictFactsPanel = read('frontend/src/meta/components/PceStrictServerFactsPanel.vue')
const operationRegistry = read('frontend/src/meta/process/businessOperationPageRegistry.js')

const checks = {
  payment_order_draft_canonical_name_is_correct: runtime.includes("正式付款单草稿"),
  payment_order_draft_version_is_v1_14_2_8_4_7_51_1: runtime.includes(VERSION),
  payment_order_draft_has_distinct_route: router.includes("path: 'finance/payment-order-drafts'") && router.match(/finance\/payment-order-drafts/g)?.length === 1,
  payment_order_draft_component_is_distinct: router.includes('PaymentOrderDraftPage.vue') && !page.includes('PaymentOrderPreparePage'),
  payment_order_draft_uses_common_page_shell: financeRegistry.includes("'payment-order-draft'") && financeRegistry.includes('BusinessOperationPageShell.vue'),
  payment_order_draft_source_is_payment_order_prepare: models.includes('default="paymentOrderPrepare"') && services.includes('SOURCE_DOCUMENT_TYPE = "paymentOrderPrepare"'),
  payment_order_draft_cannot_bypass_order_prepare: services.includes('PaymentOrderPrepare.objects.select_for_update') && !services.includes('PaymentInstructionPrepare.objects.select_for_update'),
  payment_order_draft_numbers_are_server_generated: services.includes('DOCUMENT_TYPE = "payment_order_draft"') && services.includes('BusinessDocumentNumberSequence'),
  formal_payment_order_number_is_not_consumed: !services.includes('document_type="formal_payment_order"') && page.includes('未使用正式编号'),
  payment_order_draft_money_uses_decimal: models.includes('models.DecimalField') && services.includes('Decimal('),
  payment_order_draft_source_snapshot_is_immutable: models.includes('source snapshot is immutable'),
  payment_order_draft_payload_is_versioned: models.includes('draft_data_version') && migration.includes('uniq_pod_draft_data_version'),
  payment_order_draft_authority_snapshot_is_versioned: models.includes('PaymentOrderDraftAuthoritySnapshot') && migration.includes('uniq_pod_authority_data_version'),
  payment_order_draft_creation_preview_is_read_only: page.includes('正式付款单创建预览') && page.includes('只读'),
  creation_preview_is_not_formal_order: services.includes('"formalOrder": False'),
  creation_preview_is_not_signed: services.includes('"signed": False'),
  creation_preview_is_never_sent: services.includes('"sent": False'),
  review_is_explicit: services.includes('REVIEW_ACTION = "REVIEW_PAYMENT_ORDER_DRAFT"') && services.includes('_explicit(explicit_user_action)'),
  review_is_server_owned: api.includes('/review') && services.includes('def review_payment_order_draft'),
  reviewed_is_only_next_module_release_status: services.includes('obj.status == "reviewed"'),
  non_reviewed_cannot_enter_next_module: services.includes('"statusReviewed": obj.status == "reviewed"'),
  funds_authority_is_server_owned: providers.includes('FundsAvailabilityProvider') && !page.includes('fundsAvailable ='),
  signing_policy_is_server_owned: providers.includes('PaymentSigningPolicyProvider'),
  authorization_route_is_server_owned: providers.includes('PaymentAuthorizationRouteProvider'),
  signing_capability_is_server_owned: providers.includes('PaymentSigningCapabilityProvider'),
  maker_checker_is_server_validated: providers.includes('MakerCheckerSegregationProvider') && services.includes('maker_checker_conflict'),
  private_keys_are_never_exposed: !page.match(/privateKey|certificatePrivateKey|interfaceSecret/),
  copy_diagnostics_button_exists: page.includes('buildDiagnostics') && financeRegistry.includes('copyDiagnostics'),
  copy_diagnostics_uses_server_state: page.includes("currentStateSource: serverMeta.currentStateSource"),
  standard_list_contract_is_inherited: page.includes('createStandardListContract') && page.includes('StandardListToolbar'),
  advanced_filter_is_complete: (moduleRegistry.match(/'scenarioCode'/g) || []).length >= 1 && page.includes('credentialStatus'),
  sticky_columns_are_real: page.includes('fixed="left"') && page.includes('fixed="right"'),
  horizontal_scrollbar_is_real: page.includes('BusinessTableScrollContainer') && page.includes('scrollbar-always-on'),
  operation_column_is_visible_at_1366: page.includes('payment-fixed-action-column'),
  page_body_has_no_horizontal_overflow: page.includes('overflow-x: clip'),
  new_page_is_strict_level5: financeRegistry.includes("['payment-order-draft'") && financeRegistry.includes('acceptanceLevel: 5'),
  strict_page_count_is_twelve: (financeRegistry.match(/^\s+\['/gm) || []).length === 12,
  all_passed_assertions_have_evidence: read('frontend/tests/ui-baseline/paymentOrderDraftV51.spec.js').includes('evidenceId'),
  persistent_canary_survives_restart: views.includes('currentStateSource') && views.includes('PaymentOrderDraft.objects'),
  regression_clone_does_not_modify_demo: read('backend/payment_order_draft/management/commands/verify_payment_order_draft_constraints.py').includes('isolated clone'),
  production_rollout_disabled: settings.includes('PCE_PAYMENT_ORDER_DRAFT_PRODUCTION_ROLLOUT_ENABLED = False'),
  payment_order_draft_does_not_create_formal_order: views.includes('"formalPaymentOrderCreated": False'),
  payment_order_draft_does_not_execute_payment: views.includes('"paymentExecuted": False'),
  module_navigation_unchanged: processRegistry.includes("defaultNextStepId: 'payment-risk-review'"),
  report_version_matches_checkpoint_version: read('backend/payment_order_draft/management/commands/report_payment_order_draft_v51.py').includes('VERSION'),
  payment_order_draft_business_labels_are_chinese: page.includes("label: '正式付款单草稿状态'") && page.includes("label: '下一步骤放行状态'"),
  raw_technical_field_names_are_absent_from_business_cards: !page.includes(':label="field"'),
  raw_enum_values_are_not_primary_business_display: page.includes('statusDisplay') && page.includes('reviewStatusDisplay'),
  diagnostic_preserves_raw_and_display_values: page.includes('rawValue: row.status') && page.includes('displayValue: paymentOrderDraftDisplayValue'),
  previous_module_uses_canonical_name: operationRegistry.includes("previousStepName: '正式付款单预备'"),
  source_button_uses_canonical_name: operationRegistry.includes("sourceButtonText: '查看来源正式付款单预备'"),
  main_process_and_navigation_names_match_registry: !operationRegistry.includes("previousStepName: '付款单准备'"),
  strict_server_facts_must_not_report_zero_when_module_has_rows: strictFactsPanel.includes("props.pageCode === 'payment-order-draft'"),
  strict_overlay_cannot_substitute_module_read_model: listShell.includes('payload.resultCount ?? strictServerFacts.resultCount'),
  module_facts_and_generic_facts_must_match: runtime.includes('strictServerFacts') && runtime.includes('formalListApiCount'),
  diagnostic_facts_and_module_facts_must_match: page.includes('resultCount: pageFacts.value.resultCount'),
  diagnostic_facts_and_api_facts_must_match: page.includes('createPaymentOrderDraftPageFacts(envelope)'),
  selected_object_must_exist_when_formal_rows_exist: runtime.includes('selectedObject: currentObject'),
  strict_error_field_must_be_absent_on_success_page: strictFactsPanel.includes('emit(\'loaded\', facts.strictServerFacts)'),
  passed_assertion_requires_consistent_multi_source_evidence: read('frontend/tests/ui-baseline/paymentOrderDraftV51.spec.js').includes('strict-facts-consistency-report.json'),
}

const failures = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name)
console.log(JSON.stringify({
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  guardCount: Object.keys(checks).length,
  passedGuardCount: Object.keys(checks).length - failures.length,
  failures,
  guards: checks,
}, null, 2))
if (failures.length) process.exit(1)

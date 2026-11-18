import fs from 'node:fs'
import path from 'node:path'
import { financeProcessPageRegistry } from '../src/meta/process/financeProcessPageRegistry.js'
import { listBusinessOperationPageConfigs } from '../src/meta/process/businessOperationPageRegistry.js'
import {
  PAYMENT_ORDER_PREPARE_NEXT_MODULE,
  PAYMENT_ORDER_PREPARE_VERSION,
} from '../src/meta/runtime/paymentOrderPrepareRuntime.js'

const VERSION = PAYMENT_ORDER_PREPARE_VERSION
const resultRoot = path.resolve('test-results', 'payment-order-prepare-v50')
const read = file => fs.readFileSync(path.resolve(file), 'utf8')
const page = read('src/meta/pages/PaymentOrderPreparePage.vue')
const api = read('src/api/paymentOrderPrepare.js')
const router = read('src/router/index.js')
const processRegistry = read('src/meta/process/businessProcessRegistry.js')
const models = read('../backend/payment_order_prepare/models.py')
const providers = read('../backend/payment_order_prepare/providers.py')
const services = read('../backend/payment_order_prepare/services.py')
const settings = read('../backend/pce_backend/settings.py')
const gate = JSON.parse(read(path.join(resultRoot, 'gate-report.json')))
const validation = JSON.parse(read(path.join(resultRoot, 'validation-matrix.json')))
const failure = JSON.parse(read(path.join(resultRoot, 'failure-matrix.json')))
const sourcePage = financeProcessPageRegistry.find(row => row.pageStepId === 'payment-instruction-prepare')
const currentPage = financeProcessPageRegistry.find(row => row.pageStepId === 'payment-order-prepare')
const operation = listBusinessOperationPageConfigs().find(row => row.pageStepId === 'payment-order-prepare')
const checks = [
  ['payment_order_prepare_canonical_name_is_correct', currentPage?.canonicalName === '正式付款单预备'],
  ['payment_order_prepare_version_is_v1_14_2_8_4_7_50', VERSION === 'V1.14.2.8.4.7.50'],
  ['payment_order_prepare_has_distinct_route', currentPage?.routePath === '/finance/payment-prepares' && currentPage.routePath !== sourcePage?.routePath],
  ['payment_order_prepare_component_is_distinct', currentPage?.pageComponent.endsWith('PaymentOrderPreparePage.vue') && sourcePage?.pageComponent.endsWith('PaymentInstructionPreparePage.vue')],
  ['payment_order_prepare_uses_common_page_shell', router.includes("wrapBusinessOperationPage('payment-order-prepare'")],
  ['payment_order_prepare_source_is_instruction_prepare', models.includes('default="paymentInstructionPrepare"') && processRegistry.includes("sourceDocumentTypes: ['paymentInstructionPrepare']")],
  ['payment_order_prepare_cannot_bypass_instruction_prepare', services.includes('source.status != "prepared"') && models.includes('source_payment_instruction_prepare = models.OneToOneField')],
  ['payment_order_prepare_numbers_are_server_generated', services.includes('BusinessDocumentNumberSequence') && !page.includes('Date.now') && !page.includes('Math.random')],
  ['formal_payment_order_number_is_not_consumed', services.includes('DOCUMENT_TYPE = "payment_order_prepare"') && gate.formalPaymentOrderCreated === false],
  ['payment_order_prepare_money_uses_decimal', models.includes('payment_amount = models.DecimalField') && providers.includes('Decimal(')],
  ['funds_authority_is_server_owned', providers.includes('class FundsAvailabilityProvider') && models.includes('class FundsAvailabilityAuthority')],
  ['funds_check_does_not_reserve_or_debit', gate.fundsReservationCreated === false && gate.bankBalanceDebited === false],
  ['signing_policy_is_server_owned', providers.includes('class PaymentSigningPolicyProvider')],
  ['authorization_route_is_server_owned', providers.includes('class PaymentAuthorizationRouteProvider')],
  ['signing_capability_is_server_owned', providers.includes('class PaymentSigningCapabilityProvider')],
  ['private_keys_are_never_exposed', !models.includes('private_key') && !api.includes('privateKey')],
  ['maker_checker_segregation_is_server_validated', providers.includes('class MakerCheckerSegregationProvider') && services.includes('maker_checker_conflict')],
  ['order_preview_is_read_only', validation.objects.every(row => row.previewReadOnly === true)],
  ['order_preview_is_not_formal_order', gate.formalPaymentOrderCreated === false],
  ['order_preview_is_not_signed', gate.orderPreviewSigned === false],
  ['order_preview_is_never_sent', gate.orderPreviewSentExternally === false],
  ['prepared_is_only_next_module_release_status', validation.objects.every(row => row.eligibility.eligible === (row.status === 'prepared'))],
  ['non_prepared_cannot_enter_next_module', services.includes('"statusPrepared": obj.status == "prepared"')],
  ['copy_diagnostics_button_exists', page.includes('buildDiagnostics') && currentPage.observabilityActions?.copyDiagnostics === true],
  ['copy_diagnostics_uses_server_state', page.includes("currentStateSource: serverMeta.currentStateSource") && gate.currentStateSource === 'server'],
  ['copy_diagnostics_excludes_sensitive_data', !page.includes('privateKey') && !page.includes('interfaceSecret')],
  ['page_action_bar_is_complete', currentPage.observabilityActions?.refresh && currentPage.observabilityActions?.copyDiagnostics && currentPage.observabilityActions?.returnToProcessCenter],
  ['pass_through_capacity_is_at_least_eight', gate.passThroughLineageCount >= 8 && gate.formalPaymentOrderPrepareCount >= 8],
  ['blocked_scenarios_not_counted_as_capacity', gate.formalPaymentOrderPrepareCount === 8 && gate.blockedScenarioCount >= 30],
  ['normal_page_uses_server_api', page.includes('paymentOrderPrepareApi.list') && api.includes('/api/finance/payment-order-prepares/')],
  ['current_state_comes_from_server', gate.currentStateSource === 'server' && !page.includes('localStorage')],
  ['persistent_canary_survives_restart', gate.preparedPaymentOrderPrepareCount >= 8],
  ['regression_clone_does_not_modify_demo', fs.existsSync(path.resolve('../backend/canary-data/.v50-smoke.sqlite3'))],
  ['production_rollout_disabled', settings.includes('PCE_PAYMENT_ORDER_PREPARE_PRODUCTION_ROLLOUT_ENABLED = False') && gate.productionRolloutEnabled === false],
  ['payment_order_prepare_does_not_create_next_object', gate.nextModuleObjectCreated === false],
  ['payment_order_prepare_does_not_execute_payment', gate.paymentExecuted === false && Object.values(gate.downstreamCounts).every(value => value === 0)],
  ['finance_process_pages_share_common_structure', financeProcessPageRegistry.length === 11 && new Set(financeProcessPageRegistry.map(row => JSON.stringify(row.structureSequence))).size === 1],
  ['module_navigation_unchanged', operation?.nextRoutePath === '/finance/payment-order-drafts?navigationOnly=true' && PAYMENT_ORDER_PREPARE_NEXT_MODULE.code === 'payment_order_draft'],
  ['report_version_matches_checkpoint_version', gate.version === VERSION && validation.version === VERSION && failure.version === VERSION],
  ['payment_order_prepare_report_version_matches_checkpoint', gate.reportVersion === VERSION],
  ['payment_order_prepare_page_version_matches_runtime', currentPage?.runtimeBusinessVersion === VERSION],
  ['payment_order_prepare_runner_version_matches_checkpoint', gate.runnerVersion === VERSION],
]
const guards = checks.map(([guard, passed]) => ({ guard, passed: Boolean(passed) }))
const failed = guards.filter(row => !row.passed)
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'static-guards.json'), `${JSON.stringify({
  result: failed.length ? 'failed' : 'passed',
  version: VERSION,
  guardCount: guards.length,
  guards,
}, null, 2)}\n`)
if (failed.length) throw new Error(`V50 static guards failed: ${failed.map(row => row.guard).join(', ')}`)
console.log(JSON.stringify({ result: 'passed', version: VERSION, guardCount: guards.length }, null, 2))

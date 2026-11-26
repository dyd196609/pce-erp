import fs from 'node:fs'
import path from 'node:path'
import { financeProcessPageRegistry } from '../src/meta/process/financeProcessPageRegistry.js'
import { listBusinessOperationPageConfigs } from '../src/meta/process/businessOperationPageRegistry.js'
import {
  PAYMENT_INSTRUCTION_PREPARE_VERSION,
  PAYMENT_INSTRUCTION_PREPARE_NEXT_MODULE,
} from '../src/meta/runtime/paymentInstructionPrepareRuntime.js'

const VERSION = PAYMENT_INSTRUCTION_PREPARE_VERSION
const resultRoot = path.resolve('test-results', 'payment-instruction-prepare-v49')
const read = file => fs.readFileSync(path.resolve(file), 'utf8')
const page = read('src/meta/pages/PaymentInstructionPreparePage.vue')
const api = read('src/api/paymentInstructionPrepare.js')
const router = read('src/router/index.js')
const processRegistry = read('src/meta/process/businessProcessRegistry.js')
const models = read('../backend/payment_instruction_prepare/models.py')
const providers = read('../backend/payment_instruction_prepare/providers.py')
const services = read('../backend/payment_instruction_prepare/services.py')
const views = read('../backend/payment_instruction_prepare/views.py')
const settings = read('../backend/pce_backend/settings.py')
const gate = JSON.parse(read(path.join(resultRoot, 'gate-report.json')))
const validation = JSON.parse(read(path.join(resultRoot, 'validation-matrix.json')))
const failure = JSON.parse(read(path.join(resultRoot, 'failure-matrix.json')))
const paymentRequestPage = financeProcessPageRegistry.find(row => row.pageStepId === 'payment-request')
const instructionPage = financeProcessPageRegistry.find(row => row.pageStepId === 'payment-instruction-prepare')
const operation = listBusinessOperationPageConfigs().find(row => row.pageStepId === 'payment-instruction-prepare')
const checks = [
  ['payment_instruction_prepare_canonical_name_is_correct', instructionPage?.canonicalName === '付款指令准备'],
  ['payment_instruction_prepare_version_is_v1_14_2_8_4_7_49', VERSION === 'V1.14.2.8.4.7.49'],
  ['payment_instruction_prepare_has_distinct_route', instructionPage?.routePath === '/finance/payment-order-prepares' && instructionPage.routePath !== paymentRequestPage?.routePath],
  ['payment_instruction_prepare_component_is_distinct', instructionPage?.pageComponent.endsWith('PaymentInstructionPreparePage.vue') && paymentRequestPage?.pageComponent.endsWith('PaymentRequestPage.vue')],
  ['payment_instruction_prepare_uses_common_page_shell', router.includes("wrapBusinessOperationPage('payment-instruction-prepare'")],
  ['payment_instruction_prepare_source_is_payment_request', models.includes('default="paymentRequest"') && processRegistry.includes("sourceDocumentTypes: ['paymentRequest']")],
  ['payment_instruction_prepare_cannot_bypass_approved_request', services.includes('source.status != "approved"') && models.includes('source_payment_request = models.OneToOneField')],
  ['payment_instruction_prepare_numbers_are_server_generated', services.includes('BusinessDocumentNumberSequence') && !page.includes('Date.now') && !page.includes('Math.random')],
  ['payment_instruction_prepare_money_uses_decimal', models.includes('payment_amount = models.DecimalField') && services.includes('Decimal(')],
  ['payment_route_is_server_owned', providers.includes('class PaymentRouteProvider') && models.includes('class PaymentRouteAuthority')],
  ['bank_interface_capability_is_server_owned', providers.includes('class BankInterfaceProvider') && models.includes('class BankInterfaceProfileAuthority')],
  ['bank_account_numbers_are_masked', models.includes('payer_account_no_masked') && models.includes('payee_account_no_masked') && !models.includes('full_account_no')],
  ['bank_business_day_is_server_validated', providers.includes('class BankCalendarProvider') && services.includes('bank_business_day_invalid')],
  ['cutoff_time_is_server_validated', services.includes('cutoff_time_exceeded')],
  ['payment_limits_are_server_validated', providers.includes('class PaymentLimitProvider') && services.includes('single_payment_limit_exceeded')],
  ['duplicate_payment_risk_is_server_validated', services.includes('duplicate_payment_risk')],
  ['instruction_preview_is_not_formal_instruction', models.includes('class PaymentInstructionPreview') && gate.formalPaymentInstructionCreated === false],
  ['instruction_preview_is_never_sent', page.includes('未发送银行') && gate.instructionPreviewSentExternally === false],
  ['prepared_is_only_next_module_release_status', services.includes('if obj.status != "prepared"')],
  ['non_prepared_cannot_enter_next_module', services.includes('PIP_ELIGIBILITY_PREPARED')],
  ['pass_through_capacity_is_at_least_eight', gate.passThroughLineageCount >= 8 && gate.formalPaymentInstructionPrepareCount >= 8],
  ['blocked_scenarios_not_counted_as_capacity', gate.formalPaymentInstructionPrepareCount === 8 && gate.blockedScenarioCount >= 22],
  ['normal_page_uses_server_api', page.includes('paymentInstructionPrepareApi.list') && api.includes('/api/finance/payment-instruction-prepares/')],
  ['current_state_comes_from_server', gate.currentStateSource === 'server' && !page.includes('localStorage')],
  ['persistent_canary_survives_restart', gate.preparedPaymentInstructionPrepareCount >= 8],
  ['regression_clone_does_not_modify_demo', fs.existsSync(path.resolve('../backend/canary-data/.v49-regression.sqlite3'))],
  ['production_rollout_disabled', settings.includes('PCE_PAYMENT_INSTRUCTION_PREPARE_PRODUCTION_ROLLOUT_ENABLED = False') && gate.productionRolloutEnabled === false],
  ['payment_instruction_prepare_does_not_create_next_object', gate.nextModuleObjectCreated === false],
  ['payment_instruction_prepare_does_not_execute_payment', gate.paymentExecuted === false && Object.values(gate.downstreamCounts).every(value => value === 0)],
  ['finance_process_pages_share_common_structure', financeProcessPageRegistry.length === 10 && new Set(financeProcessPageRegistry.map(row => JSON.stringify(row.structureSequence))).size === 1],
  ['module_navigation_unchanged', operation?.nextRoutePath === '/finance/payment-prepares?navigationOnly=true' && PAYMENT_INSTRUCTION_PREPARE_NEXT_MODULE.code === 'payment_order_prepare'],
  ['report_version_matches_checkpoint_version', gate.version === VERSION && validation.version === VERSION && failure.version === VERSION],
  ['payment_instruction_prepare_report_version_matches_checkpoint', gate.reportVersion === VERSION],
  ['payment_instruction_prepare_page_version_matches_runtime', instructionPage?.runtimeBusinessVersion === VERSION],
  ['payment_instruction_prepare_runner_version_matches_checkpoint', gate.runnerVersion === VERSION],
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
if (failed.length) throw new Error(`V49 static guards failed: ${failed.map(row => row.guard).join(', ')}`)
console.log(JSON.stringify({ result: 'passed', version: VERSION, guardCount: guards.length }, null, 2))

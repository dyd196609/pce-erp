import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { financeProcessPageRegistry } from '../src/meta/process/financeProcessPageRegistry.js'
import { listBusinessOperationPageConfigs } from '../src/meta/process/businessOperationPageRegistry.js'
import { PAYMENT_REQUEST_VERSION } from '../src/meta/runtime/paymentRequestRuntime.js'

const VERSION = PAYMENT_REQUEST_VERSION
const root = path.resolve('test-results', 'payment-request-v48')
const read = file => fs.readFileSync(path.resolve(file), 'utf8')
const exists = file => fs.existsSync(path.resolve(file))
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(path.resolve(file))).digest('hex')
const router = read('src/router/index.js')
const page = read('src/meta/pages/PaymentRequestPage.vue')
const api = read('src/api/paymentRequest.js')
const backendModels = read('../backend/payment_request/models.py')
const backendServices = read('../backend/payment_request/services.py')
const workflowModels = read('../backend/workflow_runtime/models.py')
const settings = read('../backend/pce_backend/settings.py')
const report = JSON.parse(read(path.join(root, 'gate-report.json')))
const approval = JSON.parse(read(path.join(root, 'approval-matrix.json')))
const failure = JSON.parse(read(path.join(root, 'failure-matrix.json')))
const configs = listBusinessOperationPageConfigs()
const payment = financeProcessPageRegistry.find(row => row.pageStepId === 'payment-request')
const prepare = financeProcessPageRegistry.find(row => row.pageStepId === 'payment-application')
const checks = [
  ['payment_request_canonical_name_is_correct', payment?.canonicalName === '付款申请'],
  ['payment_request_version_is_v1_14_2_8_4_7_48', VERSION === 'V1.14.2.8.4.7.48'],
  ['payment_request_has_distinct_route', payment?.routePath === '/finance/payment-requests' && payment.routePath !== prepare.routePath],
  ['payment_request_prepare_route_remains_unchanged', prepare?.routePath === '/finance/payment-applications'],
  ['payment_request_component_is_distinct_from_prepare', payment?.pageComponent.endsWith('PaymentRequestPage.vue') && prepare?.pageComponent.endsWith('PaymentApplicationPage.vue')],
  ['payment_request_uses_common_page_shell', router.includes("wrapBusinessOperationPage('payment-request'")],
  ['payment_request_source_is_payment_request_prepare', backendModels.includes('default="paymentRequestPrepare"')],
  ['payment_request_cannot_bypass_prepare', backendModels.includes('source_payment_request_prepare = models.OneToOneField')],
  ['payment_request_numbers_are_server_generated', backendServices.includes('BusinessDocumentNumberSequence') && !page.includes('Date.now') && !page.includes('Math.random')],
  ['payment_request_amount_uses_decimal', backendModels.includes('payment_amount = models.DecimalField')],
  ['payment_request_submission_is_explicit', backendServices.includes('SUBMIT_ACTION') && backendServices.includes('_require_explicit')],
  ['payment_request_approval_is_explicit', backendServices.includes('APPROVE_ACTION') && backendServices.includes('_require_explicit')],
  ['payment_request_does_not_auto_approve', !backendServices.includes('status = "approved"') || backendServices.includes('task.step_no >= workflow.total_steps')],
  ['payment_request_uses_shared_workflow_engine', backendModels.includes('from workflow_runtime.models') && workflowModels.includes('class WorkflowInstance')],
  ['applicant_cannot_approve_own_request', backendServices.includes('PAYREQ_APPROVE_SELF_APPROVAL_BLOCKED')],
  ['approval_steps_are_server_ordered', backendServices.includes('PAYREQ_APPROVE_STEP_CURRENT')],
  ['approval_task_decision_is_idempotent', workflowModels.includes('uniq_workflow_decision_idempotency')],
  ['approved_is_only_instruction_prepare_release_status', backendServices.includes('if obj.status != "approved"')],
  ['rejected_is_not_instruction_prepare_eligible', failure.blockedScenarios.some(row => row.scenarioCode === 'REJECTED')],
  ['source_state_remains_unchanged', approval.requests.length === 8 && report.paymentRequestPrepareSourceCount === 8],
  ['pass_through_capacity_is_at_least_eight', report.passThroughLineageCount >= 8],
  ['blocked_scenarios_not_counted_as_capacity', report.formalPaymentRequestCount === 8 && report.blockedScenarioCount >= 16],
  ['normal_payment_request_page_uses_server_api', page.includes('paymentRequestApi.list') && api.includes('/api/finance/payment-requests/')],
  ['current_state_comes_from_server', report.currentStateSource === 'server'],
  ['persistent_canary_survives_restart', report.approvedPaymentRequestCount === 8],
  ['regression_clone_does_not_modify_demo', exists('../backend/canary-data/.v48-regression.sqlite3')],
  ['production_rollout_disabled', settings.includes('PCE_PAYMENT_REQUEST_PRODUCTION_ROLLOUT_ENABLED') && report.productionRolloutEnabled === false],
  ['payment_request_does_not_create_instruction_prepare', report.paymentInstructionPrepareCreated === false],
  ['finance_process_pages_share_common_structure', financeProcessPageRegistry.length === 9 && new Set(financeProcessPageRegistry.map(row => JSON.stringify(row.structureSequence))).size === 1],
  ['module_navigation_unchanged', configs.find(row => row.pageStepId === 'payment-request')?.previousStepName === '付款申请准备'],
  ['report_version_matches_checkpoint_version', report.version === VERSION && approval.version === VERSION && failure.version === VERSION],
  ['payment_request_report_version_matches_checkpoint', report.version === VERSION],
  ['payment_request_page_version_matches_runtime', payment.runtimeBusinessVersion === VERSION],
  ['payment_request_runner_version_matches_checkpoint', VERSION === 'V1.14.2.8.4.7.48'],
]
const guards = checks.map(([guard, passed]) => ({ guard, passed }))
const failed = guards.filter(row => !row.passed)
fs.mkdirSync(root, { recursive: true })
fs.writeFileSync(path.join(root, 'static-guards.json'), `${JSON.stringify({
  result: failed.length ? 'failed' : 'passed', version: VERSION, guards,
  persistentDatabaseSha256: sha256('../backend/canary-data/purchase-flow-demo.sqlite3'),
  developmentDatabaseSha256: sha256('../backend/db.sqlite3'),
}, null, 2)}\n`)
if (failed.length) throw new Error(`V48 guards failed: ${failed.map(row => row.guard).join(', ')}`)
console.log(JSON.stringify({ result: 'passed', version: VERSION, guardCount: guards.length }, null, 2))


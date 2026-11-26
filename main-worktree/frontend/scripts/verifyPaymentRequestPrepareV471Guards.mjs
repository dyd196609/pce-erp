import fs from 'node:fs'
import path from 'node:path'
import {
  PAYMENT_REQUEST_PREPARE_RUNTIME,
  PAYMENT_REQUEST_PREPARE_VERSION,
} from '../src/meta/runtime/paymentRequestPrepareRuntime.js'

const VERSION = PAYMENT_REQUEST_PREPARE_VERSION
const resultRoot = path.resolve('test-results', 'payment-request-prepare-v471')
const read = file => fs.readFileSync(path.resolve(file), 'utf8')
const router = read('src/router/index.js')
const page = read('src/meta/pages/PaymentApplicationPage.vue')
const processRegistry = read('src/meta/process/businessProcessRegistry.js')
const operationRegistry = read('src/meta/process/businessOperationPageRegistry.js')
const runtime = read('src/meta/runtime/paymentRequestPrepareRuntime.js')

const checks = [
  ['payment_request_prepare_has_single_visible_version', page.includes('PAYMENT_REQUEST_PREPARE_VERSION') && !page.includes("const VERSION = '")],
  ['all_visible_runtime_versions_match_v47_1', runtime.includes(`version: '${VERSION}'`) && !page.includes('V1.14.2.8.4.7.47')],
  ['legacy_v1_14_2_8_4_3_is_absent', !page.includes('V1.14.2.8.4.3')],
  ['legacy_v1_14_2_7_2_1_is_absent', !page.includes('V1.14.2.7.2.1')],
  ['payment_request_legacy_shell_is_not_mounted', /path:\s*'finance\/payment-applications'[\s\S]*?component:\s*\(\)\s*=>\s*import\('@\/meta\/pages\/PaymentApplicationPage\.vue'\)/.test(router)],
  ['current_page_title_is_payment_request_prepare', page.includes('data-acceptance-id="page-business-title"') && page.includes('付款申请准备')],
  ['current_process_step_is_payment_request_prepare', page.includes(':value="RUNTIME.currentModule.name"') && PAYMENT_REQUEST_PREPARE_RUNTIME.currentModule.code === 'payment_request_prepare'],
  ['previous_process_step_is_payable_confirmation_prepare', page.includes(':value="RUNTIME.previousModule.name"') && PAYMENT_REQUEST_PREPARE_RUNTIME.previousModule.code === 'payable_confirmation_prepare'],
  ['next_process_step_is_payment_request', page.includes(':value="RUNTIME.nextModule.name"') && PAYMENT_REQUEST_PREPARE_RUNTIME.nextModule.code === 'payment_request'],
  ['payment_instruction_prepare_is_not_next_step', !/stepId:\s*'payment-application'[\s\S]*?nextStepIds:\s*\['payment-instruction-prepare'\]/.test(processRegistry)],
  ['enter_payment_instruction_prepare_button_is_absent', !page.includes('进入付款指令准备')],
  ['single_business_process_navigation_exists', (page.match(/data-acceptance-id="payment-request-process-navigation"/g) || []).length === 1],
  ['single_canonical_page_title_exists', (page.match(/data-acceptance-id="page-business-title"/g) || []).length === 1],
  ['formal_v47_capacity_remains_unchanged', page.includes('payment-request-prepare-capacity') && page.includes('blockedScenarioCount')],
  ['payment_request_count_remains_zero', page.includes(':value="downstream.paymentRequests || 0"') && page.includes('paymentRequestCreated=false')],
  ['single_runtime_version_source', runtime.includes('PAYMENT_REQUEST_PREPARE_RUNTIME') && runtime.includes('PAYMENT_REQUEST_PREPARE_VERSION')],
  ['legacy_operation_contract_replaced', operationRegistry.includes("pageTitle: '付款申请准备'") && operationRegistry.includes("nextStepName: '付款申请'") && !operationRegistry.includes("nextButtonText: '进入付款指令准备'")],
  ['navigation_is_write_free', page.includes("path: '/process-center'") && page.includes("navigationOnly: 'true'") && !page.includes("path: '/finance/payment-order-prepares'")],
]

const guards = checks.map(([guard, passed]) => ({ guard, passed }))
const failed = guards.filter(item => !item.passed)
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'static-guards.json'),
  `${JSON.stringify({
    result: failed.length ? 'failed' : 'passed',
    version: VERSION,
    canonicalName: PAYMENT_REQUEST_PREPARE_RUNTIME.canonicalName,
    guards,
  }, null, 2)}\n`,
  'utf8',
)
if (failed.length) {
  throw new Error(`V47.1 static guards failed: ${failed.map(item => item.guard).join(', ')}`)
}
console.log(JSON.stringify({ result: 'passed', version: VERSION, guardCount: guards.length }, null, 2))

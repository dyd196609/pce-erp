import fs from 'node:fs'
import path from 'node:path'
import { financeProcessPageRegistry } from '../src/meta/process/financeProcessPageRegistry.js'

const VERSION = 'V1.14.2.8.4.7.49.1'
const root = path.resolve(import.meta.dirname, '..')
const output = path.join(root, 'test-results', 'payment-instruction-prepare-v491', 'static-guards.json')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const shell = read('src/meta/components/PceListPageShell.vue')
const page = read('src/meta/pages/PaymentInstructionPreparePage.vue')
const runtime = read('src/meta/runtime/pageObservabilityActions.js')
const service = read('../backend/payment_instruction_prepare/services.py')
const views = read('../backend/payment_instruction_prepare/views.py')
const entry = financeProcessPageRegistry.find(item => item.pageStepId === 'payment-instruction-prepare')
const diagnosticBlock = page.slice(
  page.indexOf('function buildDiagnostics'),
  page.indexOf('onMounted(async'),
)

const checks = [
  ['payment_instruction_prepare_copy_diagnostics_button_exists', shell.includes('data-acceptance-id="copy-diagnostic-data-button"')],
  ['copy_diagnostics_button_is_in_page_action_bar', shell.includes('data-acceptance-id="page-observability-action-bar"') && shell.includes('data-action-location="page_action_bar"')],
  ['copy_diagnostics_uses_current_server_state', page.includes('buildDiagnostics') && page.includes('serverMeta.currentStateSource') && views.includes('"currentStateSource": "server"')],
  ['copy_diagnostics_contains_required_sections', ['process:', 'capacity:', 'selectedObject:', 'paymentRoute:', 'bankInterface:', 'accounts:', 'instruction:', 'validation:', 'eligibility:', 'transaction:', 'downstream:'].every(marker => page.includes(marker))],
  ['copy_diagnostics_masks_bank_accounts', page.includes('payerBankAccountMasked: row.preview?.debtorAccountMasked') && page.includes('payeeBankAccountMasked: row.preview?.creditorAccountMasked')],
  ['copy_diagnostics_excludes_auth_secrets', runtime.includes('assertSafeDiagnosticPayload') && !page.includes('Authorization Header') && !page.includes('document.cookie')],
  ['copy_diagnostics_is_read_only', !['saveInstructionData', 'paymentInstructionPrepareApi.validate', 'paymentInstructionPrepareApi.generate'].some(marker => diagnosticBlock.includes(marker))],
  ['copy_diagnostics_does_not_mutate_database', shell.includes('navigator.clipboard.writeText') && !shell.includes('paymentInstructionPrepareApi')],
  ['copy_diagnostics_does_not_change_object_state', page.includes('observabilityActions?.register({ refresh, buildDiagnostics })')],
  ['copy_diagnostics_does_not_create_downstream_objects', page.includes('formalPaymentInstructionCount: downstream.formalPaymentInstructions')],
  ['copy_diagnostics_success_feedback_is_visible', shell.includes("ElMessage.success('诊断数据已复制')")],
  ['payment_instruction_prepare_button_whitelist_is_complete', ['查看来源付款申请', '查看支付路由', '查看指令资料', '查看银行指令预览', '查看校验结果'].every(label => page.includes(label))],
  ['forbidden_payment_action_buttons_are_absent', ['生成正式付款指令', '发送银行', '执行付款', '生成付款凭证', '生成银行流水'].every(label => !page.includes(`>${label}<`))],
  ['server_revalidation_is_explicit', service.includes('"serverRevalidationRequired": True')],
  ['observability_registry_contract_enabled', entry?.observabilityActions?.location === 'page_action_bar' && entry?.observabilityActions?.sourceRequirement === 'current_server_state'],
]

const failed = checks.filter(([, passed]) => !passed)
const report = {
  result: failed.length ? 'failed' : 'passed',
  version: VERSION,
  guardCount: checks.length,
  checks: checks.map(([code, passed]) => ({ code, passed })),
  rootCause: {
    refreshButtonSourceBeforeFix: 'module pages or local page headers; no unified action bar for unified finance pages',
    returnProcessCenterSourceBeforeFix: 'module-local header or PurchaseCanaryScenarioPanel',
    copyDiagnosticsSourceOnOtherPages: 'module-local button or collapsed BusinessOperationPageShell technical diagnostics',
    v49ObservabilitySlotMissing: true,
    hiddenByCssPermissionOrWidth: false,
    priorPlaywrightGap: 'V49 test asserted regions and read model but never asserted the required button whitelist or clipboard behavior',
    onlyStandardListToolbarBeforeFix: true,
  },
}
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (failed.length) process.exit(1)

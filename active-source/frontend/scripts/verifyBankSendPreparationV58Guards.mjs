import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

import {
  BusinessActionRegistry,
} from '../src/meta/runtime/pceBusinessActionRegistry.js'
import {
  BANK_SEND_PREPARATION_MODULE,
  BANK_SEND_PREPARATION_VERSION,
} from '../src/meta/runtime/bankSendPreparationRuntime.js'
import {
  findFinanceProcessPage,
} from '../src/meta/process/financeProcessPageRegistry.js'

const root = process.cwd()
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
const backendModel = read('../backend/bank_send_preparation/models.py')
const backendService = read('../backend/bank_send_preparation/services.py')
const backendViews = read('../backend/bank_send_preparation/views.py')
const backendUrls = read('../backend/bank_send_preparation/urls.py')
const permissionContract = read('../backend/workflow_runtime/action_permissions.py')
const backendWriteIntentContract = read(
  '../backend/workflow_runtime/write_intents.py',
)
const backendFacts = read('../backend/workflow_runtime/facts.py')
const strictFactsPanel = read(
  'src/meta/components/PceStrictServerFactsPanel.vue',
)
const page = read('src/meta/pages/BankSendPreparationPage.vue')
const runtime = read('src/meta/runtime/bankSendPreparationRuntime.js')
const frontendWriteIntentContract = read(
  'src/meta/runtime/pceWriteIntentContract.js',
)
const webAcceptanceContract = read(
  'src/meta/runtime/pceWebAcceptanceContract.js',
)
const acceptanceStandard = read(
  '../docs/standards/PCE-WEB-ACCEPTANCE-V1.1.md',
)
const agents = read('../../AGENTS.md')
const api = read('src/api/bankSendPreparation.js')
const router = read('src/router/index.js')
const migration = read(
  '../backend/bank_send_preparation/migrations/0001_initial.py',
)
const resultRoot = path.join(
  root,
  'test-results',
  'bank-send-preparation-v58-1-1',
)
const contract = BusinessActionRegistry.getContract('bank-send-preparation')
const registeredPage = findFinanceProcessPage('bank-send-preparation')
const actionIds = (contract?.actions || []).map(item => item.actionId)
const forbiddenActionIds = [
  'send-bank',
  'generate-bank-message',
  'create-bank-message',
  'debit-funds',
  'create-bank-transaction',
  'execute-payment',
]
const secretPatterns = [
  /["']password["']\s*:/i,
  /["']privateKey["']\s*:/i,
  /["']clientSecret["']\s*:/i,
  /["']accessToken["']\s*:/i,
  /["']signingCredential["']\s*:/i,
]

const guards = {
  preview_write_allowed:
    backendWriteIntentContract.includes(
      'PREVIEW_PREPARATION_WRITE = "preview_preparation_write"',
    )
      && frontendWriteIntentContract.includes(
        "PREVIEW_PREPARATION_WRITE: 'preview_preparation_write'",
      )
      && backendService.includes('build_write_intent_facts')
      && backendService.includes('BankMessagePreview.objects.create')
      && acceptanceStandard.includes('只读预览不是业务执行'),
  business_progress_write_blocked:
    [
      'bankMessages',
      'paymentExecutions',
      'fundsDebits',
      'bankTransactions',
      'paymentVouchers',
      'ledgerEntries',
      'postings',
    ].every(field => backendService.includes(`"${field}": 0`))
      && backendWriteIntentContract.includes(
        '"forbiddenBusinessProgressWriteCount"',
      )
      && backendWriteIntentContract.includes(
        '"businessProgressWriteBlocked"',
      ),
  bank_send_not_created:
    backendService.includes('"bankMessages": 0')
      && backendService.includes('"paymentExecutions": 0')
      && backendViews.includes('"bankSendEnabled": False')
      && forbiddenActionIds.every(actionId => (
        contract?.forbiddenActions?.includes(actionId)
      )),
  preview_only_enforced:
    backendModel.includes('PREVIEW_ONLY = "preview_only"')
      && backendModel.includes('name="bmp_preview_only_enforced"')
      && backendModel.includes(
        'Bank message preview status must remain preview_only',
      )
      && backendService.includes('"sent": False')
      && backendService.includes('"executed": False')
      && backendWriteIntentContract.includes('"previewOnlyEnforced": True')
      && !api.includes('/send'),
  bank_send_preparation_facts_single_source:
    backendFacts.includes('class BankSendPreparationFacts:')
      && backendFacts.includes('"factType": "BankSendPreparationFacts"')
      && backendViews.includes(
        '"bankSendPreparationFacts":',
      )
      && runtime.includes('assertBankSendPreparationFacts(data)'),
  api_capacity_from_authoritative_facts:
    [
      'sourceFormalPaymentOrderCount',
      'bankSendPreparationCount',
      'preparedCount',
      'eligibleCount',
      'previewCount',
    ].every(field => backendFacts.includes(`"${field}"`))
      && backendViews.includes('**capacity')
      && backendViews.includes(
        '"count": bank_send_preparation_facts[',
      ),
  strict_facts_from_bank_send_preparation_facts:
    runtime.includes(
      'const bankSendPreparationFacts = assertBankSendPreparationFacts(data)',
    )
      && runtime.includes(
        'bankSendPreparationFacts.bankSendPreparationCount,',
      )
      && runtime.includes('resultCount: factLoadResultCount(')
      && runtime.includes('strictServerFacts = {')
      && runtime.includes('bankSendPreparationFacts,')
      && page.includes('bankSendPreparationFacts')
      && page.includes('writeIntentClassification'),
  incomplete_contract_not_silently_zeroed:
    strictFactsPanel.includes("defineEmits(['loaded', 'load-error'])")
      && !strictFactsPanel.includes(
        "emit('loaded', { currentStateSource: 'server', pageCode: props.pageCode, resultCount: 0",
      ),
  bank_secret_not_exposed:
    backendService.includes('"secretExposed": False')
      && backendService.includes('"bankSecretExposed": False')
      && secretPatterns.every(pattern => !pattern.test(backendService))
      && page.includes('银行密钥暴露')
      && page.includes('敏感字段暴露'),
  bank_send_preparation_model_persisted:
    migration.includes('name="BankSendPreparation"')
      && migration.includes('name="BankSendGate"')
      && migration.includes('name="BankMessagePreview"')
      && backendModel.includes('source_formal_payment_order = models.OneToOneField'),
  bank_send_gate_complete:
    [
      'sourceStatusPassed',
      'approvalPassed',
      'freezeHashPassed',
      'riskReviewPassed',
      'fundsAvailable',
      'bankInterfaceAvailable',
      'signingCapabilityReady',
      'segregationValid',
    ].every(field => backendService.includes(`"${field}"`)),
  business_state_transition_required:
    backendModel.includes(
      'Bank send preparation status must use BusinessStateTransition',
    )
      && backendService.includes('create_business_object_with_initial_state')
      && backendService.includes('transition_business_object')
      && backendService.includes('ALLOWED_STATE_TRANSITIONS'),
  business_action_registry_connected:
    actionIds.length === 3
      && actionIds.includes('view-bank-send-eligibility')
      && actionIds.includes('view-bank-send-gate')
      && actionIds.includes('generate-bank-message-preview')
      && page.includes('current-module="bank-send-preparation"'),
  permission_validator_required:
    backendService.includes('ActionPermissionValidator().evaluate')
      && permissionContract.includes('"bank-send-preparation"')
      && permissionContract.includes('"generate-bank-message-preview"'),
  server_read_model_only:
    api.includes('/api/finance/bank-send-prepares/')
      && backendViews.includes('"currentStateSource": "server"')
      && page.includes('currentStateSource: \'server\'')
      && !page.includes('localStorage'),
  api_page_diagnostic_strict_facts_write_intent_consistent:
    backendViews.includes('"writeIntentFacts": write_intent_facts')
      && runtime.includes('writeIntentFacts')
      && runtime.includes('assertWriteIntentFacts')
      && page.includes('previewPreparationWriteCount')
      && page.includes('auditWriteCount')
      && page.includes('forbiddenBusinessProgressWriteCount')
      && !page.includes('businessWriteRequestCount'),
  acceptance_contract_classifies_safe_preparation_writes:
    webAcceptanceContract.includes('safePreparationWriteAllowed: true')
      && webAcceptanceContract.includes(
        'WriteIntentCategory.BUSINESS_PROGRESS_WRITE',
      )
      && acceptanceStandard.includes(
        'forbiddenBusinessProgressWriteCount',
      )
      && agents.includes('PCE 安全准备阶段写入意图长期规则'),
  page_route_and_acceptance_registered:
    BANK_SEND_PREPARATION_VERSION.startsWith('V1.14.2.8.4.7.58.')
      && BANK_SEND_PREPARATION_MODULE.canonicalName === '银行发送准备'
      && registeredPage?.routePath === '/finance/bank-send-prepares'
      && router.includes("path: 'finance/bank-send-prepares'"),
  page_required_sections_present:
    [
      '金丝雀容量',
      '来源正式付款单',
      '银行发送资格',
      '接口能力',
      '报文预览',
      '最终门禁',
      '下游零对象保护',
    ].every(label => page.includes(label)),
  production_rollout_disabled:
    backendViews.includes('"productionRolloutEnabled": False')
      && backendViews.includes('"bankSendEnabled": False'),
}

const failedGuards = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const report = {
  result: failedGuards.length ? 'failed' : 'passed',
  version: BANK_SEND_PREPARATION_VERSION,
  canonicalName: BANK_SEND_PREPARATION_MODULE.canonicalName,
  sourceDocumentType: BANK_SEND_PREPARATION_MODULE.sourceDocumentType,
  currentStateSource: 'server',
  actionIds,
  guardCount: Object.keys(guards).length,
  blockerCount: failedGuards.length,
  failedGuards,
  guards,
  bankSendCreated: false,
  paymentExecuted: false,
  fundsDebited: false,
  bankTransactionCreated: false,
  productionUserDataWritten: false,
  previewPreparationWriteCountRule: '>=0',
  forbiddenBusinessProgressWriteCount: 0,
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'static-guard-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (failedGuards.length) {
  throw new Error(`V58.1.1 static guards failed: ${failedGuards.join(', ')}`)
}

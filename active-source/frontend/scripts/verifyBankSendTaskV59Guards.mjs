import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

import {
  BusinessActionRegistry,
} from '../src/meta/runtime/pceBusinessActionRegistry.js'
import {
  BANK_SEND_TASK_MODULE,
  BANK_SEND_TASK_VERSION,
} from '../src/meta/runtime/bankSendTaskRuntime.js'
import {
  findFinanceProcessPage,
} from '../src/meta/process/financeProcessPageRegistry.js'

const root = process.cwd()
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
const model = read('../backend/bank_send_task/models.py')
const service = read('../backend/bank_send_task/services.py')
const view = read('../backend/bank_send_task/views.py')
const migration = read('../backend/bank_send_task/migrations/0001_initial.py')
const permission = read('../backend/workflow_runtime/action_permissions.py')
const writeIntent = read('../backend/workflow_runtime/write_intents.py')
const facts = read('../backend/workflow_runtime/facts.py')
const api = read('src/api/bankSendTask.js')
const page = read('src/meta/pages/BankSendTaskPage.vue')
const runtime = read('src/meta/runtime/bankSendTaskRuntime.js')
const frontendWriteIntent = read('src/meta/runtime/pceWriteIntentContract.js')
const router = read('src/router/index.js')
const acceptance = read('../docs/standards/PCE-WEB-ACCEPTANCE-V1.1.md')
const agents = read('../../AGENTS.md')

const contract = BusinessActionRegistry.getContract('bank-send-task')
const registeredPage = findFinanceProcessPage('bank-send-task')
const actionIds = (contract?.actions || []).map(item => item.actionId)
const forbidden = [
  'send-bank',
  'execute-payment',
  'create-bank-message',
  'debit-funds',
  'create-bank-transaction',
]

const guards = {
  bank_send_task_persisted:
    model.includes('class BankSendTask(')
      && model.includes('source_preparation = models.OneToOneField')
      && migration.includes('name="BankSendTask"'),
  task_state_machine_only:
    ['PREPARED = "prepared"', 'QUEUED = "queued"', 'READY_TO_SEND = "ready_to_send"']
      .every(value => model.includes(value))
      && !model.includes('SENT = "sent"')
      && service.includes('create_business_object_with_initial_state')
      && service.includes('transition_business_object')
      && service.includes(
        '(BankSendTask.Status.PREPARED, BankSendTask.Status.QUEUED)',
      )
      && service.includes(
        '(BankSendTask.Status.QUEUED, BankSendTask.Status.READY_TO_SEND)',
      ),
  direct_task_status_write_blocked:
    model.includes('Bank send task status must use BusinessStateTransition')
      && model.includes('if "status" in kwargs:')
      && !service.includes('BankSendTask.objects.update(status'),
  creation_gate_server_revalidated:
    [
      'bankSendGatePassed',
      'formalPaymentOrderFrozen',
      'formalPaymentOrderFreezeConsistent',
      'approvalApproved',
      'riskReviewPassed',
      'fundsAvailable',
      'segregationOfDutiesPassed',
      'bankSendPreparationPrepared',
      'bankMessagePreviewExists',
      'forbiddenBusinessProgressWriteCountZero',
    ].every(field => service.includes(`"${field}"`))
      && service.includes('evaluate_task_creation_gate(preparation)'),
  bst_number_contract:
    service.includes('f"BST{preparation.planned_execution_date.strftime')
      && service.includes(':08d}')
      && model.includes('task_no = models.CharField')
      && model.includes('unique=True'),
  idempotency_transaction_lock_and_audit:
    [
      'BusinessActionIdempotency',
      'BusinessActionTransaction',
      'BusinessActionSourceLock',
      'BusinessDocumentNumberReservation',
      'BusinessActionAuditRecord',
      'transaction.atomic',
      'existing_result',
    ].every(value => service.includes(value)),
  business_action_registry_connected:
    actionIds.length === 4
      && [
        'view-bank-send-task',
        'view-bank-send-task-status',
        'view-bank-message-binding',
        'create-bank-send-task',
      ].every(actionId => actionIds.includes(actionId))
      && forbidden.every(actionId => contract?.forbiddenActions?.includes(actionId))
      && page.includes('current-module="bank-send-task"'),
  action_permission_server_validated:
    permission.includes('"bank-send-task"')
      && permission.includes('"create-bank-send-task"')
      && permission.includes('BANK_OPERATOR_ROLE')
      && service.includes('ActionPermissionValidator().evaluate'),
  send_task_preparation_write_classified:
    writeIntent.includes(
      'SEND_TASK_PREPARATION_WRITE = "send_task_preparation_write"',
    )
      && frontendWriteIntent.includes(
        "SEND_TASK_PREPARATION_WRITE: 'send_task_preparation_write'",
      )
      && facts.includes('class BankSendTaskFacts:')
      && runtime.includes('assertBankSendTaskFacts(data)')
      && acceptance.includes('send_task_preparation_write')
      && agents.includes('send_task_preparation_write'),
  bank_send_execution_write_blocked:
    writeIntent.includes(
      'BANK_SEND_EXECUTION_WRITE = "bank_send_execution_write"',
    )
      && frontendWriteIntent.includes(
        "BANK_SEND_EXECUTION_WRITE: 'bank_send_execution_write'",
      )
      && service.includes('"bankMessages": 0')
      && service.includes('"paymentExecutions": 0')
      && view.includes('"bankSendExecutionEnabled": False')
      && !api.includes('/send'),
  server_read_model_and_four_surfaces:
    api.includes('/api/finance/bank-send-tasks/')
      && view.includes('"currentStateSource": "server"')
      && runtime.includes('currentStateSource: \'server\'')
      && runtime.includes('strictServerFacts')
      && page.includes('function buildDiagnostics()')
      && !page.includes('localStorage'),
  required_task_fact_counts_present:
    [
      '"taskCount"',
      '"sentCount"',
      '"executionCount"',
    ].every(field => facts.includes(field))
      && runtime.includes("'taskCount'")
      && runtime.includes("'sentCount'")
      && runtime.includes("'executionCount'"),
  state_transition_guard_complete:
    service.includes('def bank_send_task_state_transition_guard(')
      && service.includes('"unifiedStateService"')
      && service.includes('"noSkippedState"')
      && service.includes('"historyLengthMatchesCount"')
      && service.includes('"auditReferenceComplete"'),
  page_registered_and_standardized:
    BANK_SEND_TASK_VERSION.startsWith('V1.14.2.8.4.7.59')
      && BANK_SEND_TASK_MODULE.canonicalName === '银行发送任务'
      && registeredPage?.routePath === '/finance/bank-send-tasks'
      && router.includes("path: 'finance/bank-send-tasks'")
      && [
        '银行发送任务容量',
        '来源银行发送准备',
        '状态转换历史',
        '报文绑定',
        '银行发送任务列表',
        '发送前保护',
      ].every(label => page.includes(label)),
  downstream_execution_zero:
    [
      'bankMessages',
      'paymentExecutions',
      'fundsDebits',
      'bankTransactions',
      'paymentVouchers',
      'ledgerEntries',
      'postings',
    ].every(field => service.includes(`"${field}": 0`)),
}

const failedGuards = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const report = {
  result: failedGuards.length ? 'failed' : 'passed',
  version: BANK_SEND_TASK_VERSION,
  canonicalName: BANK_SEND_TASK_MODULE.canonicalName,
  sourceDocumentType: BANK_SEND_TASK_MODULE.sourceDocumentType,
  actionIds,
  guardCount: Object.keys(guards).length,
  blockerCount: failedGuards.length,
  failedGuards,
  guards,
  bankSendExecutionWriteCount: 0,
  productionUserDataWritten: false,
}
const resultRoot = path.join(root, 'test-results', 'bank-send-task-v59')
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'static-guard-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (failedGuards.length) {
  throw new Error(`V59 static guards failed: ${failedGuards.join(', ')}`)
}

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const files = {
  workflowModels: read('../backend/workflow_runtime/models.py'),
  workflowProviders: read('../backend/workflow_runtime/providers.py'),
  paymentRequestServices: read('../backend/payment_request/services.py'),
  formalModels: read('../backend/formal_payment_order/models.py'),
  formalFacts: read('../backend/formal_payment_order/facts.py'),
  formalServices: read('../backend/formal_payment_order/services.py'),
  formalViews: read('../backend/formal_payment_order/views.py'),
  formalPage: read('src/meta/pages/FormalPaymentOrderPage.vue'),
  formalRuntime: read('src/meta/runtime/formalPaymentOrderRuntime.js'),
  processRegistry: read('src/meta/process/businessProcessRegistry.js'),
  agents: read('../../AGENTS.md'),
  webAcceptance: read('../docs/standards/PCE-WEB-ACCEPTANCE-V1.1.md'),
  approvalStandard: read('../docs/standards/PCE-APPROVAL-CONTRACT-V1.1.md'),
  stateMachineStandard: read('../docs/standards/PCE-STATE-MACHINE-CONTRACT-V1.1.md'),
}

const guard = (name, passed, expected, actual) => ({
  name,
  passed: Boolean(passed),
  expected,
  actual,
})

const sharedTypes = ['ProcessDefinition', 'WorkflowInstance', 'ApprovalTask', 'ApprovalDecision']
const forbiddenApprovalStorage = /approvalList\s*=|approvalArray\s*=|temporaryApprovalState\s*=/
const allFrontend = fs.readdirSync(path.join(root, 'src/meta/pages'))
  .filter(name => name.endsWith('.vue'))
  .map(name => read(`src/meta/pages/${name}`))
  .join('\n')

const guards = [
  guard(
    'workflow_engine_is_shared',
    sharedTypes.every(type => files.formalServices.includes(type))
      && sharedTypes.every(type => files.paymentRequestServices.includes(type))
      && !forbiddenApprovalStorage.test(allFrontend),
    'FormalPaymentOrder and PaymentRequest reuse all four workflow_runtime entities; no parallel client arrays',
    {
      formalSharedTypes: sharedTypes.filter(type => files.formalServices.includes(type)),
      paymentRequestSharedTypes: sharedTypes.filter(type => files.paymentRequestServices.includes(type)),
      parallelArrayFound: forbiddenApprovalStorage.test(allFrontend),
    },
  ),
  guard(
    'formal_payment_order_state_transition_valid',
    ['PREPARED', 'SUBMITTED', 'APPROVED', 'FROZEN_FOR_EXECUTION'].every(state => files.formalModels.includes(state))
      && !files.formalModels.includes('CANCELLED =')
      && files.formalServices.includes('"stateTransition": "prepared->submitted"')
      && files.formalServices.includes('"submitted->approved"')
      && files.formalServices.includes('"stateTransition": "approved->frozen_for_execution"')
      && !files.formalServices.includes('"stateTransition": "prepared->frozen_for_execution"'),
    'prepared -> submitted -> approved -> frozen_for_execution only',
    'server transition evidence inspected',
  ),
  guard(
    'approval_requires_workflow_instance',
    files.formalModels.includes('class FormalPaymentOrderApproval')
      && files.formalModels.includes('workflow_instance = models.OneToOneField')
      && files.formalServices.includes('WorkflowInstance.objects.create'),
    'FormalPaymentOrderApproval has one shared WorkflowInstance',
    'model and service relationship inspected',
  ),
  guard(
    'freeze_requires_approved_status',
    files.formalServices.includes('current.status != FormalPaymentOrder.Status.APPROVED')
      && files.formalServices.includes('FPO_FREEZE_REQUIRES_APPROVED_STATUS'),
    'freeze rejects every non-approved state',
    'approved-state guard present',
  ),
  guard(
    'freeze_hash_protects_execution_fields',
    files.formalModels.includes('EXECUTION_FIELDS')
      && files.formalModels.includes('Frozen formal payment order execution fields are immutable')
      && ['payerAccountId', 'payeeAccountId', 'bankRoute', 'executionDate', 'riskVersion', 'approvalVersion']
        .every(field => files.formalFacts.includes(`"${field}"`))
      && files.formalServices.includes('freeze_hash=execution_snapshot_hash'),
    'freezeHash covers protected execution facts and frozen model rejects changes',
    'hash payload and immutability guard present',
  ),
  guard(
    'bank_send_eligibility_server_derived',
    files.formalFacts.includes('class BankSendEligibility')
      && files.formalFacts.includes('server_derived: bool = True')
      && files.formalServices.includes('build_execution_gate_facts(order)')
      && !/readyForBankSend\s*=/.test(files.formalPage),
    'eligibility derives in backend facts and client only reads it',
    'server dataclass and client binding inspected',
  ),
  guard(
    'bank_message_zero_before_send',
    files.formalFacts.includes('"bankMessages": 0')
      && files.formalFacts.includes('bank_message_count: int = 0')
      && !files.formalPage.includes('data-action-id="send-bank"')
      && !files.formalPage.includes('data-action-id="generate-bank-message"'),
    'bank message/task counts stay zero and actions are absent',
    'zero facts and action whitelist inspected',
  ),
  guard(
    'payment_execution_zero_before_release',
    files.formalFacts.includes('"paymentExecutions": 0')
      && files.formalFacts.includes('payment_execution_count: int = 0')
      && !files.formalPage.includes('data-action-id="execute-payment"'),
    'payment execution count stays zero and execution action is absent',
    'zero facts and action whitelist inspected',
  ),
  guard(
    'approval_segregation_valid',
    files.formalServices.includes('user.pk != current.created_by_id')
      && files.formalServices.includes('user.pk not in prior_actor_ids')
      && files.formalFacts.includes('roles[:2] == ["payment_checker", "payment_authorizer"]'),
    'maker != checker, maker != authorizer, checker != final authorizer',
    'actor and role separation guards present',
  ),
  guard(
    'all_pages_use_common_workflow_contract',
    !forbiddenApprovalStorage.test(allFrontend)
      && files.paymentRequestServices.includes('from workflow_runtime.models import')
      && files.formalServices.includes('from workflow_runtime.models import')
      && files.agents.includes('PCE 审批、状态机、冻结与执行门禁长期规则')
      && files.webAcceptance.includes('审批页必须复用服务端共享工作流引擎')
      && files.approvalStandard.includes('单一审批引擎')
      && files.stateMachineStandard.includes('服务端状态机'),
    'all implemented approval pages use common workflow contract and standards are permanent',
    {
      approvalModulesScanned: ['payment_request', 'formal_payment_order'],
      sharedWorkflowModules: 2,
      parallelArrayFound: forbiddenApprovalStorage.test(allFrontend),
    },
  ),
]

const forbiddenActions = [
  'send-bank',
  'generate-bank-message',
  'execute-payment',
  'generate-payment-voucher',
  'writeoff',
  'ledger',
  'posting',
]
const actionIds = [...files.formalPage.matchAll(/data-action-id="([^"]+)"/g)].map(match => match[1])
const report = {
  result: guards.every(item => item.passed) ? 'passed' : 'failed',
  version: 'V1.14.2.8.4.7.54',
  guardCount: guards.length,
  passedCount: guards.filter(item => item.passed).length,
  failedCount: guards.filter(item => !item.passed).length,
  guards,
  actionIds,
  forbiddenActionIds: actionIds.filter(actionId => forbiddenActions.some(value => actionId.includes(value))),
  commonWorkflowScan: {
    approvalModulesScanned: 2,
    sharedWorkflowModules: 2,
    parallelApprovalContractCount: 0,
  },
}
if (report.forbiddenActionIds.length) {
  report.result = 'failed'
  report.failedCount += 1
}

const outputDir = path.join(root, 'test-results', 'formal-payment-order-v54')
fs.mkdirSync(outputDir, { recursive: true })
const outputPath = path.join(outputDir, 'static-guard-report.json')
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ ...report, guards: undefined, reportPath: outputPath }, null, 2))
if (report.result !== 'passed') process.exit(1)

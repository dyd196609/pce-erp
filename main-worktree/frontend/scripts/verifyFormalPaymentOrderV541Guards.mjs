import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.54.1'
const root = process.cwd()
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const files = {
  workflowModels: read('../backend/workflow_runtime/models.py'),
  transitionService: read('../backend/workflow_runtime/state_transitions.py'),
  formalModels: read('../backend/formal_payment_order/models.py'),
  formalFacts: read('../backend/formal_payment_order/facts.py'),
  formalServices: read('../backend/formal_payment_order/services.py'),
  formalPage: read('src/meta/pages/FormalPaymentOrderPage.vue'),
  formalRuntime: read('src/meta/runtime/formalPaymentOrderRuntime.js'),
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
const directFormalStatusMutation = /\bcurrent\.status\s*=(?!=)/.test(
  files.formalServices,
)
const guards = [
  guard(
    'state_requires_transition_record',
    files.workflowModels.includes('class BusinessStateTransition')
      && files.formalServices.includes('transition_business_object')
      && files.formalFacts.includes('status_transition_history'),
    'every FormalPaymentOrder status change creates BusinessStateTransition',
    'shared model/service/fact history present',
  ),
  guard(
    'status_change_requires_audit',
    files.formalServices.includes('_gate_audit')
      && ['SUBMIT_ACTION', 'APPROVE_ACTION', 'FREEZE_ACTION']
        .every(action => files.formalServices.includes(action)),
    'each three-step transition remains in the committed audit transaction',
    'transition and audit calls share atomic service paths',
  ),
  guard(
    'submitted_requires_workflow',
    files.formalServices.includes('WorkflowInstance.objects.create')
      && files.formalServices.includes('workflow_instance=workflow'),
    'submitted transition references shared workflow instance',
    'workflow is created before transition',
  ),
  guard(
    'approved_requires_decision',
    files.formalServices.includes('ApprovalDecision.objects.create')
      && files.formalFacts.includes('len(decisions) >= 2')
      && files.formalFacts.includes('approval.approval_status == "approved"'),
    'approved requires two committed decisions',
    'decision and state-fact guards present',
  ),
  guard(
    'frozen_requires_snapshot',
    files.formalModels.includes('class FormalPaymentOrderFreezeSnapshot')
      && files.formalServices.includes('FormalPaymentOrderFreezeSnapshot.objects.create')
      && files.formalFacts.includes('and freeze'),
    'frozen_for_execution requires immutable FormalPaymentOrderFreezeSnapshot',
    'snapshot model/service/fact guard present',
  ),
  guard(
    'freeze_hash_required',
    files.formalModels.includes('freeze_hash = models.CharField')
      && files.formalFacts.includes('and freeze.freeze_hash')
      && files.formalFacts.includes('execution_snapshot_hash'),
    'freezeHash is non-empty and matches current protected execution facts',
    'hash field and verification present',
  ),
  guard(
    'status_matches_workflow',
    files.formalFacts.includes('workflow.status == "approved"')
      && files.formalFacts.includes('EXPECTED_STATE_TRANSITIONS'),
    'business status and workflow state are evaluated together',
    'server fact consistency function present',
  ),
  guard(
    'status_matches_freeze',
    files.formalFacts.includes('order.status == "frozen_for_execution"')
      && files.formalFacts.includes('freeze_status="frozen" if freeze else "not_frozen"'),
    'frozen status and snapshot are evaluated together',
    'server fact mapping present',
  ),
  guard(
    'strictFacts_matches_state_machine',
    files.formalRuntime.includes('statusTransitionHistory')
      && files.formalRuntime.includes('stateMachineConsistent')
      && files.formalPage.includes('statusTransitionHistory')
      && files.formalPage.includes('strictServerFacts'),
    'API/page/diagnostic/strictFacts share server state transition facts',
    'runtime and diagnostics bindings present',
  ),
  guard(
    'no_manual_status_mutation',
    !directFormalStatusMutation
      && files.formalModels.includes('FormalPaymentOrderQuerySet')
      && files.formalModels.includes('must use BusinessStateTransition')
      && files.agents.includes('所有业务状态必须通过状态转换服务产生')
      && files.webAcceptance.includes('BusinessStateTransition')
      && files.stateMachineStandard.includes('BusinessStateTransition')
      && files.approvalStandard.includes('BusinessStateTransition'),
    'formal services contain no direct status assignment and standards prohibit it',
    {
      directFormalStatusMutation,
      modelSaveGuard: files.formalModels.includes('must use BusinessStateTransition'),
    },
  ),
]
const failures = guards.filter(row => !row.passed).map(row => row.name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  guardCount: guards.length,
  passedCount: guards.filter(row => row.passed).length,
  failedCount: failures.length,
  failures,
  guards,
}
const resultRoot = path.join(root, 'test-results', 'formal-payment-order-v541')
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'static-guard-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify({
  ...report,
  guards: undefined,
  reportPath: path.join(resultRoot, 'static-guard-report.json'),
}, null, 2))
if (failures.length) process.exit(1)

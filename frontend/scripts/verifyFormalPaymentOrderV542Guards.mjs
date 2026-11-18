import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.54.2'
const root = process.cwd()
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const files = {
  workflowModels: read('../backend/workflow_runtime/models.py'),
  workflowFacts: read('../backend/workflow_runtime/facts.py'),
  transitionService: read('../backend/workflow_runtime/state_transitions.py'),
  migration: read('../backend/workflow_runtime/migrations/0003_transition_fact_integrity.py'),
  formalModels: read('../backend/formal_payment_order/models.py'),
  formalFacts: read('../backend/formal_payment_order/facts.py'),
  formalServices: read('../backend/formal_payment_order/services.py'),
  formalRuntime: read('src/meta/runtime/formalPaymentOrderRuntime.js'),
  formalPage: read('src/meta/pages/FormalPaymentOrderPage.vue'),
  agents: read('../../AGENTS.md'),
  stateMachineStandard: read('../docs/standards/PCE-STATE-MACHINE-CONTRACT-V1.1.md'),
  webAcceptance: read('../docs/standards/PCE-WEB-ACCEPTANCE-V1.1.md'),
}
const guard = (name, passed, expected, actual) => ({
  name,
  passed: Boolean(passed),
  expected,
  actual,
})
const canonicalModelFields = [
  'object_type',
  'object_id',
  'source_state',
  'target_state',
  'operator',
  'timestamp',
  'reason',
  'version',
  'audit_reference',
]
const canonicalApiFields = [
  'objectType',
  'objectId',
  'sourceState',
  'targetState',
  'operator',
  'timestamp',
  'reason',
  'version',
  'auditReference',
]
const transitionPositions = [
  ...files.formalServices.matchAll(/transition_business_object\(/g),
].map(match => match.index)
const auditPositions = [
  ...files.formalServices.matchAll(/audit = _gate_audit\(/g),
].map(match => match.index)
const transitionAuditedFirst = transitionPositions.length === 3
  && auditPositions.length === 3
  && transitionPositions.every((position, index) => auditPositions[index] < position)
const directOrderCreate = /FormalPaymentOrder\.objects\.create\(/.test(files.formalServices)
const directCurrentStatusMutation = /\bcurrent\.status\s*=(?!=)/.test(files.formalServices)
const guards = [
  guard(
    'business_state_transition_has_canonical_fields',
    canonicalModelFields.every(field => files.workflowModels.includes(field)),
    canonicalModelFields,
    canonicalModelFields.filter(field => files.workflowModels.includes(field)),
  ),
  guard(
    'transition_fact_has_database_constraints',
    files.workflowModels.includes('bst_reason_required')
      && files.workflowModels.includes('bst_audit_reference_required')
      && files.workflowModels.includes('uniq_bst_audit_reference'),
    'reason/auditReference required and auditReference unique',
    true,
  ),
  guard(
    'transition_service_requires_reason_and_audit',
    files.transitionService.includes('Transition reason is required')
      && files.transitionService.includes('Transition audit reference is required'),
    'common service rejects incomplete facts',
    true,
  ),
  guard(
    'initial_state_uses_common_service',
    files.transitionService.includes('create_business_object_with_initial_state')
      && files.formalServices.includes('create_business_object_with_initial_state(')
      && !directOrderCreate,
    'FormalPaymentOrder creation uses common initialization service',
    { directOrderCreate },
  ),
  guard(
    'audit_is_persisted_before_transition',
    transitionAuditedFirst
      && files.formalServices.includes('BusinessActionAuditRecord:{audit.pk}'),
    'three state transitions bind an already-created audit in one transaction',
    { transitionCount: transitionPositions.length, auditCount: auditPositions.length },
  ),
  guard(
    'direct_formal_status_mutation_absent',
    !directCurrentStatusMutation
      && files.formalModels.includes('FormalPaymentOrderQuerySet')
      && files.formalModels.includes('initial status must use state initialization service'),
    'save, bulk update and direct initialization are blocked',
    { directCurrentStatusMutation },
  ),
  guard(
    'transition_history_is_database_authoritative',
    files.formalFacts.includes('BusinessStateTransition.objects.filter(')
      && files.formalFacts.includes('audit_reference')
      && files.formalFacts.includes('BusinessActionAuditRecord.objects.filter'),
    'facts read transitions and verify the referenced authority audit',
    true,
  ),
  guard(
    'provider_cannot_fabricate_transition_history',
    !/def _status_transition_history\([^)]*provider/i.test(files.formalFacts)
      && files.formalFacts.includes('object_type="formal_payment_order"'),
    'transition history has no Provider input',
    true,
  ),
  guard(
    'canonical_transition_fields_are_exposed',
    canonicalApiFields.every(field => files.formalFacts.includes(`"${field}"`)),
    canonicalApiFields,
    canonicalApiFields.filter(field => files.formalFacts.includes(`"${field}"`)),
  ),
  guard(
    'server_transition_count_is_explicit',
    files.workflowFacts.includes('"statusTransitionCount"')
      && files.workflowFacts.includes('len(persisted_history)')
      && files.formalFacts.includes('status_transition_facts(')
      && files.formalServices.includes('"statusTransitionCount"')
      && files.formalRuntime.includes('row.statusTransitionCount')
      && files.formalPage.includes('statusTransitionCount'),
    'API/page/diagnostic/strictFacts carry server count',
    true,
  ),
  guard(
    'migration_binds_authoritative_existing_audits',
    files.migration.includes('backfill_authoritative_transition_evidence')
      && files.migration.includes('BusinessActionAuditRecord:')
      && files.migration.includes('result="committed"'),
    'legacy V54.1 facts bind real committed audits without action replay',
    true,
  ),
  guard(
    'state_transition_standard_is_enforced',
    files.agents.includes('所有业务状态必须通过统一状态转换服务')
      && files.stateMachineStandard.includes('所有业务状态必须通过统一状态转换服务')
      && files.webAcceptance.includes('所有业务状态必须通过统一状态转换服务'),
    'AGENTS/state-machine/web standards updated',
    true,
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
const resultRoot = path.join(root, 'test-results', 'formal-payment-order-v542')
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

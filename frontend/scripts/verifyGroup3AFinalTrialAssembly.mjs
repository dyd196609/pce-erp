import { DatabaseSync } from 'node:sqlite'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..', '..')
const db = new DatabaseSync(resolve(root, 'backend', 'db.sqlite3'), { readOnly: true })
const operations = db.prepare(`
  select id, code, name, display_order, default_transition_mode
  from system_process where company_id = 1 order by display_order, id
`).all()
const trial = operations.find((row) => row.name === '试装')
const ledger = db.prepare(`
  select id, status, target_entity_id, source_identity_id, result
  from masterdata_write_request
  where organization_id = 1 and action_code = 'production.master_data.resource.maintain'
    and idempotency_key = 'GROUP3A-TRIAL-ASSEMBLY-KITTING-20260908-001'
`).get()
const audit = db.prepare(`
  select a.id, u.username as actor, a.before_snapshot, a.after_snapshot
  from system_organization_operating_audits a
  join user_system u on u.id = a.actor_id
  where a.id = json_extract(?, '$.auditId')
`).get(ledger?.result || '{}')
const identity = db.prepare(`
  select id, source_system, source_type, external_id, target_entity_type, target_entity_id, mapping_status
  from masterdata_external_identity where id = ?
`).get(ledger?.source_identity_id || -1)
const protectedCounts = Object.fromEntries([
  'pde_product_bom', 'pde_bom_version', 'pde_bom_item',
  'pde_routing', 'pde_routing_version', 'pde_routing_step',
  'pde_work_center', 'pde_standard_capacity',
].map((table) => [table, Number(db.prepare(`select count(*) as value from ${table}`).get().value)]))
db.close()

const serviceSource = readFileSync(resolve(root, 'backend', 'masterdata', 'group3a_operation_remediation_service.py'), 'utf8')
const pageSource = readFileSync(resolve(root, 'frontend', 'src', 'meta', 'pages', 'Group3AOperationTargetedRevalidationPage.vue'), 'utf8')
const before = JSON.parse(audit?.before_snapshot || '{}')
const after = JSON.parse(audit?.after_snapshot || '{}')
const result = JSON.parse(ledger?.result || '{}')
const kittingNames = operations.filter((row) => row.default_transition_mode === 'KITTING').map((row) => row.name)
const checks = {
  processCount33: operations.length === 33,
  displayOrderFrozen: operations[0]?.name === '开料' && operations[0]?.display_order === 1
    && operations[1]?.name === '拼皮' && operations[1]?.display_order === 2,
  trialAssemblyKitting: trial?.default_transition_mode === 'KITTING',
  kittingExactlyThree: kittingNames.length === 3 && ['白坯检验', '试装', '成品检'].every((name) => kittingNames.includes(name)),
  generalExactlyThirty: operations.filter((row) => row.default_transition_mode === 'GENERAL').length === 30,
  ledgerCommitted: ledger?.status === 'COMMITTED' && ledger?.target_entity_id === String(trial?.id),
  idempotencyVerified: result.idempotentReplay === false && result.previousMode === 'GENERAL' && result.currentMode === 'KITTING',
  auditExactChange: audit?.actor === 'emd_emp047'
    && before.state?.default_transition_mode === 'GENERAL'
    && after.state?.default_transition_mode === 'KITTING',
  executorChain: after.executionChain?.employeeNo === 'EMP047'
    && after.executionChain?.responsibilityCode === 'ENTERPRISE_MASTER_DATA_MAINTAINER',
  sourceIdentityPreserved: identity?.target_entity_type === 'operations'
    && identity?.target_entity_id === String(trial?.id) && identity?.mapping_status === 'MATCH',
  protectedScopeZero: Object.values(protectedCounts).every((value) => value === 0),
  serviceIsTransactionalAndExact: serviceSource.includes('@transaction.atomic')
    && serviceSource.includes('name=exact_name') && serviceSource.includes('select_for_update()'),
  oneItemAcceptanceUi: pageSource.includes('唯一待确认项：试装')
    && pageSource.includes('facts.value.focusRows || []')
    && pageSource.includes('facts.finalTarget?.transitionMode'),
}

if (Object.values(checks).some((value) => !value)) {
  console.error(JSON.stringify({ result: 'failed', checks, kittingNames, protectedCounts }, null, 2))
  process.exit(1)
}

console.log(JSON.stringify({
  result: 'passed', checks, processCount: operations.length,
  displayOrder: operations.slice(0, 2), kittingNames,
  generalCount: operations.filter((row) => row.default_transition_mode === 'GENERAL').length,
  trialAssembly: trial, auditId: audit.id, ledgerId: ledger.id,
  executor: after.executionChain, sourceIdentity: identity, protectedCounts,
}, null, 2))

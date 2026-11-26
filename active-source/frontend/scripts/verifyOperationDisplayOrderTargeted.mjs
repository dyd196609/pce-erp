import { DatabaseSync } from 'node:sqlite'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..', '..')
const db = new DatabaseSync(resolve(root, 'backend', 'db.sqlite3'), { readOnly: true })
const rows = db.prepare(`
  select id, code, name, display_order, default_transition_mode
  from system_process
  order by display_order, id
`).all()
const protectedCounts = Object.fromEntries([
  'pde_product_bom', 'pde_bom_version', 'pde_bom_item',
  'pde_routing', 'pde_routing_version', 'pde_routing_step',
  'pde_work_center', 'pde_standard_capacity',
].map((table) => [table, Number(db.prepare(`select count(*) as value from ${table}`).get().value)]))
db.close()

const modelSource = readFileSync(resolve(root, 'backend', 'system', 'models.py'), 'utf8')
const serviceSource = readFileSync(resolve(root, 'backend', 'pde', 'production_foundation_service.py'), 'utf8')
const pageSource = readFileSync(resolve(root, 'frontend', 'src', 'meta', 'pages', 'Group3AOperationTargetedRevalidationPage.vue'), 'utf8')

const checks = {
  countPreserved: rows.length === 33,
  openingFirst: rows[0]?.name === '开料' && rows[0]?.display_order === 1,
  pinpiSecond: rows[1]?.name === '拼皮' && rows[1]?.display_order === 2,
  priorRelativeOrderPreserved: rows.slice(2).every((row, index) => row.id === index + 2),
  continuousFormalOrder: rows.every((row, index) => row.display_order === index + 1),
  kittingFactsPreserved: ['白坯检验', '试装', '成品检'].every((name) => rows.some((row) => row.name === name && row.default_transition_mode === 'KITTING'))
    && rows.filter((row) => row.default_transition_mode === 'KITTING').length === 3
    && rows.filter((row) => row.default_transition_mode === 'GENERAL').length === 30,
  aliasFactPreserved: rows.some((row) => row.name === '拉丝/打磨'),
  modelHasFormalDisplayOrder: modelSource.includes('display_order = models.PositiveIntegerField(')
    && modelSource.includes('不替代任何RoutingStep.sequence'),
  apiUsesFormalDisplayOrder: serviceSource.includes('("display_order", "pk") if entity == "operations"'),
  acceptanceReadsFormalValues: pageSource.includes('facts.finalTarget?.transitionMode')
    && pageSource.includes('facts.finalTarget?.dataProvenance'),
  routingScopeUntouched: Object.values(protectedCounts).every((value) => value === 0),
}

if (Object.values(checks).some((value) => !value)) {
  console.error(JSON.stringify({ result: 'failed', checks, protectedCounts }, null, 2))
  process.exit(1)
}

console.log(JSON.stringify({
  result: 'passed',
  sortingMechanism: 'system.Process.display_order + API order_by(display_order, pk)',
  firstThree: rows.slice(0, 3),
  protectedCounts,
  checks,
  routingSemanticsChanged: false,
}, null, 2))

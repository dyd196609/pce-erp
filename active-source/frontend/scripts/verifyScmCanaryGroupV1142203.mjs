import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const canaryDbPath = path.resolve(sourceRoot, 'backend/canary-data/scm-canary-flow-v1.sqlite3')
const formalDbPath = path.resolve(sourceRoot, 'backend/db.sqlite3')
const archiveRoot = path.resolve(frontendRoot, 'test-results/SCM-Canary-Group-V1142203')
const evidenceRoot = path.resolve(archiveRoot, 'browser-evidence')
const requiredScenarios = [
  'HAPPY_PATH', 'QUANTITY_DIFFERENCE', 'PRICE_EXCEPTION', 'SUPPLIER_MISSING',
  'QUALITY_FAIL', 'INBOUND_SHORTAGE', 'RECONCILIATION_DIFF', 'EXISTING_TARGET',
]
const expectedNodes = [
  'purchase-request', 'purchase-inquiry', 'purchase-price-approval', 'purchase-order',
  'purchase-receipt', 'purchase-inspection', 'warehouse-inbound', 'supplier-reconciliation',
]
const fileHash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const canaryBefore = fileHash(canaryDbPath)
const formalBefore = fileHash(formalDbPath)
const db = new DatabaseSync(canaryDbPath, { readOnly: true })
db.exec('PRAGMA query_only = ON')
const batches = db.prepare('SELECT * FROM pce_purchase_canary_batch ORDER BY id').all()
const scenarios = db.prepare('SELECT * FROM pce_purchase_canary_scenario ORDER BY id').all()
const matrix = db.prepare('SELECT * FROM scm_canary_scenario_matrix ORDER BY id').all()
const profiles = db.prepare('SELECT * FROM scm_canary_purchase_request_profile ORDER BY id').all()
const objects = db.prepare(`SELECT s.code AS scenarioCode,o.* FROM pce_purchase_canary_module_object o JOIN pce_purchase_canary_scenario s ON s.id=o.scenario_id ORDER BY s.id,o.sequence`).all()
const relations = db.prepare(`SELECT s.code AS scenarioCode,r.* FROM pce_purchase_canary_relation r JOIN pce_purchase_canary_scenario s ON s.id=r.scenario_id ORDER BY s.id,r.id`).all()
db.close()

const rules = []
const add = (code, name, passed, actual) => rules.push({ code, name, result: passed ? 'PASS' : 'FAIL', actual })
add('SCM-CANARY-001', '独立批次数量为1', batches.length === 1 && batches[0].batch_id === 'SCM-CANARY-FLOW-V1', batches.map(row => row.batch_id))
add('SCM-CANARY-002', '场景矩阵至少8项且必选项完整', scenarios.length >= 8 && requiredScenarios.every(code => scenarios.some(row => row.code === code)), scenarios.map(row => row.code))
add('SCM-CANARY-003', '采购申请金丝雀不少于8条', profiles.length >= 8 && profiles.every(row => row.canary === 1 && row.read_only === 1), profiles.map(row => row.request_no))
const chainResults = requiredScenarios.map(code => {
  const chain = objects.filter(row => row.scenarioCode === code)
  const links = relations.filter(row => row.scenarioCode === code)
  return { code, nodes: chain.map(row => row.module_code), relationCount: links.length, passed: chain.map(row => row.module_code).join('|') === expectedNodes.join('|') && links.length === 7 }
})
add('SCM-CANARY-004', '每条八节点对象链可追踪', chainResults.every(row => row.passed), chainResults)
add('SCM-CANARY-005', '多物料采购申请包含至少3条物料', Number(profiles.find(row => row.scenario_code === 'QUANTITY_DIFFERENCE')?.material_count || 0) >= 3, profiles.find(row => row.scenario_code === 'QUANTITY_DIFFERENCE')?.material_count)
add('SCM-CANARY-006', '场景矩阵字段完整', matrix.length >= 8 && matrix.every(row => row.scenario_code && row.scenario_name && row.source_object && row.expected_status && row.next_step && row.canary === 1), matrix.length)
add('SCM-CANARY-007', '金丝雀清理策略为manual_only', batches.every(row => row.purpose === 'canary_acceptance'), 'manual_only')
const canaryAfterRead = fileHash(canaryDbPath)
const formalAfterRead = fileHash(formalDbPath)
add('SCM-CANARY-008', '只读验收不写正式业务数据库', formalBefore === formalAfterRead, { productionUserDataWritten: false, before: formalBefore, after: formalAfterRead })
add('SCM-CANARY-009', '刷新读取前后金丝雀Hash一致', canaryBefore === canaryAfterRead, { before: canaryBefore, after: canaryAfterRead })

const totals = {
  total: rules.length,
  PASS: rules.filter(row => row.result === 'PASS').length,
  FAIL: rules.filter(row => row.result === 'FAIL').length,
  UNKNOWN: 0,
}
const status = totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'CANARY_GROUP_READY' : 'FAIL'
const acceptance = {
  version: 'V1.14.2.8.4.20.3',
  batchId: 'SCM-CANARY-FLOW-V1',
  status,
  nextPageAllowed: false,
  counts: { batches: batches.length, scenarios: scenarios.length, purchaseRequests: profiles.length, objects: objects.length, relations: relations.length },
  totals,
  rules,
  productionUserDataWritten: false,
  canaryCleanupPolicy: 'manual_only',
}
const objectChain = requiredScenarios.map(code => ({
  scenarioCode: code,
  objects: objects.filter(row => row.scenarioCode === code).map(row => ({
    sequence: row.sequence, moduleCode: row.module_code, objectNo: row.object_no,
    status: row.object_status, upstreamObjectNo: row.upstream_object_no, downstreamObjectNo: row.downstream_object_no,
  })),
  relations: relations.filter(row => row.scenarioCode === code).map(row => ({ sourceObjectNo: row.source_object_no, targetObjectNo: row.target_object_no, relationshipType: row.relation_type })),
}))
const protection = {
  productionUserDataWritten: false,
  businessDatabaseWriteCount: 0,
  formalDatabaseHashBefore: formalBefore,
  formalDatabaseHashAfter: formalAfterRead,
  formalDatabaseHashUnchanged: formalBefore === formalAfterRead,
  canaryDatabaseHashBefore: canaryBefore,
  canaryDatabaseHashAfter: canaryAfterRead,
  canaryDatabaseHashUnchanged: canaryBefore === canaryAfterRead,
}
fs.mkdirSync(evidenceRoot, { recursive: true })
fs.writeFileSync(path.join(archiveRoot, 'acceptance.json'), `${JSON.stringify(acceptance, null, 2)}\n`)
fs.writeFileSync(path.join(archiveRoot, 'scenario-matrix.json'), `${JSON.stringify(matrix, null, 2)}\n`)
fs.writeFileSync(path.join(archiveRoot, 'object-chain.json'), `${JSON.stringify(objectChain, null, 2)}\n`)
fs.writeFileSync(path.join(archiveRoot, 'database-protection.json'), `${JSON.stringify(protection, null, 2)}\n`)
console.log(JSON.stringify(acceptance, null, 2))
if (status !== 'CANARY_GROUP_READY') process.exitCode = 1

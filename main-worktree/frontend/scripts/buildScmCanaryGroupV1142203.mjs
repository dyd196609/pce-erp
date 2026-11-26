import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const target = path.resolve(frontendRoot, '../backend/canary-data/scm-canary-flow-v1.sqlite3')
if (fs.existsSync(target)) {
  throw new Error(`SCM canary database already exists; refusing to overwrite: ${target}`)
}

const BATCH_ID = 'SCM-CANARY-FLOW-V1'
const VERSION = 'V1.14.2.8.4.20.3'
const nodes = Object.freeze([
  ['purchase-request', '采购申请', '/scm/purchase-request', 'PRQ'],
  ['purchase-inquiry', '采购询价', '/scm/purchase-inquiry', 'PI'],
  ['purchase-price-approval', '采购核价', '/scm/price-approval', 'PA'],
  ['purchase-order', '采购订单', '/scm/purchase-orders', 'PO'],
  ['purchase-receipt', '采购收货', '/wms/purchase-receive-preview', 'RCPT'],
  ['purchase-inspection', '质量检验', '/qms/incoming-inspections', 'INSP'],
  ['warehouse-inbound', '仓库入库', '/wms/inventory-balances', 'INB'],
  ['supplier-reconciliation', '供应商对账', '/scm/supplier-reconciliations', 'REC'],
])
const scenarios = Object.freeze([
  { code: 'HAPPY_PATH', name: '正常生产材料采购', group: '正常场景组', requestNo: 'PRQ-CAN-001', materialCount: 2, expectedStatus: 'completed', blockingNode: '', blockingReason: '', nextStep: '流程完成', requestType: '生产材料', projectCode: '', costCenterCode: 'CC-PRODUCTION', feature: '标准八节点闭环' },
  { code: 'QUANTITY_DIFFERENCE', name: '多物料数量差异', group: '数量场景组', requestNo: 'PRQ-CAN-002', materialCount: 4, expectedStatus: 'quantity_difference', blockingNode: 'supplier-reconciliation', blockingReason: '收货、入库与对账数量存在差异', nextStep: '差异分析', requestType: '多物料采购', projectCode: '', costCenterCode: 'CC-PRODUCTION', feature: '4条物料明细' },
  { code: 'QUALITY_FAIL', name: '设备采购质量不合格', group: '质量场景组', requestNo: 'PRQ-CAN-003', materialCount: 1, expectedStatus: 'quality_failed', blockingNode: 'purchase-inspection', blockingReason: '设备质量检验不合格，禁止进入正常入库', nextStep: '质量异常处置', requestType: '设备采购', projectCode: 'FA-EQUIPMENT-2026', costCenterCode: 'CC-EQUIPMENT', feature: '设备类费用、固定资产' },
  { code: 'INBOUND_SHORTAGE', name: '项目采购入库不足', group: '入库场景组', requestNo: 'PRQ-CAN-004', materialCount: 3, expectedStatus: 'inbound_shortage', blockingNode: 'warehouse-inbound', blockingReason: '实际入库数量低于合格收货数量', nextStep: '入库差异处理', requestType: '项目采购', projectCode: 'PRJ-SCM-CAN-2026', costCenterCode: 'CC-PROJECT', feature: 'Project Master、Cost Center' },
  { code: 'RECONCILIATION_DIFF', name: '紧急采购对账差异', group: '对账场景组', requestNo: 'PRQ-CAN-005', materialCount: 2, expectedStatus: 'difference_found', blockingNode: 'supplier-reconciliation', blockingReason: '供应商对账金额或数量存在差异', nextStep: '供应商差异确认', requestType: '紧急采购', projectCode: '', costCenterCode: 'CC-URGENT', feature: '特殊审批场景' },
  { code: 'SUPPLIER_MISSING', name: '多供应商询价缺失', group: '供应商场景组', requestNo: 'PRQ-CAN-006', materialCount: 2, expectedStatus: 'supplier_missing', blockingNode: 'purchase-inquiry', blockingReason: '有效供应商不足，不能完成供应商比较', nextStep: '补充供应商', requestType: '多供应商询价', projectCode: '', costCenterCode: 'CC-PROCUREMENT', feature: '供应商比较' },
  { code: 'PRICE_EXCEPTION', name: '核价价格异常', group: '金额场景组', requestNo: 'PRQ-CAN-007', materialCount: 2, expectedStatus: 'price_exception', blockingNode: 'purchase-price-approval', blockingReason: '核价价格偏离控制区间', nextStep: '价格风险复核', requestType: '价格异常', projectCode: '', costCenterCode: 'CC-PROCUREMENT', feature: '核价风险' },
  { code: 'EXISTING_TARGET', name: '异常关闭与目标已存在', group: '正常场景组', requestNo: 'PRQ-CAN-008', materialCount: 1, expectedStatus: 'closed', blockingNode: 'purchase-request', blockingReason: '申请已异常关闭，且目标对象已存在', nextStep: '流程终止', requestType: '异常关闭', projectCode: '', costCenterCode: 'CC-PROCUREMENT', feature: '流程终止' },
])
const hash = value => crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex')
const db = new DatabaseSync(target)
db.exec(`
  PRAGMA journal_mode = DELETE;
  PRAGMA foreign_keys = ON;
  CREATE TABLE pce_purchase_canary_batch (id INTEGER PRIMARY KEY, batch_id TEXT UNIQUE NOT NULL, tenant_id TEXT NOT NULL, purpose TEXT NOT NULL, version TEXT NOT NULL, schema_version TEXT NOT NULL, created_at TEXT NOT NULL);
  CREATE TABLE pce_purchase_canary_scenario (id INTEGER PRIMARY KEY, code TEXT NOT NULL, name TEXT NOT NULL, expected_outcome TEXT NOT NULL, block_reason TEXT NOT NULL, scenario_hash TEXT NOT NULL, batch_id INTEGER NOT NULL REFERENCES pce_purchase_canary_batch(id), UNIQUE(batch_id, code));
  CREATE TABLE pce_purchase_canary_module_object (id INTEGER PRIMARY KEY, sequence INTEGER NOT NULL, module_code TEXT NOT NULL, module_name TEXT NOT NULL, route_path TEXT NOT NULL, object_no TEXT NOT NULL, object_status TEXT NOT NULL, upstream_object_no TEXT NOT NULL, downstream_object_no TEXT NOT NULL, next_step_allowed INTEGER NOT NULL, block_reason TEXT NOT NULL, evidence_hash TEXT NOT NULL, scenario_id INTEGER NOT NULL REFERENCES pce_purchase_canary_scenario(id), UNIQUE(scenario_id, module_code), UNIQUE(scenario_id, object_no));
  CREATE TABLE pce_purchase_canary_relation (id INTEGER PRIMARY KEY, source_object_no TEXT NOT NULL, target_object_no TEXT NOT NULL, relation_type TEXT NOT NULL, relation_hash TEXT NOT NULL, scenario_id INTEGER NOT NULL REFERENCES pce_purchase_canary_scenario(id), UNIQUE(scenario_id, source_object_no, target_object_no));
  CREATE TABLE scm_canary_scenario_matrix (id INTEGER PRIMARY KEY, scenario_code TEXT UNIQUE NOT NULL, scenario_name TEXT NOT NULL, scenario_group TEXT NOT NULL, source_object TEXT NOT NULL, target_object TEXT NOT NULL, expected_status TEXT NOT NULL, blocking_reason TEXT NOT NULL, next_step TEXT NOT NULL, canary INTEGER NOT NULL);
  CREATE TABLE scm_canary_purchase_request_profile (id INTEGER PRIMARY KEY, scenario_code TEXT UNIQUE NOT NULL, request_no TEXT UNIQUE NOT NULL, request_type TEXT NOT NULL, project_code TEXT NOT NULL, cost_center_code TEXT NOT NULL, material_count INTEGER NOT NULL, feature TEXT NOT NULL, canary INTEGER NOT NULL, read_only INTEGER NOT NULL);
`)

const insertBatch = db.prepare('INSERT INTO pce_purchase_canary_batch (batch_id,tenant_id,purpose,version,schema_version,created_at) VALUES (?,?,?,?,?,?)')
const insertScenario = db.prepare('INSERT INTO pce_purchase_canary_scenario (code,name,expected_outcome,block_reason,scenario_hash,batch_id) VALUES (?,?,?,?,?,?)')
const insertObject = db.prepare('INSERT INTO pce_purchase_canary_module_object (sequence,module_code,module_name,route_path,object_no,object_status,upstream_object_no,downstream_object_no,next_step_allowed,block_reason,evidence_hash,scenario_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)')
const insertRelation = db.prepare('INSERT INTO pce_purchase_canary_relation (source_object_no,target_object_no,relation_type,relation_hash,scenario_id) VALUES (?,?,?,?,?)')
const insertMatrix = db.prepare('INSERT INTO scm_canary_scenario_matrix (scenario_code,scenario_name,scenario_group,source_object,target_object,expected_status,blocking_reason,next_step,canary) VALUES (?,?,?,?,?,?,?,?,1)')
const insertProfile = db.prepare('INSERT INTO scm_canary_purchase_request_profile (scenario_code,request_no,request_type,project_code,cost_center_code,material_count,feature,canary,read_only) VALUES (?,?,?,?,?,?,?,1,1)')

db.exec('BEGIN IMMEDIATE')
try {
  insertBatch.run(BATCH_ID, 'tenant-scm-canary-v1', 'canary_acceptance', VERSION, 'scm-canary-flow-v1', new Date().toISOString())
  const batchId = Number(db.prepare('SELECT id FROM pce_purchase_canary_batch WHERE batch_id=?').get(BATCH_ID).id)
  scenarios.forEach((scenario, scenarioIndex) => {
    const blockIndex = nodes.findIndex(([code]) => code === scenario.blockingNode)
    const objectNumbers = nodes.map(([, , , prefix]) => `${prefix}-CAN-${String(scenarioIndex + 1).padStart(3, '0')}`)
    objectNumbers[0] = scenario.requestNo
    const rows = nodes.map(([moduleCode, moduleName, routePath], index) => {
      let status = 'completed'
      if (blockIndex >= 0 && index === blockIndex) status = scenario.expectedStatus
      if (blockIndex >= 0 && index > blockIndex) status = 'not_released'
      return { moduleCode, moduleName, routePath, objectNo: objectNumbers[index], status }
    })
    insertScenario.run(scenario.code, scenario.name, scenario.expectedStatus, scenario.blockingReason, hash({ scenario, rows }), batchId)
    const scenarioId = Number(db.prepare('SELECT id FROM pce_purchase_canary_scenario WHERE batch_id=? AND code=?').get(batchId, scenario.code).id)
    rows.forEach((row, index) => {
      const nextAllowed = blockIndex < 0 ? index < rows.length - 1 : index < blockIndex
      const reason = index === blockIndex ? scenario.blockingReason : ''
      insertObject.run(index + 1, row.moduleCode, row.moduleName, row.routePath, row.objectNo, row.status, objectNumbers[index - 1] || '', objectNumbers[index + 1] || '', nextAllowed ? 1 : 0, reason, hash({ ...row, nextAllowed, reason }), scenarioId)
      if (index < rows.length - 1) insertRelation.run(row.objectNo, rows[index + 1].objectNo, 'next_step', hash([scenario.code, row.objectNo, rows[index + 1].objectNo]), scenarioId)
    })
    const sourceIndex = blockIndex >= 0 ? blockIndex : rows.length - 1
    insertMatrix.run(scenario.code, scenario.name, scenario.group, rows[sourceIndex].objectNo, rows[sourceIndex + 1]?.objectNo || '', scenario.expectedStatus, scenario.blockingReason, scenario.nextStep)
    insertProfile.run(scenario.code, scenario.requestNo, scenario.requestType, scenario.projectCode, scenario.costCenterCode, scenario.materialCount, scenario.feature)
  })
  db.exec('COMMIT')
} catch (error) {
  db.exec('ROLLBACK')
  db.close()
  throw error
}
db.exec('PRAGMA query_only = ON')
const summary = {
  batchCount: Number(db.prepare('SELECT COUNT(*) AS count FROM pce_purchase_canary_batch').get().count),
  scenarioCount: Number(db.prepare('SELECT COUNT(*) AS count FROM pce_purchase_canary_scenario').get().count),
  purchaseRequestCount: Number(db.prepare("SELECT COUNT(*) AS count FROM pce_purchase_canary_module_object WHERE module_code='purchase-request'").get().count),
  objectCount: Number(db.prepare('SELECT COUNT(*) AS count FROM pce_purchase_canary_module_object').get().count),
  relationCount: Number(db.prepare('SELECT COUNT(*) AS count FROM pce_purchase_canary_relation').get().count),
}
db.close()
console.log(JSON.stringify({ result: 'PASS', target, ...summary }, null, 2))

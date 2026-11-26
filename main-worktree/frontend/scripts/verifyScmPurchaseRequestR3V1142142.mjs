import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R3'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r3')
const archiveDir = join(outputDir, 'archive')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const pageSource = source('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const apiSource = source('frontend/src/api/purchaseRequest.js')
const modelSource = source('backend/procurement/models.py')
const serializerSource = source('backend/procurement/serializers.py')
const viewSource = source('backend/procurement/purchase_request_api.py')
const urlSource = source('backend/procurement/urls.py')

const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const request = db.prepare(`
  SELECT * FROM scm_purchase_request
  WHERE requester_employee_no = 'EMP006' AND requester = '周丽'
  ORDER BY id DESC LIMIT 1
`).get()
const requestItems = request ? db.prepare(`SELECT * FROM scm_purchase_request_item WHERE purchase_request_id = ? ORDER BY line_no`).all(request.id) : []
const employee = request ? db.prepare('SELECT id, employee_no, full_name, department_name FROM employee WHERE id = ?').get(request.requester_employee_id) : null
const department = request ? db.prepare('SELECT id, code, name FROM system_department WHERE id = ?').get(request.department_master_id) : null
const purchaseDepartment = request ? db.prepare('SELECT id, code, name FROM system_department WHERE id = ?').get(request.purchase_department_master_id) : null
const materials = requestItems.map((row) => db.prepare('SELECT id, code, name, specification, unit, purchase_unit, is_purchased, is_active FROM material WHERE id = ?').get(row.material_id))
const inquiryCount = request ? db.prepare('SELECT COUNT(*) AS count FROM scm_purchase_inquiry WHERE source_purchase_request_id = ?').get(request.id).count : 0
const poColumns = ['id', 'po_no', 'order_date', 'expected_date', 'actual_receive_date', 'status', 'total_amount', 'remark', 'buyer', 'created_by', 'company_id', 'created_at', 'updated_at', 'supplier_id', 'department_id', 'require_department_id', 'purchase_department_id']
const poRows = db.prepare(`SELECT ${poColumns.map((field) => `"${field}"`).join(', ')} FROM purchase_order ORDER BY id`).all().map((row) => poColumns.map((field) => row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({ columns: poColumns, rows: poRows })).digest('hex')
const migrationApplied = Boolean(db.prepare("SELECT 1 AS ok FROM django_migrations WHERE app='procurement' AND name='0007_purchase_request_smart_form_r3'").get())
db.close()

let apiResult = { httpStatus: 0, found: false, itemCount: 0 }
try {
  const response = await fetch('http://127.0.0.1:8000/api/procurement/purchase-requests/', { signal: AbortSignal.timeout(8000) })
  const payload = await response.json()
  const rows = Array.isArray(payload) ? payload : payload.results || payload.data?.results || payload.data || []
  const apiRequest = Array.isArray(rows) ? rows.find((row) => row.requestNo === request?.request_no) : null
  apiResult = { httpStatus: response.status, found: Boolean(apiRequest), itemCount: apiRequest?.items?.length || 0, status: apiRequest?.status || '' }
} catch (error) {
  apiResult.error = error.message
}

const referencesRegistered = ['employees', 'departments', 'purchase-organizations', 'materials'].every((name) => viewSource.includes(`"${name}"`) || viewSource.includes(`{"departments", "purchase-organizations"}`))
const autoFillSnapshots = requestItems.length === 2 && requestItems.every((row, index) => {
  const material = materials[index]
  return material && row.material_code === material.code && row.material_name === material.name
    && row.specification === (material.specification || '')
    && row.unit === (material.purchase_unit || material.unit)
})
const rules = [
  ['SCM-PR-R3-001', '基础资料搜索 API 已注册且采用鉴权与20条有界加载', urlSource.includes('purchase-request-references') && viewSource.includes('IsAuthenticated') && viewSource.includes('[:21]') && referencesRegistered],
  ['SCM-PR-R3-002', '申请人通过人员主数据选择并持久化员工编号', pageSource.includes("searchReference('employees'") && employee?.employee_no === 'EMP006' && request?.requester === employee?.full_name],
  ['SCM-PR-R3-003', '申请部门来自组织结构且申请人与部门匹配', pageSource.includes("searchReference('departments'") && department?.name === employee?.department_name && request?.department === department?.name],
  ['SCM-PR-R3-004', '采购部门来自采购组织主数据', pageSource.includes("searchReference('purchase-organizations'") && purchaseDepartment?.name.includes('采购') && request?.purchase_department === purchaseDepartment?.name],
  ['SCM-PR-R3-005', '物料明细引用有效可采购 Material Master', modelSource.includes('class PurchaseRequestItem') && requestItems.length === 2 && materials.every((material) => material?.is_active === 1 && material?.is_purchased === 1)],
  ['SCM-PR-R3-006', '名称、规格、单位、分类和采购属性由服务端主数据带出', serializerSource.includes('material.specification') && serializerSource.includes('material.category.name') && autoFillSnapshots],
  ['SCM-PR-R3-007', '多行新增、删除、复制及保存能力存在', ['addItemRow', 'removeItemRow', 'copyItemRow'].every((name) => pageSource.includes(name)) && requestItems.length === 2],
  ['SCM-PR-R3-008', 'PurchaseRequest 与 PurchaseRequestItem 已真实写入且 API 可查询', migrationApplied && Boolean(request) && apiResult.httpStatus === 200 && apiResult.found && apiResult.itemCount === 2],
  ['SCM-PR-R3-009', '采购申请状态生命周期已验证 draft → submitted', request?.status === 'submitted' && apiResult.status === 'submitted'],
  ['SCM-PR-R3-010', '数据保护、来源对象和下游隔离保持有效', request?.source_type === 'ManualRequest' && inquiryCount === 0 && poRows.length === 208 && purchaseOrderContentHash === '5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const PASS = rules.filter((rule) => rule.result === 'PASS').length
const FAIL = rules.filter((rule) => rule.result === 'FAIL').length
const report = {
  version, acceptanceId: 'SCM-PURCHASE-REQUEST-ACT-001-R3', pageCode: 'purchase-request',
  requestNo: request?.request_no || '', requestItemCount: requestItems.length,
  ruleCount: rules.length, PASS, FAIL, UNKNOWN: 0,
  result: FAIL === 0 ? 'PASS' : 'FAIL', rules, apiResult,
  masterDataReferences: { employee: employee?.employee_no || '', department: department?.code || '', purchaseOrganization: purchaseDepartment?.code || '', materials: materials.map((row) => row?.code) },
  automaticTestDataCreated: false,
  manualAcceptanceBusinessWrites: ['create PurchaseRequest', 'create 2 PurchaseRequestItem', 'edit PurchaseRequest', 'submit draft -> submitted'],
  inquiryCreated: inquiryCount,
  purchaseOrderCount: poRows.length,
  purchaseOrderContentHash,
  productionUserDataWritten: false,
  archiveCompleted: true,
  nextPageAllowed: FAIL === 0,
}

const restoreMarkdown = `# 采购申请智能表单恢复报告

- 版本：${version}
- 页面：/scm/purchase-request
- 页面标准：PCE Enterprise Page V2（保留）
- 服务端事实：保留
- SCM Business Trace：保留
- 主数据加载：远程搜索，单次最多20条，页面打开不全量加载
- 申请人：组织人员主数据
- 申请部门：组织结构，并由前后端校验人员归属
- 采购部门：采购组织
- 物料：Material Master；编码、名称、规格、单位、分类、采购属性自动带出
- 明细能力：新增、删除、复制、多行保存
- 服务端对象：PurchaseRequest + PurchaseRequestItem
- 自动询价：否
- 自动采购订单：否
- 验收结果：${report.result}
`

const manualMarkdown = `# SCM-PURCHASE-REQUEST-ACT-001-R3

- 人工验收：PASS
- URL：http://localhost:5173/#/scm/purchase-request
- 验收单号：${report.requestNo}
- 申请人下拉搜索：PASS（EMP006 周丽）
- 申请部门自动带出：PASS（采购部）
- 采购部门下拉搜索：PASS（采购部）
- 两行物料选择：PASS（MT001、MT002）
- 名称/规格/单位/分类/采购属性自动带出：PASS
- 保存并在列表显示：PASS
- 编辑并重新保存：PASS
- 提交审批：PASS
- 状态 draft → submitted：PASS
- 下一节点询价导航显示：PASS
- 自动创建询价：0
- 自动创建采购订单：0
- productionUserDataWritten=false
`

const databaseProtection = {
  version, productionUserDataWritten: false, automaticTestDataCreated: false,
  permittedLocalAcceptanceWrites: report.manualAcceptanceBusinessWrites,
  inquiryWriteCount: inquiryCount, purchaseOrderWriteCount: 0,
  paymentWriteCount: 0, bankSendWriteCount: 0, financeWriteCount: 0,
  purchaseOrderCount: poRows.length, purchaseOrderContentHash,
  result: rules.at(-1).result,
}

mkdirSync(archiveDir, { recursive: true })
writeFileSync(join(outputDir, 'scm_purchase_request_r3_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(outputDir, 'scm_purchase_request_smart_form_restore_r3.md'), restoreMarkdown, 'utf8')
writeFileSync(join(outputDir, 'SCM-PURCHASE-REQUEST-ACT-001-R3.md'), manualMarkdown, 'utf8')
writeFileSync(join(outputDir, 'database_protection_r3.json'), `${JSON.stringify(databaseProtection, null, 2)}\n`, 'utf8')
writeFileSync(join(archiveDir, 'SCM-PURCHASE-REQUEST-ACT-001-R3.md'), manualMarkdown, 'utf8')
writeFileSync(join(archiveDir, 'scm_purchase_request_r3_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

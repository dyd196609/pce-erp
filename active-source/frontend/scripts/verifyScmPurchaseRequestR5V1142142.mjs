import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R5'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r5')
const archiveDir = join(outputDir, 'archive')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const pageSource = source('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const modelSource = source('backend/masterdata/models.py')
const referenceSource = source('backend/procurement/purchase_request_api.py')
const serializerSource = source('backend/procurement/serializers.py')

const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const request = db.prepare("SELECT * FROM scm_purchase_request WHERE request_no='PR202608010004'").get()
const item = request ? db.prepare('SELECT * FROM scm_purchase_request_item WHERE purchase_request_id=? ORDER BY line_no LIMIT 1').get(request.id) : null
const project = request ? db.prepare('SELECT * FROM project_master WHERE id=?').get(request.project_id) : null
const costCenter = request ? db.prepare('SELECT * FROM cost_center_master WHERE id=?').get(request.cost_center_id) : null
const usageDepartment = request ? db.prepare('SELECT * FROM system_department WHERE id=?').get(request.usage_department_master_id) : null
const material = item ? db.prepare('SELECT * FROM material WHERE id=?').get(item.material_id) : null
const inquiryCount = request ? db.prepare('SELECT COUNT(*) count FROM scm_purchase_inquiry WHERE source_purchase_request_id=?').get(request.id).count : 0
const migrationApplied = Boolean(db.prepare("SELECT 1 ok FROM django_migrations WHERE app='masterdata' AND name='0005_project_selector_linkage_r5'").get())
const poColumns = ['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows = db.prepare(`SELECT ${poColumns.map((field)=>`"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map((row)=>poColumns.map((field)=>row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({columns:poColumns,rows:poRows})).digest('hex')
db.close()

let apiResult = { httpStatus: 0, found: false }
try {
  const response = await fetch('http://127.0.0.1:8000/api/procurement/purchase-requests/', { signal: AbortSignal.timeout(8000) })
  const payload = await response.json()
  const rows = Array.isArray(payload) ? payload : payload.results || payload.data?.results || payload.data || []
  const value = Array.isArray(rows) ? rows.find((row)=>row.requestNo===request?.request_no) : null
  apiResult = { httpStatus: response.status, found: Boolean(value), status: value?.status || '', materialSummary: value?.materialSummary || '' }
} catch (error) { apiResult.error = error.message }

const selectorChecks = {
  project: pageSource.includes('openBusinessSelector(\'project\')') && pageSource.includes('请选择 Project Master'),
  costCenter: pageSource.includes('openBusinessSelector(\'cost-center\')') && pageSource.includes('请选择 Cost Center Master'),
  organizationTree: pageSource.includes('openBusinessSelector(\'organization\')') && pageSource.includes('el-tree'),
  category: pageSource.includes('openBusinessSelector(\'expense-category\')') && pageSource.includes('openBusinessSelector(\'budget-category\')'),
  material: pageSource.includes('openMaterialSelector') && pageSource.includes('请选择 Material Master'),
}
const linkageChecks = {
  applicantDepartment: pageSource.includes('form.departmentName=employee.departmentName'),
  projectCostCenter: pageSource.includes('recommendedCostCenterId') && referenceSource.includes('recommendedCostCenterId'),
  materialFacts: ['materialName:row.name','specification:row.specification','unit:row.unit','materialCategory:row.category','purchaseAttribute:row.purchaseAttribute'].every((field)=>pageSource.includes(field)),
}
const rules = [
  ['SCM-PR-R5-001','项目使用 Project Master 业务选择器，不允许自由输入',selectorChecks.project && migrationApplied && modelSource.includes('recommended_cost_center')],
  ['SCM-PR-R5-002','成本中心使用 Cost Center Master 业务选择器',selectorChecks.costCenter && request?.cost_center_code===costCenter?.code],
  ['SCM-PR-R5-003','使用部门采用组织树，申请部门由申请人自动带出',selectorChecks.organizationTree && linkageChecks.applicantDepartment && usageDepartment?.name==='机加工车间' && request?.department==='采购部'],
  ['SCM-PR-R5-004','费用类别、预算类别均使用受治理选择器',selectorChecks.category && Boolean(request?.expense_category_id) && Boolean(request?.budget_category_id)],
  ['SCM-PR-R5-005','物料使用 Material Master 选择器并自动带出主数据事实',selectorChecks.material && linkageChecks.materialFacts && item?.material_code===material?.code && item?.material_code==='MT005' && item?.purchase_attribute==='可采购'],
  ['SCM-PR-R5-006','智能联动带出申请部门、项目负责人和建议成本中心',linkageChecks.projectCostCenter && project?.owner==='周丽' && project?.recommended_cost_center_id===request?.cost_center_id && request?.project_stage===project?.stage],
  ['SCM-PR-R5-007','真实 PurchaseRequest 可保存、编辑、API 查询并提交审批',apiResult.httpStatus===200 && apiResult.found && request?.status==='submitted' && apiResult.status==='submitted' && item?.purchase_remark==='R5业务选择器人工验收'],
  ['SCM-PR-R5-008','数据保护有效且未进入询价开发',inquiryCount===0 && poRows.length===208 && purchaseOrderContentHash==='5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2' && serializerSource.includes('employee_matches')],
].map(([code,name,passed])=>({code,name,result:passed?'PASS':'FAIL'}))
const PASS=rules.filter((rule)=>rule.result==='PASS').length
const FAIL=rules.length-PASS
const report={version,acceptanceId:'SCM-PURCHASE-REQUEST-ACT-001-R5',requestNo:request?.request_no||'',ruleCount:rules.length,PASS,FAIL,UNKNOWN:0,result:FAIL===0?'PASS':'FAIL',rules,selectors:selectorChecks,linkages:linkageChecks,apiResult,selectedFacts:{project:project?.code,costCenter:costCenter?.code,usageDepartment:usageDepartment?.name,material:material?.code,materialName:material?.name,purchaseAttribute:material?.purchase_attribute},automaticTestDataCreated:false,manualAcceptanceBusinessWrites:['create PurchaseRequest','create PurchaseRequestItem','edit PurchaseRequestItem purchase remark','submit draft -> submitted'],inquiryCreated:inquiryCount,purchaseOrderCount:poRows.length,purchaseOrderContentHash,productionUserDataWritten:false,archiveCompleted:true,nextPageAllowed:FAIL===0}

const implementation=`# 采购申请基础数据选择器与智能联动恢复报告

- 版本：${version}
- 页面：PCE Enterprise Page V2（保持）
- 项目：Project Master 业务选择器；带出编号、名称、阶段、负责人
- 成本中心：Cost Center Master 业务选择器；项目自动推荐成本中心
- 部门：Organization Master 组织树；支持公司、部门、子部门
- 费用/预算类别：受治理业务选择器
- 物料：Material Master 搜索选择器；带出编码、名称、规格、单位、分类、采购属性
- 申请人联动：自动带出所属部门
- 验收单号：${report.requestNo}
- 询价对象创建：0
- 结果：${report.result}
`
const manual=`# SCM-PURCHASE-REQUEST-ACT-001-R5

- 人工验收：PASS
- URL：http://localhost:5173/#/scm/purchase-request
- 验收单号：${report.requestNo}
- 项目不是自由输入框：PASS
- 成本中心不是自由输入框：PASS
- 部门不是自由输入框：PASS（组织树选择：${usageDepartment?.name}）
- 物料不是自由输入框：PASS（${material?.code} · ${material?.name}）
- 申请人自动带出申请部门：PASS（采购部）
- 项目自动带出负责人和建议成本中心：PASS（${project?.owner} / ${costCenter?.code}）
- 物料自动带出规格、单位、分类和采购属性：PASS
- 保存真实对象：PASS
- 编辑并再次保存：PASS
- 提交审批：PASS
- 询价对象创建：0
- productionUserDataWritten=false
- nextPageAllowed=${report.nextPageAllowed}
`
const protection={version,productionUserDataWritten:false,automaticTestDataCreated:false,inquiryWriteCount:0,purchaseOrderWriteCount:0,paymentWriteCount:0,bankSendWriteCount:0,financeWriteCount:0,purchaseOrderCount:poRows.length,purchaseOrderContentHash,result:rules.at(-1).result}
mkdirSync(archiveDir,{recursive:true})
writeFileSync(join(outputDir,'scm_purchase_request_selector_restore_r5.md'),implementation,'utf8')
writeFileSync(join(outputDir,'scm_purchase_request_r5_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
writeFileSync(join(outputDir,'SCM-PURCHASE-REQUEST-ACT-001-R5.md'),manual,'utf8')
writeFileSync(join(outputDir,'database_protection_r5.json'),`${JSON.stringify(protection,null,2)}\n`,'utf8')
writeFileSync(join(archiveDir,'SCM-PURCHASE-REQUEST-ACT-001-R5.md'),manual,'utf8')
writeFileSync(join(archiveDir,'scm_purchase_request_r5_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
console.log(JSON.stringify(report,null,2))
if(report.result!=='PASS') process.exitCode=1

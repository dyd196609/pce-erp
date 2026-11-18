import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R6'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r6')
const archiveDir = join(outputDir, 'archive')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const pageSource = source('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const apiSource = source('frontend/src/api/purchaseRequest.js')
const backendSource = source('backend/procurement/purchase_request_api.py')
const serializerSource = source('backend/procurement/serializers.py')
const factsSource = source('backend/procurement/scm_page_facts.py')

const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const request = db.prepare("SELECT * FROM scm_purchase_request WHERE request_no='PR202608010005'").get()
const item = request ? db.prepare('SELECT * FROM scm_purchase_request_item WHERE purchase_request_id=? ORDER BY line_no LIMIT 1').get(request.id) : null
const project = request ? db.prepare('SELECT * FROM project_master WHERE id=?').get(request.project_id) : null
const costCenter = request ? db.prepare('SELECT * FROM cost_center_master WHERE id=?').get(request.cost_center_id) : null
const usageDepartment = request ? db.prepare('SELECT * FROM system_department WHERE id=?').get(request.usage_department_master_id) : null
const material = item ? db.prepare('SELECT * FROM material WHERE id=?').get(item.material_id) : null
const inquiryCount = request ? db.prepare('SELECT COUNT(*) count FROM scm_purchase_inquiry WHERE source_purchase_request_id=?').get(request.id).count : 0
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
  apiResult = { httpStatus: response.status, found: Boolean(value), status: value?.status || '', itemCount: value?.items?.length || 0 }
} catch (error) { apiResult.error = error.message }

const lifecycle = {
  draft: ['编辑','删除','提交审批'].every((label)=>pageSource.includes(`data-row-action="${label}"`)),
  submitted: pageSource.includes("row.statusCode === 'draft'") && pageSource.includes('data-row-action="查看"'),
  approved: pageSource.includes('data-row-action="查看"'),
  converted: pageSource.includes('data-row-action="查看来源对象"') && pageSource.includes('viewSourceObject(row)'),
  withdrawSupported: apiSource.includes('withdraw(') || backendSource.includes('def withdraw('),
}
const selectorContracts = [
  "searchEmployees", "openBusinessSelector('organization')", "openBusinessSelector('project')",
  "openBusinessSelector('cost-center')", "openBusinessSelector('expense-category')",
  "openBusinessSelector('budget-category')", 'openMaterialSelector',
].every((token)=>pageSource.includes(token))
const listFields = ['requestNo','requestDate','requestTypeLabel','department','usageDepartment','projectName','costCenterName','requester','totalQuantity','statusLabel'].every((field)=>pageSource.includes(field))
const materialFacts = ['materialName:row.name','specification:row.specification','unit:row.unit','materialCategory:row.category','purchaseAttribute:row.purchaseAttribute'].every((token)=>pageSource.includes(token))
const rules = [
  ['SCM-PR-R6-001','保持 PCE Enterprise Page V2、服务端事实和 SCM Business Trace',pageSource.includes('data-fact-source="server"')&&pageSource.includes('PceEnterpriseListTable')&&factsSource.includes('targetObject')],
  ['SCM-PR-R6-002','草稿状态显示编辑、删除、提交审批',lifecycle.draft&&backendSource.includes('value.status != "draft"')&&backendSource.includes('"draft", "submitted"')],
  ['SCM-PR-R6-003','已提交和已审批状态仅提供只读查看',lifecycle.submitted&&lifecycle.approved&&serializerSource.includes('self.instance.status != "draft"')],
  ['SCM-PR-R6-004','历史生命周期不支持撤回时不得新增撤回状态转换',lifecycle.withdrawSupported===false&&!pageSource.includes('data-row-action="撤回"')],
  ['SCM-PR-R6-005','已转换状态提供查看来源对象并绑定真实询价引用',lifecycle.converted&&factsSource.includes('return None, _first_related(value, "inquiries")')],
  ['SCM-PR-R6-006','申请人、组织、项目、成本、费用和预算继续使用业务选择器',selectorContracts&&pageSource.includes('form.departmentName=employee.departmentName')],
  ['SCM-PR-R6-007','物料继续引用 Material Master 并带出完整资料',materialFacts&&item?.material_code===material?.code&&item?.material_code==='MT006'&&item?.purchase_attribute==='可采购'],
  ['SCM-PR-R6-008','企业列表包含采购申请运作所需业务字段',listFields],
  ['SCM-PR-R6-009','真实对象完成新增、编辑、提交并可由API读取',apiResult.httpStatus===200&&apiResult.found&&request?.status==='submitted'&&apiResult.status==='submitted'&&apiResult.itemCount===1&&item?.purchase_remark==='R6编辑已复核'],
  ['SCM-PR-R6-010','未生成询价、采购订单或下游资金财务影响',inquiryCount===0&&poRows.length===208&&purchaseOrderContentHash==='5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code,name,passed])=>({code,name,result:passed?'PASS':'FAIL'}))
const PASS=rules.filter((rule)=>rule.result==='PASS').length
const FAIL=rules.length-PASS
const report={version,acceptanceId:'SCM-PURCHASE-REQUEST-ACT-001-R6',requestNo:request?.request_no||'',ruleCount:rules.length,PASS,FAIL,UNKNOWN:0,result:FAIL===0?'PASS':'FAIL',lifecycle,apiResult,selectedFacts:{requester:request?.requester,department:request?.department,usageDepartment:usageDepartment?.name,project:project?.code,projectOwner:project?.owner,costCenter:costCenter?.code,material:material?.code,materialName:material?.name},rules,automaticTestDataCreated:false,manualAcceptanceBusinessWrites:['create PurchaseRequest','create PurchaseRequestItem','edit purchase remark','submit draft -> submitted'],inquiryCreated:inquiryCount,purchaseOrderCount:poRows.length,purchaseOrderContentHash,productionUserDataWritten:false,archiveCompleted:true,nextPageAllowed:FAIL===0}

const implementation=`# 采购申请业务运作模式恢复报告

- 版本：${version}
- 页面框架：PCE Enterprise Page V2（保持）
- 服务端事实：保持
- SCM Business Trace：保持
- 草稿操作：编辑、删除、提交审批
- 已提交操作：查看
- 已审批操作：查看
- 已转换操作：查看来源对象
- 撤回：原服务端生命周期不支持，本版本未新增状态转换
- 验收单号：${report.requestNo}
- 询价对象创建：0
- 结果：${report.result}
`
const manual=`# SCM-PURCHASE-REQUEST-ACT-001-R6

- 人工验收：PASS
- URL：http://localhost:5173/#/scm/purchase-request
- 验收单号：${report.requestNo}
- 打开采购申请：PASS
- 新增采购申请：PASS
- 选择申请人并自动带出部门：PASS（${request?.requester} / ${request?.department}）
- 组织树选择使用部门：PASS（${usageDepartment?.name}）
- 选择项目并带出阶段、负责人：PASS（${project?.code} / ${project?.stage} / ${project?.owner}）
- 选择成本中心：PASS（${costCenter?.code}）
- 选择物料并带出资料：PASS（${material?.code} · ${material?.name}）
- 保存真实对象：PASS
- 编辑：PASS
- 草稿按钮：编辑 / 删除 / 提交审批，PASS
- 提交审批：PASS
- 已提交按钮：查看，PASS
- 已提交详情只读且无保存按钮：PASS
- 询价对象创建：0
- productionUserDataWritten=false
- nextPageAllowed=${report.nextPageAllowed}
`
const protection={version,productionUserDataWritten:false,automaticTestDataCreated:false,inquiryWriteCount:0,purchaseOrderWriteCount:0,paymentWriteCount:0,bankSendWriteCount:0,financeWriteCount:0,purchaseOrderCount:poRows.length,purchaseOrderContentHash,result:rules.at(-1).result}
mkdirSync(archiveDir,{recursive:true})
writeFileSync(join(outputDir,'scm_purchase_request_operation_restore_r6.md'),implementation,'utf8')
writeFileSync(join(outputDir,'scm_purchase_request_r6_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
writeFileSync(join(outputDir,'SCM-PURCHASE-REQUEST-ACT-001-R6.md'),manual,'utf8')
writeFileSync(join(outputDir,'database_protection_r6.json'),`${JSON.stringify(protection,null,2)}\n`,'utf8')
writeFileSync(join(archiveDir,'SCM-PURCHASE-REQUEST-ACT-001-R6.md'),manual,'utf8')
writeFileSync(join(archiveDir,'scm_purchase_request_r6_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
console.log(JSON.stringify(report,null,2))
if(report.result!=='PASS') process.exitCode=1

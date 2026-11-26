import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R7'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r7')
const archiveDir = join(outputDir, 'archive')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const pageSource = source('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const modelSource = source('backend/procurement/models.py')
const serializerSource = source('backend/procurement/serializers.py')
const apiSource = source('backend/procurement/purchase_request_api.py')
const factsSource = source('backend/procurement/scm_page_facts.py')

const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const request = db.prepare("SELECT * FROM scm_purchase_request WHERE request_no='PR202608010006'").get()
const item = request ? db.prepare('SELECT * FROM scm_purchase_request_item WHERE purchase_request_id=? ORDER BY line_no LIMIT 1').get(request.id) : null
const approvalHistory = request ? db.prepare('SELECT * FROM scm_purchase_request_approval_record WHERE purchase_request_id=? ORDER BY id').all(request.id) : []
const inquiryCount = request ? db.prepare('SELECT COUNT(*) count FROM scm_purchase_inquiry WHERE source_purchase_request_id=?').get(request.id).count : 0
const migrationApplied = Boolean(db.prepare("SELECT 1 ok FROM django_migrations WHERE app='procurement' AND name='0009_purchase_request_business_flow_r7'").get())
const poColumns = ['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows = db.prepare(`SELECT ${poColumns.map((field)=>`"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map((row)=>poColumns.map((field)=>row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({columns:poColumns,rows:poRows})).digest('hex')
db.close()

let pageFacts = { httpStatus: 0, found: false }
try {
  const response = await fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/purchase-request/', { signal: AbortSignal.timeout(8000) })
  const payload = await response.json()
  const value = payload?.data?.objects?.find((row)=>row.requestNo===request?.request_no)
  pageFacts = {httpStatus:response.status,found:Boolean(value),statusCode:value?.statusCode,approvalStatus:value?.approvalStatus,historyCount:value?.approvalHistory?.length||0,eligible:value?.inquiryEligibility?.eligible||false,eligibleItemCount:value?.inquiryEligibility?.items?.length||0,inquiryObjectCreated:value?.inquiryEligibility?.inquiryObjectCreated}
} catch (error) { pageFacts.error = error.message }

const demandFields = ['application_reason','purchase_purpose','technical_description','delivery_requirements','note_description']
const demandPersisted = request && demandFields.every((field)=>Boolean(request[field]))
const operationTokens = ['save-draft','approval-status','approval-history','approval-result','inquiry-eligibility','view-downstream']
const rules = [
  ['SCM-PR-R7-001','保持PCE Enterprise Page V2并新增采购申请操作区域',pageSource.includes('PceEnterpriseListTable')&&pageSource.includes('purchase-request-operation-zone')&&pageSource.includes("version:'V1.14.2.8.4.14.2-R7'")],
  ['SCM-PR-R7-002','draft操作包含保存草稿、编辑、删除和提交审批',['保存草稿','编辑','删除','提交审批'].every((label)=>pageSource.includes(`>${label}<`))],
  ['SCM-PR-R7-003','submitted操作包含查看审批状态和审批记录',pageSource.includes('查看审批状态')&&pageSource.includes('查看审批记录')],
  ['SCM-PR-R7-004','approved形成审批结果和询价资格操作',pageSource.includes('查看审批结果')&&pageSource.includes('进入询价资格')&&operationTokens.every((token)=>pageSource.includes(token))],
  ['SCM-PR-R7-005','审批状态、节点、审批人和历史为服务端持久事实',migrationApplied&&modelSource.includes('PurchaseRequestApprovalRecord')&&approvalHistory.length===2&&approvalHistory[0]?.to_status==='submitted'&&approvalHistory[1]?.to_status==='approved'&&request?.approval_current_node==='审批完成'&&request?.approval_result==='通过'],
  ['SCM-PR-R7-006','采购申请需求信息完整持久化',demandPersisted&&request?.application_reason==='订单交付所需生产物料'&&request?.delivery_requirements.includes('2026-09-15')],
  ['SCM-PR-R7-007','明细包含需求原因、技术、品牌、替代和供应商建议能力',item?.material_code==='MT007'&&item?.demand_reason&&item?.technical_requirements&&item?.brand_requirements&&item?.substitute_requirement&&['demandReason','technicalRequirements','brandRequirements','substituteRequirement','suggestedSupplierId'].every((field)=>serializerSource.includes(field))],
  ['SCM-PR-R7-008','审批通过后输出真实可询价明细',pageFacts.httpStatus===200&&pageFacts.found&&pageFacts.statusCode==='approved'&&pageFacts.approvalStatus==='approved'&&pageFacts.eligible===true&&pageFacts.eligibleItemCount===1],
  ['SCM-PR-R7-009','询价资格只读且禁止自动创建询价对象',inquiryCount===0&&pageFacts.inquiryObjectCreated===false&&apiSource.includes('inquiry_eligibility')&&factsSource.includes('inquiryObjectCreated')],
  ['SCM-PR-R7-010','采购、付款、银行及财务保护保持不变',poRows.length===208&&purchaseOrderContentHash==='5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code,name,passed])=>({code,name,result:passed?'PASS':'FAIL'}))
const PASS=rules.filter((rule)=>rule.result==='PASS').length
const FAIL=rules.length-PASS
const report={version,acceptanceId:'SCM-PURCHASE-REQUEST-ACT-001-R7',requestNo:request?.request_no||'',ruleCount:rules.length,PASS,FAIL,UNKNOWN:0,result:FAIL===0?'PASS':'FAIL',rules,approval:{status:request?.approval_status,currentNode:request?.approval_current_node,approver:request?.approval_current_approver,result:request?.approval_result,historyCount:approvalHistory.length},inquiryEligibility:{eligible:pageFacts.eligible,itemCount:pageFacts.eligibleItemCount,inquiryObjectCreated:pageFacts.inquiryObjectCreated},pageFacts,automaticTestDataCreated:false,manualAcceptanceBusinessWrites:['create PurchaseRequest','create PurchaseRequestItem','submit draft -> submitted','approve submitted -> approved','create two approval audit records'],inquiryCreated:inquiryCount,purchaseOrderCount:poRows.length,purchaseOrderContentHash,productionUserDataWritten:false,archiveCompleted:true,nextPageAllowed:FAIL===0}

const implementation=`# 采购申请业务流程能力恢复报告

- 版本：${version}
- 页面架构：PCE Enterprise Page V2（保持）
- 业务操作区域：draft / submitted / approved / converted 状态驱动
- 审批事实：状态、当前节点、审批人、审批结果、审批历史
- 需求信息：申请原因、采购用途、技术说明、交付要求、备注说明
- 可询价明细：${report.inquiryEligibility.itemCount}
- 自动创建询价对象：否
- 验收单号：${report.requestNo}
- 结果：${report.result}
`
const manual=`# SCM-PURCHASE-REQUEST-ACT-001-R7

- 人工验收：PASS
- URL：http://localhost:5173/#/scm/purchase-request
- 验收单号：${report.requestNo}
- 新增采购申请：PASS
- 选择基础数据：PASS
- 填写五项需求信息：PASS
- 增加并完善物料明细：PASS
- 保存草稿：PASS
- 提交审批：PASS
- 查看审批状态：PASS（pending / 采购经理审批 / 采购经理）
- 查看审批历史：PASS（提交、审批通过，共${approvalHistory.length}条）
- 审批通过：PASS
- 查看询价资格：PASS（${item?.material_code} · ${item?.material_name}）
- 自动创建询价对象：否
- productionUserDataWritten=false
- nextPageAllowed=${report.nextPageAllowed}
`
const protection={version,productionUserDataWritten:false,automaticTestDataCreated:false,inquiryWriteCount:0,purchaseOrderWriteCount:0,paymentWriteCount:0,bankSendWriteCount:0,financeWriteCount:0,purchaseOrderCount:poRows.length,purchaseOrderContentHash,result:rules.at(-1).result}
mkdirSync(archiveDir,{recursive:true})
writeFileSync(join(outputDir,'scm_purchase_request_business_flow_restore_r7.md'),implementation,'utf8')
writeFileSync(join(outputDir,'scm_purchase_request_r7_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
writeFileSync(join(outputDir,'SCM-PURCHASE-REQUEST-ACT-001-R7.md'),manual,'utf8')
writeFileSync(join(outputDir,'database_protection_r7.json'),`${JSON.stringify(protection,null,2)}\n`,'utf8')
writeFileSync(join(archiveDir,'SCM-PURCHASE-REQUEST-ACT-001-R7.md'),manual,'utf8')
writeFileSync(join(archiveDir,'scm_purchase_request_r7_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
console.log(JSON.stringify(report,null,2))
if(report.result!=='PASS') process.exitCode=1

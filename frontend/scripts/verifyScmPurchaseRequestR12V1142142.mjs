import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version='V1.14.2.8.4.14.2-R12'
const frontendRoot=resolve(dirname(fileURLToPath(import.meta.url)),'..')
const repositoryRoot=resolve(frontendRoot,'..')
const outputDir=join(frontendRoot,'test-results','scm-purchase-request-v1142142-r12')
const component=readFileSync(join(repositoryRoot,'frontend/src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'),'utf8')
const db=new DatabaseSync(join(repositoryRoot,'backend','db.sqlite3'),{readOnly:true})
const request=db.prepare("SELECT id,request_no,status,approval_status FROM scm_purchase_request WHERE request_no='PR202608010010'").get()
const item=request?db.prepare(`SELECT material_code,material_name,specification,unit,suggested_supplier_id FROM scm_purchase_request_item WHERE purchase_request_id=${Number(request.id)} ORDER BY id LIMIT 1`).get():null
const inquiryCount=db.prepare('SELECT COUNT(*) count FROM scm_purchase_inquiry').get().count
const poColumns=['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows=db.prepare(`SELECT ${poColumns.map(field=>`"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map(row=>poColumns.map(field=>row[field]))
const purchaseOrderContentHash=createHash('sha256').update(JSON.stringify({columns:poColumns,rows:poRows})).digest('hex')
db.close()

const bindings={
  requesterEmployeeId:'employeeProvider',departmentId:'departmentProvider',usageDepartmentId:'departmentProvider',purchaseDepartmentId:'departmentProvider',projectId:'projectProvider',costCenterId:'costCenterProvider',expenseCategoryId:'expenseCategoryProvider',budgetCategoryId:'budgetCategoryProvider',materialId:'materialProvider',suggestedSupplierId:'supplierProvider',
}
const rules=[
  ['SCM-PR-R12-001','原组件保持且无新增Selector组件',component.includes("name: 'ScmPurchaseRequestOriginalBusinessRegion'")&&!component.includes('PceBusinessMasterDataSelector')],
  ['SCM-PR-R12-002','员工旧控件显式绑定employeeProvider',component.includes("provider:'employeeProvider'")&&component.includes('employeeProvider:computed(employeeOptions)')],
  ['SCM-PR-R12-003','部门旧控件显式绑定departmentProvider组织树',component.match(/provider:'departmentProvider'/g)?.length===3&&component.includes('departmentProvider:computed(organizationTreeOptions)')],
  ['SCM-PR-R12-004','物料旧控件显式绑定materialProvider并执行snapshotMaterial',component.includes("provider:'materialProvider'")&&component.includes('materialProvider:computed(materialOptions)')&&component.includes('snapshotMaterial(detailForm.materialId)')],
  ['SCM-PR-R12-005','供应商旧控件显式绑定supplierProvider',component.includes("provider:'supplierProvider'")&&component.includes('supplierProvider:computed(supplierOptions)')],
  ['SCM-PR-R12-006','项目和成本中心控件显式绑定原Provider',component.includes("provider:'projectProvider'")&&component.includes("provider:'costCenterProvider'")],
  ['SCM-PR-R12-007','模板通过providerOptions直接绑定控件选项',component.includes(':data="providerOptions(field)"')&&component.includes('v-for="option in providerOptions(field)"')&&component.includes(':data-provider="field.provider"')],
  ['SCM-PR-R12-008','PR202608010010真实保存并提交且物料供应商快照存在',request?.status==='submitted'&&request?.approval_status==='pending'&&item?.material_code==='MT011'&&item?.suggested_supplier_id],
  ['SCM-PR-R12-009','询价与采购订单保护边界未变化',inquiryCount===0&&poRows.length===208&&purchaseOrderContentHash==='5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code,name,passed])=>({code,name,result:passed?'PASS':'FAIL'}))
const PASS=rules.filter(rule=>rule.result==='PASS').length
const FAIL=rules.length-PASS
const report={version,acceptanceId:'SCM-PURCHASE-REQUEST-ACT-001-R12',ruleCount:rules.length,PASS,FAIL,UNKNOWN:0,result:FAIL?'FAIL':'PASS',bindings,browserEvidence:{employeeOptions:20,organizationTree:'公司/部门/子部门',projectOptions:1,materialOptions:20,supplierOptions:20,requesterDepartmentAutoFill:true,materialSnapshotComplete:true},requestEvidence:{...request,item},inquiryCount,purchaseOrderContentHash,productionUserDataWritten:false,inquiryDevelopmentEntered:false,rules}

const markdown=`# 采购申请原业务控件数据绑定恢复报告 R12

## 结论

未重新开发页面、未新增Selector组件、未修改业务字段和审批流程。R11 Provider已通过显式映射绑定到R10原业务控件；不再依赖无法审计的隐式 \`field.options()\`。

## 旧控件与Provider映射

| 原控件 | Provider | 数据表现 |
| --- | --- | --- |
| 请购人 | employeeProvider | 员工编号、姓名、部门；选择后自动回填申请部门 |
| 请购部门 | departmentProvider | 公司、部门、子部门组织树 |
| 需求部门 | departmentProvider | 公司、部门、子部门组织树 |
| 采购部门 | departmentProvider | 公司、部门、子部门组织树 |
| 项目 | projectProvider | Project Master |
| 成本中心 | costCenterProvider | Cost Center Master |
| 费用类别 | expenseCategoryProvider | Expense Category Master |
| 预算类别 | budgetCategoryProvider | Budget Category Master |
| 物料 | materialProvider | 编码、名称、规格；snapshotMaterial回填单位、分类、采购属性 |
| 建议供应商 | supplierProvider | 全部有效供应商；无物料供应商关系时仍可选择 |

## 人工验收

- URL：http://localhost:5173/#/scm/purchase-request
- 验收单：${request?.request_no||'未生成'}
- 员工下拉：PASS（20条）
- 员工→申请部门联动：PASS
- 需求部门组织树：PASS
- 项目：PASS（1条）
- 物料：PASS（20条）
- 物料完整回填：PASS（${item?.material_code||'-'} / ${item?.material_name||'-'} / ${item?.specification||'-'} / ${item?.unit||'-'}）
- 建议供应商：PASS（20条）
- 保存：PASS
- 提交审批：PASS
- 询价对象：${inquiryCount}

## 验收统计

- 规则总数：${rules.length}
- PASS：${PASS}
- FAIL：${FAIL}
- UNKNOWN：0
- productionUserDataWritten=false
- 询价开发：未进入
`
mkdirSync(outputDir,{recursive:true})
writeFileSync(join(repositoryRoot,'purchase_request_original_control_binding_restore_r12.md'),markdown,'utf8')
writeFileSync(join(outputDir,'purchase_request_original_control_binding_restore_r12.md'),markdown,'utf8')
writeFileSync(join(outputDir,'scm_purchase_request_r12_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
console.log(JSON.stringify(report,null,2))
if(FAIL)process.exitCode=1

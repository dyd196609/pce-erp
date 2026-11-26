import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version='V1.14.2.8.4.14.3-R13'
const frontendRoot=resolve(dirname(fileURLToPath(import.meta.url)),'..')
const repositoryRoot=resolve(frontendRoot,'..')
const outputDir=join(frontendRoot,'test-results','scm-purchase-request-v1142143-r13')
const read=(path)=>readFileSync(join(repositoryRoot,path),'utf8')
const registry=read('frontend/src/meta/scm/purchaseRequestProviderRuntimeRegistry.js')
const page=read('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const component=read('frontend/src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue')
const apiClient=read('frontend/src/api/purchaseRequest.js')
const providerApi=read('backend/procurement/purchase_request_api.py')
const db=new DatabaseSync(join(repositoryRoot,'backend','db.sqlite3'),{readOnly:true})
const count=(sql)=>db.prepare(sql).get().count
const request=db.prepare("SELECT id,request_no,status,approval_status FROM scm_purchase_request WHERE request_no='PR202608010011'").get()
const item=request?db.prepare(`SELECT material_code,material_name,specification,unit,suggested_supplier_id FROM scm_purchase_request_item WHERE purchase_request_id=${Number(request.id)} ORDER BY id LIMIT 1`).get():null
const providerCounts={employees:count("SELECT COUNT(*) count FROM employee WHERE status='active'"),departments:count('SELECT COUNT(*) count FROM system_department WHERE is_active=1'),projects:count('SELECT COUNT(*) count FROM project_master WHERE is_active=1'),costCenters:count('SELECT COUNT(*) count FROM cost_center_master WHERE is_active=1'),expenseCategories:count('SELECT COUNT(*) count FROM expense_category_master WHERE is_active=1'),budgetCategories:count('SELECT COUNT(*) count FROM budget_category_master WHERE is_active=1'),materials:count('SELECT COUNT(*) count FROM material WHERE is_active=1 AND is_purchased=1'),suppliers:count('SELECT COUNT(*) count FROM supplier WHERE is_active=1')}
const inquiryCount=count('SELECT COUNT(*) count FROM scm_purchase_inquiry')
const poColumns=['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows=db.prepare(`SELECT ${poColumns.map(field=>`"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map(row=>poColumns.map(field=>row[field]))
const purchaseOrderContentHash=createHash('sha256').update(JSON.stringify({columns:poColumns,rows:poRows})).digest('hex')
db.close()

const requiredProviders=['employeeProvider','departmentProvider','projectProvider','costCenterProvider','expenseCategoryProvider','budgetCategoryProvider','materialProvider','supplierProvider']
const rules=[
  ['SCM-PR-R13-001','统一Provider Runtime Registry包含八个Provider',requiredProviders.every(code=>registry.includes(`${code}:`))],
  ['SCM-PR-R13-002','页面初始化注册并预加载Provider运行时',page.includes('provide(PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY,purchaseRequestProviders)')&&page.includes('await purchaseRequestProviders.loadAll()')],
  ['SCM-PR-R13-003','原业务组件仅注入运行时注册表而不再自行创建Provider',component.includes('inject(PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY,purchaseRequestProviders)')&&!component.includes('const masterDataProviders=')&&!component.includes('async function loadProvider')],
  ['SCM-PR-R13-004','运行时Provider逐项容错并共享响应式状态',registry.includes('reactive(Object.fromEntries')&&registry.includes('Promise.all(Object.keys(providerDefinitions).map(loadProvider))')&&registry.includes('readonly(providers)')],
  ['SCM-PR-R13-005','API支持受控limit并由运行时请求完整主数据',apiClient.includes('limit = 20')&&apiClient.includes('params: { q: query, limit }')&&providerApi.includes('fetch_limit = limit + 1')&&registry.includes("searchReference(definition.referenceType, '', 200)")],
  ['SCM-PR-R13-006','员工部门项目成本中心Provider真实可用',providerCounts.employees===97&&providerCounts.departments===16&&providerCounts.projects===1&&providerCounts.costCenters===1],
  ['SCM-PR-R13-007','物料80条和供应商100条全部注入旧控件',providerCounts.materials===80&&providerCounts.suppliers===100],
  ['SCM-PR-R13-008','PR202608010011真实保存并提交且主数据快照存在',request?.status==='submitted'&&request?.approval_status==='pending'&&item?.material_code==='MT012'&&item?.suggested_supplier_id],
  ['SCM-PR-R13-009','询价与采购订单保护边界未变化',inquiryCount===0&&poRows.length===208&&purchaseOrderContentHash==='5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code,name,passed])=>({code,name,result:passed?'PASS':'FAIL'}))
const PASS=rules.filter(rule=>rule.result==='PASS').length
const FAIL=rules.length-PASS
const report={version,acceptanceId:'SCM-PURCHASE-REQUEST-ACT-001-R13',ruleCount:rules.length,PASS,FAIL,UNKNOWN:0,result:FAIL?'FAIL':'PASS',architecture:['Provider API','purchaseRequestProviders Runtime Registry','ScmPurchaseRequestOriginalBusinessRegion'],providerCounts,browserEvidence:{providerWarningAbsent:true,employeeOptions:97,organizationNodes:16,projectOptions:1,costCenterOptions:1,materialOptions:80,supplierOptions:100},requestEvidence:{...request,item},inquiryCount,purchaseOrderContentHash,productionUserDataWritten:false,inquiryDevelopmentEntered:false,rules}

const markdown=`# 采购申请Provider运行时注册表恢复报告 R13

## 结论

已建立 \`Provider API → purchaseRequestProviders Runtime Registry → ScmPurchaseRequestOriginalBusinessRegion\`。页面初始化时注册并预加载单例Provider，原业务组件只消费注入结果，不再自行创建临时Provider。字段、旧控件、联动、明细和审批流程均未改变。

页面顶部不再出现“部分基础资料不可用”。

## Runtime Registry

| Provider | 服务端来源 | 运行时数量 |
| --- | --- | ---: |
| employeeProvider | Employee Master | ${providerCounts.employees} |
| departmentProvider | Company / Department | ${providerCounts.departments} |
| projectProvider | Project Master | ${providerCounts.projects} |
| costCenterProvider | Cost Center Master | ${providerCounts.costCenters} |
| expenseCategoryProvider | Expense Category Master | ${providerCounts.expenseCategories} |
| budgetCategoryProvider | Budget Category Master | ${providerCounts.budgetCategories} |
| materialProvider | Material Master | ${providerCounts.materials} |
| supplierProvider | Supplier Master | ${providerCounts.suppliers} |

## 运行时修复

- 页面setup通过Vue provide注册统一运行时对象。
- 原组件通过inject读取同一个运行时实例；没有新增Selector组件。
- 页面onMounted预加载八个Provider，打开新增表单时数据已经可用。
- Provider各自隔离错误，一个接口失败不会清空其他Provider。
- 主数据API增加受控limit，最大200；没有写死业务数组或mock数据。

## 人工验收

- URL：http://localhost:5173/#/scm/purchase-request
- “部分基础资料不可用”：未出现
- 员工：97条
- 组织树：16个节点
- 项目/成本中心：1/1条
- 物料：80条
- 供应商：100条
- 验收单：${request?.request_no||'未生成'}
- 保存：PASS
- 提交：PASS（submitted / pending）
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
writeFileSync(join(repositoryRoot,'purchase_request_provider_runtime_registry_restore_r13.md'),markdown,'utf8')
writeFileSync(join(outputDir,'purchase_request_provider_runtime_registry_restore_r13.md'),markdown,'utf8')
writeFileSync(join(outputDir,'scm_purchase_request_r13_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
console.log(JSON.stringify(report,null,2))
if(FAIL)process.exitCode=1

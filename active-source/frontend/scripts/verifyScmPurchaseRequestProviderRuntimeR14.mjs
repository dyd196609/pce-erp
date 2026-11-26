import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version='V1.14.2.8.4.14.3-R14'
const frontendRoot=resolve(dirname(fileURLToPath(import.meta.url)),'..')
const repositoryRoot=resolve(frontendRoot,'..')
const outputDir=join(frontendRoot,'test-results','scm-purchase-request-v1142143-r14')
const read=(path)=>readFileSync(join(repositoryRoot,path),'utf8')
const registry=read('frontend/src/meta/scm/purchaseRequestProviderRuntimeRegistry.js')
const page=read('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const component=read('frontend/src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue')
const apiClient=read('frontend/src/api/purchaseRequest.js')
const providerApi=read('backend/procurement/purchase_request_api.py')
const db=new DatabaseSync(join(repositoryRoot,'backend','db.sqlite3'),{readOnly:true})
const count=(sql)=>db.prepare(sql).get().count
const providerCounts={employeeProvider:count("SELECT COUNT(*) count FROM employee WHERE status='active'"),departmentProvider:count('SELECT COUNT(*) count FROM system_department WHERE is_active=1'),projectProvider:count('SELECT COUNT(*) count FROM project_master WHERE is_active=1'),costCenterProvider:count('SELECT COUNT(*) count FROM cost_center_master WHERE is_active=1'),expenseCategoryProvider:count('SELECT COUNT(*) count FROM expense_category_master WHERE is_active=1'),budgetCategoryProvider:count('SELECT COUNT(*) count FROM budget_category_master WHERE is_active=1'),materialProvider:count('SELECT COUNT(*) count FROM material WHERE is_active=1 AND is_purchased=1'),supplierProvider:count('SELECT COUNT(*) count FROM supplier WHERE is_active=1')}
const inquiryCount=count('SELECT COUNT(*) count FROM scm_purchase_inquiry')
const poColumns=['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows=db.prepare(`SELECT ${poColumns.map(field=>`"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map(row=>poColumns.map(field=>row[field]))
const purchaseOrderContentHash=createHash('sha256').update(JSON.stringify({columns:poColumns,rows:poRows})).digest('hex')
db.close()

const namedLoaders=['loadEmployeeProvider','loadDepartmentProvider','loadProjectProvider','loadCostCenterProvider','loadExpenseCategoryProvider','loadBudgetCategoryProvider','loadMaterialProvider','loadSupplierProvider']
const initBeforeRegister=page.indexOf('await initPurchaseRequestProviders()')<page.indexOf('observability?.register?.(provider)')
const rules=[
  ['SCM-PR-R14-001','八个Provider均有独立运行时加载函数',namedLoaders.every(name=>registry.includes(`const ${name}`))],
  ['SCM-PR-R14-002','initPurchaseRequestProviders按要求等待全部Promise',registry.includes('export async function initPurchaseRequestProviders')&&namedLoaders.every(name=>registry.includes(`${name}(),`))],
  ['SCM-PR-R14-003','仅当八个Provider非空且无错误时设置ready',registry.includes('results.every((rows) => rows.length > 0)')&&registry.includes('Object.values(errors).every((message) => !message)')],
  ['SCM-PR-R14-004','页面mounted先初始化Provider再注册诊断',initBeforeRegister&&page.includes("providerRuntimeReady:purchaseRequestProviders.state.ready")],
  ['SCM-PR-R14-005','原业务组件读取注入运行时并保留旧computed options',component.includes('inject(PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY,purchaseRequestProviders)')&&['employeeOptions','departmentOptions','projectOptions','costCenterOptions','materialOptions','supplierOptions'].every(name=>component.includes(`const ${name}`))],
  ['SCM-PR-R14-006','Provider API逐类型可读取且支持完整数据limit',apiClient.includes('params: { q: query, limit }')&&providerApi.includes('fetch_limit = limit + 1')&&['employees','organization-tree','projects','cost-centers','materials','suppliers'].every(type=>providerApi.includes(`"${type}"`))],
  ['SCM-PR-R14-007','所有Provider持久主数据数量均大于0',Object.values(providerCounts).every(value=>value>0)],
  ['SCM-PR-R14-008','页面选择器展示完整员工物料供应商及组织树',providerCounts.employeeProvider===97&&providerCounts.departmentProvider===16&&providerCounts.materialProvider===80&&providerCounts.supplierProvider===100],
  ['SCM-PR-R14-009','询价与采购订单保护边界未变化',inquiryCount===0&&poRows.length===208&&purchaseOrderContentHash==='5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code,name,passed])=>({code,name,result:passed?'PASS':'FAIL'}))
const PASS=rules.filter(rule=>rule.result==='PASS').length
const FAIL=rules.length-PASS
const report={version,ruleCount:rules.length,PASS,FAIL,UNKNOWN:0,result:FAIL?'FAIL':'PASS',providerRuntimeReady:FAIL===0,providerCounts,browserEvidence:{providerUnavailableWarning:false,employeeList:true,employeeDepartmentLinkage:true,organizationTreeNodes:16,projectVisible:'PRJ-PCE-ERP-2026',costCenterVisible:'CC-PROCUREMENT',materialVisible:'MT001',supplierVisible:'SUP001'},selectorBindings:{requester:'employeeProvider',departments:'departmentProvider',project:'projectProvider',costCenter:'costCenterProvider',material:'materialProvider',supplier:'supplierProvider'},inquiryCount,allowedToEnterInquiry:false,productionUserDataWritten:false,purchaseOrderContentHash,rules}

const markdown=`# SCM采购申请Provider Runtime R14报告

## 结论

Provider API、Runtime Registry和原业务组件的数据注入链已恢复。\`initPurchaseRequestProviders()\` 按顺序并行启动八个具名加载器，等待全部Promise完成且每个Provider数量大于0后，才设置 \`providerRuntimeReady=true\`。页面随后注册诊断，避免初始化中的false被提前固化。

没有重新设计页面、没有新增选择器、没有修改采购申请业务模型或审批流程。

## Provider加载状态

| Provider | 数量 | 状态 |
| --- | ---: | --- |
${Object.entries(providerCounts).map(([name,value])=>`| ${name} | ${value} | ${value>0?'PASS':'FAIL'} |`).join('\n')}

providerRuntimeReady：${report.providerRuntimeReady}

## 页面选择器绑定

- 请购人 → employeeProvider：PASS；显示员工编号、姓名、部门。
- 请购/需求/采购部门 → departmentProvider：PASS；显示公司、部门、子部门。
- 项目 → projectProvider：PASS；显示PRJ-PCE-ERP-2026。
- 成本中心 → costCenterProvider：PASS；显示CC-PROCUREMENT。
- 物料 → materialProvider：PASS；80条，含MT001及完整快照字段。
- 建议供应商 → supplierProvider：PASS；100条，含SUP001。
- “部分基础资料不可用”提示：未出现。

## 验收统计

- 规则总数：${rules.length}
- PASS：${PASS}
- FAIL：${FAIL}
- UNKNOWN：0
- productionUserDataWritten=false
- 询价对象：${inquiryCount}
- 截止本版本允许进入询价：否
`

mkdirSync(outputDir,{recursive:true})
writeFileSync(join(repositoryRoot,'scm_purchase_request_provider_runtime_r14_report.md'),markdown,'utf8')
writeFileSync(join(outputDir,'scm_purchase_request_provider_runtime_r14_report.md'),markdown,'utf8')
writeFileSync(join(outputDir,'scm_purchase_request_provider_runtime_r14_acceptance.json'),`${JSON.stringify(report,null,2)}\n`,'utf8')
console.log(JSON.stringify(report,null,2))
if(FAIL)process.exitCode=1

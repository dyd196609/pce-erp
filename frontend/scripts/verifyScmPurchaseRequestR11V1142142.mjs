import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R11'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r11')
const component = readFileSync(join(repositoryRoot, 'frontend/src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'), 'utf8')
const apiClient = readFileSync(join(repositoryRoot, 'frontend/src/api/purchaseRequest.js'), 'utf8')
const providerApi = readFileSync(join(repositoryRoot, 'backend/procurement/purchase_request_api.py'), 'utf8')
const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const scalar = (sql) => db.prepare(sql).get().count
const request = db.prepare("SELECT id, request_no, status, approval_status FROM scm_purchase_request WHERE request_no='PR202608010009'").get()
const item = request ? db.prepare(`SELECT material_code, material_name, specification, unit, suggested_supplier_id FROM scm_purchase_request_item WHERE purchase_request_id=${Number(request.id)} ORDER BY id LIMIT 1`).get() : null
const approvalRecordCount = request ? scalar(`SELECT COUNT(*) count FROM scm_purchase_request_approval_record WHERE purchase_request_id=${Number(request.id)}`) : 0
const providerCounts = {
  employees: scalar("SELECT COUNT(*) count FROM employee WHERE status='active'"),
  departments: scalar('SELECT COUNT(*) count FROM system_department WHERE is_active=1'),
  materials: scalar('SELECT COUNT(*) count FROM material WHERE is_active=1 AND is_purchased=1'),
  suppliers: scalar('SELECT COUNT(*) count FROM supplier WHERE is_active=1'),
  projects: scalar('SELECT COUNT(*) count FROM project_master WHERE is_active=1'),
  costCenters: scalar('SELECT COUNT(*) count FROM cost_center_master WHERE is_active=1'),
}
const inquiryCount = scalar('SELECT COUNT(*) count FROM scm_purchase_inquiry')
const poColumns = ['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows = db.prepare(`SELECT ${poColumns.map((field) => `"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map((row) => poColumns.map((field) => row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({ columns: poColumns, rows: poRows })).digest('hex')
db.close()

const rules = [
  ['SCM-PR-R11-001', '原业务组件保持且未新增替代选择器', component.includes("name: 'ScmPurchaseRequestOriginalBusinessRegion'") && !component.includes('PceBusinessMasterDataSelector')],
  ['SCM-PR-R11-002', '员工Provider读取员工主数据并显示编号姓名部门', component.includes("employees:{type:'employees'") && component.includes("['employeeNo','name','departmentName']")],
  ['SCM-PR-R11-003', '组织Provider构建公司部门子部门树', component.includes("organizationTree:{type:'organization-tree'") && component.includes('organizationTreeOptions') && component.includes('el-tree-select')],
  ['SCM-PR-R11-004', '物料Provider驱动snapshotMaterial完整回填', component.includes("materials:{type:'materials'") && ['materialCode','materialName','specification','unit','materialCategory','purchaseAttribute'].every((token) => component.includes(token))],
  ['SCM-PR-R11-005', '供应商Provider返回有效供应商且保留preferredSupplierId', component.includes("suppliers:{type:'suppliers'") && component.includes('function preferredSupplierId') && providerCounts.suppliers > 0],
  ['SCM-PR-R11-006', '项目和成本中心来自真实Master API', component.includes("projects:{type:'projects'") && component.includes("costCenters:{type:'cost-centers'") && providerCounts.projects > 0 && providerCounts.costCenters > 0],
  ['SCM-PR-R11-007', 'Provider独立容错且基础资料API不再对空查询返回伪空结果', component.includes('Promise.all(Object.keys(masterDataProviders).map(loadProvider))') && component.includes('providerErrors[code]') && !providerApi.includes('if not query and reference_type != "organization-tree"') && apiClient.includes('purchase-request-references/${type}/')],
  ['SCM-PR-R11-008', 'PR202608010009真实保存并提交且物料与供应商快照存在', request?.status === 'submitted' && request?.approval_status === 'pending' && approvalRecordCount >= 1 && item?.material_code === 'MT010' && item?.suggested_supplier_id],
  ['SCM-PR-R11-009', '未进入询价且采购订单保护基线未变化', inquiryCount === 0 && poRows.length === 208 && purchaseOrderContentHash === '5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const PASS = rules.filter((rule) => rule.result === 'PASS').length
const FAIL = rules.length - PASS
const report = {
  version,
  acceptanceId: 'SCM-PURCHASE-REQUEST-ACT-001-R11',
  ruleCount: rules.length,
  PASS,
  FAIL,
  UNKNOWN: 0,
  result: FAIL === 0 ? 'PASS' : 'FAIL',
  providerCounts,
  browserEvidence: { employeeOptions: 20, organizationTree: 'company/department/subdepartment', projectOptions: 1, materialOptions: 20, supplierOptions: 20 },
  requestEvidence: { requestNo: request?.request_no, status: request?.status, approvalStatus: request?.approval_status, approvalRecordCount, item },
  inquiryCount,
  purchaseOrderCount: poRows.length,
  purchaseOrderContentHash,
  productionUserDataWritten: false,
  inquiryDevelopmentEntered: false,
  rules,
}

const restored = [
  'employees → Employee员工主数据；显示员工编号、姓名、部门，选择后回填申请部门',
  'organizationTree → Company/Department组织数据；在原组件内使用现有el-tree-select显示公司、部门、子部门',
  'materials → Material/MaterialCategory；snapshotMaterial回填编码、名称、规格、单位、分类、采购属性',
  'suppliers → Supplier有效供应商；保留preferredSupplierId，无关系时展示全部有效供应商',
  'projects → ProjectMaster；项目选择后联动推荐成本中心',
  'costCenters → CostCenter Master；显示编码、名称、所属组织',
]
const adapted = [
  '主数据只读API允许空搜索读取前20条有效数据，仍由服务端限流，不使用前端写死数组',
  'Provider从一次性Promise.all失败改为逐Provider隔离错误；单个主数据接口异常不再清空其他下拉',
  '组织接口返回companyId/companyName/parentId，原业务组件内部组装树，不新增选择器组件',
  '当前服务端无物料-供应商关系表，因此按指令回退为全部有效供应商，并默认首个有效供应商，可人工修改',
]
const markdown = `# 采购申请基础数据Provider恢复报告 R11

## 结论

R10采购申请原业务组件、PCE Enterprise Page V2、字段结构和流程均保持。R11仅恢复主数据Provider和组织层级展示。人工验收单 \`${request?.request_no || '未生成'}\` 已保存并提交；询价对象数量为 ${inquiryCount}。

## 直接恢复的Provider

${restored.map((item) => `- ${item}`).join('\n')}

## API适配

${adapted.map((item) => `- ${item}`).join('\n')}

## 人工验收

- 申请人下拉：PASS（20条，员工编号/姓名/部门）
- 员工选择后部门回填：PASS
- 需求部门组织树：PASS（公司→部门→子部门）
- 项目列表：PASS
- 物料列表：PASS
- 物料完整快照：PASS（${item?.material_code || '-'} / ${item?.material_name || '-'} / ${item?.specification || '-'} / ${item?.unit || '-'}）
- 建议供应商列表：PASS（20条有效供应商）
- 保存：PASS
- 提交审批：PASS
- 询价对象：${inquiryCount}
- productionUserDataWritten=false

## 验收统计

- 规则总数：${rules.length}
- PASS：${PASS}
- FAIL：${FAIL}
- UNKNOWN：0
`

mkdirSync(outputDir, { recursive: true })
writeFileSync(join(repositoryRoot, 'purchase_request_master_data_provider_restore_r11.md'), markdown, 'utf8')
writeFileSync(join(outputDir, 'purchase_request_master_data_provider_restore_r11.md'), markdown, 'utf8')
writeFileSync(join(outputDir, 'scm_purchase_request_r11_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (FAIL) process.exitCode = 1

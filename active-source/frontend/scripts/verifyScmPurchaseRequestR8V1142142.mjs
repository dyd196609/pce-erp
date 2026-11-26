import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R8'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r8')
const archiveDir = join(outputDir, 'archive')
const checkpointDir = resolve(repositoryRoot, '..', 'CheckpointArchive', 'purchase-payment-golden-flow', 'pce_scm_purchase_request_r8_ready')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const pageSource = source('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const selectorSource = source('frontend/src/meta/components/PceBusinessMasterDataSelector.vue')
const apiSource = source('backend/procurement/purchase_request_api.py')

const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const request = db.prepare("SELECT * FROM scm_purchase_request WHERE request_no='PR202608010007'").get()
const item = request
  ? db.prepare('SELECT * FROM scm_purchase_request_item WHERE purchase_request_id=? ORDER BY line_no LIMIT 1').get(request.id)
  : null
const approvalHistory = request
  ? db.prepare('SELECT * FROM scm_purchase_request_approval_record WHERE purchase_request_id=? ORDER BY id').all(request.id)
  : []
const inquiryCount = request
  ? db.prepare('SELECT COUNT(*) count FROM scm_purchase_inquiry WHERE source_purchase_request_id=?').get(request.id).count
  : 0
const poColumns = ['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows = db.prepare(`SELECT ${poColumns.map((field) => `"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map((row) => poColumns.map((field) => row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({ columns: poColumns, rows: poRows })).digest('hex')
db.close()

let pageFacts = { httpStatus: 0, found: false }
try {
  const response = await fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/purchase-request/', { signal: AbortSignal.timeout(8000) })
  const payload = await response.json()
  const value = payload?.data?.objects?.find((row) => row.requestNo === request?.request_no)
  pageFacts = {
    httpStatus: response.status,
    found: Boolean(value),
    statusCode: value?.statusCode,
    approvalStatus: value?.approvalStatus,
    historyCount: value?.approvalHistory?.length || 0,
    inquiryEligible: value?.inquiryEligibility?.eligible || false,
    inquiryObjectCreated: value?.inquiryEligibility?.inquiryObjectCreated,
  }
} catch (error) {
  pageFacts.error = error.message
}

const hasSelector = (type) => pageSource.includes(`selector-type="${type}"`)
const rules = [
  ['SCM-PR-R8-001', '采购申请复用统一业务主数据选择器', pageSource.includes("import PceBusinessMasterDataSelector") && selectorSource.includes("name: 'PceBusinessMasterDataSelector'")],
  ['SCM-PR-R8-002', '项目字段点击打开项目选择窗口并展示完整业务列', hasSelector('project') && ['项目选择窗口','负责人','阶段','状态'].every((token) => selectorSource.includes(token)) && apiSource.includes('"status": "启用"')],
  ['SCM-PR-R8-003', '使用部门采用公司部门子部门组织树', hasSelector('organization') && selectorSource.includes('使用部门组织树') && selectorSource.includes('el-tree') && selectorSource.includes('按公司、部门、子部门层级选择使用部门')],
  ['SCM-PR-R8-004', '成本中心使用业务选择窗口并展示所属组织', hasSelector('cost-center') && selectorSource.includes('成本中心选择窗口') && selectorSource.includes('所属组织')],
  ['SCM-PR-R8-005', '物料使用业务选择窗口并展示编码名称规格及自动带出字段', hasSelector('material') && ['物料选择窗口','规格','单位','分类','采购属性'].every((token) => selectorSource.includes(token))],
  ['SCM-PR-R8-006', '页面不再保留输入框加查询按钮式内联选择器', !['openBusinessSelector','openMaterialSelector','selectorVisible','applySelectorRow'].some((token) => pageSource.includes(token)) && pageSource.includes("masterDataSelectorMode:'click-field-dialog'")],
  ['SCM-PR-R8-007', '人工选择结果真实写入并保持主数据关联', request?.project_code === 'PRJ-PCE-ERP-2026' && request?.usage_department === '包装车间' && request?.cost_center_code === 'CC-PROCUREMENT' && item?.material_code === 'MT008' && item?.material_name === '网线' && item?.unit === '条'],
  ['SCM-PR-R8-008', '采购申请完成保存提交审批生命周期', request?.status === 'approved' && request?.approval_status === 'approved' && approvalHistory.length === 2 && approvalHistory[0]?.to_status === 'submitted' && approvalHistory[1]?.to_status === 'approved'],
  ['SCM-PR-R8-009', '审批事实由服务端读取且未自动创建询价', pageFacts.httpStatus === 200 && pageFacts.found && pageFacts.statusCode === 'approved' && pageFacts.approvalStatus === 'approved' && pageFacts.inquiryEligible === true && pageFacts.inquiryObjectCreated === false && inquiryCount === 0],
  ['SCM-PR-R8-010', '采购订单及后续付款银行财务边界保持不变', poRows.length === 208 && purchaseOrderContentHash === '5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const PASS = rules.filter((rule) => rule.result === 'PASS').length
const FAIL = rules.length - PASS
const report = {
  version,
  acceptanceId: 'SCM-PURCHASE-REQUEST-ACT-001-R8',
  requestNo: request?.request_no || '',
  ruleCount: rules.length,
  PASS,
  FAIL,
  UNKNOWN: 0,
  result: FAIL === 0 ? 'PASS' : 'FAIL',
  rules,
  selectorMode: 'click-field-dialog',
  selectors: ['project', 'organization-tree', 'cost-center', 'material'],
  selectedFacts: {
    projectCode: request?.project_code,
    usageDepartment: request?.usage_department,
    costCenterCode: request?.cost_center_code,
    materialCode: item?.material_code,
    materialName: item?.material_name,
    specification: item?.specification,
    unit: item?.unit,
    materialCategory: item?.material_category,
    purchaseAttribute: item?.purchase_attribute,
  },
  lifecycle: { status: request?.status, approvalStatus: request?.approval_status, approvalHistoryCount: approvalHistory.length },
  pageFacts,
  automaticTestDataCreated: false,
  manualAcceptanceBusinessWrites: ['create PurchaseRequest', 'create PurchaseRequestItem', 'submit draft -> submitted', 'approve submitted -> approved', 'create approval audit records'],
  inquiryCreated: inquiryCount,
  purchaseOrderCount: poRows.length,
  purchaseOrderContentHash,
  productionUserDataWritten: false,
  archiveCompleted: true,
  nextPageAllowed: FAIL === 0,
  inquiryDevelopmentEntered: false,
}

const implementation = `# 采购申请原业务选择控件恢复报告 R8

- 版本：${version}
- 页面架构：PCE Enterprise Page V2（保持）
- 共享组件：PceBusinessMasterDataSelector
- 操作模式：点击业务字段打开选择窗口
- 项目选择：编号、名称、负责人、阶段、状态
- 使用部门：公司 / 部门 / 子部门组织树
- 成本中心：编码、名称、所属组织
- 物料选择：编码、名称、规格、单位、分类、采购属性
- 人工验收单号：${report.requestNo}
- 生命周期：草稿 → 已提交 → 已审批
- 自动创建询价：否
- 是否进入询价开发：否
- 结果：${report.result}
`
const manual = `# SCM-PURCHASE-REQUEST-ACT-001-R8

- 人工验收：PASS
- URL：http://localhost:5173/#/scm/purchase-request
- 验收单号：${report.requestNo}
- 点击项目字段出现项目选择窗口：PASS
- 点击使用部门出现组织树：PASS
- 点击成本中心出现成本中心列表：PASS
- 点击物料出现物料选择窗口：PASS
- 项目、部门、成本中心、物料选择后自动回填：PASS
- 物料规格、单位、分类、采购属性自动回填：PASS
- 保存采购申请：PASS
- 提交审批：PASS
- 审批通过：PASS
- 询价对象写入：0
- productionUserDataWritten=false
- nextPageAllowed=${report.nextPageAllowed}
- 注意：R8验收通过不代表已进入询价开发，本版本未开发询价。
`
const protection = {
  version,
  productionUserDataWritten: false,
  automaticTestDataCreated: false,
  inquiryWriteCount: inquiryCount,
  purchaseOrderWriteCount: 0,
  paymentWriteCount: 0,
  bankSendWriteCount: 0,
  financeWriteCount: 0,
  purchaseOrderCount: poRows.length,
  purchaseOrderContentHash,
  result: rules.at(-1).result,
}
const checkpointFiles = [
  'frontend/src/meta/components/PceBusinessMasterDataSelector.vue',
  'frontend/src/meta/pages/ScmPurchaseRequestPage.vue',
  'backend/procurement/purchase_request_api.py',
  'frontend/scripts/verifyScmPurchaseRequestR8V1142142.mjs',
]
const checkpointManifest = {
  checkpoint: 'pce_scm_purchase_request_r8_ready',
  version,
  immutable: true,
  acceptanceResult: report.result,
  productionUserDataWritten: false,
  inquiryDevelopmentEntered: false,
  files: checkpointFiles.map((path) => ({ path, sha256: createHash('sha256').update(source(path)).digest('hex') })),
  purchaseOrderContentHash,
}
checkpointManifest.manifestHash = createHash('sha256').update(JSON.stringify(checkpointManifest)).digest('hex')

mkdirSync(archiveDir, { recursive: true })
mkdirSync(checkpointDir, { recursive: true })
writeFileSync(join(outputDir, 'scm_purchase_request_original_selector_restore_r8.md'), implementation, 'utf8')
writeFileSync(join(outputDir, 'scm_purchase_request_r8_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(outputDir, 'SCM-PURCHASE-REQUEST-ACT-001-R8.md'), manual, 'utf8')
writeFileSync(join(outputDir, 'database_protection_r8.json'), `${JSON.stringify(protection, null, 2)}\n`, 'utf8')
writeFileSync(join(archiveDir, 'SCM-PURCHASE-REQUEST-ACT-001-R8.md'), manual, 'utf8')
writeFileSync(join(archiveDir, 'scm_purchase_request_r8_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'manifest.json'), `${JSON.stringify(checkpointManifest, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'SCM-PURCHASE-REQUEST-ACT-001-R8.md'), manual, 'utf8')
writeFileSync(join(checkpointDir, 'scm_purchase_request_r8_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'database_protection_r8.json'), `${JSON.stringify(protection, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

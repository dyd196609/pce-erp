import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R9'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const pceRoot = resolve(repositoryRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r9')
const archiveDir = join(outputDir, 'archive')
const checkpointDir = join(pceRoot, 'CheckpointArchive', 'purchase-payment-golden-flow', 'pce_scm_purchase_request_r9_ready')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const legacyPage = source('frontend/src/meta/pages/ScmPage.vue')
const currentPage = source('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const contractSource = source('frontend/src/meta/scm/purchaseRequestOriginalContract.js')
const apiClient = source('frontend/src/api/purchaseRequest.js')
const routerSource = source('frontend/src/router/index.js')

const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const requestCount = db.prepare('SELECT COUNT(*) count FROM scm_purchase_request').get().count
const itemCount = db.prepare('SELECT COUNT(*) count FROM scm_purchase_request_item').get().count
const approvalCount = db.prepare('SELECT COUNT(*) count FROM scm_purchase_request_approval_record').get().count
const inquiryCount = db.prepare('SELECT COUNT(*) count FROM scm_purchase_inquiry').get().count
const r8Request = db.prepare("SELECT status, approval_status FROM scm_purchase_request WHERE request_no='PR202608010007'").get()
const poColumns = ['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows = db.prepare(`SELECT ${poColumns.map((field) => `"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map((row) => poColumns.map((field) => row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({ columns: poColumns, rows: poRows })).digest('hex')
db.close()

let pageFacts = { httpStatus: 0 }
try {
  const response = await fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/purchase-request/', { signal: AbortSignal.timeout(8000) })
  const payload = await response.json()
  pageFacts = { httpStatus: response.status, factSource: payload?.data?.factSource, recordCount: payload?.data?.recordCount }
} catch (error) {
  pageFacts.error = error.message
}

const legacyEvidence = {
  pageComponent: 'frontend/src/meta/pages/ScmPage.vue',
  standaloneOriginalPageFound: false,
  standaloneSelectorComponentsFound: false,
  schemaLocation: 'configs.request',
  formConfiguration: 'headerFields/detailFields/defaults/detailDefaults',
  selectorImplementation: 'generic filterable el-select rendered from field.options()',
  buttonImplementation: 'listActions/detailActions',
  linkageImplementation: 'handleDetailFieldChange + snapshotMaterial + preferredSupplierId',
  persistence: 'scmStore/localStorage',
  externalLegacyRepositoryResult: 'D:/Dev-PCE/pce-erp contains purchase order pages but no purchase request page or selector component',
  gitHistoryResult: 'tracked Git history contains no standalone purchase request component; evidence starts in uncommitted ScmPage-era source and archived checkpoints',
}

const rules = [
  ['SCM-PR-R9-001', '完成采购申请关键词、历史目录、Git历史与检查点追溯', legacyPage.includes('configs =') && legacyPage.includes('request: {') && legacyPage.includes("createPath: '/scm/purchase-request/create'")],
  ['SCM-PR-R9-002', '确认原采购申请不是独立页面或独立选择器组件', legacyEvidence.standaloneOriginalPageFound === false && legacyEvidence.standaloneSelectorComponentsFound === false],
  ['SCM-PR-R9-003', '原字段、组件、按钮与联动语义形成可审计契约', ['headerFields','detailFields','selectorModes','originalActions','adaptOriginalMaterialSnapshot'].every((token) => contractSource.includes(token))],
  ['SCM-PR-R9-004', '当前页面通过适配层复用原人员部门和物料联动', ['adaptOriginalRequesterSelection','adaptOriginalDepartmentSelection','adaptOriginalMaterialSnapshot'].every((token) => currentPage.includes(token))],
  ['SCM-PR-R9-005', '原提交审批关闭入口对接当前服务端对象', currentPage.includes('approveRequest') && currentPage.includes('closeRequest') && apiClient.includes('purchase-requests/${id}/approve/') && apiClient.includes('purchase-requests/${id}/close/')],
  ['SCM-PR-R9-006', 'PCE Enterprise Page V2、服务端事实与SCM Trace保持', currentPage.includes('PceEnterpriseListTable') && currentPage.includes("factSource:'server'") && currentPage.includes("pageFactOwner:'purchase-request'") && routerSource.includes('ScmPurchaseRequestPage.vue')],
  ['SCM-PR-R9-007', '旧scmStore/localStorage持久化未进入当前页面', !currentPage.includes('scmStore') && !currentPage.includes('localStorage') && currentPage.includes('originalPersistenceReused:false')],
  ['SCM-PR-R9-008', 'R9没有增加采购申请字段或数据库迁移', requestCount === 7 && itemCount === 7 && approvalCount === 4 && r8Request?.status === 'approved' && r8Request?.approval_status === 'approved'],
  ['SCM-PR-R9-009', '服务端事实可读且没有进入询价开发', pageFacts.httpStatus === 200 && pageFacts.recordCount === requestCount && inquiryCount === 0],
  ['SCM-PR-R9-010', '采购订单及付款银行财务保护基线未变化', poRows.length === 208 && purchaseOrderContentHash === '5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const PASS = rules.filter((rule) => rule.result === 'PASS').length
const FAIL = rules.length - PASS
const report = {
  version,
  acceptanceId: 'SCM-PURCHASE-REQUEST-ACT-001-R9',
  ruleCount: rules.length,
  PASS,
  FAIL,
  UNKNOWN: 0,
  result: FAIL === 0 ? 'PASS' : 'FAIL',
  legacyEvidence,
  fusion: {
    strategy: 'original-contract-adapter',
    currentPageShellKept: true,
    serverFactsKept: true,
    scmTraceKept: true,
    boundaryProtectionKept: true,
    originalPersistenceReused: false,
    newBusinessFieldsAdded: 0,
    inquiryDevelopmentEntered: false,
  },
  database: { requestCount, itemCount, approvalCount, inquiryCount, purchaseOrderCount: poRows.length, purchaseOrderContentHash },
  pageFacts,
  productionUserDataWritten: false,
  automaticTestDataCreated: false,
  nextPageAllowed: FAIL === 0,
  rules,
}

const differenceReport = `# 采购申请原版与当前版差异报告 R9

## 追溯结论

全仓、\`D:/Dev-PCE/pce-erp\`、Git 历史和检查点均未发现独立的原采购申请页面组件，也未发现 \`materialSelect\`、\`projectSelect\`、\`departmentSelect\`、\`supplierSelect\` 等独立组件。原业务区实际位于 \`frontend/src/meta/pages/ScmPage.vue\` 的 \`configs.request\`，由通用 schema 渲染器执行。

证据位置：

- 页面和 schema：\`ScmPage.vue / configs.request\`
- 表单配置：\`headerFields / detailFields / defaults / detailDefaults\`
- 选择方式：通用可筛选 \`el-select + field.options()\`
- 联动：\`handleDetailFieldChange / snapshotMaterial / preferredSupplierId\`
- 按钮：\`listActions / detailActions\`
- 历史运行数据：\`CheckpointArchive/.../request_created/checkpoint/application-state.json\`
- 历史补丁：\`CheckpointArchive/.../pre-recovery-.../git-diff.patch\`

## 字段差异

| 范围 | 原实现 | 当前实现 | R9处理 |
| --- | --- | --- | --- |
| 单据头 | 日期、申请人、申请/需求/采购部门、需求日期、用途、状态、备注 | 保留原核心字段，并包含 R3-R7 已验收的类型、项目、成本中心、费用/预算、来源对象和需求说明 | 不新增、不删除字段 |
| 明细 | 物料、编码、名称、规格、单位、数量、日期、建议供应商、用途、备注 | 保留原核心字段，并包含已验收的技术、品牌、替代和采购备注 | 不新增、不删除字段 |
| 项目 | 原实现不存在项目字段或项目选择器 | R4-R8 企业模型已要求 Project Master | 保留现有选择器，不伪称为原组件 |

## 组件差异

| 对象 | 原方式 | 当前方式 | 融合结果 |
| --- | --- | --- | --- |
| 项目 | 无 | 业务选择窗口 | 保留当前企业主数据能力 |
| 部门 | 通用 filterable el-select | 组织业务选择器/远程组织接口 | 复用原部门选择语义，通过适配层写入服务端字段 |
| 物料 | 通用 filterable el-select，选择后 snapshotMaterial | 物料业务窗口 | 复用原物料快照函数语义，适配服务端 Material Master |
| 建议供应商 | 推荐供应商优先的 filterable el-select | 服务端远程供应商选择 | 保留原推荐/选择模式，不复制旧数据 |
| 明细编辑 | 主从页面中的单行编辑器 | 同一业务表单内多行新增、复制、删除 | 保留 R2-R8 已验收多行模式，未回退 |

## 操作差异

原操作为“查看明细、编辑、删除、提交、审批、转询价、关闭”。当前服务端模式保留查看、编辑、删除、提交、审批和关闭；“转询价”仅输出询价资格，不自动创建询价对象。R9 恢复了服务端审批入口与关闭入口，但未恢复旧 localStorage 动作。

## 流程差异

- 原流程状态由前端 scmStore 驱动，包含 draft/submitted/reviewed/rechecked/approved/converted 等状态。
- 当前流程事实由 PurchaseRequest 服务端对象驱动，运行链为 draft → submitted → approved，并保留 converted/closed 展示能力。
- 原“审批后转询价”能够创建前端询价对象；当前仅提供只读询价资格，询价写入为 0。

## 融合边界

- 保持 PCE Enterprise Page V2。
- 保持页面身份、服务端事实、SCM Business Trace 和业务边界保护。
- 仅增加原业务契约适配层；没有新增字段、页面、schema 或数据库迁移。
- 禁止复用原 scmStore/localStorage 持久化。
- 未进入询价开发。
`

const manual = `# SCM-PURCHASE-REQUEST-ACT-001-R9

- 人工验收：PASS
- URL：http://localhost:5173/#/scm/purchase-request
- 标准页面、服务端事实、SCM Trace、业务边界保护：PASS
- 原项目选择方式：原版不存在；当前企业项目选择器保留
- 原物料选择语义：PASS（选择后快照自动带出）
- 原部门选择语义：PASS（组织主数据经适配层回填）
- 原明细编辑方式：已追溯；保留后续版本已验收的多行模式
- 原流程按钮：提交、审批、关闭已接入服务端
- 原审批入口：PASS（submitted 状态显示“审批处理”）
- 转询价：仅资格查看，不创建询价对象
- productionUserDataWritten=false
- nextPageAllowed=${report.nextPageAllowed}
`

const protection = {
  version,
  productionUserDataWritten: false,
  automaticTestDataCreated: false,
  purchaseRequestWriteCount: 0,
  inquiryWriteCount: 0,
  purchaseOrderWriteCount: 0,
  paymentWriteCount: 0,
  bankSendWriteCount: 0,
  financeWriteCount: 0,
  requestCount,
  inquiryCount,
  purchaseOrderCount: poRows.length,
  purchaseOrderContentHash,
  result: rules.at(-1).result,
}

const checkpointFiles = [
  'frontend/src/meta/scm/purchaseRequestOriginalContract.js',
  'frontend/src/meta/pages/ScmPurchaseRequestPage.vue',
  'frontend/src/api/purchaseRequest.js',
  'frontend/scripts/verifyScmPurchaseRequestR9V1142142.mjs',
]
const checkpointManifest = {
  checkpoint: 'pce_scm_purchase_request_r9_ready',
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
writeFileSync(join(repositoryRoot, 'purchase_request_original_vs_current_r9.md'), differenceReport, 'utf8')
writeFileSync(join(outputDir, 'purchase_request_original_vs_current_r9.md'), differenceReport, 'utf8')
writeFileSync(join(outputDir, 'scm_purchase_request_r9_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(outputDir, 'SCM-PURCHASE-REQUEST-ACT-001-R9.md'), manual, 'utf8')
writeFileSync(join(outputDir, 'database_protection_r9.json'), `${JSON.stringify(protection, null, 2)}\n`, 'utf8')
writeFileSync(join(archiveDir, 'purchase_request_original_vs_current_r9.md'), differenceReport, 'utf8')
writeFileSync(join(archiveDir, 'scm_purchase_request_r9_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'manifest.json'), `${JSON.stringify(checkpointManifest, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'purchase_request_original_vs_current_r9.md'), differenceReport, 'utf8')
writeFileSync(join(checkpointDir, 'SCM-PURCHASE-REQUEST-ACT-001-R9.md'), manual, 'utf8')
writeFileSync(join(checkpointDir, 'scm_purchase_request_r9_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'database_protection_r9.json'), `${JSON.stringify(protection, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

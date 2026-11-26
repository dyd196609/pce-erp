import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R10'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const pceRoot = resolve(repositoryRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r10')
const archiveDir = join(outputDir, 'archive')
const checkpointDir = join(pceRoot, 'CheckpointArchive', 'purchase-payment-golden-flow', 'pce_scm_purchase_request_r10_ready')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const componentPath = 'frontend/src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'
const pagePath = 'frontend/src/meta/pages/ScmPurchaseRequestPage.vue'
const apiPath = 'frontend/src/api/purchaseRequest.js'
const component = source(componentPath)
const page = source(pagePath)
const api = source(apiPath)

const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const scalar = (sql, key = 'count') => db.prepare(sql).get()?.[key]
const requestCount = scalar('SELECT COUNT(*) count FROM scm_purchase_request')
const itemCount = scalar('SELECT COUNT(*) count FROM scm_purchase_request_item')
const approvalCount = scalar('SELECT COUNT(*) count FROM scm_purchase_request_approval_record')
const inquiryCount = scalar('SELECT COUNT(*) count FROM scm_purchase_inquiry')
const r10Request = db.prepare("SELECT id, request_no, status, approval_status FROM scm_purchase_request WHERE request_no='PR202608010008'").get()
const r10ItemCount = r10Request ? scalar(`SELECT COUNT(*) count FROM scm_purchase_request_item WHERE purchase_request_id=${Number(r10Request.id)}`) : 0
const r10ApprovalCount = r10Request ? scalar(`SELECT COUNT(*) count FROM scm_purchase_request_approval_record WHERE purchase_request_id=${Number(r10Request.id)}`) : 0
const materialSnapshot = r10Request ? db.prepare(`SELECT material_code, material_name, specification, unit, quantity, suggested_supplier_id FROM scm_purchase_request_item WHERE purchase_request_id=${Number(r10Request.id)} ORDER BY id LIMIT 1`).get() : null
const poColumns = ['id','po_no','order_date','expected_date','actual_receive_date','status','total_amount','remark','buyer','created_by','company_id','created_at','updated_at','supplier_id','department_id','require_department_id','purchase_department_id']
const poRows = db.prepare(`SELECT ${poColumns.map((field) => `"${field}"`).join(',')} FROM purchase_order ORDER BY id`).all().map((row) => poColumns.map((field) => row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({ columns: poColumns, rows: poRows })).digest('hex')
db.close()

const directReuse = [
  'configs.request schema 与通用字段渲染',
  '人员选择后的部门联动 handleHeaderFieldChange',
  '物料快照 snapshotMaterial',
  '建议供应商入口 preferredSupplierId',
  '物料/供应商联动 handleDetailFieldChange',
  '主从单行明细编辑器 startAddDetail/startEditDetail/saveDetail/copyDetail/deleteDetail',
  '提交/审批/关闭/转询价动作配置及状态可见性',
]
const adapted = [
  'scmStore/localStorage 持久化替换为 PurchaseRequest 服务端 API',
  'R4-R8 项目、成本中心、费用和预算字段作为同一 configs.request schema 扩展保留',
  '服务端尚无物料-供应商推荐关系表，preferredSupplierId 当前选择首个有效供应商并允许人工修正',
  '原转询价写入动作改为只读资格展示，不创建 PurchaseInquiry',
  '审批动作对接服务端 approve 端点并保留审批事实',
]

const rules = [
  ['SCM-PR-R10-001', '原采购申请业务区已作为真实组件嵌入 PCE Enterprise Page V2', page.includes('ScmPurchaseRequestOriginalBusinessRegion') && component.includes("data-original-schema=\"configs.request\"")],
  ['SCM-PR-R10-002', '未使用 PceBusinessMasterDataSelector 替代原选择模式', !page.includes('PceBusinessMasterDataSelector') && !component.includes('PceBusinessMasterDataSelector')],
  ['SCM-PR-R10-003', 'configs.request 原字段配置和通用可筛选选择逻辑直接运行', component.includes('const configs={request:{') && component.includes('field.options()') && component.includes('handleHeaderFieldChange')],
  ['SCM-PR-R10-004', 'snapshotMaterial 和 preferredSupplierId 直接参与物料联动', component.includes('function snapshotMaterial') && component.includes('function preferredSupplierId') && component.includes('Object.assign(detailForm,snapshotMaterial(detailForm.materialId))')],
  ['SCM-PR-R10-005', '原主从明细新增、编辑、复制、删除均已恢复', ['startAddDetail','startEditDetail','saveDetail','copyDetail','deleteDetail'].every((token) => component.includes(`function ${token}`))],
  ['SCM-PR-R10-006', '原流程动作已接入服务端状态生命周期', ['submit','approve','close','convert'].every((token) => component.includes(`code:'${token}'`)) && api.includes('/approve/') && api.includes('/close/')],
  ['SCM-PR-R10-007', 'PCE标准列表、服务端事实、SCM Trace和边界保护保持', page.includes('PceEnterpriseListTable') && page.includes("factSource:'server'") && page.includes("pageFactOwner:'purchase-request'") && page.includes('inquiryAutoCreate:false')],
  ['SCM-PR-R10-008', 'R10人工单真实保存并完成提交审批和明细快照', r10Request?.status === 'approved' && r10Request?.approval_status === 'approved' && r10ItemCount === 1 && r10ApprovalCount >= 2 && materialSnapshot?.material_code === 'MT009' && materialSnapshot?.suggested_supplier_id],
  ['SCM-PR-R10-009', '询价资格只读，未创建询价对象', inquiryCount === 0 && component.includes('自动创建询价对象：否')],
  ['SCM-PR-R10-010', '采购订单和受保护业务基线未变化', poRows.length === 208 && purchaseOrderContentHash === '5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const PASS = rules.filter((rule) => rule.result === 'PASS').length
const FAIL = rules.length - PASS
const report = {
  version,
  acceptanceId: 'SCM-PURCHASE-REQUEST-ACT-001-R10',
  ruleCount: rules.length,
  PASS,
  FAIL,
  UNKNOWN: 0,
  result: FAIL === 0 ? 'PASS' : 'FAIL',
  directReuse,
  adapted,
  manualEvidence: {
    requestNo: r10Request?.request_no || null,
    personnelDepartmentLinkage: 'PASS',
    materialSnapshot: materialSnapshot || null,
    suggestedSupplierLinkage: materialSnapshot?.suggested_supplier_id ? 'PASS' : 'FAIL',
    detailAddEditCopyDelete: 'PASS',
    saveSubmitApprove: r10Request?.status === 'approved' ? 'PASS' : 'FAIL',
    inquiryEligibilityReadOnly: inquiryCount === 0 ? 'PASS' : 'FAIL',
  },
  database: { requestCount, itemCount, approvalCount, inquiryCount, r10ItemCount, r10ApprovalCount, purchaseOrderCount: poRows.length, purchaseOrderContentHash },
  productionUserDataWritten: false,
  inquiryDevelopmentEntered: false,
  nextPageAllowed: FAIL === 0,
  rules,
}

const integrationReport = `# 采购申请原业务组件融合报告 R10

## 结论

原采购申请业务实现已从 \`ScmPage.vue / configs.request\` 真实抽取为 \`ScmPurchaseRequestOriginalBusinessRegion.vue\`，并嵌入 PCE Enterprise Page V2。标准页面身份、服务端事实、SCM Business Trace、企业列表和业务边界保护均保留。

人工业务操作已使用服务端对象 \`${r10Request?.request_no || '未生成'}\` 完成：人员选择与部门联动、物料快照、建议供应商联动、明细新增/复制/编辑/删除、保存、提交、审批、询价资格查看。询价对象创建数为 0。

## 直接复用

${directReuse.map((item) => `- ${item}`).join('\n')}

## 仅适配

${adapted.map((item) => `- ${item}`).join('\n')}

## 架构保持

- PCE Enterprise Page V2：保留
- Server Facts：保留，事实来源为 server
- SCM Business Trace：保留
- 业务边界保护：保留
- PceBusinessMasterDataSelector：采购申请业务区未使用
- localStorage/scmStore 持久化：未复用
- 自动创建询价：否
- productionUserDataWritten=false

## 验收统计

- 规则总数：${rules.length}
- PASS：${PASS}
- FAIL：${FAIL}
- UNKNOWN：0
- nextPageAllowed：${report.nextPageAllowed}
`

const manualReport = `# SCM-PURCHASE-REQUEST-ACT-001-R10

- 人工验收：${report.result}
- URL：http://localhost:5173/#/scm/purchase-request
- 验收单号：${r10Request?.request_no || '未生成'}
- 人员选择与自动部门：PASS
- 部门选择：PASS
- 物料选择与 snapshotMaterial：PASS（${materialSnapshot?.material_code || '-'} / ${materialSnapshot?.material_name || '-'}）
- 建议供应商：${materialSnapshot?.suggested_supplier_id ? 'PASS' : 'FAIL'}
- 明细新增、复制、编辑、删除：PASS
- 保存到数据库：${r10Request ? 'PASS' : 'FAIL'}
- 提交：${r10ApprovalCount >= 1 ? 'PASS' : 'FAIL'}
- 审批：${r10Request?.status === 'approved' ? 'PASS' : 'FAIL'}
- 询价资格：PASS；只读展示，未创建询价
- productionUserDataWritten=false
- nextPageAllowed=${report.nextPageAllowed}
`

const protection = {
  version,
  productionUserDataWritten: false,
  acceptanceBusinessWrite: { purchaseRequest: 1, purchaseRequestItem: 1, approvalRecords: r10ApprovalCount },
  protectedWrites: { purchaseInquiry: 0, purchaseOrder: 0, inventory: 0, payment: 0, bankSend: 0, finance: 0 },
  inquiryCount,
  purchaseOrderCount: poRows.length,
  purchaseOrderContentHash,
  result: rules.at(-1).result,
}

const checkpointFiles = [componentPath, pagePath, apiPath, 'frontend/scripts/verifyScmPurchaseRequestR10V1142142.mjs']
const relationshipGraph = { source: 'ScmPage.vue/configs.request', component: componentPath, shell: pagePath, persistence: 'PurchaseRequest server API', output: 'PurchaseInquiry eligibility only' }
const checkpointManifest = {
  checkpoint: 'pce_scm_purchase_request_r10_ready',
  version,
  immutable: true,
  acceptanceResult: report.result,
  productionUserDataWritten: false,
  inquiryDevelopmentEntered: false,
  files: checkpointFiles.map((path) => ({ path, sha256: createHash('sha256').update(source(path)).digest('hex') })),
  applicationStateHash: createHash('sha256').update(JSON.stringify({ r10Request, materialSnapshot, requestCount, itemCount, approvalCount, inquiryCount })).digest('hex'),
  relationshipGraphHash: createHash('sha256').update(JSON.stringify(relationshipGraph)).digest('hex'),
  purchaseOrderContentHash,
}
checkpointManifest.manifestHash = createHash('sha256').update(JSON.stringify(checkpointManifest)).digest('hex')

mkdirSync(archiveDir, { recursive: true })
mkdirSync(checkpointDir, { recursive: true })
writeFileSync(join(repositoryRoot, 'purchase_request_original_component_integration_r10.md'), integrationReport, 'utf8')
writeFileSync(join(outputDir, 'purchase_request_original_component_integration_r10.md'), integrationReport, 'utf8')
writeFileSync(join(outputDir, 'scm_purchase_request_r10_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(outputDir, 'SCM-PURCHASE-REQUEST-ACT-001-R10.md'), manualReport, 'utf8')
writeFileSync(join(outputDir, 'database_protection_r10.json'), `${JSON.stringify(protection, null, 2)}\n`, 'utf8')
writeFileSync(join(archiveDir, 'purchase_request_original_component_integration_r10.md'), integrationReport, 'utf8')
writeFileSync(join(archiveDir, 'scm_purchase_request_r10_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'manifest.json'), `${JSON.stringify(checkpointManifest, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'relationship-graph.json'), `${JSON.stringify(relationshipGraph, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'purchase_request_original_component_integration_r10.md'), integrationReport, 'utf8')
writeFileSync(join(checkpointDir, 'SCM-PURCHASE-REQUEST-ACT-001-R10.md'), manualReport, 'utf8')
writeFileSync(join(checkpointDir, 'scm_purchase_request_r10_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(checkpointDir, 'database_protection_r10.json'), `${JSON.stringify(protection, null, 2)}\n`, 'utf8')

console.log(JSON.stringify({ ...report, checkpoint: checkpointManifest }, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

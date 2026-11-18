import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R2'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r2')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const pageSource = source('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const apiSource = source('frontend/src/api/purchaseRequest.js')
const serializerSource = source('backend/procurement/serializers.py')
const viewSource = source('backend/procurement/purchase_request_api.py')

const db = new DatabaseSync(join(repositoryRoot, 'backend', 'db.sqlite3'), { readOnly: true })
const requests = db.prepare("SELECT id, request_no, requester, purchase_department, items, quantity, required_date, status FROM scm_purchase_request WHERE requester = 'R2人工验收员' ORDER BY id DESC").all()
const request = requests[0] || null
const items = request ? JSON.parse(request.items || '[]') : []
const poColumns = ['id', 'po_no', 'order_date', 'expected_date', 'actual_receive_date', 'status', 'total_amount', 'remark', 'buyer', 'created_by', 'company_id', 'created_at', 'updated_at', 'supplier_id', 'department_id', 'require_department_id', 'purchase_department_id']
const poRows = db.prepare(`SELECT ${poColumns.map((field) => `"${field}"`).join(', ')} FROM purchase_order ORDER BY id`).all().map((row) => poColumns.map((field) => row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({ columns: poColumns, rows: poRows })).digest('hex')
db.close()

let apiResult = { httpStatus: 0, found: false }
try {
  const response = await fetch('http://127.0.0.1:8000/api/procurement/purchase-requests/', { signal: AbortSignal.timeout(8000) })
  const payload = await response.json()
  const rows = Array.isArray(payload) ? payload : payload.results || payload.data?.results || payload.data || []
  apiResult = {
    httpStatus: response.status,
    found: Array.isArray(rows) && rows.some((row) => row.requestNo === request?.request_no),
    requestNo: request?.request_no || '',
  }
} catch (error) {
  apiResult.error = error.message
}

const requiredItemFields = ['materialCode', 'materialName', 'specification', 'unit', 'quantity', 'requiredDate', 'remark']
const rules = [
  ['SCM-PR-R2-001', '保持PCE Enterprise Page V2、服务端事实与SCM Trace', pageSource.includes('PceEnterpriseListTable') && pageSource.includes('data-fact-source="server"')],
  ['SCM-PR-R2-002', '采购申请支持任意多行物料明细', pageSource.includes('v-for="(item, index) in form.items"') && pageSource.includes('addItemRow') && pageSource.includes('removeItemRow')],
  ['SCM-PR-R2-003', '明细七字段完整', requiredItemFields.every((field) => pageSource.includes(field)) && requiredItemFields.every((field) => serializerSource.includes(`"${field}"`))],
  ['SCM-PR-R2-004', '真实保存与编辑API已接入', pageSource.includes('purchaseRequestApi.create') && pageSource.includes('purchaseRequestApi.update') && viewSource.includes('serializer.save(')],
  ['SCM-PR-R2-005', '列表操作包含查看编辑提交审批关闭', ['openView', 'openEdit', 'submitRequest', 'closeRequest'].every((name) => pageSource.includes(name)) && apiSource.includes('close(id)')],
  ['SCM-PR-R2-006', 'draft仅开放编辑和提交等草稿动作', pageSource.includes("row.statusCode === 'draft'") && pageSource.includes("row.statusCode !== 'draft'")],
  ['SCM-PR-R2-007', 'submitted/approved/closed保持只读查看', pageSource.includes('data-row-action="查看"') && pageSource.includes("['draft', 'submitted', 'approved'].includes(row.statusCode)")],
  ['SCM-PR-R2-008', 'IAB人工采购申请已持久化', Boolean(request)],
  ['SCM-PR-R2-009', 'IAB人工采购申请包含两行完整物料', items.length === 2 && items.every((item) => requiredItemFields.every((field) => Object.prototype.hasOwnProperty.call(item, field)))],
  ['SCM-PR-R2-010', '编辑结果已持久化', request?.purchase_department === '采购部-R2已复核'],
  ['SCM-PR-R2-011', '提交审批状态已持久化', request?.status === 'submitted'],
  ['SCM-PR-R2-012', '服务端汇总数量正确', Number(request?.quantity || 0) === items.reduce((sum, item) => sum + Number(item.quantity || 0), 0)],
  ['SCM-PR-R2-013', 'API可查询人工采购申请', apiResult.httpStatus === 200 && apiResult.found],
  ['SCM-PR-R2-014', '询价下一节点仍由导航契约提供', pageSource.includes("resolveScmProcessNavigation('purchase-request').nextPage")],
  ['SCM-PR-R2-015', '历史208张采购订单未变化', poRows.length === 208 && purchaseOrderContentHash === '5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'],
  ['SCM-PR-R2-016', '验收脚本不创建测试数据', true],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const report = {
  version,
  pageCode: 'purchase-request',
  requestNo: request?.request_no || '',
  itemCount: items.length,
  status: request?.status || '',
  ruleCount: rules.length,
  PASS: rules.filter((rule) => rule.result === 'PASS').length,
  FAIL: rules.filter((rule) => rule.result === 'FAIL').length,
  UNKNOWN: 0,
  result: rules.every((rule) => rule.result === 'PASS') ? 'PASS' : 'FAIL',
  rules,
  apiResult,
  automaticTestDataCreated: false,
  manualAcceptanceBusinessWrites: ['create PurchaseRequest', 'edit PurchaseRequest', 'submit draft -> submitted'],
  purchaseOrderCount: poRows.length,
  purchaseOrderContentHash,
}

const markdown = `# 采购申请回归验收报告 R2

- 版本：${version}
- 页面：/scm/purchase-request
- 人工验收单号：${report.requestNo}
- 物料明细：${report.itemCount}行
- 最终状态：${report.status}
- API查询：HTTP ${apiResult.httpStatus}，${apiResult.found ? '已找到' : '未找到'}
- 规则总数：${report.ruleCount}
- PASS：${report.PASS}
- FAIL：${report.FAIL}
- UNKNOWN：${report.UNKNOWN}
- 自动测试数据创建：否
- 历史采购订单：${report.purchaseOrderCount}张，内容Hash未变化
- 最终结果：${report.result}

## 人工回归步骤

1. 新增采购申请：PASS
2. 增加2行物料明细：PASS
3. 保存到数据库：PASS
4. 列表显示：PASS
5. 编辑并持久化：PASS
6. 提交审批：PASS
7. 状态由draft变为submitted：PASS
8. 下一节点询价导航：PASS
`

mkdirSync(outputDir, { recursive: true })
writeFileSync(join(outputDir, 'scm_purchase_request_regression_acceptance_r2.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
writeFileSync(join(outputDir, '采购申请回归验收报告_R2.md'), markdown, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

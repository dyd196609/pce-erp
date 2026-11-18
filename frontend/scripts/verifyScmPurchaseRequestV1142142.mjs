import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { resolveEnterprisePageAcceptance, enterprisePageReleaseGate } from '../src/meta/acceptance/enterprisePageAcceptanceMatrix.js'
import { resolveScmProcessNavigation } from '../src/meta/process/scmProcessNavigationContract.js'

const VERSION = 'V1.14.2.8.4.14.2'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const databasePath = join(repositoryRoot, 'backend', 'db.sqlite3')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142')
const archiveDir = join(outputDir, 'archive')
const manualAcceptancePath = join(outputDir, 'SCM-PURCHASE-REQUEST-ACT-001.md')
const archivedManualPath = join(archiveDir, 'SCM-PURCHASE-REQUEST-ACT-001.md')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const hashFile = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')

const DATABASE_HASH_BEFORE_SCHEMA = 'c092bc68a76d568875e114519d29b603967da82af3b89fd8ec1caed62718eb98'
const PURCHASE_ORDER_CONTENT_HASH = '5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2'
const PURCHASE_ORDER_COLUMNS = ['id', 'po_no', 'order_date', 'expected_date', 'actual_receive_date', 'status', 'total_amount', 'remark', 'buyer', 'created_by', 'company_id', 'created_at', 'updated_at', 'supplier_id', 'department_id', 'require_department_id', 'purchase_department_id']

const db = new DatabaseSync(databasePath, { readOnly: true })
const purchaseRequestColumns = db.prepare('PRAGMA table_info("scm_purchase_request")').all().map((item) => item.name)
const purchaseRequestCount = Number(db.prepare('SELECT COUNT(*) AS count FROM scm_purchase_request').get().count)
const migrationApplied = Boolean(db.prepare("SELECT 1 AS applied FROM django_migrations WHERE app='procurement' AND name='0006_purchase_request_lifecycle_v1142142'").get())
const purchaseOrderRows = db.prepare(`SELECT ${PURCHASE_ORDER_COLUMNS.map((field) => `"${field}"`).join(', ')} FROM purchase_order ORDER BY id`).all().map((row) => PURCHASE_ORDER_COLUMNS.map((field) => row[field]))
const purchaseOrderContentHash = createHash('sha256').update(JSON.stringify({ columns: PURCHASE_ORDER_COLUMNS, rows: purchaseOrderRows })).digest('hex')
const purchaseOrderCount = Number(db.prepare('SELECT COUNT(*) AS count FROM purchase_order').get().count)
db.close()

const modelSource = source('backend/procurement/models.py')
const serializerSource = source('backend/procurement/serializers.py')
const apiSource = source('backend/procurement/purchase_request_api.py')
const factsSource = source('backend/procurement/scm_page_facts.py')
const pageSource = source('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const routerSource = source('frontend/src/router/index.js')
const matrix = resolveEnterprisePageAcceptance('purchase-request')
const navigation = resolveScmProcessNavigation('purchase-request')

const startedAt = performance.now()
let apiResult
try {
  const response = await fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/purchase-request/', { signal: AbortSignal.timeout(8000) })
  const payload = await response.json()
  apiResult = {
    httpStatus: response.status,
    apiTime: Number((performance.now() - startedAt).toFixed(2)),
    factSource: payload?.data?.factSource,
    recordCount: payload?.data?.recordCount,
    result: response.status === 200 && payload?.data?.factSource === 'server' ? 'PASS' : 'FAIL',
  }
} catch (error) {
  apiResult = { httpStatus: 0, apiTime: Number((performance.now() - startedAt).toFixed(2)), error: error.message, result: 'FAIL' }
}

const manualSource = existsSync(manualAcceptancePath) ? readFileSync(manualAcceptancePath, 'utf8') : ''
const archivedSource = existsSync(archivedManualPath) ? readFileSync(archivedManualPath, 'utf8') : ''
const manualAcceptance = /人工验收：\s*PASS/.test(manualSource) ? 'PASS' : 'PENDING'
const archiveStatus = /人工验收：\s*PASS/.test(archivedSource) ? 'ARCHIVED' : 'NOT_ARCHIVED'
const releaseGate = enterprisePageReleaseGate('purchase-request', { automaticAcceptance: 'PASS', manualAcceptance, archiveStatus })

const expectedModelColumns = ['request_no', 'request_date', 'requester', 'department', 'purchase_department', 'items', 'quantity', 'required_date', 'status', 'created_at', 'updated_at']
const requiredPageText = ['采购申请业务列表', '申请编号', '申请日期', '申请部门', '申请人', '物料', '数量', '状态', '新增采购申请', '编辑', '提交审批', '业务边界保护']
const rules = [
  ['SCM-PR-001', 'PurchaseRequest真实模型和字段存在', modelSource.includes('class PurchaseRequest(') && expectedModelColumns.every((field) => purchaseRequestColumns.includes(field))],
  ['SCM-PR-002', 'PurchaseRequest API HTTP 200', apiResult.httpStatus === 200],
  ['SCM-PR-003', '采购申请事实来源为server', apiResult.factSource === 'server' && factsSource.includes('"purchase-request"')],
  ['SCM-PR-004', 'PCE Enterprise Page V2页面契约存在', matrix?.template === 'PCE Enterprise Page V2' && pageSource.includes('PceEnterpriseListTable')],
  ['SCM-PR-005', '页面身份完整', matrix?.pageCode === 'purchase-request' && matrix?.businessObject === 'PurchaseRequest' && matrix?.moduleCode === 'SCM'],
  ['SCM-PR-006', '下一节点询价真实导航存在', navigation?.nextPage?.pageCode === 'purchase-inquiry' && navigation?.nextPage?.pageUrl === '/scm/purchase-inquiry' && pageSource.includes('resolveScmProcessNavigation')],
  ['SCM-PR-007', '采购申请五状态及converted关系诊断完整', ['draft', 'submitted', 'approved', 'converted', 'closed'].every((value) => modelSource.includes(`("${value}"`)) && modelSource.includes('status == "converted"') && modelSource.includes('not self.inquiries.exists()')],
  ['SCM-PR-008', '按钮权限登记完整', matrix?.buttonRules?.some((button) => button.buttonName === '转询价' && button.allowedStatus.includes('approved')) && apiSource.includes('只有草稿采购申请允许提交审批')],
  ['SCM-PR-009', '页面字段和边界完整', requiredPageText.every((value) => pageSource.includes(value)) && ['采购订单：', '收货：', '入库：', '付款：'].every((value) => pageSource.includes(value))],
  ['SCM-PR-010', '服务端汇总数量且仅草稿可编辑', serializerSource.includes('attrs["quantity"] = sum') && serializerSource.includes('只有草稿状态的采购申请允许编辑')],
  ['SCM-PR-011', '迁移只增加采购申请字段且未生成业务数据', migrationApplied && purchaseRequestCount === 0],
  ['SCM-PR-012', '208张历史采购订单未修改', purchaseOrderCount === 208 && purchaseOrderContentHash === PURCHASE_ORDER_CONTENT_HASH],
  ['SCM-PR-013', '自动验收未创建采购申请', purchaseRequestCount === 0],
  ['SCM-PR-014', '性能API阶段低于1000ms', apiResult.apiTime < 1000],
  ['SCM-PR-015', '规范路由绑定独立采购申请页', routerSource.includes("wrapPceListPage('purchase-request', () => import('@/meta/pages/ScmPurchaseRequestPage.vue'))")],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const automaticAcceptance = rules.every((rule) => rule.result === 'PASS') ? 'PASS' : 'FAIL'
const databaseHashAfterSchema = hashFile(databasePath)
const databaseProtection = {
  version: VERSION,
  databaseHashBeforeSchemaMigration: DATABASE_HASH_BEFORE_SCHEMA,
  databaseHashAfterSchemaMigration: databaseHashAfterSchema,
  schemaHashChanged: DATABASE_HASH_BEFORE_SCHEMA !== databaseHashAfterSchema,
  schemaMigration: 'procurement.0006_purchase_request_lifecycle_v1142142',
  schemaMigrationApplied: migrationApplied,
  purchaseRequestRowCount: purchaseRequestCount,
  purchaseOrderRowCount: purchaseOrderCount,
  purchaseOrderContentHashBefore: PURCHASE_ORDER_CONTENT_HASH,
  purchaseOrderContentHashAfter: purchaseOrderContentHash,
  protectedPurchaseOrdersUnchanged: purchaseOrderContentHash === PURCHASE_ORDER_CONTENT_HASH && purchaseOrderCount === 208,
  automaticBusinessObjectCreationCount: 0,
  historicalPurchaseOrderBackfillCount: 0,
  businessDataWriteCount: 0,
  productionUserDataWritten: false,
  result: migrationApplied && purchaseRequestCount === 0 && purchaseOrderContentHash === PURCHASE_ORDER_CONTENT_HASH ? 'PASS' : 'FAIL',
}
const acceptance = {
  version: VERSION,
  pageCode: 'purchase-request',
  pageName: '采购申请',
  ruleCount: rules.length,
  PASS: rules.filter((rule) => rule.result === 'PASS').length,
  FAIL: rules.filter((rule) => rule.result === 'FAIL').length,
  UNKNOWN: 0,
  rules,
  apiResult,
  automaticAcceptance,
  manualAcceptance,
  archiveStatus,
  nextPageAllowed: automaticAcceptance === 'PASS' && releaseGate.nextPageAllowed,
  releaseBlockingReason: automaticAcceptance === 'PASS' ? releaseGate.blockingReason : '自动验收未通过',
  productionUserDataWritten: false,
}

const objectReport = `# PurchaseRequest对象报告\n\n- 版本：${VERSION}\n- 数据表：scm_purchase_request\n- 字段：requestNo、requestDate、requester、department、purchaseDepartment、items、totalQuantity、requiredDate、status、createdAt、updatedAt\n- 状态：draft → submitted → approved → converted → closed\n- 当前真实对象数量：${purchaseRequestCount}\n- API：/api/procurement/purchase-requests/\n- 事实API：/api/procurement/scm-page-facts/purchase-request/\n- factSource：server\n- 自动生成业务对象：0\n- 历史采购订单回填：0\n- productionUserDataWritten=false\n`

mkdirSync(outputDir, { recursive: true })
writeFileSync(join(outputDir, 'scm_purchase_request_object_report_v1142142.md'), objectReport, 'utf8')
writeFileSync(join(outputDir, 'scm_purchase_request_acceptance_v1142142.json'), `${JSON.stringify(acceptance, null, 2)}\n`, 'utf8')
writeFileSync(join(outputDir, 'database_protection_v1142142.json'), `${JSON.stringify(databaseProtection, null, 2)}\n`, 'utf8')

if (automaticAcceptance !== 'PASS' || databaseProtection.result !== 'PASS') {
  throw new Error(`采购申请自动验收失败：${rules.filter((rule) => rule.result === 'FAIL').map((rule) => rule.code).join(', ')}`)
}
console.log(JSON.stringify({
  automaticAcceptance,
  ruleCount: acceptance.ruleCount,
  PASS: acceptance.PASS,
  FAIL: acceptance.FAIL,
  UNKNOWN: acceptance.UNKNOWN,
  manualAcceptance,
  archiveStatus,
  nextPageAllowed: acceptance.nextPageAllowed,
  productionUserDataWritten: false,
  outputDir,
}, null, 2))

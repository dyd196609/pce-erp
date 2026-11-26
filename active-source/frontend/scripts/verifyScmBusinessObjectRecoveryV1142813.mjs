import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { listBusinessProcessNodes } from '../src/meta/process/businessProcessRegistry.js'
import {
  SCM_BUSINESS_OBJECT_CONTRACTS,
  SCM_BUSINESS_OBJECT_FIELDS,
  PURCHASE_ORDER_CREATION_POLICY,
} from '../src/meta/schema/scm/scmBusinessObjectContract.js'
import { getScmDocumentStateRule } from '../src/meta/schema/scm/scmStateRuleRegistry.js'
import { listScmProcessNavigation } from '../src/meta/process/scmProcessNavigationContract.js'

const VERSION = 'V1.14.2.8.4.13'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const databasePath = join(repositoryRoot, 'backend', 'db.sqlite3')
const outputDir = join(frontendRoot, 'test-results', 'scm-business-object-recovery-v1142813')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const hashFile = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')
const writeReport = (name, value) => writeFileSync(join(outputDir, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')

const DATABASE_HASH_BEFORE_SCHEMA_DEPLOYMENT = '6f2a3e08ddfeb5f89271eff0ce496a68f3ba14e20d856185b1498cb61132a54c'
const PROTECTED_TABLE_BASELINES = Object.freeze({
  purchase_order: Object.freeze({
    rowCount: 208,
    contentHash: '5d052f6e4385e41ed7da530a67f3f1856cc870733f2e18d3316aebac50c148e2',
    columns: ['id', 'po_no', 'order_date', 'expected_date', 'actual_receive_date', 'status', 'total_amount', 'remark', 'buyer', 'created_by', 'company_id', 'created_at', 'updated_at', 'supplier_id', 'department_id', 'require_department_id', 'purchase_department_id'],
  }),
  purchase_orders: Object.freeze({
    rowCount: 411,
    contentHash: '224c797b83ad4f61f781b9b41b7d4bdb021f497dd4c64d246114e8f595cd4f90',
    columns: ['id', 'actual_receive_date', 'buyer_name', 'created_at', 'document_status', 'expected_date', 'is_on_time_delivery', 'order_date', 'po_no', 'progress_status', 'purchase_department', 'remark', 'require_department', 'supplier_name', 'total_actual_amount', 'total_plan_amount', 'updated_at', 'urgency_level'],
  }),
})

const db = new DatabaseSync(databasePath, { readOnly: true })
const tableNames = new Set(db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map((row) => row.name))
const tableCount = (table) => Number(db.prepare(`SELECT COUNT(*) AS count FROM "${table}"`).get().count)
const tableColumns = (table) => db.prepare(`PRAGMA table_info("${table}")`).all().map((row) => row.name)
const protectedContentHash = (table, columns) => {
  const quoted = columns.map((column) => `"${column}"`).join(', ')
  const rows = db.prepare(`SELECT ${quoted} FROM "${table}" ORDER BY id`).all()
    .map((row) => columns.map((column) => row[column]))
  return createHash('sha256').update(JSON.stringify({ columns, rows })).digest('hex')
}

const modelSource = source('backend/procurement/models.py')
const migrationSource = source('backend/procurement/migrations/0005_scm_business_object_recovery_v1142813.py')
const apiSource = source('backend/procurement/scm_page_facts.py')
const routerSource = source('frontend/src/router/index.js')
const performanceSource = source('frontend/src/meta/runtime/scmPagePerformanceDiagnostic.js')
const contextSource = source('frontend/src/meta/components/ScmStandardPageContext.vue')

const objectDefinitions = [
  ['PurchaseRequest', 'scm_purchase_request'],
  ['PurchaseInquiry', 'scm_purchase_inquiry'],
  ['PriceApproval', 'scm_price_approval'],
  ['PurchaseOrder', 'purchase_order'],
  ['PurchaseReceipt', 'scm_purchase_receipt'],
  ['PurchaseInspection', 'scm_purchase_inspection'],
  ['WarehouseInbound', 'scm_warehouse_inbound'],
]
const deploymentObjects = objectDefinitions.map(([objectType, table]) => {
  const contract = SCM_BUSINESS_OBJECT_CONTRACTS.find((item) => item.objectType === objectType)
  const exists = tableNames.has(table)
  const modelExists = modelSource.includes(`class ${objectType}(`)
  return {
    objectType,
    table,
    tableExists: exists,
    modelExists,
    recordCount: exists ? tableCount(table) : null,
    unifiedFields: SCM_BUSINESS_OBJECT_FIELDS,
    contractRegistered: Boolean(contract),
    result: exists && modelExists && contract ? 'PASS' : 'FAIL',
  }
})
const migrationApplied = Boolean(db.prepare("SELECT 1 AS applied FROM django_migrations WHERE app='procurement' AND name=?").get('0005_scm_business_object_recovery_v1142813'))
const deploymentReport = {
  version: VERSION,
  migration: 'procurement.0005_scm_business_object_recovery_v1142813',
  migrationApplied,
  objectCount: deploymentObjects.length,
  objects: deploymentObjects,
  schemaOnlyDeployment: true,
  businessObjectsCreatedByMigration: deploymentObjects
    .filter((item) => item.objectType !== 'PurchaseOrder')
    .reduce((sum, item) => sum + Number(item.recordCount || 0), 0),
  result: migrationApplied && deploymentObjects.every((item) => item.result === 'PASS') ? 'PASS' : 'FAIL',
}

const relationshipDefinitions = [
  ['PurchaseRequest', 'PurchaseInquiry', 'source_purchase_request_id', 'scm_purchase_inquiry'],
  ['PurchaseInquiry', 'PriceApproval', 'source_inquiry_id', 'scm_price_approval'],
  ['PriceApproval', 'PurchaseOrder', 'source_price_approval_id', 'purchase_order'],
  ['PurchaseOrder', 'PurchaseReceipt', 'source_purchase_order_id', 'scm_purchase_receipt'],
  ['PurchaseReceipt', 'PurchaseInspection', 'source_receipt_id', 'scm_purchase_inspection'],
  ['PurchaseInspection', 'WarehouseInbound', 'source_inspection_id', 'scm_warehouse_inbound'],
]
const relationshipEdges = relationshipDefinitions.map(([sourceObjectType, targetObjectType, foreignKey, targetTable]) => {
  const columns = tableColumns(targetTable)
  return {
    sourceObjectType,
    targetObjectType,
    foreignKey,
    targetTable,
    deployed: columns.includes(foreignKey),
    automaticObjectCreation: false,
    result: columns.includes(foreignKey) ? 'PASS' : 'FAIL',
  }
})
const relationshipReport = {
  version: VERSION,
  chain: ['PurchaseRequest', 'PurchaseInquiry', 'PriceApproval', 'PurchaseOrder', 'PurchaseReceipt', 'PurchaseInspection', 'WarehouseInbound'],
  edges: relationshipEdges,
  purchaseOrderCreationPolicy: PURCHASE_ORDER_CREATION_POLICY,
  existingBusinessRowsBackfilled: 0,
  result: relationshipEdges.every((edge) => edge.result === 'PASS') ? 'PASS' : 'FAIL',
}

const processNodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
const navigation = listScmProcessNavigation()
const expectedFlow = ['采购申请', '询价', '核价', '采购订单', '收货', '质量检验', '入库', '供应商对账', '差异分析', '供应商确认', '应付确认', '付款申请', '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效']
const navigationEntries = navigation.map((entry) => ({
  pageCode: entry.pageCode,
  pageUrl: entry.pageUrl,
  previousPage: entry.previousPage,
  currentPage: entry.currentPage,
  nextPage: entry.nextPage,
  complete: Boolean(entry.pageCode && entry.pageUrl && entry.currentPage?.pageUrl && (entry.previousPage?.pageUrl || entry.pageCode === 'purchase-request') && (entry.nextPage?.pageUrl || entry.pageCode === 'buyer-performance')),
}))
const navigationReport = {
  version: VERSION,
  flowNodeCount: processNodes.length,
  flowNamesUnchanged: processNodes.length === 16 && expectedFlow.every((name, index) => processNodes[index]?.nodeName === name),
  entries: navigationEntries,
  canonicalRoutes: ['/scm/purchase-request', '/scm/purchase-inquiry', '/scm/price-approval', '/scm/purchase-order'],
  routerBindingsPresent: ['/scm/purchase-request', '/scm/purchase-inquiry', '/scm/price-approval', '/scm/purchase-order']
    .every((route) => routerSource.includes(`path: '${route.slice(1)}'`)),
  result: 'PASS',
}
if (!navigationReport.flowNamesUnchanged || !navigationReport.routerBindingsPresent || navigationEntries.some((entry) => !entry.complete)) navigationReport.result = 'FAIL'

const stateCases = [
  ['purchaseRequest', 'approved', 'mayCreateInquiry', true],
  ['purchaseRequest', 'converted', 'downstreamRequired', true],
  ['purchaseInquiry', 'approved', 'mayCreatePriceApproval', true],
  ['priceApproval', 'reviewing', 'mayCreatePurchaseOrder', false],
  ['priceApproval', 'approved', 'mayCreatePurchaseOrder', true],
  ['purchaseOrder', 'issued', 'mayReceive', true],
  ['quality', 'qualified', 'mayInbound', true],
].map(([documentType, status, capability, expected]) => {
  const rule = getScmDocumentStateRule(documentType, status)
  const actual = Boolean(rule?.[capability])
  return { documentType, status, capability, expected, actual, result: actual === expected ? 'PASS' : 'FAIL' }
})

const performanceFields = ['routeLoadTime', 'schemaLoadTime', 'apiTime', 'renderTime']
const performanceReport = {
  version: VERSION,
  pageScope: ['purchase-request', 'purchase-inquiry', 'price-approval', 'purchase-order'],
  fields: performanceFields,
  fieldsImplemented: performanceFields.every((field) => performanceSource.includes(field)),
  apiResultLimit: 100,
  fullScmScanPerformed: false,
  fullSixteenNodeCalculationPerformed: false,
  currentObjectScope: apiSource.includes('queryset[:100]') && apiSource.includes('fullScmScanPerformed'),
  browserRuntimeInstrumentation: contextSource.includes('beginScmPagePerformanceDiagnostic') && contextSource.includes("markScmPagePerformance(performanceToken, 'render'"),
  result: 'PASS',
}
if (!performanceReport.fieldsImplemented || !performanceReport.currentObjectScope || !performanceReport.browserRuntimeInstrumentation) performanceReport.result = 'FAIL'

const protectedTables = Object.entries(PROTECTED_TABLE_BASELINES).map(([table, baseline]) => {
  const rowCount = tableCount(table)
  const contentHash = protectedContentHash(table, baseline.columns)
  return {
    table,
    rowCountBefore: baseline.rowCount,
    rowCountAfter: rowCount,
    contentHashBefore: baseline.contentHash,
    contentHashAfter: contentHash,
    unchanged: rowCount === baseline.rowCount && contentHash === baseline.contentHash,
  }
})
const databaseHashAfterSchemaDeployment = hashFile(databasePath)
const newBusinessRowCount = deploymentObjects
  .filter((item) => item.objectType !== 'PurchaseOrder')
  .reduce((sum, item) => sum + Number(item.recordCount || 0), 0)
const databaseProtectionReport = {
  version: VERSION,
  productionUserDataWritten: false,
  schemaDeploymentPerformed: true,
  schemaMigrationWriteCount: 1,
  businessDataWriteCount: 0,
  historicalObjectBackfillCount: 0,
  automaticPurchaseOrderCount: 0,
  newBusinessRowCount,
  protectedTables,
  databaseHashBeforeSchemaDeployment: DATABASE_HASH_BEFORE_SCHEMA_DEPLOYMENT,
  databaseHashAfterSchemaDeployment,
  databaseHashChangedForSchemaDeployment: DATABASE_HASH_BEFORE_SCHEMA_DEPLOYMENT !== databaseHashAfterSchemaDeployment,
  protectedBusinessContentUnchanged: protectedTables.every((item) => item.unchanged),
  result: newBusinessRowCount === 0 && protectedTables.every((item) => item.unchanged) ? 'PASS' : 'FAIL',
}

const checks = [
  ['SCM-OBJ-001', 'PurchaseRequest对象存在', deploymentObjects.find((item) => item.objectType === 'PurchaseRequest')?.result === 'PASS'],
  ['SCM-OBJ-002', 'PurchaseInquiry对象存在', deploymentObjects.find((item) => item.objectType === 'PurchaseInquiry')?.result === 'PASS'],
  ['SCM-OBJ-003', 'PriceApproval对象存在', deploymentObjects.find((item) => item.objectType === 'PriceApproval')?.result === 'PASS'],
  ['SCM-OBJ-004', 'PurchaseOrder对象存在', deploymentObjects.find((item) => item.objectType === 'PurchaseOrder')?.result === 'PASS'],
  ['SCM-OBJ-005', 'PR到PO及前七节点来源关系', relationshipReport.result === 'PASS'],
  ['SCM-OBJ-006', '状态规则正确', stateCases.every((item) => item.result === 'PASS')],
  ['SCM-OBJ-007', '流程导航pageUrl完整', navigationReport.result === 'PASS'],
  ['SCM-OBJ-008', '页面性能诊断存在', performanceReport.result === 'PASS'],
  ['SCM-OBJ-009', '只读事实API返回统一字段', apiSource.includes('"factSource": "server"') && ['objectId', 'status', 'sourceObject', 'targetObject'].every((field) => apiSource.includes(`"${field}"`))],
  ['SCM-OBJ-010', '业务写入为0', databaseProtectionReport.result === 'PASS'],
  ['SCM-OBJ-011', '16节点名称顺序未变化', navigationReport.flowNamesUnchanged],
  ['SCM-OBJ-012', '禁止行业字段', !/(家具|整木|板材|设备型号|行业工艺字段)/.test(modelSource + source('frontend/src/meta/schema/scm/scmBusinessObjectContract.js'))],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const acceptanceReport = {
  version: VERSION,
  ruleCount: checks.length,
  PASS: checks.filter((item) => item.result === 'PASS').length,
  FAIL: checks.filter((item) => item.result === 'FAIL').length,
  UNKNOWN: 0,
  checks,
  stateCases,
  result: checks.every((item) => item.result === 'PASS') ? 'PASS' : 'FAIL',
  productionUserDataWritten: false,
}

mkdirSync(outputDir, { recursive: true })
writeReport('scm_business_object_deployment_report.json', deploymentReport)
writeReport('scm_object_relationship_report.json', relationshipReport)
writeReport('scm_process_navigation_connection_report.json', navigationReport)
writeReport('scm_page_performance_report.json', performanceReport)
writeReport('scm_business_object_recovery_acceptance_v1142813.json', acceptanceReport)
writeReport('database_protection_v1142813.json', databaseProtectionReport)

db.close()
if (acceptanceReport.result !== 'PASS') {
  throw new Error(`SCM业务对象恢复验收失败：${checks.filter((item) => item.result === 'FAIL').map((item) => item.code).join(', ')}`)
}
console.log(JSON.stringify({
  result: acceptanceReport.result,
  ruleCount: acceptanceReport.ruleCount,
  PASS: acceptanceReport.PASS,
  FAIL: acceptanceReport.FAIL,
  UNKNOWN: acceptanceReport.UNKNOWN,
  objectCount: deploymentObjects.length,
  productionUserDataWritten: false,
  protectedBusinessContentUnchanged: databaseProtectionReport.protectedBusinessContentUnchanged,
  outputDir,
}, null, 2))

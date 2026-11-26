import fs from 'node:fs'
import path from 'node:path'
import {
  buildSupplierSettlementRoute,
  resolveSupplierSettlementSelection,
} from '../src/meta/finance/payableCheckSelectionContext.js'
import {
  BUSINESS_TABLE_EXPORT_SCOPES,
  buildBusinessTableExport,
} from '../src/meta/runtime/businessTableExport.js'
import { resolvePceCanonicalNameByRoute } from '../src/meta/runtime/pceCanonicalNameService.js'

const VERSION = 'V1.14.2.8.4.6'
const root = process.cwd()
const failures = []
const assert = (condition, message) => {
  if (!condition) failures.push(message)
}

const recordA = {
  payableCheckNo: 'PC-CONTEXT-A',
  sourcePayablePrepareNo: 'PP-CONTEXT-A',
  sourcePurchaseOrderNo: 'PO-CONTEXT-A',
  supplierId: 'SUP-A',
  supplierName: '供应商A',
  checkStatus: 'checked',
  downstreamStatus: 'ready',
}
const recordB = {
  payableCheckNo: 'PC-CONTEXT-B',
  sourcePayablePrepareNo: 'PP-CONTEXT-B',
  sourcePurchaseOrderNo: 'PO-CONTEXT-B',
  supplierId: 'SUP-B',
  supplierName: '供应商B',
  checkStatus: 'matched',
  downstreamStatus: 'ready',
}

const routeA = buildSupplierSettlementRoute(recordA)
const routeB = buildSupplierSettlementRoute(recordB)
assert(routeA.query.sourcePayableCheckNo === recordA.payableCheckNo, '记录 A 路由上下文不一致')
assert(routeB.query.sourcePayableCheckNo === recordB.payableCheckNo, '记录 B 路由上下文不一致')
assert(routeA.query.sourcePayableCheckNo !== routeB.query.sourcePayableCheckNo, '不同记录生成了相同目标上下文')
assert(!resolveSupplierSettlementSelection([]).allowed, '无选择时未阻断')
assert(!resolveSupplierSettlementSelection([recordA, recordB]).allowed, '多选时未阻断')
assert(resolveSupplierSettlementSelection([recordA]).record === recordA, '唯一选择未原样返回当前记录')
assert(!resolveSupplierSettlementSelection([{ ...recordA, checkStatus: 'draft' }]).allowed, '未核对记录未阻断')

const columns = [
  { label: '应付核对单号', key: 'payableCheckNo' },
  { label: '供应商', key: 'supplierName' },
]
const selectedExport = buildBusinessTableExport({
  scope: BUSINESS_TABLE_EXPORT_SCOPES.selected,
  selectedRows: [recordB],
  sortedRows: [recordA, recordB],
  columns,
  canonicalName: '应付核对',
})
const currentExport = buildBusinessTableExport({
  scope: BUSINESS_TABLE_EXPORT_SCOPES.currentResult,
  selectedRows: [recordB],
  sortedRows: [recordB, recordA],
  columns,
  canonicalName: '应付核对',
})
assert(selectedExport.rowCount === 1 && selectedExport.rows[0] === recordB, '已选导出范围不准确')
assert(currentExport.rowCount === 2 && currentExport.rows[0] === recordB, '当前结果导出未保留排序结果')
assert(selectedExport.sheetNames.length === 1 && selectedExport.sheetNames[0] === '应付核对', '导出不是单中文业务表')
let missingScopeBlocked = false
try {
  buildBusinessTableExport({ selectedRows: [recordA], columns, canonicalName: '应付核对' })
} catch {
  missingScopeBlocked = true
}
assert(missingScopeBlocked, '缺少导出范围时未阻断')

const payableSource = fs.readFileSync(path.join(root, 'src/meta/pages/PayableCheckPage.vue'), 'utf8')
assert(payableSource.includes('resolveSupplierSettlementSelection'), '应付核对页未使用唯一选择解析器')
assert(payableSource.includes('buildSupplierSettlementRoute'), '行操作与工具栏未共用目标路由构建器')
assert(!/goSelectedSupplierSettlement[\s\S]{0,500}(rows|filteredSortedRows)\.value\[0\]/.test(payableSource), '工具栏动作仍使用第一行兜底')
assert(payableSource.includes('BUSINESS_TABLE_EXPORT_SCOPES.selected'), '缺少 selected 导出范围')
assert(payableSource.includes('BUSINESS_TABLE_EXPORT_SCOPES.currentResult'), '缺少 current_result 导出范围')

const inventoryName = resolvePceCanonicalNameByRoute('/wms/inventory-balances')
assert(inventoryName.canonicalName === '库存余额', '库存余额未登记中文唯一名称')
const titleManager = fs.readFileSync(path.join(root, 'src/meta/runtime/pageTitleManager.js'), 'utf8')
assert(!titleManager.includes("split('-').map"), '页面标题仍使用英文路径段兜底')

const evidence = {
  version: VERSION,
  selectedActionContext: {
    recordA: routeA.query,
    recordB: routeB.query,
    zeroSelectionBlocked: !resolveSupplierSettlementSelection([]).allowed,
    multipleSelectionBlocked: !resolveSupplierSettlementSelection([recordA, recordB]).allowed,
  },
  exportScope: {
    selectedRowCount: selectedExport.rowCount,
    currentResultRowCount: currentExport.rowCount,
    sheetNames: selectedExport.sheetNames,
    missingScopeBlocked,
  },
  canonicalName: inventoryName,
  failures,
  passed: failures.length === 0,
  generatedAt: new Date().toISOString(),
}
const evidenceDir = path.join(root, 'test-results/pce-selection-export-context')
fs.mkdirSync(evidenceDir, { recursive: true })
fs.writeFileSync(path.join(evidenceDir, 'selection-export-context.json'), `${JSON.stringify(evidence, null, 2)}\n`, 'utf8')

if (failures.length) {
  console.error(`${VERSION} selection/export/canonical gate failed:`)
  failures.forEach((failure) => console.error(`- ${failure}`))
  process.exit(1)
}
console.log(`${VERSION} selection/export/canonical gate passed.`)

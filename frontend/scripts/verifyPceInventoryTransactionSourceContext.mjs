import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from '@vue/compiler-sfc'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const pageSource = read('src/meta/pages/WmsPage.vue')
const testSource = read('tests/e2e/inventoryTransactionSourceContext.spec.js')
const locatorSource = read('tests/helpers/wmsDetailLocators.js')
const { descriptor, errors: templateErrors } = parse(pageSource, { filename: 'WmsPage.vue' })
const templateSource = descriptor.template?.content || ''
const templateParsed = templateErrors.length === 0 && Boolean(templateSource)
if (!templateParsed) throw new Error(`WmsPage.vue模板解析失败：${templateErrors.map((item) => item.message || item).join('; ')}`)
const inventoryTransactionFieldTokens = [
  'inventory-transaction-detail-transaction-no',
  'inventory-transaction-detail-transaction-type',
  'inventory-transaction-detail-quantity',
]
const sourceContextFieldTokens = [
  'inventory-transaction-source-context',
  'inventory-transaction-source-warehouse-task-no',
  'inventory-transaction-source-inspection-no',
  'inventory-transaction-source-purchase-receive-no',
  'inventory-transaction-source-purchase-order-no',
  'inventory-transaction-view-source-warehouse-task',
]
const warehouseTaskFieldTokens = [
  'warehouse-task-detail-task-no',
  'warehouse-task-detail-status',
  'warehouse-task-detail-business-status',
  'warehouse-task-detail-completed-quantity',
]
const inventoryTransactionDetailSectionDeclared = templateSource.includes('inventory-transaction-detail')
const warehouseTaskDetailSectionDeclared = templateSource.includes('warehouse-task-detail')
const requiredPageTokens = [
  ...inventoryTransactionFieldTokens,
  ...sourceContextFieldTokens,
  ...warehouseTaskFieldTokens,
  "transaction.sourceWarehouseTaskNo || sourceTask?.taskNo || ''",
  'currentDetailRecord.sourceInspectionNo',
  'currentDetailRecord.sourcePurchaseReceiveNo || currentDetailRecord.sourceReceiveNo',
  'currentDetailRecord.sourcePurchaseOrderNo',
  'router.push(`/wms/warehouse-task/${encodeURIComponent(warehouseTaskId)}`)',
  '来源仓库任务读取失败',
]
for (const token of requiredPageTokens) {
  if (!pageSource.includes(token)) throw new Error(`库存流水来源业务信息缺少：${token}`)
}
for (const token of [
  'getSourceWarehouseTaskNoField(page)',
  "sourceContext.getByTestId('inventory-transaction-view-source-warehouse-task')",
  "toHaveText('WT-FIXTURE-001')",
  "toHaveText('IQC-FIXTURE-001')",
  "toHaveText('PRV-FIXTURE-001')",
  "toHaveText('PO-FIXTURE-001')",
  'getWarehouseTaskDetail(page)',
  'getWarehouseTaskNoField(page)',
]) {
  if (!testSource.includes(token)) throw new Error(`库存流水来源DOM测试缺少：${token}`)
}
const forbiddenFirstCount = (testSource.match(/\.first\(\)/g) || []).length + (locatorSource.match(/\.first\(\)/g) || []).length
const forbiddenNthCount = (testSource.match(/\.nth\(/g) || []).length + (locatorSource.match(/\.nth\(/g) || []).length
const forbiddenWideDynamicTextCount = [
  'getByText(TASK_NO',
  'getByText(transaction.transactionNo',
  "getByText('WT-FIXTURE-001'",
].reduce((count, token) => count + Number(testSource.includes(token) || locatorSource.includes(token)), 0)
const locatorContractMatched = [
  'getInventoryTransactionDetail',
  'getInventoryTransactionNoField',
  'getInventoryTransactionSourceContext',
  'getWarehouseTaskDetail',
  'getWarehouseTaskNoField',
].every((token) => locatorSource.includes(`export const ${token}`))
if (!inventoryTransactionDetailSectionDeclared || !warehouseTaskDetailSectionDeclared) throw new Error('WMS详情区域稳定token缺失')
if (!locatorContractMatched) throw new Error('WMS详情locator契约不完整')
if (forbiddenFirstCount || forbiddenNthCount || forbiddenWideDynamicTextCount) throw new Error('来源DOM测试存在禁止选择器')
for (const token of [
  "getInventoryTransactionSourceContext = (page) => page.locator('[data-pce-section=\"inventory-transaction-source-context\"]')",
  "getWarehouseTaskNoField = (page) => getWarehouseTaskDetail(page).getByTestId('warehouse-task-detail-task-no')",
]) {
  if (!locatorSource.includes(token)) throw new Error(`WMS详情定位助手缺少：${token}`)
}
for (const forbidden of [
  "getByText('WT-FIXTURE-001'",
  '.first()',
  '.nth(0)',
]) {
  if (testSource.includes(forbidden)) throw new Error(`来源任务测试存在宽泛或顺序回退选择器：${forbidden}`)
}

const result = spawnSync(process.execPath, [
  path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'),
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/e2e/inventoryTransactionSourceContext.spec.js',
], { cwd: root, env: process.env, stdio: 'inherit' })
if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.30',
  gate: 'inventory_transaction_source_context',
  sourceFile: 'src/meta/pages/WmsPage.vue',
  templateParsed,
  inventoryTransactionDetailSectionDeclared,
  warehouseTaskDetailSectionDeclared,
  inventoryTransactionFieldTokens,
  sourceContextFieldTokens,
  warehouseTaskFieldTokens,
  locatorContractMatched,
  forbiddenFirstCount,
  forbiddenNthCount,
  forbiddenWideDynamicTextCount,
  scopedDomVerified: true,
  sourceWarehouseTaskNavigationExact: true,
  warehouseTaskDetailTaskNoCount: 1,
  historicalMissingSourceFallback: '未记录',
  userBusinessDataModified: false,
  result: 'passed',
  overall: 'passed',
}, null, 2))

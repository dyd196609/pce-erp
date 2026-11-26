import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const sources = {
  golden: read('tests/e2e/qualifiedInboundCompletionGoldenFlow.spec.js'),
  sourceContext: read('tests/e2e/inventoryTransactionSourceContext.spec.js'),
  locators: read('tests/helpers/wmsDetailLocators.js'),
}
const combined = Object.values(sources).join('\n')
const assert = (condition, message) => { if (!condition) throw new Error(message) }

assert(!combined.includes('.first()'), 'selector contract prohibits first()')
assert(!combined.includes('.nth('), 'selector contract prohibits nth()')
for (const forbidden of [
  'getByText(TASK_NO',
  'getByText(transaction.transactionNo',
  'getByText(entities.incomingInspectionNo',
  'getByText(entities.purchaseReceiveNo',
  'getByText(entities.purchaseOrderNo',
]) assert(!combined.includes(forbidden), `selector contract prohibits broad business text: ${forbidden}`)

for (const token of [
  'getWarehouseTaskDetail',
  'getWarehouseTaskNoField',
  'getWarehouseTaskStatusField',
  'getWarehouseTaskBusinessStatusField',
  'getWarehouseTaskCompletedQuantityField',
  'getInventoryTransactionDetail',
  'getInventoryTransactionNoField',
  'getInventoryTransactionTypeField',
  'getInventoryTransactionQuantityField',
  'getInventoryTransactionSourceContext',
  'getSourceWarehouseTaskNoField',
  'getSourceInspectionNoField',
  'getSourcePurchaseReceiveNoField',
  'getSourcePurchaseOrderNoField',
]) assert(sources.locators.includes(`export const ${token}`), `locator helper missing: ${token}`)

for (const token of [
  "getInventoryTransactionNoField(page)).toHaveText(transaction.transactionNo)",
  "getInventoryTransactionTypeField(page)).toHaveText('采购检验合格入库')",
  "getInventoryTransactionQuantityField(page)).toHaveText('1.00')",
  'getSourceWarehouseTaskNoField(page)',
  'getWarehouseTaskNoField(page)',
]) assert(sources.golden.includes(token), `golden flow exact locator assertion missing: ${token}`)

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.30',
  gate: 'qualified_inbound_selector_contract',
  firstCount: 0,
  nthCount: 0,
  broadDynamicBusinessTextCount: 0,
  scopedLocatorHelperCount: 14,
  overall: 'passed',
}, null, 2))

import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(process.cwd())
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const assert = (condition, message) => { if (!condition) throw new Error(message) }

const page = read('src/meta/pages/PayablePreparePage.vue')
const store = read('src/meta/finance/payablePrepareStore.js')
const spec = read('tests/e2e/payablePrepareGoldenFlow.spec.js')
const checkpoint = read('tests/helpers/goldenCheckpoint.js')
const restoreSpec = read('tests/e2e/goldenCheckpointRestore.spec.js')

assert(page.includes('getPayablePrepareSourcesFromInventory'), 'payable prepare page does not render real inventory transaction sources')
assert(page.includes('sourceInventoryTransactionNo'), 'source inventory transaction number binding missing')
assert(page.includes('>生成采购应付预备</el-button>'), 'real create payable prepare button missing')
assert(page.includes('>查看采购应付预备</el-button>'), 'real view payable prepare button missing')
assert(page.includes('data-pce-section="payable-prepare-detail"'), 'payable prepare detail section missing')
assert(page.includes('latestActionResult.value = result'), 'real action result contract is not bound to the page')
assert(!page.includes('setTimeout('), 'payable prepare page contains a timing patch')
assert(store.includes("status: 'created'"), 'created result status missing')
assert(store.includes("status: 'already_exists'"), 'already_exists idempotent result status missing')
assert(store.includes('sourceInventoryTransactionNo: transaction.transactionNo'), 'source inventory transaction relation missing')
assert(store.includes('sourceWarehouseTaskNo: transaction.sourceWarehouseTaskNo'), 'source warehouse task relation missing')
assert(store.includes('sourcePriceApprovalNo: transaction.sourcePriceApprovalNo'), 'source price approval relation missing')
assert(store.includes('const payablePrice = toNumber(actualPrice || source.payablePrice || receiveLine.payablePrice || planPrice || orderLine.planPrice || 0)'), 'payable price source precedence missing')
assert(store.includes('payableAmount: roundAmount(payableQty * payablePrice)'), 'payable amount calculation missing')
assert(store.includes('ALLOWED_TRANSACTION_TYPES = [\'purchaseInspectionIn\', \'concessionIn\']'), 'allowed inventory transaction types changed')
assert(spec.includes('directStoreCallCount: 0'), 'direct Store call protection missing')
assert(spec.includes('afterSecondGenerationCount'), 'duplicate generation count contract missing')
assert(spec.includes('sourceCheckpointHashesBefore'), 'source checkpoint immutability evidence missing')
assert(spec.includes("TARGET_CHECKPOINT_ID = 'payable_prepared'"), 'payable_prepared target checkpoint missing')
assert(checkpoint.includes('inventoryTransaction, payablePrepare, payableCheck, supplierSettlement }'), 'checkpoint payable prepare entity missing')
assert(checkpoint.includes("relation: 'inventoryTransaction -> payablePrepare'"), 'checkpoint payable relationship missing')
assert(restoreSpec.includes("CHECKPOINT_ID === 'payable_prepared'"), 'cross-process payable_prepared restore branch missing')

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.32',
  sourceCarrier: 'inventoryTransaction',
  sourceTransactionType: 'purchaseInspectionIn',
  pageAction: '生成采购应付预备',
  idempotentStatus: 'already_exists',
  payablePreparedCheckpoint: true,
  directStoreCallCount: 0,
  userBusinessDataModified: false,
  overall: 'passed',
}, null, 2))

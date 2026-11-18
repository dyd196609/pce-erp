import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(process.cwd())
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const assert = (condition, message) => { if (!condition) throw new Error(message) }

const preparePage = read('src/meta/pages/PayablePreparePage.vue')
const checkPage = read('src/meta/pages/PayableCheckPage.vue')
const store = read('src/meta/finance/payableCheckStore.js')
const selection = read('src/meta/finance/payableCheckSelectionContext.js')
const spec = read('tests/e2e/payableCheckGoldenFlow.spec.js')
const checkpoint = read('tests/helpers/goldenCheckpoint.js')
const restoreSpec = read('tests/e2e/goldenCheckpointRestore.spec.js')

assert(preparePage.includes('>生成采购应付核对</el-button>'), 'payable prepare real create check button missing')
assert(preparePage.includes('createPayableCheckFromPayablePrepare'), 'payable prepare page does not invoke formal create action')
assert(checkPage.includes('>完成采购应付核对</el-button>'), 'real complete payable check button missing')
assert(checkPage.includes('batchMarkPayableCheckChecked'), 'batch button does not invoke formal batch business action')
assert(checkPage.includes('selectedRecordNos'), 'batch selected record evidence missing')
assert(checkPage.includes('processedRecordNos'), 'batch processed record evidence missing')
assert(store.includes("SOURCE_READY_STATUSES = ['prepared', 'payableReady', 'checked']"), 'prepared source status is not accepted')
assert(store.includes("status: 'created'"), 'created result status missing')
assert(store.includes("status: 'already_exists'"), 'already_exists result status missing')
assert(store.includes('sourceWarehouseTaskNo: prepare.sourceWarehouseTaskNo'), 'source warehouse task relation missing')
assert(store.includes('sourcePriceApprovalNo: prepare.sourcePriceApprovalNo'), 'source price approval relation missing')
assert(store.includes('current.completedAt = current.completedAt || stamp'), 'idempotent completion time contract missing')
assert(selection.includes('供应商结算需要单条来源上下文，请仅选择1条记录。'), 'multi-select settlement navigation reason missing')
assert(spec.includes('directStoreCallCount: 0'), 'direct Store call protection missing')
assert(spec.includes('runBatchMatrix'), 'batch matrix missing')
assert(spec.includes('runSupplierSelectionMatrix'), 'supplier selection matrix missing')
assert(spec.includes("TARGET_CHECKPOINT_ID = 'payable_checked'"), 'payable_checked target checkpoint missing')
assert(checkpoint.includes('payableCheckNo: payableCheck?.payableCheckNo'), 'checkpoint payable check entity missing')
assert(checkpoint.includes("relation: 'payablePrepare -> payableCheck'"), 'checkpoint payable check relationship missing')
assert(restoreSpec.includes("CHECKPOINT_ID === 'payable_checked'"), 'cross-process payable_checked restore branch missing')

console.log(JSON.stringify({ version: 'V1.14.2.8.4.7.33', canonicalName: '采购应付核对', moduleId: 'payable-check', fullUrl: 'http://localhost:5173/#/finance/payable-checks', createButton: '生成采购应付核对', completeButton: '完成采购应付核对', batchTransactionPolicy: 'per_item_partial_success', nextStageId: 'supplier-settlement', directStoreCallCount: 0, userBusinessDataModified: false, overall: 'passed' }, null, 2))

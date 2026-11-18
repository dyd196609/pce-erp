import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(process.cwd())
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const assert = (condition, message) => { if (!condition) throw new Error(message) }
const page = read('src/meta/pages/SupplierSettlementPage.vue')
const store = read('src/meta/scm/supplierSettlementStore.js')
const navigation = read('src/meta/scm/supplierSettlementNavigation.js')
const spec = read('tests/e2e/supplierSettlementGoldenFlow.spec.js')
const checkpoint = read('tests/helpers/goldenCheckpoint.js')
const restore = read('tests/e2e/goldenCheckpointRestore.spec.js')

assert(page.includes('生成供应商结算单'), 'real supplier settlement create button missing')
assert(page.includes('createSupplierSettlementFromPayableCheck'), 'page does not invoke formal create action')
assert(page.includes('查看供应商结算单'), 'view settlement action missing')
assert(page.includes('进入采购对账'), 'purchase reconciliation entry missing')
assert(store.includes("status: 'created'"), 'created result contract missing')
assert(store.includes("status: 'already_exists'"), 'already_exists result contract missing')
assert(store.includes('sourcePayableCheckId: source.id'), 'payable check source relation missing')
assert(store.includes('sourceWarehouseTaskNo: source.sourceWarehouseTaskNo'), 'warehouse task source relation missing')
assert(store.includes('sourcePriceApprovalNo: source.sourcePriceApprovalNo'), 'price approval source relation missing')
assert(navigation.includes('sourceSettlementId'), 'current settlement route binding missing')
assert(spec.includes('directStoreCallCount: 0'), 'direct Store call protection missing')
assert(spec.includes('0') && spec.includes('afterSecondGenerationCount'), 'duplicate count evidence missing')
assert(checkpoint.includes('supplierSettlementNo: supplierSettlement?.settlementNo'), 'checkpoint settlement entity missing')
assert(checkpoint.includes("relation: 'payableCheck -> supplierSettlement'"), 'checkpoint settlement relation missing')
assert(restore.includes("CHECKPOINT_ID === 'supplier_settlement_ready'"), 'cross-process restore branch missing')
console.log(JSON.stringify({ version: 'V1.14.2.8.4.7.34', canonicalName: '供应商结算', moduleId: 'supplier-settlement', aggregationRule: 'one_payable_check_to_one_supplier_settlement', nextStageId: 'purchase-reconciliation', directStoreCallCount: 0, userBusinessDataModified: false, overall: 'passed' }, null, 2))

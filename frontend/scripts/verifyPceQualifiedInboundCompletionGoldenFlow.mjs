import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(process.cwd())
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const assert = (condition, message) => { if (!condition) throw new Error(message) }

const wmsPage = read('src/meta/pages/WmsPage.vue')
const qmsPage = read('src/meta/pages/QmsPage.vue')
const command = read('src/meta/wms/qualifiedInboundCommand.js')
const store = read('src/meta/wms/wmsStore.js')
const receiveStore = read('src/meta/wms/purchaseReceiveStore.js')
const spec = read('tests/e2e/qualifiedInboundCompletionGoldenFlow.spec.js')

assert(wmsPage.includes('confirmQualifiedInboundWarehouseTask'), 'warehouse task page is not bound to the unique command')
assert(wmsPage.includes('>确认入库</el-button>'), 'warehouse task detail confirm inbound button missing')
assert(wmsPage.includes('>查看库存流水</el-button>'), 'warehouse task detail inventory transaction link missing')
assert(wmsPage.includes('data-pce-section="inventory-transaction-source-context"'), 'inventory transaction source context section missing')
assert(wmsPage.includes('data-testid="inventory-transaction-source-warehouse-task-no"'), 'source warehouse task DOM binding missing')
assert(wmsPage.includes('data-testid="inventory-transaction-view-source-warehouse-task"'), 'source warehouse task navigation missing')
assert(spec.includes('getSourceWarehouseTaskNoField(page)'), 'golden flow does not verify source warehouse task in scoped DOM')
assert(spec.includes("sourceContext.getByTestId('inventory-transaction-view-source-warehouse-task')"), 'golden flow does not verify source warehouse task navigation')
assert(spec.includes('getWarehouseTaskNoField(page)'), 'golden flow does not verify the exact warehouse task number field')
assert(spec.includes('expectWarehouseTaskDetail(page, taskId, taskNo)'), 'task list navigation does not use the exact warehouse task detail field')
assert(!spec.includes('getByText(taskNo'), 'golden flow still uses a broad task number text selector')
assert(!spec.includes('.first()'), 'golden flow still uses first() fallback')
assert(!spec.includes('.nth('), 'golden flow still uses nth() fallback')
assert(wmsPage.includes('const state = wmsState.value'), 'warehouse task detail is not derived from reactive WMS state')
assert(wmsPage.includes('await nextTick()'), 'warehouse task detail does not wait for Vue reactive rendering')
assert(wmsPage.includes("businessStatus: 'warehouse-task-detail-business-status'"), 'warehouse task business status field is not uniquely identified')
assert(spec.includes("getWarehouseTaskStatusField(page)).toHaveText('已完成')"), 'golden flow does not verify generic done status text')
assert(spec.includes("getWarehouseTaskBusinessStatusField(page)).toHaveText('已入库')"), 'golden flow does not verify qualified inbound business status text')
assert(spec.includes('getInventoryTransactionNoField(page)'), 'golden flow does not use the exact inventory transaction number field')
assert(wmsPage.includes("refreshedTask?.status === 'done'"), 'success notice is not guarded by refreshed task validation')
assert(!wmsPage.includes("if (currentType.value === 'tasks') return getWarehouseTaskById(id)"), 'warehouse task detail still uses a non-reactive getter snapshot')
assert(!qmsPage.includes('@click="postInventory"'), 'QMS detail still owns an independent inbound action')
assert(!qmsPage.includes('@click="postInventoryFromList(row)"'), 'QMS list still owns an independent inbound action')
assert(!qmsPage.includes('runBatchPostInbound'), 'QMS batch still owns an independent inbound action')
assert(command.includes('runBusinessFlowTransaction'), 'cross-store transaction coordinator missing')
assert(command.includes("status: 'already_completed'"), 'idempotent already_completed result missing')
assert(command.includes("payableGenerated: false"), 'payable boundary missing')
assert(store.includes('sourceWarehouseTaskNo'), 'inventory transaction warehouse task source missing')
assert(receiveStore.includes('applyPurchaseReceiveInventoryPostResult'), 'purchase receive writeback missing')
assert(spec.includes("TARGET_CHECKPOINT_ID = 'qualified_inbound_completed'"), 'target checkpoint assertion missing')
assert(spec.includes("directStoreCallCount: 0"), 'direct Store call protection missing')

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.30',
  uniqueExecutionCarrier: 'warehouse_task_detail',
  uniqueCommand: 'confirmQualifiedInboundWarehouseTask',
  qmsIndependentInboundEntryCount: 0,
  transactionCoordinator: true,
  payableGenerated: false,
  overall: 'passed',
}, null, 2))

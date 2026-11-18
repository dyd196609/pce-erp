import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listPceDefectRegressionRegistry } from '../src/meta/runtime/pceDefectRegressionRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const pageSource = read('src/meta/pages/PurchaseReceivePage.vue')
const wmsPageSource = read('src/meta/pages/WmsPage.vue')
const storeSource = read('src/meta/wms/purchaseReceiveStore.js')
const testSource = read('tests/e2e/purchaseReceiveIncomingInspectionGoldenFlow.spec.js')
const errors = []
const assert = (condition, message) => { if (!condition) errors.push(message) }

for (const required of [
  'return receives.value.find',
  'receives.value = listPurchaseReceives()',
  "refreshed.status !== 'received'",
  "detail.value?.status !== 'inspectionPrepared'",
  '>生成来料检验单</el-button>',
  '>查看来料检验单</el-button>',
  'await nextTick()',
]) assert(pageSource.includes(required), `采购收货详情响应式回写缺少：${required}`)

for (const required of [
  'const state = wmsState.value',
  'state.warehouseTasks.find',
  'wmsState.value = getWmsState()',
  'await nextTick()',
  "refreshedTask?.status === 'done'",
  'Number(refreshedTask.completedQuantity) === 1',
  'Boolean(refreshedTask.inventoryTransactionId)',
  '正式入库结果校验失败，请勿重复操作',
]) assert(wmsPageSource.includes(required), `仓库任务详情响应式回写缺少：${required}`)

for (const forbidden of [
  "if (currentType.value === 'tasks') return getWarehouseTaskById(id)",
  'window.location.reload()',
  'setTimeout(() => refresh',
  'taskCompleted = true',
]) assert(!wmsPageSource.includes(forbidden), `仓库任务详情存在旧快照掩盖模式：${forbidden}`)

for (const forbidden of [
  'computed(() => route.params.id ? getPurchaseReceiveById(route.params.id) : null)',
  'window.location.reload()',
  'setTimeout(() => refresh',
  'generated.value = true',
]) assert(!pageSource.includes(forbidden), `采购收货详情存在旧快照掩盖模式：${forbidden}`)

for (const required of [
  "status: 'received'",
  "errorCode: 'already_submitted'",
  'actualReceivedQuantity:',
  "status: 'already_exists'",
  'sourceReceiveNo: receive.receiveNo',
]) assert(storeSource.includes(required), `采购收货动作结果契约缺少：${required}`)

for (const required of [
  'afterFirstAndSecondSubmitState',
  'relatedIncomingInspections).toHaveLength(1)',
  "toHaveCount(0)",
  "name: '查看来料检验单'",
  'inventoryQuantityTotal',
  'supplierSettlements',
]) assert(testSource.includes(required), `详情动作后运行时门禁缺少：${required}`)

for (const number of [...Array.from({ length: 8 }, (_, index) => index + 167), ...Array.from({ length: 6 }, (_, index) => index + 242)]) {
  const defectId = `PCE-REG-${number}`
  assert(listPceDefectRegressionRegistry().some((item) => item.defectId === defectId), `缺少重复缺陷登记：${defectId}`)
}

if (errors.length) {
  console.error('采购收货详情动作后响应式回写门禁失败：')
  errors.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log(JSON.stringify({
  page: 'purchase-receive-detail',
  version: 'V1.14.2.8.4.7.24',
  gate: 'detail_post_action_refresh_consistency',
  reactiveDetailDependencies: ['receives.value', 'wmsState.value'],
  coveredDetails: ['purchase-arrival-prepare', 'purchase-receive', 'warehouse-task'],
  postActionRefreshObservable: true,
  successAfterStateVerification: true,
  reloadWorkaroundCount: 0,
  delayedRefreshWorkaroundCount: 0,
}, null, 2))

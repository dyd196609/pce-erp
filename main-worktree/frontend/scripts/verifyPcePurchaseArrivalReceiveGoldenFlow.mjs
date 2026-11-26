import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listBusinessProcessSteps } from '../src/meta/process/businessProcessRegistry.js'
import { listPceDefectRegressionRegistry } from '../src/meta/runtime/pceDefectRegressionRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const routerSource = read('src/router/index.js')
const testSource = read('tests/e2e/purchaseArrivalReceiveGoldenFlow.spec.js')
const helperSource = read('tests/helpers/goldenCheckpoint.js')
const errors = []
const assert = (condition, message) => { if (!condition) errors.push(message) }
const steps = listBusinessProcessSteps()

const arrival = steps.find((item) => item.stageId === 'purchase-arrival-preview')
const receive = steps.find((item) => item.stageId === 'purchase-receive-preview')
assert(arrival?.route === '/wms/purchase-receive-preview', '采购到货预备真实路由不一致。')
assert(receive?.route === '/wms/purchase-receives', '采购收货预备真实路由不一致。')
assert(arrival?.checkpointId === 'arrival_ready', '采购到货预备检查点不一致。')
assert(receive?.checkpointId === 'receive_ready', '采购收货预备检查点不一致。')
assert(routerSource.includes("path: 'wms/purchase-receive-preview'"), '缺少采购到货预备路由。')
assert(routerSource.includes("path: 'wms/purchase-receives'"), '缺少采购收货预备路由。')

for (const required of [
  "SOURCE_CHECKPOINT_ID = 'order_issued'",
  "'arrival_ready'",
  "'receive_ready'",
  "name: '进入 WMS 收货预备'",
  "name: '直接生成采购收货预备单'",
  "name: '查看采购收货预备单'",
  'verifyCheckpointIntegrity(SOURCE_CHECKPOINT_ID',
  'stoppedBeforeIncomingInspection: true',
]) assert(testSource.includes(required), `金丝雀续跑缺少必要证据：${required}`)

for (const forbidden of [
  "page.goto('/#/wms/purchase-receive-preview'",
  'createPurchaseReceiveFromScmPurchaseOrder(',
  'createPurchaseReceiveTaskFromScmPurchaseOrder(',
  'savePurchaseReceiveState(',
  "localStorage.setItem('scm-state-v1'",
]) assert(!testSource.includes(forbidden), `金丝雀续跑违反真实页面边界：${forbidden}`)

for (const required of [
  "purchaseReceiveState: JSON.parse(local['wms-purchase-receive-state-v1'] || '{}')",
  'purchaseReceiveNo: purchaseReceive?.receiveNo',
  'downstreamRelations',
]) assert(helperSource.includes(required), `检查点业务上下文缺少：${required}`)

for (const defectId of ['PCE-REG-115', 'PCE-REG-116', 'PCE-REG-117', 'PCE-REG-118', 'PCE-REG-119', 'PCE-REG-120']) {
  assert(listPceDefectRegressionRegistry().some((item) => item.defectId === defectId), `缺少重复缺陷登记：${defectId}`)
}

if (errors.length) {
  console.error('采购到货至收货预备金丝雀门禁失败：')
  errors.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log(JSON.stringify({
  page: 'verifyPcePurchaseArrivalReceiveGoldenFlow',
  version: 'V1.14.2.8.4.7.6',
  sourceCheckpoint: 'order_issued',
  targetCheckpoints: ['arrival_ready', 'receive_ready'],
  routes: [arrival.route, receive.route],
  directStoreCallCount: 0,
  directDownstreamRouteJumpCount: 0,
  stoppedBeforeIncomingInspection: true,
  userBusinessDataModified: false,
}, null, 2))

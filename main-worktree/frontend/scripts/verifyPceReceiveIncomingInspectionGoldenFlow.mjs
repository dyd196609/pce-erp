import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listBusinessProcessSteps } from '../src/meta/process/businessProcessRegistry.js'
import { listPceDefectRegressionRegistry } from '../src/meta/runtime/pceDefectRegressionRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const testSource = read('tests/e2e/purchaseReceiveIncomingInspectionGoldenFlow.spec.js')
const helperSource = read('tests/helpers/goldenCheckpoint.js')
const errors = []
const assert = (condition, message) => { if (!condition) errors.push(message) }
const steps = listBusinessProcessSteps()
const receive = steps.find((item) => item.stageId === 'purchase-receive-preview')
const inspection = steps.find((item) => item.stageId === 'incoming-inspection')

assert(receive?.route === '/wms/purchase-receives', '采购收货预备真实路由不一致。')
assert(inspection?.route === '/qms/incoming-inspections', '来料检验真实路由不一致。')
assert(receive?.nextStepIds?.includes('incoming-inspection'), '采购收货预备下一阶段未指向来料检验。')

for (const required of [
  "SOURCE_CHECKPOINT_ID = 'receive_ready'",
  "TARGET_CHECKPOINT_ID = 'incoming_inspection_ready'",
  "name: '编辑收货信息'",
  "name: '提交收货预备'",
  "name: '生成来料检验单'",
  "name: '查看来料检验'",
  'relatedIncomingInspections).toHaveLength(1)',
  "inspection.status).toBe('pending')",
  'noInventoryWrite: true',
  'noPayableGeneration: true',
  'sourceCheckpointHashAfter',
]) assert(testSource.includes(required), `收货至来料检验金丝雀缺少必要证据：${required}`)

for (const forbidden of [
  'createIncomingInspectionFromPurchaseReceive(',
  'createInspectionPreviewFromPurchaseReceive(',
  'submitPurchaseReceive(',
  "localStorage.setItem(",
  "page.goto('/#/qms/incoming-inspection/",
  "name: '开始检验' }).click",
]) assert(!testSource.includes(forbidden), `收货至来料检验金丝雀违反真实页面边界：${forbidden}`)

for (const required of [
  "qmsState: JSON.parse(local['qms-state-v1'] || '{}')",
  'incomingInspectionNo: incomingInspection?.inspectionNo',
  "relation: 'purchaseReceivePreview -> incomingInspection'",
]) assert(helperSource.includes(required), `检查点缺少来料检验上下文：${required}`)

for (let number = 177; number <= 194; number += 1) {
  const defectId = `PCE-REG-${number}`
  assert(listPceDefectRegressionRegistry().some((item) => item.defectId === defectId), `缺少重复缺陷登记：${defectId}`)
}

if (errors.length) {
  console.error('采购收货预备至来料检验预备金丝雀门禁失败：')
  errors.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log(JSON.stringify({
  page: 'verifyPceReceiveIncomingInspectionGoldenFlow',
  version: 'V1.14.2.8.4.7.18',
  sourceCheckpoint: 'receive_ready',
  targetCheckpoint: 'incoming_inspection_ready',
  routes: [receive.route, inspection.route],
  directStoreCallCount: 0,
  directDownstreamRouteJumpCount: 0,
  stoppedBeforeInspectionExecution: true,
  noInventoryWrite: true,
  noPayableGeneration: true,
  userBusinessDataModified: false,
}, null, 2))

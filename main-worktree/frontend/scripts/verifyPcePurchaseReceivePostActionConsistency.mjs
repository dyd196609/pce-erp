import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listPceDefectRegressionRegistry } from '../src/meta/runtime/pceDefectRegressionRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const pageSource = read('src/meta/pages/WmsPage.vue')
const storeSource = read('src/meta/wms/purchaseReceiveStore.js')
const testSource = read('tests/e2e/purchaseReceivePostActionConsistency.spec.js')
const errors = []
const assert = (condition, message) => { if (!condition) errors.push(message) }

for (const required of [
  'resolvePurchaseReceivePrepareLink',
  "linkStatus: 'generated'",
  "linkStatus: 'conflict'",
  "linkStatus: 'read_failed'",
  "status: 'created'",
  "status: 'already_exists'",
  'targetNo:',
  'targetRecord:',
]) assert(storeSource.includes(required), `生成结果契约或关联解析缺失：${required}`)

for (const required of [
  'purchaseReceives.value = listPurchaseReceives()',
  "rowPurchaseReceiveLink(row).linkStatus === 'not_generated'",
  "rowPurchaseReceiveLink(row).linkStatus === 'generated'",
  ':data-target-no="rowPurchaseReceiveLink(row).targetNo"',
  '采购收货预备单生成结果校验失败，请勿重复操作。',
]) assert(pageSource.includes(required), `页面生成后状态回写缺失：${required}`)

for (const forbidden of ['window.location.reload', 'generated = true']) {
  assert(!pageSource.includes(forbidden), `页面包含禁止的状态修正方式：${forbidden}`)
}

for (const required of [
  'successToastRequiresTarget: true',
  'targetCountStableOnSecondAction: true',
  'noInventoryWrite: true',
  'noInspectionObject: true',
  'noPayableObject: true',
  'sourceAfter.actualHash',
]) assert(testSource.includes(required), `定向门禁缺少运行时证据：${required}`)

for (const defectId of ['PCE-REG-151', 'PCE-REG-152', 'PCE-REG-153', 'PCE-REG-154', 'PCE-REG-155', 'PCE-REG-156', 'PCE-REG-157', 'PCE-REG-158']) {
  assert(listPceDefectRegressionRegistry().some((item) => item.defectId === defectId), `缺少重复缺陷登记：${defectId}`)
}

if (errors.length) {
  console.error('采购收货预备生成结果一致性静态门禁失败：')
  errors.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.13',
  contract: 'purchase_receive_post_action_consistency',
  targetCheckpoint: 'receive_ready',
  registeredDefects: ['PCE-REG-151', 'PCE-REG-152', 'PCE-REG-153', 'PCE-REG-154', 'PCE-REG-155', 'PCE-REG-156', 'PCE-REG-157', 'PCE-REG-158'],
  businessStoreDirectCallInBrowserGate: false,
}, null, 2))

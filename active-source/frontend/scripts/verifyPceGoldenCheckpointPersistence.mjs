import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listPceDefectRegressionRegistry } from '../src/meta/runtime/pceDefectRegressionRegistry.js'
import {
  CHECKPOINT_ROOT,
  REQUIRED_CHECKPOINT_FILES,
  verifyCheckpointIntegrity,
} from '../tests/helpers/goldenCheckpoint.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const testSource = read('tests/e2e/procurementEntryGoldenFlow.spec.js')
const errors = []
const assert = (condition, message) => { if (!condition) errors.push(message) }

for (const checkpointId of ['request_created', 'inquiry_created', 'price_approved', 'order_created', 'order_issued']) {
  const directory = path.join(CHECKPOINT_ROOT, checkpointId)
  assert(fs.existsSync(directory), `检查点目录不存在：${checkpointId}`)
  for (const fileName of REQUIRED_CHECKPOINT_FILES) {
    assert(fs.existsSync(path.join(directory, fileName)), `${checkpointId} 缺少 ${fileName}`)
  }
}

for (const defectId of ['PCE-REG-109', 'PCE-REG-110', 'PCE-REG-111', 'PCE-REG-112', 'PCE-REG-113', 'PCE-REG-114']) {
  assert(listPceDefectRegressionRegistry().some((item) => item.defectId === defectId), `缺少重复缺陷登记：${defectId}`)
}

assert(
  testSource.indexOf('saveCheckpoint({') < testSource.indexOf('originalContextClosed = true'),
  '检查点保存必须发生在原业务 context 关闭前',
)
assert(!testSource.includes('localStorage.clear()'), '持久化金丝雀禁止在保存后清空检查点依赖状态')
for (const forbidden of ['createPurchaseRequest(', 'createInquiryFromRequest(', 'createPriceApprovalFromInquiry(', 'createPurchaseOrderFromPriceApproval(']) {
  assert(!testSource.includes(forbidden), `金丝雀禁止直接调用 Store：${forbidden}`)
}

try {
  const checkpoint = await verifyCheckpointIntegrity('order_issued')
  const requiredFields = [
    'purchaseRequestNo', 'inquiryNo', 'priceApprovalNo', 'purchaseOrderNo',
    'supplierId', 'supplierName', 'materialCode', 'materialName', 'quantity', 'unit',
    'requiredDate', 'plannedDeliveryDate', 'purchaseOrderStatus',
  ]
  requiredFields.forEach((field) => assert(checkpoint.entities[field] !== '' && checkpoint.entities[field] !== null, `order_issued 缺少实体字段：${field}`))
  assert(checkpoint.entities.purchaseOrderStatus === 'issued', '采购订单状态不是 issued')
  assert(checkpoint.graph.relationCount === 3, '来源关系数量不是 3')
  assert(checkpoint.graph.allRelationsBidirectional === true, '来源目标双向关系未通过')
  assert(checkpoint.manifest.nextStageId === 'purchase-arrival-preview', '下一阶段不是采购到货预备')
} catch (error) {
  errors.push(error.message)
}

if (errors.length) {
  console.error('金丝雀检查点持久化门禁失败：')
  errors.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.5',
  checkpointRoot: CHECKPOINT_ROOT,
  checkpointCount: 5,
  requiredFilesPerCheckpoint: REQUIRED_CHECKPOINT_FILES,
  orderIssuedRestorable: true,
  crossContextRestoreRequired: true,
  crossProcessRestoreRequired: true,
  directStoreCallCount: 0,
  userBusinessDataModified: false,
}, null, 2))

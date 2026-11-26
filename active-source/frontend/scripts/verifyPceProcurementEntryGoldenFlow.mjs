import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listBusinessProcessSteps } from '../src/meta/process/businessProcessRegistry.js'
import { listPceDefectRegressionRegistry } from '../src/meta/runtime/pceDefectRegressionRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const routerSource = read('src/router/index.js')
const storeSource = read('src/meta/scm/scmStore.js')
const purchaseReceiveStoreSource = read('src/meta/wms/purchaseReceiveStore.js')
const pageSource = read('src/meta/pages/ScmPage.vue')
const e2eSource = read('tests/e2e/procurementEntryGoldenFlow.spec.js')

const expected = [
  ['procurement-request', 'purchase-request', '采购申请', '/scm/purchase-request', 'createPurchaseRequest', 'request_created'],
  ['purchase-inquiry', 'purchase-inquiry', '采购询价', '/scm/purchase-inquiries', 'createInquiryFromRequest', 'inquiry_created'],
  ['price-approval', 'price-approval', '采购核价', '/scm/price-approvals', 'createPriceApprovalFromInquiry', 'price_approved'],
  ['purchase-order', 'purchase-order', '采购订单', '/scm/purchase-orders', 'createPurchaseOrderFromPriceApproval', 'order_issued'],
  ['purchase-arrival-preview', 'purchase-receive-preview', '采购到货预备', '/wms/purchase-receive-preview', 'goToWmsReceivePreview', 'arrival_ready'],
  ['purchase-receive-preview', 'purchase-receive', '采购收货预备', '/wms/purchase-receives', 'createPurchaseReceiveFromScmPurchaseOrder', 'receive_ready'],
]

const errors = []
const assert = (condition, message) => { if (!condition) errors.push(message) }
const steps = listBusinessProcessSteps()

expected.forEach(([stageId, moduleId, canonicalName, route, entryAction, checkpointId], index) => {
  const step = steps.find((item) => item.stageId === stageId)
  assert(Boolean(step), `缺少采购阶段：${stageId}`)
  if (!step) return
  assert(step.moduleId === moduleId, `${stageId} moduleId 不正确`)
  assert(step.canonicalName === canonicalName, `${stageId} canonicalName 不正确`)
  assert(step.route === route && step.routePath === route, `${stageId} 路由不正确`)
  assert(step.sourceStageId === (expected[index - 1]?.[0] || null), `${stageId} 来源阶段不连续`)
  const expectedTargetStageId = expected[index + 1]?.[0] || 'incoming-inspection'
  assert(step.targetStageId === expectedTargetStageId, `${stageId} 目标阶段不连续`)
  assert(step.entryAction === entryAction, `${stageId} entryAction 不正确`)
  assert(step.checkpointId === checkpointId, `${stageId} checkpointId 不正确`)
  assert(step.completionCondition?.statusField === 'status' && step.completionCondition.acceptedValues.length > 0, `${stageId} 缺少真实状态完成条件`)
  assert(typeof step.blockingReasonResolver === 'string' && step.blockingReasonResolver.startsWith('resolve_'), `${stageId} 缺少阻断原因解析标识`)
  assert(routerSource.includes(`path: '${route.slice(1)}'`), `${stageId} 真实路由不存在`)
  assert(storeSource.includes(`function ${entryAction}`) || purchaseReceiveStoreSource.includes(`function ${entryAction}`) || pageSource.includes(`function ${entryAction}`), `${stageId} 真实入口动作不存在：${entryAction}`)
})

for (const defectId of ['PCE-REG-099', 'PCE-REG-100', 'PCE-REG-101', 'PCE-REG-102', 'PCE-REG-103']) {
  assert(listPceDefectRegressionRegistry().some((item) => item.defectId === defectId), `缺少重复缺陷登记：${defectId}`)
}

for (const forbidden of ['createPurchaseRequest(', 'createInquiryFromRequest(', 'createPriceApprovalFromInquiry(', 'createPurchaseOrderFromPriceApproval(']) {
  assert(!e2eSource.includes(forbidden), `金丝雀禁止直接调用 Store/动作函数：${forbidden}`)
}
assert(e2eSource.includes("page.goto('/#/scm/purchase-request/create'"), '金丝雀必须从真实采购申请新增页面开始')
assert(e2eSource.includes("'order_issued'"), '金丝雀必须生成 order_issued 检查点')
assert(e2eSource.includes('saveCheckpoint({'), '金丝雀必须保存可恢复检查点')

if (errors.length) {
  console.error('采购前端流程注册门禁失败：')
  errors.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log(JSON.stringify({
  page: 'verifyPceProcurementEntryGoldenFlow',
  version: 'V1.14.2.8.4.7.5',
  stageCount: expected.length,
  stages: expected.map(([stageId, moduleId, canonicalName, route, entryAction, checkpointId]) => ({ stageId, moduleId, canonicalName, route, entryAction, checkpointId })),
  stopsAt: 'order_issued',
  directStoreCallCount: 0,
  userBusinessDataModified: false,
}, null, 2))

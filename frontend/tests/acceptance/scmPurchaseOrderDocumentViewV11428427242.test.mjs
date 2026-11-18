import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildPurchaseOrderLifecycleDetailReadModelV114284272 } from
  '../../src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js'
import { buildPurchaseOrderViewModelV1142842724 } from
  '../../src/meta/viewModels/purchaseOrderViewModelV1142842724.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()
const clone = value => JSON.parse(JSON.stringify(value))

function fixture() {
  return {
    purchaseOrder: {
      id: 'PO-ID-001', purchaseOrderNo: 'PO202608090001', poNo: 'PO202608090001',
      gateNo: 'POG202608090099', sourceGateId: 'GATE-ID-099',
      sourcePurchaseRequestIds: ['PR001', 'PR002'],
      sourceRelations: {
        purchaseRequestIds: ['PR001', 'PR002'], purchaseInquiryIds: ['PI001'],
        quoteComparisonIds: ['QC001'], priceApprovalIds: ['PA001'],
        supplierRecommendationIds: ['SR001'], gateNo: 'POG202608090099',
      },
      supplierId: 'SUP001', supplierName: '华东供应商', buyerId: 'EMP001',
      buyerName: '采购员甲', orderDate: '2026-08-09', plannedArrivalDate: '2026-08-20',
      status: 'approved', lifecycleStatus: 'approved', totalAmount: 560,
      remark: '人工确认备注', createdBy: '制单员甲', createdAt: '2026-08-09 09:30',
      gateMaterialItems: Array.from({ length: 9 }, (_, index) => ({ id: `GATE-${index}` })),
      recommendationItems: Array.from({ length: 8 }, (_, index) => ({ id: `REC-${index}` })),
      purchaseRequestItems: Array.from({ length: 7 }, (_, index) => ({ id: `PR-LINE-${index}` })),
    },
    orderLines: [
      { id: 'POI-1', poId: 'PO-ID-001', lineNo: 1, materialCode: 'MAT001',
        materialName: '铝材', specification: '40x40', unit: '米', quantity: 2,
        price: 100, amount: 200, plannedArrivalDate: '2026-08-20' },
      { id: 'POI-2', poId: 'PO-ID-001', lineNo: 2, materialCode: 'MAT002',
        materialName: '铜线', specification: 'BV2.5', unit: '卷', quantity: 3,
        price: 120, amount: 360, plannedArrivalDate: '2026-08-20' },
    ],
  }
}

test('governance files and requested rules are loaded', () => {
  const files = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
    'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
    'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
    'docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md',
  ]
  const governance = files.map(path => { const content = read(path); assert.ok(content.trim()); return content }).join('\n')
  for (const rule of ['DATA-IDENTITY-001', 'DATA-EXTRACT-001', 'ARRAY-COMPLETENESS-001',
    'LIST-EXPORT-001', 'TECH-FIELD-SEPARATION-001', 'DETAIL-NAVIGATION-001',
    'TEST-DATA-001', 'PURCHASE-ORDER-DOCUMENT-VIEW-001']) assert.ok(governance.includes(rule), rule)
})

test('forbidden creation, Gate, recommendation, lifecycle, approval, core, model and database assets stay frozen with governed detail route', () => {
  const scan = JSON.parse(read('scm_purchase_order_document_view_scan_v11428427242.json'))
  const frozen = {
    'backend/procurement/models.py': scan.frozenAssetBaseline.purchaseOrderModelSha256,
    'frontend/src/meta/actions/scm/createPurchaseOrderActionV114284271.js': scan.frozenAssetBaseline.purchaseOrderCreationActionSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js': scan.frozenAssetBaseline.purchaseOrderCreationGuardSha256,
    'frontend/src/meta/runtime/supplierRecommendationActionRuntimeV1142811.js': scan.frozenAssetBaseline.supplierRecommendationActionSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js': scan.frozenAssetBaseline.purchaseOrderLifecycleRuntimeSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalContextV114284272.js': scan.frozenAssetBaseline.purchaseOrderApprovalContextSha256,
    'frontend/src/meta/scm/scmStore.js': scan.frozenAssetBaseline.purchaseOrderCoreStoreSha256,
    'backend/db.sqlite3': scan.frozenAssetBaseline.databaseSha256,
  }
  Object.entries(frozen).forEach(([path, expected]) => assert.equal(sha256(path), expected, path))
  assert.match(read('frontend/src/router/index.js'),
    /path: 'scm\/purchase-order\/:id'[\s\S]*PurchaseOrderDetailPage\.vue/)
})

test('PurchaseOrder, Gate and source request identities remain separate', () => {
  const input = fixture()
  const detail = buildPurchaseOrderLifecycleDetailReadModelV114284272(input)
  const view = buildPurchaseOrderViewModelV1142842724({
    purchaseOrder: input.purchaseOrder, orderLines: detail.purchaseOrderItems,
    lifecycleDetail: detail, viewRole: 'management',
  })
  assert.equal(view.identity.purchaseOrderNo, 'PO202608090001')
  assert.equal(view.identity.sourceGateNo, 'POG202608090099')
  assert.equal(view.identity.purchaseOrderNoField, 'purchaseOrderNo')
  assert.equal(view.identity.businessNoParsed, false)
  assert.equal(view.identity.numberSeparated, true)
  assert.deepEqual(detail.sourceTrace.sourcePurchaseRequestIds, ['PR001', 'PR002'])
})

test('detail material rows only come from PurchaseOrderItem array and counts remain consistent', () => {
  const input = fixture()
  const detail = buildPurchaseOrderLifecycleDetailReadModelV114284272(input)
  assert.equal(detail.purchaseOrderItemSource, 'PurchaseOrderItem[]')
  assert.deepEqual(detail.purchaseOrderItems.map(item => item.id), ['POI-1', 'POI-2'])
  assert.equal(detail.materialCountConsistency.purchaseOrderItemCount, 2)
  assert.equal(detail.materialCountConsistency.detailDisplayCount, 2)
  assert.equal(detail.materialCountConsistency.consistent, true)
  assert.equal(detail.materialCountConsistency.fallbackSourceUsed, false)
  assert.deepEqual(detail.materialCountConsistency.forbiddenSourcesUsed, [])
  const view = buildPurchaseOrderViewModelV1142842724({
    purchaseOrder: input.purchaseOrder, orderLines: detail.purchaseOrderItems,
    lifecycleDetail: detail, viewRole: 'buyer',
  })
  assert.equal(view.materialDetail.rows.length, 2)
  assert.equal(view.materialDetail.countConsistent, true)
})

test('explicit cross-order PurchaseOrderItem is rejected instead of displayed', () => {
  const input = fixture()
  input.orderLines.push({ id: 'FOREIGN-ITEM', poId: 'OTHER-PO', materialCode: 'BAD', quantity: 99 })
  const detail = buildPurchaseOrderLifecycleDetailReadModelV114284272(input)
  assert.equal(detail.result, 'FAIL')
  assert.equal(detail.factLoadStatus, 'purchase_order_item_identity_mismatch')
  assert.equal(detail.purchaseOrderItems.length, 2)
  assert.deepEqual(detail.materialCountConsistency.mismatchedOrderItemIds, ['FOREIGN-ITEM'])
  assert.equal(detail.materialCountConsistency.consistent, false)
})

test('standard document view has business regions, concise vertical source chain and maker facts', () => {
  const component = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  for (const term of ['采购订单基础信息', '来源追踪', '采购物料明细', '审批信息', '制单信息',
    '采购日期', '计划到货日期', '订单金额', '制单人', '制单日期', 'PurchaseOrderItem[]']) {
    assert.ok(component.includes(term), term)
  }
  assert.ok(component.includes("content: '↓'"))
  assert.ok(component.includes('group.summary'))
  assert.equal(component.includes('v-for="id in group.values"'), false)
})

test('detail navigation and enhanced procurement filters are present', () => {
  const component = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  for (const term of ['返回列表', '返回上一级', '刷新', 'DETAIL-NAVIGATION-001']) assert.ok(component.includes(term), term)
  for (const filter of [
    "{ key: 'rootRequestNo', label: '采购申请编号'",
    "{ key: 'requestDepartment', label: '申请部门'",
    "{ key: 'demandDepartment', label: '需求部门'",
    "{ key: 'supplierId', label: '供应商'", "{ key: 'buyerId', label: '采购员'",
    "{ key: 'status', label: '状态'", "{ key: 'deliveryUrgency', label: '紧急程度'",
    "{ key: 'orderDate', label: '采购日期'",
    "{ key: 'earliestArrivalDate', label: '计划到货日期'",
  ]) assert.ok(page.includes(filter), filter)
})

test('development test data generator uses independent business numbers and production data is never rewritten', () => {
  const generator = read('frontend/src/meta/scm/scmMockDataGenerator.js')
  const governance = read('docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md')
  assert.ok(generator.includes('`PO20260715${seq}`'))
  assert.ok(generator.includes("testDataClassification: 'DEVELOPMENT_TEST_DATA'"))
  assert.ok(governance.includes('企业生产数据未经业务所有者授权禁止删除、重建、改号或覆盖'))
  assert.equal(generator.includes('sourceGateId.replace'), false)
})

test('human facts and historical data are projection-only and remain untouched', () => {
  const input = fixture()
  const before = clone(input)
  const detail = buildPurchaseOrderLifecycleDetailReadModelV114284272(input)
  buildPurchaseOrderViewModelV1142842724({ purchaseOrder: input.purchaseOrder,
    orderLines: detail.purchaseOrderItems, lifecycleDetail: detail, viewRole: 'buyer' })
  assert.deepEqual(input, before)
  assert.equal(detail.businessWriteCount, 0)
  assert.equal(detail.productionDataWritten, false)
  assert.equal(detail.purchaseOrderCreated, false)
  assert.equal(detail.purchaseOrderStatusChanged, false)
})

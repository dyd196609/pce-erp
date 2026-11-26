import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildPurchaseOrderLifecycleDetailReadModelV114284272 } from
  '../../src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js'
import { buildPurchaseOrderViewModelV1142842724 } from
  '../../src/meta/viewModels/purchaseOrderViewModelV1142842724.js'
import { buildPurchaseOrderPrintViewModelV11428427243 } from
  '../../src/meta/viewModels/purchaseOrderPrintViewModelV11428427243.js'
import { buildPurchaseOrderPrintDocumentV11428427243 } from
  '../../src/meta/viewModels/purchaseOrderPrintTemplateV11428427243.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()
const clone = value => JSON.parse(JSON.stringify(value))

function fixture() {
  return {
    purchaseOrder: {
      id: 'PO-ID-PRINT-001', objectNo: 'PO202608090001',
      purchaseOrderNo: 'PO-LEGACY-SECONDARY', poNo: 'PO-LEGACY-SECONDARY',
      gateNo: 'POG202608090099', sourceGateId: 'GATE-ID-099', supplierName: '华东供应商',
      buyerName: '采购员甲', orderDate: '2026-08-09', plannedArrivalDate: '2026-08-20',
      lifecycleStatus: 'approved', deliveryUrgencyLabel: '一般', currency: 'CNY',
      remark: '人工确认备注', createdBy: '制单员甲', createdAt: '2026-08-09',
      gateMaterialItems: [{ id: 'GATE-LINE-NOT-PRINTED' }],
      recommendationItems: [{ id: 'RECOMMENDATION-NOT-PRINTED' }],
      quoteComparisonItems: [{ id: 'QUOTE-NOT-PRINTED' }],
    },
    orderLines: [
      { id: 'POI-1', poId: 'PO-ID-PRINT-001', lineNo: 1, materialCode: 'MAT001',
        materialName: '铝材', specification: '40x40', unit: '米', quantity: 2,
        price: 100, amount: 200, plannedArrivalDate: '2026-08-20' },
      { id: 'POI-2', poId: 'PO-ID-PRINT-001', lineNo: 2, materialCode: 'MAT002',
        materialName: '铜线', specification: 'BV2.5', unit: '卷', quantity: 3,
        price: 120, amount: 360, plannedArrivalDate: '2026-08-20' },
    ],
  }
}

function build(role = 'management') {
  const input = fixture()
  const detail = buildPurchaseOrderLifecycleDetailReadModelV114284272(input)
  const view = buildPurchaseOrderViewModelV1142842724({ purchaseOrder: input.purchaseOrder,
    orderLines: detail.purchaseOrderItems, lifecycleDetail: detail, viewRole: role })
  return { input, detail, view, print: buildPurchaseOrderPrintViewModelV11428427243({
    purchaseOrderViewModel: view, companyName: 'PCE示范制造有限公司' }) }
}

test('governance files load PRINT-FORM-001 and related rules', () => {
  const files = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
    'docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md',
    'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
    'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
    'docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md',
  ]
  const governance = files.map(path => { const value = read(path); assert.ok(value.trim()); return value }).join('\n')
  for (const rule of ['PRINT-FORM-001', 'LIST-EXPORT-001', 'TECH-FIELD-SEPARATION-001',
    'DATA-IDENTITY-001', 'DATA-EXTRACT-001', 'ARRAY-COMPLETENESS-001',
    'DETAIL-NAVIGATION-001', 'PURCHASE-ORDER-PRINT-001']) assert.ok(governance.includes(rule), rule)
})

test('PurchaseOrder, Gate, lifecycle and database assets remain frozen while authorized detail route stays governed', () => {
  const scan = JSON.parse(read('scm_purchase_order_print_model_scan_v11428427243.json'))
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

test('print model uses canonical objectNo and exactly the PurchaseOrderItem projection', () => {
  const { detail, print } = build()
  assert.equal(print.documentInfo.documentNo, 'PO202608090001')
  assert.equal(print.documentInfo.documentNoField, 'objectNo')
  assert.equal(print.printMeta.purchaseOrderItemSource, 'PurchaseOrderItem[]')
  assert.equal(print.detailRows.length, detail.purchaseOrderItems.length)
  assert.equal(print.printMeta.countConsistent, true)
  assert.equal(print.printMeta.prohibitedDetailSourcesUsed, false)
  assert.deepEqual(print.detailRows.map(row => row.materialCode), ['MAT001', 'MAT002'])
  assert.equal(JSON.stringify(print.detailRows).includes('GATE-LINE-NOT-PRINTED'), false)
})

test('standard print document has four-part layout and editable authorized approval fields', () => {
  const { print } = build('management')
  const html = buildPurchaseOrderPrintDocumentV11428427243(print)
  assert.equal(print.basicInfo.layout, 'six')
  assert.equal(print.basicInfo.columnCount, 6)
  assert.ok(html.indexOf('PCE示范制造有限公司') < html.indexOf('采购订单</div>'))
  for (const term of ['基本信息', '采购物料明细', '审批', '审核', '复核', '制表',
    'data-layout="six"', 'data-item-source="PurchaseOrderItem[]"']) assert.ok(html.includes(term), term)
  assert.ok(html.includes('aria-label="审批人"'))
  assert.equal(print.approvalInfo.autoGeneratedApprovalResult, false)
  assert.equal(html.includes('审批通过'), false)
  assert.equal(html.includes('data-generated-from-page-dom="false"'), true)
})

test('role print permission hides warehouse price and supplier internal approval', () => {
  const warehouse = build('warehouse').print
  const supplier = build('supplier').print
  const buyer = build('buyer').print
  assert.equal(warehouse.printMeta.detailColumns.some(item => ['unitPrice', 'amount'].includes(item.key)), false)
  assert.deepEqual(warehouse.approvalInfo.slots.map(item => item.code), ['maker'])
  assert.deepEqual(supplier.approvalInfo.slots.map(item => item.code), ['maker'])
  assert.deepEqual(buyer.approvalInfo.slots.map(item => item.code),
    ['approval', 'review', 'recheck', 'maker'])
  assert.equal(buyer.approvalInfo.editable, true)
  assert.equal(warehouse.approvalInfo.editable, false)
})

test('preview page uses independent model instead of printing the detail DOM', () => {
  const component = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  for (const term of ['采购订单打印预览', 'PurchaseOrderPrintViewModel', 'PRINT-FORM-001',
    'buildPurchaseOrderPrintViewModelV11428427243', ':srcdoc="printPreviewHtml"']) assert.ok(component.includes(term), term)
  assert.equal(component.includes('document.body.appendChild(frame)'), false)
  assert.equal(component.includes('printDocument.write(html)'), false)
})

test('list, export and print prefer the same objectNo without mutating human data', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  assert.ok(page.includes("key === 'objectNo') return getPurchaseOrderNumber(row) || '-'"))
  const { input, print } = build()
  const before = clone(input)
  const rebuilt = buildPurchaseOrderPrintViewModelV11428427243({
    purchaseOrderViewModel: build().view, companyName: 'PCE示范制造有限公司' })
  assert.deepEqual(input, before)
  assert.equal(rebuilt.documentInfo.documentNo, print.documentInfo.documentNo)
  assert.deepEqual(rebuilt.detailRows, print.detailRows)
  assert.equal(print.printMeta.businessWriteCount, 0)
})

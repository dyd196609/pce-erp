import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  PURCHASE_ORDER_IMPORT_TEMPLATE_FIELDS_V1142842729,
  buildPurchaseOrderImportTemplateCsvV1142842729,
} from '../../src/meta/runtime/purchaseOrderImportTemplateRuntimeV1142842729.js'
import { buildPurchaseOrderBusinessNumberViewModelV1142842729 } from
  '../../src/meta/viewModels/purchaseOrderBusinessNumberViewModelV1142842729.js'
import {
  PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728,
  projectPurchaseOrderPrintBusinessViewV1142842728,
} from '../../src/meta/runtime/purchaseOrderPrintBusinessRuntimeV1142842728.js'
import { filterPurchaseOrderItemsByIdentityV1142842728 } from
  '../../src/meta/runtime/purchaseOrderDetailDataRuntimeV1142842728.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('required governance files and requirement closed-loop rules are loaded', () => {
  const paths = [
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/archive/legacy-specs/页面开发模板.md',
    'docs/governance/archive/legacy-specs/一页一验收规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面重构替换规范.md',
    'docs/governance/Codex执行证据规范.md',
    'docs/governance/页面需求执行闭环规范.md',
  ]
  const governance = paths.map(read).join('\n')
  for (const rule of ['REQUIREMENT-COMPLETENESS-001', 'BUSINESS-DATA-VIEW-001',
    'BROWSER-ACTION-001', 'REFRESH-RUNTIME-002', 'PURCHASE-ORDER-ITEM-SOURCE-001',
    'PRINT-BUSINESS-CLASSIFICATION-001']) assert.ok(governance.includes(rule), rule)
})

test('purchase order import template has the eight governed business fields', () => {
  assert.deepEqual(PURCHASE_ORDER_IMPORT_TEMPLATE_FIELDS_V1142842729.map(item => item.label),
    ['供应商', '物料编码', '物料名称', '规格', '数量', '采购单价', '计划到货日期', '备注'])
  const csv = buildPurchaseOrderImportTemplateCsvV1142842729()
  for (const label of PURCHASE_ORDER_IMPORT_TEMPLATE_FIELDS_V1142842729.map(item => item.label)) {
    assert.ok(csv.includes(label), label)
  }
  assert.ok(csv.includes('必填'))
  assert.ok(csv.includes('YYYY-MM-DD'))
})

test('list refresh is registered to a real provider chain without location reload', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  assert.match(page, /:page-refresh-handler="activeType === 'order' && pageMode === 'list' \? reloadPageData : null"/)
  const shell = read('frontend/src/meta/components/PceListPageShell.vue')
  assert.match(shell, /if \(props\.pageRefreshHandler\)/)
  assert.match(page, /readPurchaseOrderListFactSnapshotV1142842729/)
  assert.match(page, /purchase-order-list-refresh-evidence/)
  assert.match(page, /purchase-order-import-template-button/)
  assert.doesNotMatch(page, /window\.location\.reload\(|router\.go\(0\)/)
})

test('business number view model provides five independent, unparsed number cards', () => {
  const model = buildPurchaseOrderBusinessNumberViewModelV1142842729({
    purchaseOrder: { purchaseOrderNo: 'PURCHASE-001', poNo: 'PO-001',
      purchaseBatchNo: 'BATCH-01', supplierOrderNo: 'SUP-PO-9' },
    businessView: { sourceTrace: { groups: [
      { nodeCode: 'purchase_request', values: ['PR-1', 'PR-2'] },
      { nodeCode: 'purchase_order_gate', values: ['GATE-1'] },
    ] } },
  })
  assert.equal(model.model, 'PurchaseOrderBusinessNumberViewModel')
  assert.deepEqual(model.cards.map(card => card.label), ['采购订单编号', 'PO编号', '采购批次编号',
    '来源编号', '供应商订单编号'])
  assert.deepEqual(model.cards[3].values, ['PR-1', 'PR-2', 'GATE-1'])
  assert.equal(model.businessNumberParsed, false)
  assert.equal(model.horizontalOverflowAllowed, false)
})

function printFixture() {
  return {
    basicInfo: { fields: [
      { key: 'purchaseOrderNo' }, { key: 'supplierName' }, { key: 'orderDate' },
      { key: 'statusLabel' }, { key: 'totalQuantity' }, { key: 'totalAmount' },
      { key: 'plannedDeliveryDate' }, { key: 'buyerName' }, { key: 'receiptRequirement' },
      { key: 'deliveryRequirement' }, { key: 'paymentTerms' },
    ] },
    detailRows: [{ materialCode: 'MAT-1' }],
    approvalInfo: { visible: true },
    printMeta: { detailColumns: ['lineNo', 'materialCode', 'materialName', 'quantity',
      'unitPrice', 'amount', 'plannedDeliveryDate', 'receiptStatusLabel']
      .map(key => ({ key })) },
  }
}

test('print selector exposes five business classifications with distinct projections', () => {
  assert.deepEqual(PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728.map(item => item.label),
    ['采购员使用', '仓库使用', '供应商使用', '财务留档', '管理查看'])
  const warehouse = projectPurchaseOrderPrintBusinessViewV1142842728(printFixture(), 'warehouse')
  const supplier = projectPurchaseOrderPrintBusinessViewV1142842728(printFixture(), 'supplier')
  const finance = projectPurchaseOrderPrintBusinessViewV1142842728(printFixture(), 'finance')
  assert.ok(warehouse.basicInfo.fields.some(field => field.key === 'receiptRequirement'))
  assert.ok(supplier.basicInfo.fields.some(field => field.key === 'deliveryRequirement'))
  assert.ok(finance.basicInfo.fields.some(field => field.key === 'paymentTerms'))
  assert.ok(finance.approvalInfo.visible)
})

test('item isolation rejects unrelated, missing and conflicting parent identities', () => {
  const filtered = filterPurchaseOrderItemsByIdentityV1142842728([
    { id: 'A', poId: 'po-1' }, { id: 'B', purchaseOrderId: 'po-1' },
    { id: 'C', poId: 'po-2' }, { id: 'D' },
    { id: 'E', poId: 'po-1', purchaseOrderId: 'po-2' },
  ], 'po-1')
  assert.deepEqual(filtered.map(item => item.id), ['A', 'B'])
})

test('PurchaseOrder core, Action, Gate, lifecycle and database remain frozen', () => {
  const frozen = JSON.parse(read('purchase_order_requirement_runtime_scan_v1142842729.json'))
    .frozenAssetBaseline
  const paths = {
    purchaseOrderModelSha256: 'backend/procurement/models.py',
    purchaseOrderCoreStoreSha256: 'frontend/src/meta/scm/scmStore.js',
    purchaseOrderActionSha256: 'frontend/src/meta/actions/scm/createPurchaseOrderActionV114284271.js',
    purchaseOrderGateSha256: 'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js',
    lifecycleStateMachineSha256: 'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js',
    databaseSha256: 'backend/db.sqlite3',
  }
  Object.entries(paths).forEach(([key, path]) => assert.equal(sha256(path), frozen[key], path))
})

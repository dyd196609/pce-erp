import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  filterPurchaseOrderItemsByIdentityV1142842728,
  reloadPurchaseOrderDetailDataV1142842728,
} from '../../src/meta/runtime/purchaseOrderDetailDataRuntimeV1142842728.js'
import { buildPurchaseOrderNumberViewModelV1142842728 } from
  '../../src/meta/viewModels/purchaseOrderNumberViewModelV1142842728.js'
import {
  PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728,
  buildPurchaseOrderBusinessPrintDocumentV1142842728,
  projectPurchaseOrderPrintBusinessViewV1142842728,
} from '../../src/meta/runtime/purchaseOrderPrintBusinessRuntimeV1142842728.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('governance files are loaded and v2.8 rules are applied', () => {
  const governance = [
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面重构替换规范.md',
    'docs/governance/Codex执行证据规范.md',
  ].map(read).join('\n')
  for (const rule of ['REFRESH-RUNTIME-002', 'PURCHASE-ORDER-ITEM-SOURCE-001',
    'PRINT-BUSINESS-CLASSIFICATION-001']) assert.ok(governance.includes(rule), rule)
})

test('strict PurchaseOrderItem source rejects unrelated, missing and conflicting parents', () => {
  const rows = [
    { id: 'A', poId: 'po-1', materialCode: 'MAT-A' },
    { id: 'B', purchaseOrderId: 'po-1', materialCode: 'MAT-B' },
    { id: 'C', poId: 'po-2', materialCode: 'MAT-C' },
    { id: 'D', materialCode: 'TEST-CACHE' },
    { id: 'E', poId: 'po-1', purchaseOrderId: 'po-2', materialCode: 'CONFLICT' },
  ]
  const filtered = filterPurchaseOrderItemsByIdentityV1142842728(rows, 'po-1')
  assert.deepEqual(filtered.map(item => item.id), ['A', 'B'])
  assert.deepEqual(filtered.map(item => item.lineNo), [1, 2])
})

test('real refresh re-reads the snapshot, preserves order and reports isolation counts', async () => {
  let reads = 0
  const loadSnapshot = () => {
    reads += 1
    return { purchaseOrders: [{ id: 'po-1', poNo: 'PO-001', status: 'draft' }],
      purchaseOrderItems: [
        { id: 'A', poId: 'po-1', materialCode: 'MAT-A', quantity: 1 },
        { id: 'B', poId: 'po-2', materialCode: 'MAT-B', quantity: 1 },
        { id: 'C', materialCode: 'CACHE', quantity: 1 },
      ] }
  }
  const first = await reloadPurchaseOrderDetailDataV1142842728({
    purchaseOrderId: 'po-1', loadSnapshot, executionSequence: 0 })
  const second = await reloadPurchaseOrderDetailDataV1142842728({
    purchaseOrderId: 'po-1', loadSnapshot, previousBusinessKey: first.businessKey,
    executionSequence: 1 })
  assert.equal(reads, 2)
  assert.equal(first.businessKey, second.businessKey)
  assert.notEqual(first.providerExecutionId, second.providerExecutionId)
  assert.equal(second.sourcePurchaseOrderItemCount, 3)
  assert.equal(second.currentPurchaseOrderItemCount, 1)
  assert.equal(second.filteredItemCount, 1)
  assert.equal(second.businessWriteCount, 0)
})

test('number view model separates five business identities without parsing the PO number', () => {
  const model = buildPurchaseOrderNumberViewModelV1142842728({
    purchaseOrder: { id: 'po-1', poNo: 'PO-001' },
    businessView: { identity: { purchaseOrderNo: 'PO-001' }, sourceTrace: { groups: [
      { nodeCode: 'purchase_order_gate', values: ['GATE-1'] },
      { nodeCode: 'purchase_request', values: ['PR-1', 'PR-2'] },
      { nodeCode: 'purchase_inquiry', values: ['INQ-1'] },
      { nodeCode: 'quote_comparison', values: ['QC-1'] },
    ] } },
  })
  assert.deepEqual(model.cards.map(card => card.label), ['PO编号', '来源Gate编号',
    '来源采购申请编号', '关联询价编号', '关联报价比较编号'])
  assert.deepEqual(model.cards[2].values, ['PR-1', 'PR-2'])
  assert.equal(model.businessNumberParsed, false)
})

function printFixture() {
  return {
    companyInfo: { companyName: 'PCE制造有限公司' },
    documentInfo: { documentName: '采购订单', documentNo: 'PO-001' },
    basicInfo: { layout: 'six', fields: [
      { key: 'purchaseOrderNo', label: '采购订单编号', value: 'PO-001' },
      { key: 'supplierName', label: '供应商', value: '供应商A' },
      { key: 'orderDate', label: '采购日期', value: '2026-08-09' },
      { key: 'statusLabel', label: '当前状态', value: '草稿' },
      { key: 'totalQuantity', label: '采购数量', value: 2 },
      { key: 'totalAmount', label: '订单金额', value: '100.00 CNY' },
      { key: 'plannedDeliveryDate', label: '计划到货日期', value: '2026-08-20' },
      { key: 'buyerName', label: '采购员', value: '采购员A' },
    ], longText: [] },
    detailRows: [{ lineNo: 1, materialCode: 'MAT-1', materialName: '物料A',
      specification: 'A', unit: '件', quantity: 2, unitPrice: 50, amount: 100,
      plannedDeliveryDate: '2026-08-20', receiptStatusLabel: '未收货' }],
    approvalInfo: { visible: true, slots: [] },
    printMeta: { detailTitle: '采购物料明细', roleLabel: '管理版',
      purchaseOrderItemSource: 'PurchaseOrderItem[]', printDetailCount: 1,
      detailColumns: ['lineNo','materialCode','materialName','specification','unit','quantity',
        'unitPrice','amount','plannedDeliveryDate','receiptStatusLabel']
        .map(key => ({ key, label: key })) },
  }
}

test('print classifications are five business purposes and warehouse preview changes fields', () => {
  assert.deepEqual(PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728.map(item => item.label),
    ['采购员使用', '仓库使用', '供应商发送', '财务留档', '管理查看'])
  const buyer = projectPurchaseOrderPrintBusinessViewV1142842728(printFixture())
  const warehouse = projectPurchaseOrderPrintBusinessViewV1142842728(printFixture(), 'warehouse')
  assert.equal(buyer.printMeta.outputClassification, 'buyer')
  assert.ok(buyer.printMeta.detailColumns.some(column => column.key === 'unitPrice'))
  assert.ok(warehouse.printMeta.detailColumns.every(column => !['unitPrice', 'amount'].includes(column.key)))
  assert.ok(warehouse.printMeta.detailColumns.some(column => column.key === 'receiptStatusLabel'))
  const html = buildPurchaseOrderBusinessPrintDocumentV1142842728(printFixture(),
    { outputClassification: 'warehouse' })
  assert.match(html, /data-output-classification="warehouse"/)
  assert.match(html, /输出用途：仓库使用 · 收货/)
})

test('route page wires fresh snapshot reload and visible item isolation evidence', () => {
  const page = read('frontend/src/meta/pages/PurchaseOrderDetailPage.vue')
  const view = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  assert.match(page, /reloadPurchaseOrderDetailDataV1142842728/)
  assert.match(page, /loadSnapshot: readPurchaseOrderDetailFactSnapshotV1142842728/)
  assert.doesNotMatch(page, /getScmPurchaseOrderItems/)
  assert.match(view, /当前PurchaseOrderItem数量/)
  assert.match(view, /打印输出用途/)
  assert.doesNotMatch(view, /outputClassification: 'standard'/)
  assert.doesNotMatch(page, /window\.location\.reload\(|router\.go\(0\)/)
})

test('PurchaseOrder core, Provider, Action, Gate, lifecycle and database stay frozen', () => {
  const frozen = JSON.parse(read('purchase_order_data_print_runtime_scan_v1142842728.json'))
    .frozenAssetBaseline
  const paths = {
    purchaseOrderModelSha256: 'backend/procurement/models.py',
    purchaseOrderProviderSha256: 'frontend/src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js',
    purchaseOrderActionSha256: 'frontend/src/meta/actions/scm/createPurchaseOrderActionV114284271.js',
    purchaseOrderCoreStoreSha256: 'frontend/src/meta/scm/scmStore.js',
    purchaseOrderGateSha256: 'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js',
    lifecycleStateMachineSha256: 'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js',
    databaseSha256: 'backend/db.sqlite3',
  }
  Object.entries(paths).forEach(([key, path]) => assert.equal(sha256(path), frozen[key], path))
})

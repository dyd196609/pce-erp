import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { reloadPurchaseOrderDetailPageDataV1142842726 } from
  '../../src/meta/runtime/purchaseOrderDetailPageRuntimeV1142842726.js'
import {
  PURCHASE_ORDER_OUTPUT_CLASSIFICATIONS_V1142842727,
  buildPurchaseOrderClassifiedPrintDocumentV1142842727,
  projectPurchaseOrderPrintOutputV1142842727,
} from '../../src/meta/runtime/purchaseOrderPrintOutputRuntimeV1142842727.js'
import { evaluatePurchaseOrderDetailRuntimeV1142842727 } from
  '../../src/meta/runtime/purchaseOrderDetailRuntimeAcceptanceV1142842727.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('requested governance is loaded and v2.7 runtime rules are applied', () => {
  const paths = [
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/archive/legacy-specs/页面开发模板.md',
    'docs/governance/archive/legacy-specs/一页一验收规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面重构替换规范.md',
    'docs/governance/Codex执行证据规范.md',
  ]
  const governance = paths.map(path => read(path)).join('\n')
  for (const rule of ['PAGE-RUNTIME-001', 'PURCHASE-ORDER-DETAIL-RUNTIME-002',
    'PAGE-MIGRATION-002', 'Runtime Evidence:']) assert.ok(governance.includes(rule), rule)
})

test('real route activates the new runtime component and never imports the old renderer', () => {
  const router = read('frontend/src/router/index.js')
  const page = read('frontend/src/meta/pages/PurchaseOrderDetailPage.vue')
  assert.match(router, /path: 'scm\/purchase-order\/:id'[\s\S]*PurchaseOrderDetailPage\.vue/)
  assert.match(page, /PurchaseOrderDetailRuntimeViewV1142842727/)
  assert.doesNotMatch(page, /ScmPurchaseOrderLifecyclePanelV114284272/)
  assert.doesNotMatch(page, /GenericDetailRenderer/)
})

test('new layout has classification, readable number cards and all required business regions', () => {
  const view = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  for (const region of ['business-view', 'classification', 'order-number-card',
    'basic-information', 'source-relations', 'material-detail', 'lifecycle', 'operations']) {
    assert.ok(view.includes(`data-detail-region="${region}"`), region)
  }
  for (const label of ['采购订单类型', '订单来源', '业务用途', '输出模板', '订单编号',
    'PO编号', '来源Gate编号', '来源单据数量', '复制']) assert.ok(view.includes(label), label)
})

test('material detail is a dedicated sticky-header horizontally scrolling wide table', () => {
  const view = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  for (const field of ['序号', '物料编码', '物料名称', '规格', '单位', '数量',
    '采购执行单价', '金额', '计划到货日期', '收货状态']) assert.ok(view.includes(field), field)
  assert.doesNotMatch(view, /<el-table/)
  assert.match(view, /data-table-layout="sticky-header-horizontal-scroll"/)
  assert.match(view, /position:sticky/)
  assert.match(view, /overflow:auto/)
  assert.match(view, /min-width:1500px/)
})

function printFixture() {
  return {
    companyInfo: { companyName: 'PCE制造有限公司' },
    documentInfo: { documentName: '采购订单', documentNo: 'PO-001' },
    basicInfo: { layout: 'six', fields: [
      { label: '采购订单编号', value: 'PO-001' }, { label: '供应商', value: '供应商A' },
      { label: '采购日期', value: '2026-08-09' }, { label: '订单金额', value: '100.00' },
      { label: '当前状态', value: '草稿' }, { label: '计划到货日期', value: '2026-08-20' },
      { label: '采购员', value: '采购员A' },
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

test('print output classification restores four real template projections with standard default', () => {
  assert.deepEqual(PURCHASE_ORDER_OUTPUT_CLASSIFICATIONS_V1142842727.map(item => item.label),
    ['标准采购订单', '简易采购订单', '物料明细采购订单', '供应商传真订单'])
  const standard = projectPurchaseOrderPrintOutputV1142842727(printFixture())
  const simple = projectPurchaseOrderPrintOutputV1142842727(printFixture(), 'simple')
  const fax = projectPurchaseOrderPrintOutputV1142842727(printFixture(), 'supplier_fax')
  assert.equal(standard.printMeta.outputClassification, 'standard')
  assert.ok(simple.basicInfo.fields.length < standard.basicInfo.fields.length)
  assert.ok(fax.printMeta.detailColumns.every(column => !['unitPrice', 'amount'].includes(column.key)))
  const html = buildPurchaseOrderClassifiedPrintDocumentV1142842727(printFixture(),
    { outputClassification: 'material_detail' })
  assert.match(html, /data-output-classification="material_detail"/)
  assert.match(html, /物料明细采购订单 · 突出物料/)
})

test('refresh performs repeated Provider loads while preserving the current order and zero writes', async () => {
  let loads = 0
  const loadOrder = id => { loads += 1; return { id, poNo: 'PO-001', status: 'draft',
    classification: 'LEGACY_PURCHASE_ORDER' } }
  const loadItems = id => [{ id: 'L-1', poId: id, materialCode: 'MAT-1', quantity: 1 }]
  const first = await reloadPurchaseOrderDetailPageDataV1142842726({
    purchaseOrderId: 'po-1', loadOrder, loadItems })
  const second = await reloadPurchaseOrderDetailPageDataV1142842726({
    purchaseOrderId: 'po-1', loadOrder, loadItems, previousBusinessKey: first.businessKey })
  assert.equal(loads, 2)
  assert.equal(first.businessKey, second.businessKey)
  assert.equal(second.businessWriteCount, 0)
  const page = read('frontend/src/meta/pages/PurchaseOrderDetailPage.vue')
  assert.match(page, /new Date\(\)\.toISOString\(\)/)
  assert.doesNotMatch(page, /window\.location\.reload\(|router\.go\(0\)/)
})

test('runtime acceptance requires real layout, interaction and refresh evidence', () => {
  const result = evaluatePurchaseOrderDetailRuntimeV1142842727({
    urlOpened: true, pageTitleVisible: true, classificationVisible: true,
    numberCardsVisible: true, basicInformationVisible: true, sourceRelationsVisible: true,
    materialWideTableVisible: true, lifecycleVisible: true, operationButtonsVisible: true,
    oldRendererUsed: false, oldLayoutPresent: false, newLayoutActive: true,
    printClassificationChanged: true, printPreviewUpdated: true,
    refreshRequested: true, providerReloaded: true, stateUpdated: true,
    uiTimestampUpdated: true, routeStable: true, businessObjectStable: true,
    businessWriteCount: 0,
  })
  assert.equal(result.result, 'PASS')
  assert.equal(evaluatePurchaseOrderDetailRuntimeV1142842727({}).result, 'FAIL')
})

test('PurchaseOrder core, Provider, Action, Gate, lifecycle and database stay frozen', () => {
  const frozen = JSON.parse(read('purchase_order_detail_real_runtime_scan_v1142842727.json'))
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

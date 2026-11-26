import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  buildPurchaseOrderPrintPreviewDocumentV1142842725,
  normalizePurchaseOrderPrintSettingsV1142842725,
} from '../../src/meta/runtime/purchaseOrderPrintPreviewRuntimeV1142842725.js'
import {
  PURCHASE_ORDER_DETAIL_REGIONS_V1142842725,
  evaluatePurchaseOrderDetailAcceptanceV1142842725,
} from '../../src/meta/runtime/purchaseOrderDetailAcceptanceV1142842725.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

function printView() {
  return {
    companyInfo: { companyName: 'PCE示范制造有限公司' },
    documentInfo: { documentName: '采购订单', documentNo: 'PO202608090001' },
    basicInfo: { layout: 'six', fields: [
      { label: '采购订单编号', value: 'PO202608090001' },
      { label: '供应商', value: '华东供应商' },
      { label: '当前状态', value: '已审批' },
    ], longText: [] },
    detailRows: [{ lineNo: 1, materialCode: 'MAT001', materialName: '铝材',
      quantity: 2, plannedDeliveryDate: '2026-08-20', receiptStatusLabel: '未收货' }],
    approvalInfo: { visible: true, slots: [] },
    printMeta: { detailTitle: '采购物料明细', roleLabel: '管理版',
      purchaseOrderItemSource: 'PurchaseOrderItem[]', printDetailCount: 1,
      detailColumns: [
        { key: 'lineNo', label: '序号' }, { key: 'materialCode', label: '物料编码' },
        { key: 'materialName', label: '物料名称' }, { key: 'quantity', label: '数量' },
      ] },
  }
}

test('requested legacy governance files and current PRINT-FORM-001 mapping are loaded', () => {
  const files = [
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/archive/legacy-specs/页面开发模板.md',
    'docs/governance/archive/legacy-specs/一页一验收规范.md',
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
    'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
  ]
  const governance = files.map(path => { const value = read(path); assert.ok(value.trim()); return value }).join('\n')
  assert.ok(governance.includes('PRINT-FORM-001'))
  assert.ok(governance.includes('页面开发模板'))
  assert.ok(governance.includes('一页一验收'))
})

test('PurchaseOrder model, Provider, Action, Gate, creation entry, lifecycle and database stay frozen', () => {
  const scan = JSON.parse(read('scm_purchase_order_print_detail_scan_v1142842725.json'))
  const frozen = {
    'backend/procurement/models.py': scan.frozenAssetBaseline.purchaseOrderModelSha256,
    'frontend/src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js': scan.frozenAssetBaseline.purchaseOrderProviderSha256,
    'frontend/src/meta/actions/scm/createPurchaseOrderActionV114284271.js': scan.frozenAssetBaseline.purchaseOrderActionSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js': scan.frozenAssetBaseline.purchaseOrderGateSha256,
    'frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue': scan.frozenAssetBaseline.purchaseOrderCreateEntrySha256,
    'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js': scan.frozenAssetBaseline.purchaseOrderLifecycleSha256,
    'backend/db.sqlite3': scan.frozenAssetBaseline.databaseSha256,
  }
  Object.entries(frozen).forEach(([path, expected]) => assert.equal(sha256(path), expected, path))
})

test('print settings default to A4 portrait and support governed choices', () => {
  assert.deepEqual(normalizePurchaseOrderPrintSettingsV1142842725({}), {
    paperSize: 'A4', orientation: 'portrait', scale: 100, margin: 'standard',
  })
  for (const scale of [80, 90, 100, 110]) {
    assert.equal(normalizePurchaseOrderPrintSettingsV1142842725({ scale }).scale, scale)
  }
  assert.equal(normalizePurchaseOrderPrintSettingsV1142842725({ orientation: 'landscape' }).orientation,
    'landscape')
  assert.equal(normalizePurchaseOrderPrintSettingsV1142842725({ margin: 'compact' }).margin, 'compact')
})

test('preview runtime emits portrait/landscape page rules, scale, margins and centered layout', () => {
  const portrait = buildPurchaseOrderPrintPreviewDocumentV1142842725(printView(), {})
  assert.match(portrait, /@page\{size:A4 portrait;margin:12mm\}/)
  assert.match(portrait, /data-orientation="portrait"/)
  assert.match(portrait, /data-scale="100"/)
  assert.match(portrait, /\.form-header,.document-name\{text-align:center\}/)
  assert.match(portrait, /\.basic-table th,.basic-table td\{text-align:center!important\}/)
  const landscape = buildPurchaseOrderPrintPreviewDocumentV1142842725(printView(), {
    orientation: 'landscape', scale: 80, margin: 'compact',
  })
  assert.match(landscape, /@page\{size:A4 landscape;margin:7mm\}/)
  assert.match(landscape, /data-scale="80"/)
})

test('PurchaseOrderDetailView exposes all five stable regions and no new business action', () => {
  const component = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  assert.ok(component.includes('data-detail-view="PurchaseOrderDetailView"'))
  for (const region of PURCHASE_ORDER_DETAIL_REGIONS_V1142842725) {
    assert.ok(component.includes(`data-detail-region="${region.code}"`), region.code)
    assert.ok(component.includes(region.label), region.label)
  }
  for (const term of ['打印设置', 'A4', '竖向', '横向', '80%', '90%', '100%', '110%',
    '标准', '紧凑', '刷新预览']) assert.ok(component.includes(term), term)
  assert.equal(component.includes('CREATE_PURCHASE_ORDER'), false)
})

test('PurchaseOrderDetailAcceptance checks regions, fields and projection data binding', () => {
  const result = evaluatePurchaseOrderDetailAcceptanceV1142842725({
    businessView: {
      identity: { purchaseOrderNo: 'PO202608090001' },
      baseInfo: { supplierName: '华东供应商' },
      materialDetail: { rows: [], source: 'PurchaseOrderItem[]' },
      lifecycle: { lifecycleStatusLabel: '已审批' },
      dataProtection: { projectionOnly: true },
    },
    presentRegionCodes: PURCHASE_ORDER_DETAIL_REGIONS_V1142842725.map(item => item.code),
  })
  assert.equal(result.result, 'PASS')
  assert.equal(result.businessWriteCount, 0)
  assert.equal(result.regionResults.length, 5)
})


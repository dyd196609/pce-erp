import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildPurchaseOrderBusinessNumberViewModelV1142842729,
  resolveCanonicalPurchaseOrderNumberV11428427211 } from
  '../../src/meta/viewModels/purchaseOrderBusinessNumberViewModelV1142842729.js'
import { filterPurchaseOrderItemsByIdentityV1142842728 } from
  '../../src/meta/runtime/purchaseOrderDetailDataRuntimeV1142842728.js'
import { buildPurchaseOrderImportWorkbookV11428427211 } from
  '../../src/meta/runtime/purchaseOrderImportTemplateRuntimeV11428427211.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('required governance applies real business, DOM match and canonical number rules', () => {
  const governance = ['docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/页面真实运行验收规范.md', 'docs/governance/页面需求执行闭环规范.md',
    'docs/governance/Codex执行证据规范.md'].map(read).join('\n')
  for (const rule of ['REAL-BUSINESS-DATA-001', 'DOM-BUSINESS-MATCH-001',
    'NUMBER-CANONICAL-001', 'PURCHASE-ORDER-NUMBER-SOURCE-001',
    'PURCHASE-ORDER-ITEM-OWNERSHIP-001', 'TEMPLATE-SCHEMA-MATCH-001']) {
    assert.ok(governance.includes(rule), rule)
  }
})

test('one canonical PurchaseOrder number is read from the formal instance field', () => {
  const order = { objectNo: 'PO-FORMAL-001', purchaseOrderNo: 'PO-SECONDARY',
    poNo: 'PO-LEGACY' }
  assert.deepEqual(resolveCanonicalPurchaseOrderNumberV11428427211(order), {
    field: 'objectNo', value: 'PO-FORMAL-001', generatedByFrontend: false,
    rule: 'PURCHASE-ORDER-NUMBER-SOURCE-CHECK-002',
  })
  const model = buildPurchaseOrderBusinessNumberViewModelV1142842729({
    purchaseOrder: { objectNo: 'PO202607150081', poNo: 'PO-LEGACY' },
    businessView: { sourceTrace: { groups: [] } },
  })
  assert.equal(model.purchaseOrderNumber, 'PO202607150081')
  assert.equal(model.purchaseOrderNumberField, 'objectNo')
  assert.equal(model.cards.filter(card => card.label === '采购订单编号').length, 1)
  assert.ok(model.cards.every(card => card.label !== 'PO编号'))
})

test('PurchaseOrderItem ownership accepts only canonical purchaseOrderId', () => {
  const items = [
    { id: 'A', purchaseOrderId: 'PO-ID-1', materialCode: 'MAT-A' },
    { id: 'B', purchaseOrderId: 'PO-ID-2', materialCode: 'MAT-B' },
    { id: 'C', poId: 'PO-ID-1', materialCode: 'LEGACY-NOT-NORMALIZED' },
    { id: 'D', purchaseOrderId: 'PO-ID-1', purchaseOrderRelationConflict: true,
      materialCode: 'CONFLICT' },
  ]
  assert.deepEqual(filterPurchaseOrderItemsByIdentityV1142842728(items, 'PO-ID-1')
    .map(item => item.materialCode), ['MAT-A'])
})

test('XLSX import template is generated from PurchaseOrder Schema with two sheets', () => {
  const workbook = buildPurchaseOrderImportWorkbookV11428427211()
  assert.equal(workbook.fileName, '采购订单导入模板.xlsx')
  assert.deepEqual(workbook.sheetNames, ['采购订单导入', '字段说明'])
  assert.equal(workbook.definition.schemaSource, 'PurchaseOrder Schema')
  assert.equal(workbook.bytes[0], 0x50)
  assert.equal(workbook.bytes[1], 0x4b)
  const dataSheet = workbook.entries.find(entry => entry.name.endsWith('sheet1.xml')).content
  const instructionSheet = workbook.entries.find(entry => entry.name.endsWith('sheet2.xml')).content
  for (const field of workbook.definition.fields) assert.ok(dataSheet.includes(field.label), field.label)
  for (const label of ['字段名称', '是否必填', '数据类型', '示例', '说明']) {
    assert.ok(instructionSheet.includes(label), label)
  }
  for (const field of workbook.definition.excludedSystemFields) {
    assert.equal(dataSheet.includes(field.label), false, field.label)
  }
})

test('refresh exposes loading, success and last refresh time without page reload', () => {
  const page = read('frontend/src/meta/pages/PurchaseOrderDetailPage.vue')
  const component = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  assert.match(page, /refreshStatus\.value = 'refreshing'/)
  assert.match(page, /refreshStatus\.value = 'success'/)
  assert.match(page, /lastRefreshTime\.value = result\.providerExecutedAt/)
  assert.match(component, /刷新中/)
  assert.match(component, /刷新成功/)
  assert.match(component, /最近刷新时间/)
  assert.doesNotMatch(page, /window\.location\.reload\(|router\.go\(0\)/)
})

test('Gate, lifecycle and database remain frozen', () => {
  const frozen = JSON.parse(read('purchase_order_true_runtime_scan_v11428427210.json'))
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

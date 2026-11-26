import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildFormalPurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'
import {
  assertCanonicalPurchaseOrderNumberV11428427212,
  PURCHASE_ORDER_CANONICAL_NUMBER_FIELD_V11428427213,
} from '../../src/meta/runtime/purchaseOrderNumberRuntimeV11428427212.js'
import { resolveCanonicalPurchaseOrderNumberV11428427211,
  buildPurchaseOrderBusinessNumberViewModelV1142842729 } from
  '../../src/meta/viewModels/purchaseOrderBusinessNumberViewModelV1142842729.js'
import {
  buildPurchaseOrderHeaderSchemaViewV11428427213,
  getPurchaseOrderItemSchemaColumnsV11428427213,
} from '../../src/meta/runtime/purchaseOrderSchemaViewRuntimeV11428427213.js'
import {
  buildPurchaseOrderImportWorkbookV11428427212,
  verifyPurchaseOrderImportTemplateSchemaBindingV11428427213,
} from '../../src/meta/runtime/purchaseOrderImportTemplateRuntimeV11428427212.js'
import {
  PURCHASE_ORDER_HEADER_SCHEMA_FIELDS,
  PURCHASE_ORDER_ITEM_SCHEMA_FIELDS,
} from '../../src/meta/schema/purchase/purchaseOrder.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('governance files are loaded and the V2.13 rules are applied', () => {
  const governance = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面需求执行闭环规范.md',
    'docs/governance/Codex执行证据规范.md',
    'docs/governance/采购订单导入模板规范.md',
  ].map(read).join('\n')
  for (const rule of ['GOV-001', 'PAGE-RUNTIME-001', 'NUMBER-CANONICAL-001',
    'CODEX-EVIDENCE-001', 'PURCHASE-ORDER-IMPORT-TEMPLATE-002',
    'IMPORT-TEMPLATE-SCHEMA-BIND-002']) assert.ok(governance.includes(rule), rule)
})

test('PurchaseOrder.objectNo is the only canonical business number source', () => {
  assert.equal(PURCHASE_ORDER_CANONICAL_NUMBER_FIELD_V11428427213, 'objectNo')
  const purchaseOrder = {
    objectNo: 'PO202606040002',
    purchaseOrderNo: 'PO-SRDB-PAP-PI-202608040005',
    poNo: 'PO-SRDB-PAP-PI-202608040005',
    sourceGateId: 'POG-SRDB-PAP-PI-202608040005',
  }
  assert.deepEqual(resolveCanonicalPurchaseOrderNumberV11428427211(purchaseOrder), {
    field: 'objectNo', value: 'PO202606040002', generatedByFrontend: false,
    rule: 'PURCHASE-ORDER-NUMBER-SOURCE-CHECK-002',
  })
  assert.equal(assertCanonicalPurchaseOrderNumberV11428427212(purchaseOrder).valid, true)
  assert.equal(assertCanonicalPurchaseOrderNumberV11428427212({
    objectNo: 'PO-SRDB-PAP-PI-202608040005', sourceGateId: 'POG-001',
  }).valid, false)
})

test('creation, state restore, list, detail and print consume objectNo', () => {
  const created = buildFormalPurchaseOrderV114284271({
    gate: { gateId: 'POG-SRDB-PAP-PI-001' },
    supplierPurchaseDraft: { supplierId: 'SUP-001', supplierName: '供应商一' },
    now: '2026-08-10T12:34:56.789Z', sequence: 3,
  }).purchaseOrder
  assert.equal(created.objectNo, 'PO20260810123456789003')
  assert.equal(created.purchaseOrderNo, created.objectNo)
  assert.equal(created.poNo, created.objectNo)

  const store = read('frontend/src/meta/scm/scmStore.js')
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const viewModel = read('frontend/src/meta/viewModels/purchaseOrderViewModelV1142842724.js')
  const printModel = read('frontend/src/meta/viewModels/purchaseOrderPrintViewModelV11428427243.js')
  assert.match(store, /canonicalObjectNo = patch\.objectNo \|\| createNo\('PO'\)/)
  assert.match(store, /objectNo:\s*canonicalObjectNo/)
  assert.match(page, /key: 'objectNo', label: '采购订单编号'/)
  assert.match(page, /key === 'objectNo'\) return getPurchaseOrderNumber\(row\) \|\| '-'/)
  assert.match(viewModel, /resolveCanonicalPurchaseOrderNumberV11428427211/)
  assert.match(printModel, /documentNoField: 'objectNo'/)
})

test('PO duplicate is removed while source Gate remains traceable', () => {
  const component = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  const oldNumberView = read('frontend/src/meta/viewModels/purchaseOrderNumberViewModelV1142842728.js')
  assert.equal(component.includes('>PO编号<'), false)
  assert.equal(oldNumberView.includes("'PO编号'"), false)
  const model = buildPurchaseOrderBusinessNumberViewModelV1142842729({
    purchaseOrder: { objectNo: 'PO202606040002' },
    businessView: { sourceTrace: { groups: [
      { nodeCode: 'purchase_order_gate', values: ['POG-001'] },
    ] } },
  })
  assert.equal(model.purchaseOrderNumber, 'PO202606040002')
  assert.deepEqual(model.cards.find(card => card.code === 'source_gate_number').values,
    ['POG-001'])
})

test('detail uses PurchaseOrder header and item schemas for two primary regions', () => {
  const component = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  assert.match(component, /data-detail-structure="basic-information\+material-detail"/)
  assert.match(component, /buildPurchaseOrderHeaderSchemaViewV11428427213/)
  assert.match(component, /getPurchaseOrderItemSchemaColumnsV11428427213/)
  const header = buildPurchaseOrderHeaderSchemaViewV11428427213({
    purchaseOrder: { supplierName: '供应商一', buyerName: '采购员甲' },
    baseInfo: { supplierName: '供应商一', buyerName: '采购员甲' },
  })
  assert.deepEqual(header.fields.map(field => field.label), [
    '供应商', '采购员', '采购日期', '计划到货日期',
    '采购订单类型', '业务用途', '紧急程度', '币种',
    '付款条件', '交付地址', '交付要求', '备注',
  ])
  assert.equal(header.rowCount, 3)
  assert.deepEqual(getPurchaseOrderItemSchemaColumnsV11428427213().map(field => field.label), [
    '物料编码', '物料名称', '规格', '单位', '数量', '采购执行单价',
    '金额', '计划到货日期', '收货状态',
  ])
})

test('import workbook is strictly generated from Header and Item schemas', () => {
  const binding = verifyPurchaseOrderImportTemplateSchemaBindingV11428427213()
  assert.equal(binding.passed, true)
  assert.deepEqual(binding.headerMissing, [])
  assert.deepEqual(binding.headerUnexpected, [])
  assert.deepEqual(binding.detailMissing, [])
  assert.deepEqual(binding.detailUnexpected, [])
  const relationLabel = PURCHASE_ORDER_HEADER_SCHEMA_FIELDS
    .find(field => field.key === 'objectNo').label
  assert.deepEqual(binding.headerSchemaFields, [relationLabel,
    ...PURCHASE_ORDER_HEADER_SCHEMA_FIELDS.filter(field => field.importable).map(field => field.label)])
  assert.deepEqual(binding.detailSchemaFields, [relationLabel,
    ...PURCHASE_ORDER_ITEM_SCHEMA_FIELDS.filter(field => field.importable).map(field => field.label)])

  const workbook = buildPurchaseOrderImportWorkbookV11428427212()
  assert.deepEqual(workbook.sheetNames, ['采购订单基本信息', '采购订单物料明细'])
  assert.equal(workbook.entries.some(entry => entry.name.endsWith('sheet3.xml')), false)
  assert.equal(workbook.businessWriteCount, 0)
})

test('refresh regression retains provider reload and visible feedback', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const shell = read('frontend/src/meta/components/PceListPageShell.vue')
  assert.match(page, /loadFacts:\s*readPurchaseOrderListFactSnapshotV1142842729/)
  assert.match(page, /loadPurchaseOrderRuntimeCollection/)
  assert.match(page, /purchaseOrderListRefreshStatus\.value = 'refreshing'/)
  assert.match(page, /purchaseOrderListRefreshStatus\.value = 'success'/)
  assert.match(page, /purchaseOrderListLastRefreshTime\.value = formatPurchaseOrderRefreshTime/)
  assert.match(shell, /刷新中\.\.\./)
  assert.match(shell, /刷新成功/)
})

test('Gate, lifecycle and database frozen assets remain unchanged', () => {
  const frozen = JSON.parse(read('purchase_order_true_runtime_scan_v11428427210.json'))
    .frozenAssetBaseline
  const paths = {
    purchaseOrderGateSha256: 'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js',
    lifecycleStateMachineSha256: 'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js',
    databaseSha256: 'backend/db.sqlite3',
  }
  Object.entries(paths).forEach(([key, path]) => assert.equal(sha256(path), frozen[key], path))
})

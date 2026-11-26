import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  getPurchaseOrderNumber,
  inspectPurchaseOrderNumberPurity,
  PURCHASE_ORDER_CANONICAL_NUMBER_FIELD,
} from '../../src/meta/domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'
import { getPurchaseOrderImportTemplateContract } from
  '../../src/meta/contracts/purchaseOrderImportTemplateContract.js'
import {
  buildPurchaseOrderImportSheetRowsV11428427214,
  buildPurchaseOrderImportWorkbookV11428427212,
  verifyPurchaseOrderImportTemplateStrictMatchV11428427214,
} from '../../src/meta/runtime/purchaseOrderImportTemplateRuntimeV11428427212.js'
import {
  PURCHASE_ORDER_HEADER_SCHEMA_FIELDS,
  PURCHASE_ORDER_ITEM_SCHEMA_FIELDS,
} from '../../src/meta/schema/purchase/purchaseOrder.js'
import { filterPurchaseOrderItemsByIdentityV1142842728 } from
  '../../src/meta/runtime/purchaseOrderDetailDataRuntimeV1142842728.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('governance assets contain the V2.14 purity and strict template rules', () => {
  const governance = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面需求执行闭环规范.md',
    'docs/governance/Codex执行证据规范.md',
    'docs/governance/采购订单导入模板规范.md',
  ].map(read).join('\n')
  for (const rule of ['GOV-001', 'PAGE-RUNTIME-001', 'CODEX-EVIDENCE-001',
    'PURCHASE-ORDER-NUMBER-PURITY-001', 'IMPORT-TEMPLATE-STRICT-MATCH-001']) {
    assert.ok(governance.includes(rule), rule)
  }
})

test('canonical number getter is isolated from every source and legacy alias', () => {
  assert.equal(PURCHASE_ORDER_CANONICAL_NUMBER_FIELD, 'objectNo')
  const order = {
    objectNo: 'PO202606040002', poNo: 'PO-LEGACY', purchaseOrderNo: 'PO-LEGACY-2',
    sourceGateNo: 'PAP-PI-001', requestNo: 'PR-001', inquiryNo: 'PI-001', quoteNo: 'QC-001',
  }
  assert.equal(getPurchaseOrderNumber(order), 'PO202606040002')
  assert.equal(getPurchaseOrderNumber({ poNo: 'PO-LEGACY' }), '')
  assert.equal(getPurchaseOrderNumber({ purchaseOrderNo: 'PO-LEGACY' }), '')
  assert.equal(inspectPurchaseOrderNumberPurity(order).valid, true)
  for (const number of ['PO-SRDB-PAP-PI-001', 'PO-PI-001', 'PO-QC-001', 'PO-PAP-001',
    'PO-Gate-001']) assert.equal(inspectPurchaseOrderNumberPurity({ objectNo: number }).valid, false)
})

test('list, detail, print, export, search and sort consume the canonical getter', () => {
  const files = [
    'frontend/src/meta/pages/ScmPage.vue',
    'frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue',
    'frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue',
    'frontend/src/meta/runtime/purchaseOrderDetailPageRuntimeV1142842726.js',
    'frontend/src/meta/runtime/purchaseOrderDetailDataRuntimeV1142842728.js',
    'frontend/src/meta/viewModels/purchaseOrderPrintViewModelV11428427243.js',
    'frontend/src/meta/viewModels/purchaseOrderExportTemplateV1142842724.js',
  ]
  files.forEach(path => assert.match(read(path), /getPurchaseOrderNumber/, path))
  const page = read(files[0])
  assert.match(page, /getPurchaseOrderNumber\(row\).*searchable/)
  assert.match(page, /filteredRows\.value\.map\(row => \(\{ \.\.\.row, objectNo: getPurchaseOrderNumber\(row\) \}\)\)/)
  assert.match(page, /key === 'objectNo'\) return getPurchaseOrderNumber\(row\)/)
  const getter = read('frontend/src/meta/domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js')
  assert.doesNotMatch(getter, /order\.(?:poNo|purchaseOrderNo|source\w+|requestNo|inquiryNo|quoteNo)/)
})

test('import Contract is derived from Schema and Excel structures match exactly', () => {
  const contract = getPurchaseOrderImportTemplateContract()
  const relation = PURCHASE_ORDER_HEADER_SCHEMA_FIELDS.find(field => field.key === 'objectNo')
  const schemaHeader = [relation,
    ...PURCHASE_ORDER_HEADER_SCHEMA_FIELDS.filter(field => field.importable !== false)]
  const schemaDetail = [relation,
    ...PURCHASE_ORDER_ITEM_SCHEMA_FIELDS.filter(field => field.importable !== false)]
  assert.deepEqual(contract.basic.fields.map(field => field.key), schemaHeader.map(field => field.key))
  assert.deepEqual(contract.detail.fields.map(field => field.key), schemaDetail.map(field => field.key))

  const rows = buildPurchaseOrderImportSheetRowsV11428427214()
  assert.deepEqual(rows.basicRows[0], ['序号', '字段名称', '字段值'])
  assert.deepEqual(rows.basicRows.slice(1).map(row => row[0]),
    schemaHeader.map((_, index) => index + 1))
  assert.deepEqual(rows.basicRows.slice(1).map(row => row[1]),
    schemaHeader.map(field => field.label))
  assert.deepEqual(rows.detailRows[0], ['序号', ...schemaDetail.map(field => field.label)])
  assert.deepEqual(rows.instructionRows[0],
    ['序号', 'Sheet名称', '显示名称', '系统字段名', '是否必填', '数据类型', '说明'])
  const strict = verifyPurchaseOrderImportTemplateStrictMatchV11428427214()
  assert.equal(strict.passed, true)
  assert.equal(strict.countMatch, true)
  assert.equal(strict.nameMatch, true)
  assert.equal(strict.orderMatch, true)
  assert.equal(strict.structureMatch, true)
  const workbook = buildPurchaseOrderImportWorkbookV11428427212()
  assert.deepEqual(workbook.sheetNames, ['采购订单基本信息', '采购订单物料明细'])
  assert.equal(workbook.strictMatchRule, 'IMPORT-TEMPLATE-STRICT-MATCH-001')
  assert.equal(workbook.businessWriteCount, 0)
})

test('detail basic fields have left sequence and items remain isolated by PurchaseOrder.id', () => {
  const component = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  assert.match(component, /data-basic-field-index="index \+ 1"/)
  assert.match(component, /class="basic-field-index"/)
  assert.match(component, /data-current-purchase-order-id="purchaseOrder\.id"/)
  const rows = filterPurchaseOrderItemsByIdentityV1142842728([
    { id: 'A-1', purchaseOrderId: 'PO-A', materialCode: 'MAT-A' },
    { id: 'B-1', purchaseOrderId: 'PO-B', materialCode: 'MAT-B' },
    { id: 'A-X', purchaseOrderId: 'PO-A', materialCode: 'MAT-X',
      purchaseOrderRelationConflict: true },
  ], 'PO-A')
  assert.deepEqual(rows.map(row => row.id), ['A-1'])
})

test('forbidden Gate, lifecycle and database assets remain unchanged', () => {
  const frozen = JSON.parse(read('purchase_order_true_runtime_scan_v11428427210.json'))
    .frozenAssetBaseline
  const paths = {
    purchaseOrderGateSha256: 'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js',
    lifecycleStateMachineSha256: 'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js',
    databaseSha256: 'backend/db.sqlite3',
  }
  Object.entries(paths).forEach(([key, path]) => assert.equal(sha256(path), frozen[key], path))
})

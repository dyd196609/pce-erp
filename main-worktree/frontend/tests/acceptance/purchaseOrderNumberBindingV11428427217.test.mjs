import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import purchaseOrderSchema, { PURCHASE_ORDER_LIST_SCHEMA_COLUMNS } from
  '../../src/meta/schema/purchase/purchaseOrder.js'
import { adaptPurchaseOrderRuntimeModel } from
  '../../src/meta/runtime/purchaseOrderRuntimeAdapter.js'
import { buildPurchaseOrderLifecycleDetailReadModelV114284272 } from
  '../../src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js'
import { buildPurchaseOrderViewModelV1142842724 } from
  '../../src/meta/viewModels/purchaseOrderViewModelV1142842724.js'
import { buildPurchaseOrderPrintViewModelV11428427243 } from
  '../../src/meta/viewModels/purchaseOrderPrintViewModelV11428427243.js'
import { buildPurchaseOrderPrintDocumentV11428427241 } from
  '../../src/meta/viewModels/purchaseOrderExportTemplateV1142842724.js'
import { inspectPurchaseOrderNumberPurity } from
  '../../src/meta/domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()
const sqliteSchemaCookie = path => readFileSync(resolve(root, path)).readUInt32BE(40)
const legacyFields = ['purchaseOrderNo', 'poNo', 'sourceNo', 'sourceObjectNo',
  'gateNo', 'displayNo']

test('governance files are loaded and page field source has one rule', () => {
  const paths = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/PCE-ERP运行层文件职责规范.md',
    'docs/governance/业务对象编号唯一性规范.md',
    'docs/governance/旧运行链禁止访问规范.md',
    'docs/governance/页面字段来源唯一规范.md',
  ]
  const content = paths.map(read).join('\n')
  for (const rule of ['GOV-001', 'RUNTIME-FILE-RESPONSIBILITY-001',
    'BUSINESS-OBJECT-NUMBER-UNIQUE-001', 'RUNTIME-CHAIN-001',
    'PAGE-FIELD-SOURCE-UNIQUE-001', 'NUMBER-FIELD-LEGACY-BLOCK-003']) {
    assert.ok(content.includes(rule), rule)
  }
})

test('PurchaseOrder list Schema has objectNo as its only business number field', () => {
  const numberColumn = PURCHASE_ORDER_LIST_SCHEMA_COLUMNS[0]
  assert.equal(numberColumn.field, 'objectNo')
  assert.equal(numberColumn.key, 'objectNo')
  assert.equal(numberColumn.businessField, 'PurchaseOrder.objectNo')
  assert.equal(numberColumn.runtimeField, 'PurchaseOrderRuntimeModel.objectNo')
  assert.equal(numberColumn.fallbackAllowed, false)
  assert.equal(purchaseOrderSchema.ui.list.columns[1], numberColumn)
  const keys = PURCHASE_ORDER_LIST_SCHEMA_COLUMNS.map(column => column.key)
  for (const field of legacyFields) assert.equal(keys.includes(field), false, field)
})

test('list page consumes Schema column and renders row.objectNo without a formatter', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  assert.match(page, /columns:\s*PURCHASE_ORDER_LIST_SCHEMA_COLUMNS/)
  assert.match(page, /data-field-source="PurchaseOrderRuntimeModel\.objectNo"/)
  assert.match(page, /\{\{ row\.objectNo \}\}/)
  assert.doesNotMatch(page,
    /activeType\.value === 'order' && key === 'objectNo'\) return getPurchaseOrderNumber/)
  const orderBlock = page.slice(page.indexOf('order: {'),
    page.indexOf('detailFields:', page.indexOf('order: {')))
  for (const field of legacyFields) assert.doesNotMatch(orderBlock,
    new RegExp(`(?:field|key): ['"]${field}['"]`), field)
})

test('Server objectNo survives Provider/Runtime/Schema/DOM chain unchanged', () => {
  const serverFact = {
    id: 'PO-ID-217', objectType: 'PurchaseOrder', objectNo: 'PO202606040002',
    purchaseOrderNo: 'PO-SRDB-PAP-PI-OLD', poNo: 'QC-OLD',
    gateNo: 'Gate-OLD', supplierId: 'SUP-1', status: 'draft',
  }
  const providerFact = serverFact
  const runtime = adaptPurchaseOrderRuntimeModel({ purchaseOrder: providerFact })
  assert.equal(providerFact.objectNo, 'PO202606040002')
  assert.equal(runtime.objectNo, 'PO202606040002')
  for (const field of ['purchaseOrderNo', 'poNo', 'gateNo']) {
    assert.equal(runtime[field], undefined, field)
  }
  assert.equal(PURCHASE_ORDER_LIST_SCHEMA_COLUMNS[0].field, 'objectNo')
  assert.equal(runtime[PURCHASE_ORDER_LIST_SCHEMA_COLUMNS[0].field], 'PO202606040002')
  assert.equal(runtime.businessWriteCount, 0)
})

test('detail, print and export keep only the canonical PurchaseOrder number', () => {
  const runtime = adaptPurchaseOrderRuntimeModel({
    purchaseOrder: { id: 'PO-ID-217', objectType: 'PurchaseOrder',
      objectNo: 'PO202606040002', purchaseOrderNo: 'PO-SRDB-PAP-PI-OLD',
      poNo: 'QC-OLD', supplierId: 'SUP-1', status: 'draft' },
  })
  const detail = buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder: runtime, orderLines: [],
  })
  assert.equal(detail.baseInfo.objectNo, 'PO202606040002')
  assert.equal(detail.baseInfo.purchaseOrderNo, undefined)
  assert.equal(detail.sourceTrace.gateNo, undefined)
  const view = buildPurchaseOrderViewModelV1142842724({
    purchaseOrder: runtime, orderLines: [], lifecycleDetail: detail,
  })
  assert.equal(view.identity.objectNo, 'PO202606040002')
  assert.equal(view.identity.purchaseOrderNo, undefined)
  const print = buildPurchaseOrderPrintViewModelV11428427243({
    purchaseOrderViewModel: view,
  })
  assert.equal(print.documentInfo.documentNo, 'PO202606040002')
  const html = buildPurchaseOrderPrintDocumentV11428427241(view)
  assert.ok(html.includes('PO202606040002'))
  for (const fragment of ['PO-SRDB-PAP-PI', 'QC-OLD', 'Gate-OLD']) {
    assert.equal(html.includes(fragment), false, fragment)
  }
})

test('NUMBER-FIELD-LEGACY-BLOCK-003 rejects legacy number fragments', () => {
  assert.equal(inspectPurchaseOrderNumberPurity({ objectNo: 'PO202606040002' }).valid, true)
  for (const objectNo of ['PO-SRDB-1', 'PO-PAP-PI-1', 'PO-QC-1', 'PO-Gate-1']) {
    assert.equal(inspectPurchaseOrderNumberPurity({ objectNo }).valid, false, objectNo)
  }
})

test('forbidden assets and import template remain unchanged', () => {
  const frozen = JSON.parse(read('purchase_order_true_runtime_scan_v11428427210.json'))
    .frozenAssetBaseline
  assert.equal(sha256('frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js'),
    frozen.purchaseOrderGateSha256)
  assert.equal(sha256('frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js'),
    frozen.lifecycleStateMachineSha256)
  assert.equal(sqliteSchemaCookie('backend/db.sqlite3'), 2279)
  assert.equal(sha256('frontend/src/meta/contracts/purchaseOrderImportTemplateContract.js'),
    'CBB7920FF5E9C96FBE5E41722AE7BADE591EF338A9F66EA26F0CC0DBF831CDAB')
  assert.equal(sha256('frontend/src/meta/runtime/purchaseOrderImportTemplateRuntimeV11428427212.js'),
    '6EA87812A23F37CB5817EC95A96E39EBE11D59693B2ADFAD05D2737753CA1CFD')
})

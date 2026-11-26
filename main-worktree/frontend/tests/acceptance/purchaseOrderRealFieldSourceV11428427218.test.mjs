import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { readPurchaseOrderListFactSnapshotV1142842729,
  PURCHASE_ORDER_LIST_SERVER_SOURCE_V11428427218 } from
  '../../src/meta/providers/purchaseOrderListDataProviderV1142842729.js'
import { readPurchaseOrderDetailFactSnapshotV1142842728 } from
  '../../src/meta/providers/purchaseOrderDetailDataProviderV1142842728.js'
import { loadPurchaseOrderRuntimeCollection } from
  '../../src/meta/runtime/purchaseOrderRuntimeAdapter.js'
import { reloadPurchaseOrderDetailDataV1142842728 } from
  '../../src/meta/runtime/purchaseOrderDetailDataRuntimeV1142842728.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const serverResponse = Object.freeze({
  success: true,
  data: Object.freeze({
    factSource: 'server',
    apiEndpoint: PURCHASE_ORDER_LIST_SERVER_SOURCE_V11428427218,
    recordCount: 1,
    objects: Object.freeze([Object.freeze({
      objectId: 221,
      objectType: 'PurchaseOrder',
      objectNo: 'PO202606040002',
      sourceObject: Object.freeze({ objectNo: 'PO-SRDB-PAP-PI-LEGACY' }),
      statusCode: 'draft',
      statusLabel: '草稿',
      quantity: '3',
      amount: '2140.00',
      createdAt: '2026-06-04T22:57:44.557659',
      items: Object.freeze([]),
    })]),
  }),
})
const loadServerFacts = async pageCode => {
  assert.equal(pageCode, 'purchase-order')
  return serverResponse
}

test('governance adds the real DOM field source gate', () => {
  const content = [
    'docs/governance/PCE-ERP运行层文件职责规范.md',
    'docs/governance/业务对象编号唯一性规范.md',
    'docs/governance/旧运行链禁止访问规范.md',
    'docs/governance/页面字段来源唯一规范.md',
    'docs/governance/页面真实字段来源追踪规范.md',
  ].map(read).join('\n')
  for (const rule of ['RUNTIME-FILE-RESPONSIBILITY-001',
    'BUSINESS-OBJECT-NUMBER-UNIQUE-001', 'RUNTIME-CHAIN-001',
    'PAGE-FIELD-SOURCE-UNIQUE-001', 'DOM-FIELD-SOURCE-CHECK-001']) {
    assert.ok(content.includes(rule), rule)
  }
})

test('list Provider reads server PurchaseOrder facts and never adopts Gate number', async () => {
  const facts = await readPurchaseOrderListFactSnapshotV1142842729({ loadServerFacts })
  assert.equal(facts.factSource, 'server')
  assert.equal(facts.apiEndpoint, PURCHASE_ORDER_LIST_SERVER_SOURCE_V11428427218)
  assert.equal(facts.providerCode, 'PurchaseOrderListServerFactProviderV11428427218')
  assert.equal(facts.purchaseOrders.length, 1)
  assert.equal(facts.purchaseOrders[0].objectNo, 'PO202606040002')
  assert.equal(facts.purchaseOrders[0].sourceObject, undefined)
  assert.equal(facts.businessWriteCount, 0)
})

test('Runtime row preserves server objectNo without a number conversion layer', async () => {
  const facts = await readPurchaseOrderListFactSnapshotV1142842729({ loadServerFacts })
  const result = loadPurchaseOrderRuntimeCollection({ loadFacts: () => facts })
  assert.equal(result.runtimeModels.length, 1)
  assert.equal(result.runtimeModels[0].objectNo, 'PO202606040002')
  assert.equal(result.runtimeModels[0].sourceObject, undefined)
  assert.equal(result.runtimeModels[0].businessWriteCount, 0)
})

test('ScmPage exposes DOM-to-row proof and binds the real server Provider', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  assert.match(page, /data-field-source="PurchaseOrderRuntimeModel\.objectNo"/)
  assert.match(page, /data-column-key="objectNo"/)
  assert.match(page, /:data-row-object-no="row\.objectNo"/)
  assert.match(page, /data-provider-source="\/api\/procurement\/scm-page-facts\/purchase-order\/"/)
  assert.match(page, /\{\{ row\.objectNo \}\}/)
  assert.match(page, /loadServerFacts: getScmStandardPageFacts/)
})

test('detail uses the same server Provider and keeps the canonical number', async () => {
  const detailFacts = await readPurchaseOrderDetailFactSnapshotV1142842728({ loadServerFacts })
  const detail = await reloadPurchaseOrderDetailDataV1142842728({
    purchaseOrderId: '221',
    loadSnapshot: () => detailFacts,
  })
  assert.equal(detail.businessKey, 'PO202606040002')
  assert.equal(detail.purchaseOrder.objectNo, 'PO202606040002')
  assert.equal(detail.purchaseOrder.sourceObject, undefined)
  assert.equal(detail.businessWriteCount, 0)
})

test('list, print and export projections do not use legacy number fallbacks', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const schema = read('frontend/src/meta/schema/purchase/purchaseOrder.js')
  assert.match(schema, /field: 'objectNo'/)
  assert.match(page, /next\[column\.key\] = formatListCell\(row, column\.key\)/)
  assert.doesNotMatch(page,
    /key === 'objectNo'\)[^\n]*(?:purchaseOrderNo|poNo|sourceGate|displayNo)/)
})

test('Provider fails closed instead of falling back to session or Gate facts', async () => {
  await assert.rejects(
    () => readPurchaseOrderListFactSnapshotV1142842729({
      loadServerFacts: async () => ({ success: false, data: null }),
    }),
    /禁止回退/,
  )
})

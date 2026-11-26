import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const sqliteSchemaCookie = path => readFileSync(resolve(root, path)).readUInt32BE(40)

import {
  adaptPurchaseOrderRuntimeModel,
  adaptPurchaseOrderRuntimeCollection,
  loadPurchaseOrderRuntimeCollection,
  PURCHASE_ORDER_RUNTIME_ADAPTER_CODE,
  PURCHASE_ORDER_RUNTIME_MODEL_TYPE,
} from '../../src/meta/runtime/purchaseOrderRuntimeAdapter.js'
import { getPurchaseOrderNumber } from
  '../../src/meta/domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'
import {
  buildPurchaseOrderImportWorkbookV11428427212,
  verifyPurchaseOrderImportRelationV11428427215,
} from '../../src/meta/runtime/purchaseOrderImportTemplateRuntimeV11428427212.js'
import { getPurchaseOrderImportTemplateContract } from
  '../../src/meta/contracts/purchaseOrderImportTemplateContract.js'
import {
  loadProcessCenterRuntimeModel,
  normalizeProcessCenterEntry,
  PROCESS_CENTER_RUNTIME_COUNT,
} from '../../src/meta/runtime/processCenterRuntime.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('required governance and V2.15 additions are loaded and applied', () => {
  const files = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面需求执行闭环规范.md',
    'docs/governance/Codex执行证据规范.md',
    'docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md',
    'docs/governance/archive/legacy-specs/流程节点真实运行验收规范.md',
    'docs/governance/页面重构替换规范.md',
    'docs/governance/PCE-ERP运行层文件职责规范.md',
    'docs/governance/业务对象编号唯一性规范.md',
    'docs/governance/流程中心入口统一规范.md',
    'docs/governance/采购订单导入模板规范.md',
  ]
  const content = files.map(read).join('\n')
  for (const rule of ['GOV-001', 'PAGE-RUNTIME-001', 'PROCESS-011',
    'RUNTIME-FILE-RESPONSIBILITY-001', 'BUSINESS-OBJECT-NUMBER-UNIQUE-001',
    'PROCESS-CENTER-ENTRY-UNIQUE-001', 'PURCHASE-ORDER-IMPORT-RELATION-001']) {
    assert.ok(content.includes(rule), rule)
  }
})

test('PurchaseOrderRuntimeAdapter is the only runtime model conversion entry', () => {
  const facts = [{ id: 'PO-ID-1', objectType: 'PurchaseOrder', objectNo: 'PO202608100001',
    purchaseOrderNo: 'PO-SRDB-PAP-PI-001', poNo: 'PO-PI-001', supplierId: 'SUP-1',
    supplierName: '供应商一', buyerId: 'BUY-1', buyerName: '采购员一',
    orderDate: '2026-08-10', status: 'draft' }]
  const items = [
    { id: 'I-1', poId: 'PO-ID-1', materialCode: 'MAT-1' },
    { id: 'I-2', poId: 'PO-ID-2', materialCode: 'MAT-2' },
  ]
  const model = adaptPurchaseOrderRuntimeModel({ purchaseOrder: facts[0], items })
  assert.equal(model.runtimeAdapterCode, PURCHASE_ORDER_RUNTIME_ADAPTER_CODE)
  assert.equal(model.runtimeModelType, PURCHASE_ORDER_RUNTIME_MODEL_TYPE)
  assert.equal(model.objectNo, 'PO202608100001')
  assert.equal(model.purchaseOrderNo, undefined)
  assert.equal(model.poNo, undefined)
  assert.deepEqual(model.supplier, { id: 'SUP-1', name: '供应商一' })
  assert.deepEqual(model.buyer, { id: 'BUY-1', name: '采购员一' })
  assert.equal(model.purchaseDate, '2026-08-10')
  assert.deepEqual(model.items.map(item => item.id), ['I-1'])
  assert.equal(model.businessWriteCount, 0)

  const collection = adaptPurchaseOrderRuntimeCollection({
    purchaseOrders: [...facts, { id: 'DEMO', objectNo: 'PO202608100002',
      testDataClassification: 'DEVELOPMENT_TEST_DATA' }], items,
  })
  assert.deepEqual(collection.map(row => row.id), ['PO-ID-1'])
  const loaded = loadPurchaseOrderRuntimeCollection({ loadFacts: () => ({
    purchaseOrders: facts, purchaseOrderItems: items, factSource: 'PurchaseOrder Provider',
  }) })
  assert.equal(loaded.runtimeModels[0].runtimeModelType, PURCHASE_ORDER_RUNTIME_MODEL_TYPE)
})

test('list, detail and formal providers converge on PurchaseOrderRuntimeAdapter', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const detailRuntime = read('frontend/src/meta/runtime/purchaseOrderDetailDataRuntimeV1142842728.js')
  const formalProvider = read('frontend/src/meta/providers/formalPurchaseOrderProviderV114284271.js')
  assert.match(page, /loadPurchaseOrderRuntimeCollection/)
  assert.match(page, /purchaseOrderRuntimeModels\.value/)
  assert.doesNotMatch(page, /activeType\.value === 'order'\s*\? scmState\.value\[activeConfig\.value\.collection\]/)
  assert.match(detailRuntime, /adaptPurchaseOrderRuntimeModel/)
  assert.match(formalProvider, /adaptPurchaseOrderRuntime(?:Collection|Model)/)
  assert.equal(getPurchaseOrderNumber({ objectNo: 'PO202608100003',
    sourceGateNo: 'PAP-PI-003' }), 'PO202608100003')
})

test('import template has two related business sheets using PurchaseOrder number', () => {
  const contract = getPurchaseOrderImportTemplateContract()
  assert.equal(contract.relation.headerField, 'objectNo')
  assert.equal(contract.relation.detailField, 'objectNo')
  assert.equal(contract.basic.fields[0].label, '采购订单编号')
  assert.equal(contract.detail.fields[0].label, '采购订单编号')
  const relation = verifyPurchaseOrderImportRelationV11428427215()
  assert.equal(relation.passed, true)
  assert.equal(relation.headerRelationCount, 1)
  assert.equal(relation.detailRelationCount, 1)
  const workbook = buildPurchaseOrderImportWorkbookV11428427212()
  assert.deepEqual(workbook.sheetNames, ['采购订单基本信息', '采购订单物料明细'])
  assert.equal(workbook.entries.some(entry => entry.name.endsWith('sheet3.xml')), false)
  assert.equal(workbook.relationRule, 'IMPORT-RELATION-002')
  assert.equal(workbook.businessWriteCount, 0)
})

test('all process-center entries use one ProcessCenterRuntime model', () => {
  assert.equal(PROCESS_CENTER_RUNTIME_COUNT, 1)
  const model = loadProcessCenterRuntimeModel()
  assert.equal(model.runtimeCode, 'ProcessCenterRuntime')
  assert.equal(model.runtimeModelType, 'ProcessCenterRuntimeModel')
  assert.equal(model.canonicalRoute, '/process-center')
  assert.ok(model.modules.length > 0)
  assert.ok(model.processes.length > 0)
  assert.deepEqual(normalizeProcessCenterEntry(), {
    path: '/process-center', query: {}, runtimeCode: 'ProcessCenterRuntime',
  })
  assert.deepEqual(normalizeProcessCenterEntry({ moduleCode: 'scm' }), {
    path: '/process-center', query: { module: 'SCM' }, runtimeCode: 'ProcessCenterRuntime',
  })
  const page = read('frontend/src/meta/pages/EnterpriseOSPage.vue')
  const router = read('frontend/src/router/index.js')
  assert.match(page, /loadProcessCenterRuntimeModel/)
  assert.doesNotMatch(page, /from '..\/process\/businessProcessRegistry\.js'/)
  assert.match(page, /data-runtime-code="ProcessCenterRuntime"/)
  assert.match(router, /runtimeCode: 'ProcessCenterRuntime'/)
})

test('duplicate formal implementation scan has one active page entry per runtime', () => {
  const scmPage = read('frontend/src/meta/pages/ScmPage.vue')
  const processPage = read('frontend/src/meta/pages/EnterpriseOSPage.vue')
  assert.equal((scmPage.match(/purchaseOrderRuntimeAdapter\.js/g) || []).length, 1)
  assert.equal((scmPage.match(/purchaseOrderImportTemplateRuntimeV11428427212\.js/g) || []).length, 1)
  assert.equal((processPage.match(/processCenterRuntime\.js/g) || []).length, 1)
  assert.equal((read('frontend/src/meta/runtime/purchaseOrderRuntimeAdapter.js')
    .match(/export function adaptPurchaseOrderRuntimeModel/g) || []).length, 1)
  assert.equal((read('frontend/src/meta/runtime/processCenterRuntime.js')
    .match(/export function loadProcessCenterRuntimeModel/g) || []).length, 1)
})

test('forbidden Gate, lifecycle and database assets remain unchanged', () => {
  const frozen = JSON.parse(read('purchase_order_true_runtime_scan_v11428427210.json'))
    .frozenAssetBaseline
  const paths = {
    purchaseOrderGateSha256: 'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js',
    lifecycleStateMachineSha256: 'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js',
  }
  Object.entries(paths).forEach(([key, path]) => assert.equal(sha256(path), frozen[key], path))
  assert.equal(sqliteSchemaCookie('backend/db.sqlite3'), 2279, 'backend/db.sqlite3 schema')
})

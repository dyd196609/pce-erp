import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const sqliteSchemaCookie = path => readFileSync(resolve(root, path)).readUInt32BE(40)

import {
  adaptPurchaseOrderRuntimeModel,
  PURCHASE_ORDER_RUNTIME_ADAPTER_CODE,
  PURCHASE_ORDER_RUNTIME_MODEL_TYPE,
} from '../../src/meta/runtime/purchaseOrderRuntimeAdapter.js'
import {
  getPurchaseOrderNumber,
  inspectPurchaseOrderNumberPurity,
  PurchaseOrderCanonicalNumber,
} from '../../src/meta/domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'
import {
  buildPurchaseOrderImportSheetRowsV11428427214,
  buildPurchaseOrderImportWorkbookV11428427212,
  validatePurchaseOrderImportRelationRowsV11428427216,
  verifyPurchaseOrderImportRelationV11428427215,
} from '../../src/meta/runtime/purchaseOrderImportTemplateRuntimeV11428427212.js'
import {
  loadProcessCenterRuntimeModel,
  PROCESS_CENTER_ENTRY_COUNT,
  PROCESS_CENTER_RUNTIME_COUNT,
} from '../../src/meta/runtime/processCenterRuntime.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('governance files are loaded and V2.16 gates are archived first', () => {
  const paths = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/PCE-ERP运行层文件职责规范.md',
    'docs/governance/业务对象编号唯一性规范.md',
    'docs/governance/流程中心入口统一规范.md',
    'docs/governance/采购订单导入模板规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/旧运行链禁止访问规范.md',
  ]
  const content = paths.map(path => read(path)).join('\n')
  for (const rule of ['RUNTIME-CHAIN-001', 'LEGACY-FIELD-BLOCK-001',
    'NUMBER-LEGACY-BLOCK-001', 'IMPORT-RELATION-002', 'PROCESS-CENTER-ENTRY-002']) {
    assert.ok(content.includes(rule), rule)
  }
})

test('PurchaseOrder has one canonical number and one runtime conversion chain', () => {
  assert.deepEqual(PurchaseOrderCanonicalNumber, {
    objectType: 'PurchaseOrder', field: 'objectNo', reader: 'getPurchaseOrderNumber',
    fallbackAllowed: false, rule: 'NUMBER-LEGACY-BLOCK-001',
  })
  const model = adaptPurchaseOrderRuntimeModel({
    purchaseOrder: {
      id: 'PO-ID-16', objectType: 'PurchaseOrder', objectNo: 'PO202608100016',
      purchaseOrderNo: 'PAP-PI-OLD', poNo: 'QC-OLD', sourceObject: { id: 'OLD' },
      sourceObjects: [{ id: 'OLD' }], sourceGate: { gateNo: 'Gate-OLD' },
      sourceChain: ['OLD'], temporaryModel: { objectNo: 'OLD' },
    },
  })
  assert.equal(model.runtimeAdapterCode, PURCHASE_ORDER_RUNTIME_ADAPTER_CODE)
  assert.equal(model.runtimeModelType, PURCHASE_ORDER_RUNTIME_MODEL_TYPE)
  assert.equal(model.objectNo, 'PO202608100016')
  for (const key of ['purchaseOrderNo', 'poNo', 'sourceObject', 'sourceObjects',
    'sourceGate', 'sourceChain', 'temporaryModel']) assert.equal(model[key], undefined, key)
  assert.equal(getPurchaseOrderNumber(model), 'PO202608100016')
  assert.equal(inspectPurchaseOrderNumberPurity(model).valid, true)
  for (const value of ['PAP-PI-1', 'QC-1', 'Gate-1', 'source-1']) {
    assert.equal(inspectPurchaseOrderNumberPurity({ objectNo: value }).valid, false)
  }
})

test('old list adapter is removed and active list consumes PurchaseOrderRuntimeModel directly', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const listBlock = page.slice(page.indexOf('const listRows = computed'),
    page.indexOf('const listColumns = computed'))
  assert.match(listBlock, /activeType\.value === 'order'\) return purchaseOrderRuntimeModels\.value/)
  assert.doesNotMatch(listBlock, /sourceRows\s*=\s*activeType\.value === 'order'/)
  const orderConfig = page.slice(page.indexOf('order: {'), page.indexOf('detailFields:', page.indexOf('order: {')))
  assert.doesNotMatch(orderConfig, /key: 'sourceGateId'.*columns/)
  assert.doesNotMatch(read('frontend/src/meta/viewModels/purchaseOrderPrintViewModelV11428427243.js'),
    /identity\?*\.purchaseOrderNo|purchaseOrderNoField/)
  assert.doesNotMatch(read('frontend/src/meta/viewModels/purchaseOrderExportTemplateV1142842724.js'),
    /identity\.purchaseOrderNo|identity\.sourceGateNo/)
})

test('old Excel generators are removed and Header/Detail relation is enforced', () => {
  assert.equal(existsSync(resolve(root,
    'frontend/src/meta/runtime/purchaseOrderImportTemplateRuntimeV1142842729.js')), false)
  assert.equal(existsSync(resolve(root,
    'frontend/src/meta/runtime/purchaseOrderImportTemplateRuntimeV11428427211.js')), false)
  const rows = buildPurchaseOrderImportSheetRowsV11428427214()
  assert.equal(rows.basicRows[0][0], '序号')
  assert.equal(rows.detailRows[0][0], '序号')
  assert.equal(rows.basicRows[0][1], '采购订单编号')
  assert.equal(rows.detailRows[0][1], '采购订单编号')
  assert.equal(verifyPurchaseOrderImportRelationV11428427215().passed, true)
  const valid = validatePurchaseOrderImportRelationRowsV11428427216({
    headerRows: [rows.basicRows[0], [1, 'PO-BATCH-001']],
    detailRows: [rows.detailRows[0], [1, 'PO-BATCH-001'], [2, 'PO-BATCH-001']],
  })
  assert.equal(valid.passed, true)
  assert.equal(valid.businessWriteCount, 0)
  assert.equal(validatePurchaseOrderImportRelationRowsV11428427216({
    headerRows: [rows.basicRows[0], [1, 'PO-BATCH-001']],
    detailRows: [rows.detailRows[0], [1, 'PO-BATCH-002']],
  }).passed, false)
  const workbook = buildPurchaseOrderImportWorkbookV11428427212()
  assert.deepEqual(workbook.sheetNames, ['采购订单基本信息', '采购订单物料明细'])
  assert.equal(workbook.relationRule, 'IMPORT-RELATION-002')
  assert.equal(workbook.businessWriteCount, 0)
})

test('process center has exactly one formal route/runtime entry', () => {
  assert.equal(PROCESS_CENTER_ENTRY_COUNT, 1)
  assert.equal(PROCESS_CENTER_RUNTIME_COUNT, 1)
  const model = loadProcessCenterRuntimeModel()
  assert.equal(model.entryCount, 1)
  assert.equal(model.runtimeCount, 1)
  assert.equal(model.canonicalRoute, '/process-center')
  const router = read('frontend/src/router/index.js')
  const formalRoutes = [...router.matchAll(/path:\s*'process-center',\s*\r?\n\s*component:\s*\(\)\s*=>\s*import\('@\/meta\/pages\/EnterpriseOSPage\.vue'\)/g)]
  assert.equal(formalRoutes.length, 1)
  assert.doesNotMatch(read('frontend/src/meta/pages/EnterpriseOSPage.vue'),
    /from ['"]\.\.\/process\/businessProcessRegistry\.js['"]/)
})

test('forbidden Gate, lifecycle and database assets remain frozen', () => {
  const frozen = JSON.parse(read('purchase_order_true_runtime_scan_v11428427210.json'))
    .frozenAssetBaseline
  const paths = {
    purchaseOrderGateSha256: 'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js',
    lifecycleStateMachineSha256: 'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js',
  }
  for (const [key, path] of Object.entries(paths)) assert.equal(sha256(path), frozen[key], path)
  assert.equal(sqliteSchemaCookie('backend/db.sqlite3'), 2279, 'backend/db.sqlite3 schema')
})

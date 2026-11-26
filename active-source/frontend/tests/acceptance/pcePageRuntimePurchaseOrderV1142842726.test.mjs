import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { reloadPurchaseOrderDetailPageDataV1142842726 } from
  '../../src/meta/runtime/purchaseOrderDetailPageRuntimeV1142842726.js'
import { evaluatePageRuntimeAcceptanceV1142842726 } from
  '../../src/meta/runtime/pageRuntimeAcceptanceV1142842726.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('required governance files are loaded and new runtime rules are executable', () => {
  const required = [
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/archive/legacy-specs/页面开发模板.md',
    'docs/governance/archive/legacy-specs/一页一验收规范.md',
    'docs/governance/archive/legacy-specs/流程节点真实运行验收规范.md',
    'docs/governance/archive/legacy-specs/CODEX执行命令规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面重构替换规范.md',
    'docs/governance/Codex执行证据规范.md',
  ]
  required.forEach(path => assert.ok(read(path).trim(), path))
  assert.match(read('docs/governance/页面真实运行验收规范.md'), /PAGE-RUNTIME-001/)
  assert.match(read('docs/governance/页面重构替换规范.md'), /PAGE-MIGRATION-001/)
  assert.match(read('docs/governance/Codex执行证据规范.md'), /Runtime Evidence:/)
})

test('purchase order detail route directly activates PurchaseOrderDetailPage and old route renderer is removed', () => {
  const router = read('frontend/src/router/index.js')
  const oldPage = read('frontend/src/meta/pages/ScmPage.vue')
  assert.match(router, /path: 'scm\/purchase-order\/:id'[\s\S]*PurchaseOrderDetailPage\.vue/)
  assert.doesNotMatch(router, /path: 'scm\/purchase-order\/:id'[\s\S]{0,320}ScmPage\.vue/)
  assert.doesNotMatch(oldPage, /ScmPurchaseOrderLifecyclePanelV114284272/)
})

test('PurchaseOrderDetailPage establishes the real runtime chain and six business regions', () => {
  const page = read('frontend/src/meta/pages/PurchaseOrderDetailPage.vue')
  const view = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  assert.match(page, /data-route-component="PurchaseOrderDetailPage"/)
  assert.match(page, /reloadPageData/)
  assert.match(page, /reloadPurchaseOrderDetailPageDataV1142842726/)
  for (const label of ['采购订单业务视图', '采购订单基础信息', '来源关系', '采购物料明细',
    '生命周期状态', '操作区域']) assert.ok(view.includes(label), label)
  for (const field of ['采购订单编号', '供应商', '采购员', '订单金额', '当前状态',
    '采购申请', '询价', '报价比较', '核价', '供应商推荐', 'PurchaseOrderGate',
    '物料编码', '物料名称', '规格', '单位', '数量', '采购执行单价', '金额', '计划到货日期']) {
    assert.ok(view.includes(field) || read('frontend/src/meta/viewModels/purchaseOrderViewModelV1142842724.js').includes(field), field)
  }
})

test('print entry is top-right and retains the governed print preview settings', () => {
  const view = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  const nav = view.slice(view.indexOf('<nav'), view.indexOf('</nav>'))
  assert.match(nav, /打印采购订单/)
  assert.match(nav, /openPrintPreview/)
  for (const term of ['PurchaseOrderPrintPreview', 'A4', '竖向', '横向', '80%', '90%',
    '100%', '110%', '标准', '紧凑']) assert.ok(view.includes(term), term)
})

test('refresh runtime reloads provider data, preserves object identity and performs zero writes', async () => {
  let orderLoads = 0
  let itemLoads = 0
  const order = { id: 'po-1', poNo: 'PO202608090001', supplierId: 'SUP-1',
    status: 'draft', classification: 'LEGACY_PURCHASE_ORDER' }
  const result = await reloadPurchaseOrderDetailPageDataV1142842726({
    purchaseOrderId: 'po-1',
    previousBusinessKey: 'PO202608090001',
    loadOrder: id => { orderLoads += 1; return { ...order, id } },
    loadItems: id => { itemLoads += 1; return [{ id: 'line-1', poId: id,
      materialCode: 'MAT-1', quantity: 2, price: 8 }] },
  })
  assert.equal(orderLoads, 1)
  assert.equal(itemLoads, 1)
  assert.equal(result.businessKey, 'PO202608090001')
  assert.equal(result.lifecycleDetailModel.factLoadStatus, 'loaded')
  assert.equal(result.businessWriteCount, 0)
  const page = read('frontend/src/meta/pages/PurchaseOrderDetailPage.vue')
  const view = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  assert.doesNotMatch(page + view, /window\.location\.reload\(|router\.go\(0\)/)
})

test('PAGE/ACTION/REFRESH runtime acceptance passes only with real evidence', () => {
  const passed = evaluatePageRuntimeAcceptanceV1142842726({
    routerActive: true, componentActive: true, runtimeRendered: true,
    oldRendererUsed: false, buttonExists: true, buttonClicked: true,
    actionResult: true, refreshHandlerExists: true, providerReloaded: true,
    uiUpdated: true, routeStable: true, businessObjectStable: true,
    businessWriteCount: 0,
  })
  assert.equal(passed.result, 'PASS')
  assert.equal(evaluatePageRuntimeAcceptanceV1142842726({}).result, 'FAIL')
})

test('PurchaseOrder core, Provider, Action, Gate, lifecycle and database remain frozen', () => {
  const frozen = JSON.parse(read('pce_page_runtime_purchase_order_scan_v1142842726.json'))
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

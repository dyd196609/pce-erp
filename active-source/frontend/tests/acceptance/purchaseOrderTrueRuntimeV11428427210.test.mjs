import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildPurchaseOrderBusinessNumberViewModelV1142842729 } from
  '../../src/meta/viewModels/purchaseOrderBusinessNumberViewModelV1142842729.js'
import { PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728 } from
  '../../src/meta/runtime/purchaseOrderPrintBusinessRuntimeV1142842728.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('true-page-first governance is loaded and Browser DOM has highest priority', () => {
  const governance = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面重构替换规范.md',
    'docs/governance/Codex执行证据规范.md',
    'docs/governance/页面需求执行闭环规范.md',
  ].map(read).join('\n')
  for (const rule of ['BROWSER-DOM-001', 'Browser DOM', 'User Click', 'Runtime State',
    'Provider Data', 'CODEX-COMMAND-002']) assert.ok(governance.includes(rule), rule)
})

test('classification region owns a real select with all five business options', () => {
  const component = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  const region = component.match(/data-detail-region="classification"[\s\S]*?<\/article>/)?.[0] || ''
  assert.match(region, /<el-select/)
  assert.match(region, /data-acceptance-id="purchase-order-output-purpose-select"/)
  assert.match(region, /输出用途/)
  assert.deepEqual(PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728.map(item => item.label),
    ['采购员使用', '仓库使用', '供应商使用', '财务留档', '管理查看'])
})

test('PurchaseOrderBusinessNumber uses dedicated instance fields and governed pending labels', () => {
  const longComposite = `PO-${'PR001-'.repeat(10)}`
  const pending = buildPurchaseOrderBusinessNumberViewModelV1142842729({
    purchaseOrder: { poNo: longComposite }, businessView: { sourceTrace: { groups: [] } },
  })
  assert.equal(pending.businessObject, 'PurchaseOrderBusinessNumber')
  assert.equal(pending.purchaseOrderNumber, '待生成采购订单编号')
  assert.equal(pending.poNumber, '待生成PO编号')
  assert.ok(pending.cards.every(card => !card.values.includes('未建立独立采购订单编号')))
  const actual = buildPurchaseOrderBusinessNumberViewModelV1142842729({
    purchaseOrder: { purchaseOrderNumber: 'PURCHASE-001', poNumber: 'PO-001',
      supplierOrderNo: 'SUP-001' },
    businessView: { sourceTrace: { groups: [
      { nodeCode: 'purchase_order_gate', values: ['GATE-1'] },
      { nodeCode: 'purchase_request', values: ['PR-1', 'PR-2'] },
    ] } },
  })
  assert.deepEqual(actual.cards.map(card => card.label), ['采购订单编号', 'PO编号', '来源Gate编号',
    '来源采购申请编号', '供应商订单编号'])
})

test('material DOM renders only strict orderLines and exposes governed business rows', () => {
  const component = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  assert.match(component, /orderLines: props\.orderLines/)
  assert.doesNotMatch(component, /orderLines: props\.lifecycleDetailModel\.purchaseOrderItems \|\| props\.orderLines/)
  assert.match(component, /data-purchase-order-item-row/)
  assert.match(component, /DOM Render Count/)
})

test('refresh chain records click, Provider execution and DOM commit without timestamp-only acceptance', () => {
  const page = read('frontend/src/meta/pages/PurchaseOrderDetailPage.vue')
  const component = read('frontend/src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
  assert.match(page, /CLICK-/)
  assert.match(page, /result\.providerExecutionId/)
  assert.match(page, /DOM-COMMIT-/)
  assert.match(component, /purchase-order-refresh-action-trace/)
  assert.match(component, /刷新当前订单/)
  assert.doesNotMatch(page, /window\.location\.reload\(|router\.go\(0\)/)
})

test('import template remains connected to the real purchase-order list', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  assert.match(page, /purchase-order-import-template-button/)
  assert.match(page, /downloadPurchaseOrderImportTemplateV1142842729/)
})

test('PurchaseOrder core, Gate, lifecycle and database remain frozen', () => {
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

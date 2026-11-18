import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildPurchaseOrderLifecycleDetailReadModelV114284272 } from
  '../../src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const clone = value => JSON.parse(JSON.stringify(value))
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path))).digest('hex').toUpperCase()

test('governance files and five runtime governance rules are loaded', () => {
  const files = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
    'docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md',
    'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
    'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
    'docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md',
  ]
  files.forEach(path => assert.ok(read(path).trim().length > 0, path))
  const all = files.map(read).join('\n')
  for (const code of ['PAGE-RUNTIME-FREEZE-001', 'FLOW-VISUAL-FREEZE-001',
    'DATA-IDENTITY-001', 'DATA-EXTRACT-001', 'ARRAY-COMPLETENESS-001']) {
    assert.ok(all.includes(code), code)
  }
})

test('pre-implementation scan and frozen assets are present and unchanged', () => {
  const scan = JSON.parse(read('scm_purchase_order_detail_route_scan_v1142721.json'))
  assert.equal(scan.version, 'V1.14.2.8.4.27.2.1')
  assert.equal(scan.findingsBeforeImplementation.length, 4)
  const frozen = {
    'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js': scan.frozenAssetBaseline.purchaseOrderLifecycleRuntimeSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationContext.js': scan.frozenAssetBaseline.purchaseOrderCreationContextSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js': scan.frozenAssetBaseline.supplierPurchaseDraftSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/guard/purchaseOrderMaterialEligibilityGuardV114284271144.js': scan.frozenAssetBaseline.materialEligibilityGuardSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js': scan.frozenAssetBaseline.purchaseOrderCreationGuardSha256,
    'frontend/src/meta/scm/scmStore.js': scan.frozenAssetBaseline.scmStoreSha256,
    'backend/db.sqlite3': scan.frozenAssetBaseline.databaseSha256,
  }
  Object.entries(frozen).forEach(([path, hash]) => assert.equal(sha256(path), hash, path))
})

test('operation guide is Chinese, complete and positioned before procurement context', () => {
  const guide = read('frontend/src/meta/components/ScmPurchaseOrderOperationGuideV1142842721.vue')
  for (const term of ['采购订单操作流程说明', '步骤1：采购需求准备', '步骤2：创建采购订单草稿',
    '步骤3：人工确认采购信息', '步骤4：创建正式采购订单', '步骤5：提交审批',
    '步骤6：审批通过后下达供应商', '供应商、物料、数量、价格、交期、备注']) {
    assert.ok(guide.includes(term), term)
  }
  const createPage = read('frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue')
  const guardIndex = createPage.indexOf('purchase-order-creation-guard')
  const guideIndex = createPage.indexOf('<ScmPurchaseOrderOperationGuideV1142842721')
  const contextIndex = createPage.indexOf('purchase-order-gate-context')
  assert.ok(guardIndex < guideIndex && guideIndex < contextIndex)
})

test('canonical list route, compatible alias and number link all reach detail', () => {
  const router = read('frontend/src/router/index.js')
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  assert.match(router, /path: 'scm\/purchase-orders',[\s\S]*?redirect: '\/scm\/purchase-order'/)
  assert.match(router, /path: 'scm\/purchase-order\/:id'[\s\S]*?pageCode: 'purchase-order-detail'/)
  assert.ok(page.includes("listPath: '/scm/purchase-order'"))
  assert.ok(page.includes("column.key === 'poNo'"))
  assert.ok(page.includes('@click="openDetail(row)"'))
  assert.equal(page.includes("route.path === '/scm/purchase-order'"), false)
})

function governedOrder(status = 'draft') {
  return {
    objectType: 'PurchaseOrder', classification: 'GATE_CREATED', id: 'PO-ID-2721',
    poNo: 'PO202608090021', supplierId: 'SUP-001', supplierName: '示例供应商',
    lifecycleStatus: status, status, sourceGateId: 'GATE-ID-2721',
    sourcePurchaseRequestIds: ['PR-003', 'PR-001'],
    approvalStatus: status === 'pending_approval' ? 'pending_approval' : 'not_started',
    approvalHistory: [], totalAmount: 300,
  }
}

test('SourceRelations stay complete without business-number parsing or first-item extraction', () => {
  const order = governedOrder()
  const lines = [
    { id: 'L1', quantity: 2, amount: 200, sourcePurchaseRequestIds: ['PR-002', 'PR-001'] },
    { id: 'L2', quantity: 1, amount: 100, sourcePurchaseRequestIds: ['PR-004'] },
  ]
  const view = buildPurchaseOrderLifecycleDetailReadModelV114284272({ purchaseOrder: order, orderLines: lines })
  assert.deepEqual(view.sourceTrace.sourcePurchaseRequestIds, ['PR-003', 'PR-001', 'PR-002', 'PR-004'])
  assert.equal(view.sourceTrace.sourceRelationCount, 4)
  assert.equal(view.sourceArrayCompleteness.inputItemCount, 4)
  assert.deepEqual(view.sourceArrayCompleteness.missingKeys, [])
  assert.equal(view.sourceTrace.businessNoParsed, false)
  const sources = [
    'frontend/src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js',
    'frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue',
  ].map(read).join('\n')
  assert.equal(/source(?:Ids|PurchaseRequestIds)\s*\[\s*0\s*\]/.test(sources), false)
  assert.equal(/poNo[^\n]*\.split\s*\(/.test(sources), false)
})

test('new and legacy orders both open read-only detail with four required regions', () => {
  const governed = buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder: governedOrder('draft'), orderLines: [{ id: 'L1', quantity: 3, amount: 300 }],
  })
  assert.equal(governed.result, 'PASS')
  assert.equal(governed.baseInfo.purchaseOrderNo, 'PO202608090021')
  assert.equal(governed.sourceTrace.traceable, true)

  const legacyOrder = { id: 'LEGACY-PO-1', poNo: 'PO-OLD-001', supplierId: 'SUP-OLD',
    status: 'approved', totalAmount: 88, sourceObjectId: '' }
  const legacy = buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder: legacyOrder, orderLines: [{ id: 'OLD-L1', quantity: 2, amount: 88 }],
  })
  assert.equal(legacy.result, 'PASS')
  assert.equal(legacy.baseInfo.orderTypeLabel, '历史采购订单')
  assert.equal(legacy.sourceTrace.sourceLabel, '历史数据不可追溯')
  assert.equal(legacy.sourceTrace.sourcePurchaseRequestIds.length, 0)

  const panel = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  for (const term of ['采购订单基础信息', '来源追踪', '采购订单生命周期', '审批信息',
    '当前状态', '状态历史', '下一允许动作', '审批人', '审批时间', '审批意见',
    '历史采购订单', '历史数据不可追溯']) assert.ok(panel.includes(term), term)
})

test('lifecycle displays exactly one governed action for each requested state', () => {
  const expected = {
    draft: ['submit_approval', '提交审批'],
    pending_approval: ['view_approval', '查看审批'],
    approved: ['issue_purchase_order', '下达采购订单'],
    issued: ['view_receipt', '查看收货'],
  }
  Object.entries(expected).forEach(([status, [code, label]]) => {
    const view = buildPurchaseOrderLifecycleDetailReadModelV114284272({
      purchaseOrder: governedOrder(status), orderLines: [],
    })
    assert.equal(view.nextAction.code, code)
    assert.equal(view.nextAction.label, label)
  })
})

test('approval display keeps full history and resolves current record without dropping sources', () => {
  const order = { ...governedOrder('approved'), approvalStatus: 'approved', approvalHistory: [
    { recordId: 'A1', result: 'pending', approvedBy: '采购主管', approvedAt: '2026-08-09 09:00', opinion: '待复核' },
    { recordId: 'A2', result: 'approved', approvedBy: '采购经理', approvedAt: '2026-08-09 10:00', opinion: '同意' },
  ] }
  const view = buildPurchaseOrderLifecycleDetailReadModelV114284272({ purchaseOrder: order, orderLines: [] })
  assert.equal(view.approvalDisplay.history.length, 2)
  assert.equal(view.approvalDisplay.approvedBy, '采购经理')
  assert.equal(view.approvalDisplay.opinion, '同意')
})

test('refresh projection preserves supplier, material, quantity, price, delivery, remark and lifecycle', () => {
  const order = { ...governedOrder('issued'), remark: '人工订单备注', manualDataVersion: 7 }
  const lines = [{ id: 'L1', materialCode: 'MAT-001', supplierId: 'SUP-001',
    confirmedQuantity: 5, confirmedPrice: 99, confirmedDeliveryDate: '2026-08-15',
    remark: '人工行备注', sourcePurchaseRequestIds: ['PR-001'] }]
  const before = clone({ order, lines })
  const first = buildPurchaseOrderLifecycleDetailReadModelV114284272({ purchaseOrder: order, orderLines: lines })
  const refresh = buildPurchaseOrderLifecycleDetailReadModelV114284272({ purchaseOrder: order, orderLines: lines })
  assert.deepEqual({ order, lines }, before)
  assert.deepEqual(refresh, first)
  assert.equal(refresh.lifecycle.lifecycleStatus, 'issued')
  assert.equal(refresh.businessWriteCount, 0)
  assert.equal(refresh.purchaseOrderStatusChanged, false)
})

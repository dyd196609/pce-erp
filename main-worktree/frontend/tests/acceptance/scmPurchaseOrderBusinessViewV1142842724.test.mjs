import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  PURCHASE_ORDER_VIEW_PERMISSION_RULE_V1142842724,
  buildPurchaseOrderViewModelV1142842724,
  resolvePurchaseOrderViewAccessV1142842724,
} from '../../src/meta/viewModels/purchaseOrderViewModelV1142842724.js'
import { buildPurchaseOrderExportTemplateV1142842724,
  purchaseOrderExportCsvV1142842724 } from
  '../../src/meta/viewModels/purchaseOrderExportTemplateV1142842724.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()
const clone = value => JSON.parse(JSON.stringify(value))

function fixture() {
  return {
    purchaseOrder: {
      id: 'PO-ID-2724', poNo: 'PO202608090024', classification: 'GATE_CREATED',
      supplierId: 'SUP-001', supplierName: '华东供应商', buyerId: 'EMP-003', buyerName: '赵强',
      status: 'approved', lifecycleStatus: 'approved', plannedArrivalDate: '2026-08-20',
      remark: '采购内部备注', sourceGateId: 'GATE-ID-024',
      sourceRelations: { purchaseRequestIds: ['PR-001', 'PR-002'], purchaseInquiryIds: ['PI-001'],
        priceApprovalIds: ['PA-001'], supplierRecommendationIds: ['REC-001'] },
    },
    orderLines: [
      { id: 'L-1', lineNo: 1, materialCode: 'MAT-001', materialName: '原纸',
        specification: '80g', unit: '卷', quantity: 5, price: 100,
        plannedArrivalDate: '2026-08-20', receiptStatus: 'partially_received', remark: '分批到货',
        sourcePurchaseRequestIds: ['PR-003'] },
      { id: 'L-2', lineNo: 2, materialCode: 'MAT-002', materialName: '油墨',
        specification: '黑色', unit: '桶', quantity: 2, price: 80,
        plannedArrivalDate: '2026-08-21', receiptStatus: 'pending' },
    ],
    lifecycleDetail: {
      baseInfo: { orderTypeLabel: 'Gate治理采购订单' },
      sourceTrace: { sourceGateId: 'GATE-ID-024', sourcePurchaseRequestIds: ['PR-001', 'PR-002', 'PR-003'],
        traceable: true, sourceLabel: '采购订单来源关系' },
      lifecycle: { lifecycleStatus: 'approved', lifecycleStatusLabel: '已审批', validStatus: true,
        steps: [{ status: 'draft', label: '草稿', result: 'COMPLETED' },
          { status: 'approved', label: '已审批', result: 'CURRENT' }] },
      lifecycleHistory: [{ status: 'approved', statusLabel: 'approved', changedBy: '采购经理',
        changedAt: '2026-08-09 10:00', reason: '审批通过' }],
      nextAction: { code: 'issue_purchase_order', label: '下达采购订单', mode: 'controlled_action_pending' },
      approvalStatusLabel: 'approved', approvalDisplay: { approvedBy: '采购经理',
        approvedAt: '2026-08-09 10:00', opinion: '同意', history: [
          { result: 'approved', approvedBy: '采购经理', approvedAt: '2026-08-09 10:00', opinion: '同意' }] },
    },
  }
}

test('governance files and requested rules are loaded', () => {
  const files = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
    'docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md',
    'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
    'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
    'docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md',
  ]
  const all = files.map(path => { const content = read(path); assert.ok(content.trim()); return content }).join('\n')
  for (const code of ['LIST-BUSINESS-CAPABILITY-001', 'LIST-EXPORT-001',
    'TECH-FIELD-SEPARATION-001', 'DATA-IDENTITY-001', 'DATA-EXTRACT-001',
    'PURCHASE-ORDER-VIEW-PERMISSION-001']) assert.ok(all.includes(code), code)
})

test('forbidden purchase order core, lifecycle, creation, provider, store and database assets stay frozen', () => {
  const scan = JSON.parse(read('scm_purchase_order_business_view_scan_v1142724.json'))
  const frozen = {
    'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js': scan.frozenAssetBaseline.purchaseOrderLifecycleRuntimeSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationContext.js': scan.frozenAssetBaseline.purchaseOrderCreationContextSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js': scan.frozenAssetBaseline.purchaseOrderCreationGuardSha256,
    'frontend/src/meta/runtime/purchaseOrderCreationGateRuntime.js': scan.frozenAssetBaseline.purchaseOrderCreationGateRuntimeSha256,
    'frontend/src/meta/scm/scmStore.js': scan.frozenAssetBaseline.purchaseOrderCoreStoreSha256,
    'frontend/src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js': scan.frozenAssetBaseline.purchaseOrderLifecycleDetailProviderSha256,
    'backend/db.sqlite3': scan.frozenAssetBaseline.databaseSha256,
  }
  Object.entries(frozen).forEach(([path, hash]) => assert.equal(sha256(path), hash, path))
})

test('four role views enforce field separation', () => {
  const data = fixture()
  const views = Object.fromEntries(['buyer', 'warehouse', 'supplier', 'management']
    .map(role => [role, buildPurchaseOrderViewModelV1142842724({ ...data, viewRole: role })]))
  assert.equal(PURCHASE_ORDER_VIEW_PERMISSION_RULE_V1142842724, 'PURCHASE_ORDER_VIEW_PERMISSION-001')
  assert.equal(views.buyer.permissions.price, true)
  assert.equal(views.buyer.permissions.approval, true)
  assert.equal(views.warehouse.permissions.price, false)
  assert.equal(views.warehouse.permissions.approval, false)
  assert.equal(views.warehouse.materialDetail.columns.some(column => ['unitPrice', 'amount'].includes(column.key)), false)
  assert.equal(views.supplier.permissions.approval, false)
  assert.equal(views.supplier.permissions.recommendationEvidence, false)
  assert.equal(views.management.permissions.supplierEvaluation, true)
  assert.deepEqual(resolvePurchaseOrderViewAccessV1142842724('manager').allowedRoles,
    ['buyer', 'warehouse', 'supplier', 'management'])
  assert.deepEqual(resolvePurchaseOrderViewAccessV1142842724('warehouse').allowedRoles, ['warehouse'])
})

test('material detail uses business columns and Chinese labels', () => {
  const view = buildPurchaseOrderViewModelV1142842724({ ...fixture(), viewRole: 'buyer' })
  assert.deepEqual(view.materialDetail.columns.map(column => column.label),
    ['序号', '物料编码', '物料名称', '规格', '单位', '数量', '采购执行单价', '金额', '计划到货日期', '收货状态', '备注'])
  assert.equal(view.baseInfo.statusLabel, '已审批')
  assert.equal(view.materialDetail.rows[0].receiptStatusLabel, '部分收货')
  assert.equal(view.approval.history[0].resultLabel, '已审批')
  assert.equal(view.lifecycle.history[0].statusLabel, '已审批')
})

test('qualified price belongs outside purchase order detail and no material master update exists', () => {
  const view = buildPurchaseOrderViewModelV1142842724({ ...fixture(), viewRole: 'management' })
  const component = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  assert.equal(view.priceBoundary.qualifiedMaterialPriceVisible, false)
  assert.equal(view.priceBoundary.materialMasterAutoUpdate, false)
  assert.equal(component.includes('qualified-material-price-region'), false)
  assert.equal(component.includes('qualifiedPriceRows'), false)
  assert.ok(component.includes('采购执行价格'))
})

test('export templates inherit each role view without technical or unauthorized fields', () => {
  const data = fixture()
  for (const role of ['buyer', 'warehouse', 'supplier', 'management']) {
    const view = buildPurchaseOrderViewModelV1142842724({ ...data, viewRole: role })
    const template = buildPurchaseOrderExportTemplateV1142842724(view)
    assert.deepEqual(template.columns.map(column => column.key),
      view.materialDetail.columns.map(column => column.key))
    assert.equal(template.includesTechnicalFields, false)
    assert.equal(template.inheritsViewPermission, true)
    assert.match(purchaseOrderExportCsvV1142842724(template), /物料编码/)
  }
  const warehouse = buildPurchaseOrderExportTemplateV1142842724(
    buildPurchaseOrderViewModelV1142842724({ ...data, viewRole: 'warehouse' }))
  assert.equal(warehouse.columns.some(column => ['unitPrice', 'amount'].includes(column.key)), false)
})

test('source arrays remain complete and business numbers are never parsed', () => {
  const input = fixture()
  const before = clone(input)
  const view = buildPurchaseOrderViewModelV1142842724({ ...input, viewRole: 'management' })
  assert.deepEqual(input, before)
  const purchaseRequests = view.sourceTrace.groups.find(group => group.label === '采购申请').values
  assert.deepEqual(purchaseRequests, ['PR-001', 'PR-002', 'PR-003'])
  const sources = [
    'frontend/src/meta/viewModels/purchaseOrderViewModelV1142842724.js',
    'frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue',
  ].map(read).join('\n')
  assert.equal(/source\w*Ids\s*\[\s*0\s*\]/.test(sources), false)
  assert.equal(/poNo[^\n]*\.split\s*\(/.test(sources), false)
  assert.equal(view.dataProtection.businessWriteCount, 0)
})

test('detail page closes generic technical detail and supplies nine governed filters', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const component = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  const names = read('frontend/src/meta/governance/businessNameRegistry.js')
  for (const term of ['采购订单基础信息', '来源追踪', '采购物料明细', '采购订单生命周期',
    '审批信息', '采购订单业务视图', '导出']) assert.ok(component.includes(term), term)
  assert.ok(page.includes("!(activeType === 'order' && pageMode === 'detail')"))
  for (const key of ['poNo', 'supplierId', 'buyerId', 'status', 'earliestArrivalDate',
    'deliveryUrgency', 'totalAmount', 'materialSearch', 'createdAt']) {
    assert.ok(page.includes(`key: '${key}'`), key)
  }
  assert.ok(page.includes('@export-audit="handlePurchaseOrderExportAudit"'))
  assert.ok(names.includes("['PurchaseOrderDetail','purchase-order-detail','采购订单详情'"))
})

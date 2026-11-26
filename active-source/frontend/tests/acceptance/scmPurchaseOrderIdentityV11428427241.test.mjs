import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildPurchaseOrderViewModelV1142842724 } from
  '../../src/meta/viewModels/purchaseOrderViewModelV1142842724.js'
import {
  buildPurchaseOrderExportTemplateV1142842724,
  buildPurchaseOrderPrintDocumentV11428427241,
} from '../../src/meta/viewModels/purchaseOrderExportTemplateV1142842724.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()
const clone = value => JSON.parse(JSON.stringify(value))

function fixture(overrides = {}) {
  return {
    purchaseOrder: {
      id: 'PO-OBJECT-ID-001',
      poNo: 'PO-20260809-001',
      sourceGateId: 'POG-20260809-099',
      supplierName: '华东供应商',
      lifecycleStatus: 'approved',
      plannedArrivalDate: '2026-08-20',
      deliveryUrgencyCode: 'urgent',
      deliveryUrgencySource: 'PurchaseOrder.deliveryUrgencyCode',
      sourceRelations: {
        purchaseRequestIds: ['PR-001', 'PR-002'],
        purchaseInquiryIds: ['PI-001', 'PI-002'],
        quoteComparisonIds: ['QC-001'],
        priceApprovalIds: ['PA-001'],
        supplierRecommendationIds: ['SR-001', 'SR-002'],
      },
      ...overrides,
    },
    orderLines: [{
      materialCode: 'MAT-001', materialName: '原纸', quantity: 2, price: 100,
      sourcePurchaseRequestIds: ['PR-003'],
    }],
    lifecycleDetail: {
      sourceTrace: {
        sourceGateId: 'POG-20260809-099',
        sourcePurchaseRequestIds: ['PR-001', 'PR-002', 'PR-003'],
        traceable: true,
      },
      lifecycle: { lifecycleStatus: 'approved', steps: [] },
    },
  }
}

test('governance files and identity, export, urgency and extraction rules are loaded', () => {
  const files = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
    'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
    'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
    'docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md',
  ]
  const governance = files.map(path => { const content = read(path); assert.ok(content.trim()); return content }).join('\n')
  for (const rule of ['LIST-EXPORT-001', 'TECH-FIELD-SEPARATION-001',
    'DELIVERY-URGENCY-001', 'DATA-IDENTITY-001', 'DATA-EXTRACT-001']) {
    assert.ok(governance.includes(rule), rule)
  }
})

test('database, Gate, creation, lifecycle, core store and legacy provider assets stay frozen', () => {
  const scan = JSON.parse(read('scm_purchase_order_identity_scan_v11427241.json'))
  const frozen = {
    'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js': scan.frozenAssetBaseline.purchaseOrderLifecycleRuntimeSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationContext.js': scan.frozenAssetBaseline.purchaseOrderCreationContextSha256,
    'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js': scan.frozenAssetBaseline.purchaseOrderCreationGuardSha256,
    'frontend/src/meta/runtime/purchaseOrderCreationGateRuntime.js': scan.frozenAssetBaseline.purchaseOrderCreationGateRuntimeSha256,
    'frontend/src/meta/scm/scmStore.js': scan.frozenAssetBaseline.purchaseOrderCoreStoreSha256,
    'frontend/src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js': scan.frozenAssetBaseline.purchaseOrderLifecycleDetailProviderSha256,
    'backend/db.sqlite3': scan.frozenAssetBaseline.databaseSha256,
  }
  Object.entries(frozen).forEach(([path, expected]) => assert.equal(sha256(path), expected, path))
})

test('PurchaseOrder number is independent from Gate number and technical identity is hidden', () => {
  const view = buildPurchaseOrderViewModelV1142842724({ ...fixture(), viewRole: 'buyer' })
  assert.equal(view.identity.purchaseOrderNo, 'PO-20260809-001')
  assert.equal(view.identity.sourceGateNo, 'POG-20260809-099')
  assert.equal(view.identity.numberSeparated, true)
  assert.equal(view.identity.businessNoParsed, false)
  assert.equal(view.identity.objectIdVisible, false)
  const component = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  assert.ok(component.includes('采购订单业务编号'))
  assert.ok(component.includes('采购订单编号'))
  assert.ok(component.includes('来源Gate编号'))
})

test('source relations form a complete ordered business process chain without first-item extraction', () => {
  const view = buildPurchaseOrderViewModelV1142842724({ ...fixture(), viewRole: 'management' })
  assert.deepEqual(view.sourceTrace.groups.map(group => group.label),
    ['采购申请', '询价', '报价比较', '核价', '供应商推荐', '采购订单准入Gate', '采购订单'])
  assert.deepEqual(view.sourceTrace.groups[0].values, ['PR-001', 'PR-002', 'PR-003'])
  assert.deepEqual(view.sourceTrace.groups[1].values, ['PI-001', 'PI-002'])
  assert.deepEqual(view.sourceTrace.groups[4].values, ['SR-001', 'SR-002'])
  const source = read('frontend/src/meta/viewModels/purchaseOrderViewModelV1142842724.js')
  assert.equal(/source\w*Ids\s*\[\s*0\s*\]/.test(source), false)
  assert.equal(/poNo[^\n]*\.split\s*\(/.test(source), false)
})

test('urgency only displays authoritative facts and missing facts remain unknown', () => {
  const known = buildPurchaseOrderViewModelV1142842724({ ...fixture(), viewRole: 'buyer' })
  assert.deepEqual(known.urgency, {
    code: 'urgent', label: '紧急', factSource: 'PurchaseOrder.deliveryUrgencyCode',
    calculatedByPage: false, manuallyEditable: false,
  })
  const missingFixture = fixture({ deliveryUrgencyCode: '', deliveryUrgency: '', deliveryUrgencyLabel: '' })
  const missing = buildPurchaseOrderViewModelV1142842724({ ...missingFixture, viewRole: 'buyer' })
  assert.equal(missing.urgency.label, '未知/待确认')
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  assert.ok(page.includes("{ key: 'deliveryUrgency', label: '紧急程度'"))
  assert.equal(page.includes('calculateDeliveryUrgency'), false)
})

test('list/detail export and print inherit business projection and exclude technical fields', () => {
  const view = buildPurchaseOrderViewModelV1142842724({ ...fixture(), viewRole: 'warehouse' })
  const template = buildPurchaseOrderExportTemplateV1142842724(view)
  const printDocument = buildPurchaseOrderPrintDocumentV11428427241(view)
  assert.equal(template.inheritsViewPermission, true)
  assert.equal(template.includesTechnicalFields, false)
  assert.equal(template.columns.some(column => ['unitPrice', 'amount'].includes(column.key)), false)
  assert.match(printDocument, /采购订单编号：PO-20260809-001/)
  assert.match(printDocument, /来源Gate编号：POG-20260809-099/)
  assert.doesNotMatch(printDocument, /PO-OBJECT-ID-001/)
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const component = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  for (const term of ['导出当前结果', '导出已选记录', '打印当前结果', '批量打印已选订单']) {
    assert.ok(page.includes(term), term)
  }
  assert.ok(component.includes('打印采购订单'))
  assert.ok(component.includes('导出'))
})

test('batch operations use current selection and do not write PurchaseOrder business state', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  assert.ok(page.includes('selectedRows.length'))
  assert.ok(page.includes('printSelectedPurchaseOrders'))
  assert.ok(page.includes('exportSelectedList'))
  const view = buildPurchaseOrderViewModelV1142842724({ ...fixture(), viewRole: 'buyer' })
  assert.equal(view.dataProtection.businessWriteCount, 0)
})

test('legacy missing source opens with independent identity and human input remains untouched', () => {
  const input = fixture({ sourceGateId: '', sourceGateNo: '' })
  input.lifecycleDetail.sourceTrace = { traceable: false, sourcePurchaseRequestIds: [] }
  const before = clone(input)
  const view = buildPurchaseOrderViewModelV1142842724({ ...input, viewRole: 'buyer' })
  assert.deepEqual(input, before)
  assert.equal(view.identity.purchaseOrderNo, 'PO-20260809-001')
  assert.equal(view.identity.sourceGateNo, '历史数据不可追溯')
  assert.equal(view.dataProtection.businessWriteCount, 0)
  assert.equal(view.dataProtection.legacyOrderChanged, false)
  assert.equal(view.dataProtection.databaseChanged, false)
})

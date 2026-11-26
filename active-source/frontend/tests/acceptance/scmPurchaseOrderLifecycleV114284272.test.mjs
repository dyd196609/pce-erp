import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  PURCHASE_ORDER_LIFECYCLE_LABELS_V114284272,
  PURCHASE_ORDER_LIFECYCLE_TRANSITIONS_V114284272,
  buildPurchaseOrderLifecycleSnapshotV114284272,
  evaluatePurchaseOrderLifecycleTransitionV114284272,
} from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js'
import {
  buildPurchaseOrderApprovalContextV114284272,
  validatePurchaseOrderApprovalContextV114284272,
} from '../../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalContextV114284272.js'
import {
  QUALIFIED_MATERIAL_PRICE_MODEL_V114284272,
  evaluateQualifiedMaterialPriceV114284272,
  proposeMaterialMasterPriceHistoryV114284272,
} from '../../src/meta/domain/scm/purchaseOrder/domain/qualifiedMaterialPriceV114284272.js'
import { buildPurchaseOrderLifecycleDetailReadModelV114284272 } from
  '../../src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js'

const root = resolve(import.meta.dirname, '../../..')
const clone = value => JSON.parse(JSON.stringify(value))

function purchaseOrder(status = 'draft') {
  return {
    objectType: 'PurchaseOrder', classification: 'GATE_CREATED',
    id: 'PO-ID-272-001', poNo: 'PO20260809001', supplierId: 'SUP-001',
    sourceGateId: 'GATE-ID-272-001', sourcePurchaseRequestIds: [
      'PR001', 'PR002', 'PR003', 'PR004', 'PR005', 'PR006',
    ], lifecycleStatus: status, status,
  }
}

function approvalContext(status = 'pending_approval') {
  return buildPurchaseOrderApprovalContextV114284272({
    purchaseOrderId: 'PO-ID-272-001', purchaseOrderNo: 'PO20260809001',
    supplierId: 'SUP-001', sourceGateId: 'GATE-ID-272-001',
    sourcePurchaseRequestIds: ['PR001', 'PR002', 'PR003', 'PR004', 'PR005', 'PR006'],
    approvalStatus: status,
    approvalHistory: status === 'approved' ? [{
      recordId: 'POAR-001', result: 'approved', approvedBy: 'buyer-manager',
      approvedAt: '2026-08-09T10:00:00.000Z',
    }] : [],
  })
}

test('lifecycle model freezes exact states, labels and adjacent transitions', () => {
  assert.deepEqual(Object.keys(PURCHASE_ORDER_LIFECYCLE_LABELS_V114284272), [
    'draft', 'pending_approval', 'approved', 'issued', 'partially_received',
    'completed', 'cancelled',
  ])
  assert.deepEqual(PURCHASE_ORDER_LIFECYCLE_TRANSITIONS_V114284272.issued,
    ['partially_received', 'cancelled'])
  assert.deepEqual(PURCHASE_ORDER_LIFECYCLE_TRANSITIONS_V114284272.completed, [])
  const snapshot = buildPurchaseOrderLifecycleSnapshotV114284272(purchaseOrder('approved'))
  assert.equal(snapshot.lifecycleStatusLabel, '已审批')
  assert.equal(snapshot.automaticTransitionAllowed, false)
  assert.equal(snapshot.businessWriteCount, 0)
})

test('state guard accepts only explicit adjacent transitions with required evidence', () => {
  const pending = evaluatePurchaseOrderLifecycleTransitionV114284272({
    purchaseOrder: purchaseOrder('draft'), targetStatus: 'pending_approval',
    actor: 'buyer-001', approvalContext: approvalContext('pending_approval'),
  })
  assert.equal(pending.result, 'PASS')
  assert.equal(pending.stateTransitionExecuted, false)

  const approved = evaluatePurchaseOrderLifecycleTransitionV114284272({
    purchaseOrder: purchaseOrder('pending_approval'), targetStatus: 'approved',
    actor: 'approver-001', approvalContext: approvalContext('approved'),
  })
  assert.equal(approved.result, 'PASS')
  const issued = evaluatePurchaseOrderLifecycleTransitionV114284272({
    purchaseOrder: purchaseOrder('approved'), targetStatus: 'issued', actor: 'buyer-001',
    issueConfirmation: { confirmed: true, confirmedBy: 'buyer-001',
      confirmedAt: '2026-08-09T11:00:00.000Z' },
  })
  assert.equal(issued.result, 'PASS')
  const partiallyReceived = evaluatePurchaseOrderLifecycleTransitionV114284272({
    purchaseOrder: purchaseOrder('issued'), targetStatus: 'partially_received',
    actor: 'receiver-001', receiptEvidence: { confirmed: true,
      confirmedBy: 'receiver-001', confirmedAt: '2026-08-10T08:00:00.000Z' },
  })
  assert.equal(partiallyReceived.result, 'PASS')
  const completed = evaluatePurchaseOrderLifecycleTransitionV114284272({
    purchaseOrder: purchaseOrder('partially_received'), targetStatus: 'completed',
    actor: 'receiver-001', receiptEvidence: { completed: true,
      confirmedBy: 'receiver-001', confirmedAt: '2026-08-11T08:00:00.000Z' },
  })
  assert.equal(completed.result, 'PASS')
})

test('cross-state and automatic transitions are blocked without mutating PurchaseOrder', () => {
  const order = purchaseOrder('draft')
  const before = clone(order)
  const crossState = evaluatePurchaseOrderLifecycleTransitionV114284272({
    purchaseOrder: order, targetStatus: 'approved', actor: 'approver-001',
    approvalContext: approvalContext('approved'),
  })
  assert.equal(crossState.reason, 'PURCHASE_ORDER_LIFECYCLE_CROSS_STATE_TRANSITION_FORBIDDEN')
  const automatic = evaluatePurchaseOrderLifecycleTransitionV114284272({
    purchaseOrder: order, targetStatus: 'pending_approval', actor: 'system',
    automatic: true, approvalContext: approvalContext('pending_approval'),
  })
  assert.equal(automatic.reason, 'EXPLICIT_HUMAN_LIFECYCLE_ACTION_REQUIRED')
  assert.deepEqual(order, before)
  assert.equal(crossState.businessWriteCount + automatic.businessWriteCount, 0)
})

test('approval context keeps full source arrays and approval history', () => {
  const context = approvalContext('approved')
  const validation = validatePurchaseOrderApprovalContextV114284272(context)
  assert.equal(validation.result, 'PASS')
  assert.equal(validation.sourceRelationCount, 6)
  assert.deepEqual(context.sourcePurchaseRequestIds,
    ['PR001', 'PR002', 'PR003', 'PR004', 'PR005', 'PR006'])
  assert.equal(context.approvalHistory.length, 1)
  assert.equal(context.automaticApproval, false)
})

function qualifiedPriceInput(status = 'approved') {
  return {
    materialId: 'MAT-ID-001', materialCode: 'MAT-001', supplierId: 'SUP-001',
    qualifiedPrice: 100, currency: 'CNY', effectiveDate: '2026-08-09',
    sourcePurchaseOrderId: 'PO-ID-272-001', sourceSupplierId: 'SUP-001',
    sourceApprovalRecord: { recordId: 'POAR-001', result: 'approved',
      approvedBy: 'approver-001', approvedAt: '2026-08-09T10:00:00.000Z' },
    purchaseOrderStatus: status, priceHumanConfirmed: true,
    priceConfirmedBy: 'buyer-001', priceConfirmedAt: '2026-08-09T10:30:00.000Z',
  }
}

test('qualified material price requires approved or issued order and manual confirmation', () => {
  assert.equal(evaluateQualifiedMaterialPriceV114284272(
    qualifiedPriceInput('approved')).result, 'PASS')
  assert.equal(evaluateQualifiedMaterialPriceV114284272(
    qualifiedPriceInput('issued')).result, 'PASS')
  assert.equal(evaluateQualifiedMaterialPriceV114284272(
    qualifiedPriceInput('draft')).reason, 'PURCHASE_ORDER_STATUS_NOT_PRICE_QUALIFIED')
  assert.equal(evaluateQualifiedMaterialPriceV114284272({
    ...qualifiedPriceInput(), priceHumanConfirmed: false,
  }).reason, 'QUALIFIED_PRICE_HUMAN_CONFIRMATION_REQUIRED')
  assert.equal(QUALIFIED_MATERIAL_PRICE_MODEL_V114284272.materialMasterAutoUpdate, false)
})

test('material master price history is append-only projection and never persisted', () => {
  const eligible = evaluateQualifiedMaterialPriceV114284272(qualifiedPriceInput())
  const existing = [{ qualifiedMaterialPriceId: 'QMP-OLD', materialCode: 'MAT-001',
    supplierId: 'SUP-002', qualifiedPrice: 98, effectiveDate: '2026-07-01' }]
  const before = clone(existing)
  const proposal = proposeMaterialMasterPriceHistoryV114284272({
    existingHistory: existing, qualifiedMaterialPrices: [eligible.qualifiedMaterialPrice],
  })
  assert.deepEqual(existing, before)
  assert.equal(proposal.existingHistory.length, 1)
  assert.equal(proposal.appendCandidates.length, 1)
  assert.equal(proposal.projectedHistory.length, 2)
  assert.equal(proposal.historicalPriceOverwritten, false)
  assert.equal(proposal.materialMasterAutoUpdate, false)
  assert.equal(proposal.persistenceExecuted, false)
})

test('detail provider preserves every line and human values without writes', () => {
  const order = { ...purchaseOrder('approved'), approvalStatus: 'approved',
    approvalHistory: approvalContext('approved').approvalHistory,
    qualifiedPriceApprovalRecord: qualifiedPriceInput().sourceApprovalRecord }
  const lines = [
    { id: 'LINE-1', materialId: 'MAT-ID-001', materialCode: 'MAT-001',
      supplierId: 'SUP-001', confirmedPrice: 100, currency: 'CNY',
      priceEffectiveDate: '2026-08-09', priceHumanConfirmed: true,
      priceConfirmedBy: 'buyer-001', priceConfirmedAt: '2026-08-09T10:30:00.000Z' },
    { id: 'LINE-2', materialId: 'MAT-ID-002', materialCode: 'MAT-002',
      supplierId: 'SUP-001', confirmedPrice: 88, currency: 'CNY',
      priceEffectiveDate: '2026-08-09', priceHumanConfirmed: false },
  ]
  const before = clone({ order, lines })
  const first = buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder: order, orderLines: lines,
  })
  const refresh = buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder: order, orderLines: lines,
  })
  assert.deepEqual({ order, lines }, before)
  assert.deepEqual(refresh, first)
  assert.equal(first.dataExtract.inputItemCount, 2)
  assert.equal(first.dataExtract.outputItemCount, 2)
  assert.equal(first.dataExtract.sourceRelationCount, 2)
  assert.equal(first.qualifiedPriceRows[0].qualifiedPriceStatusCode, 'qualified')
  assert.equal(first.qualifiedPriceRows[1].qualifiedPriceStatusCode, 'not_qualified')
  assert.equal(first.materialMasterAutoUpdate, false)
  assert.equal(first.businessWriteCount, 0)
})

test('legacy orders are read-only isolated and page contains required regions', () => {
  const legacy = { ...purchaseOrder('approved'), classification: 'LEGACY' }
  const before = clone(legacy)
  const view = buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder: legacy,
    orderLines: [{ id: 'LEGACY-LINE-1', materialCode: 'MAT-OLD', planPrice: 90 }],
  })
  assert.deepEqual(legacy, before)
  assert.equal(view.legacyIsolated, true)
  assert.equal(view.approvalContext, null)
  assert.equal(view.qualifiedPriceRows[0].qualifiedPriceStatusCode, 'legacy_isolated')
  assert.equal(view.purchaseOrderStatusChanged, false)

  const page = readFileSync(resolve(root,
    'frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue'), 'utf8')
  for (const term of ['采购订单生命周期', '审批状态', '价格来源', '合格价格状态',
    '禁止自动修改物料档案']) assert.ok(page.includes(term), term)
})

test('implementation has no PurchaseOrder creation, automatic approval or MaterialMaster write path', () => {
  const sources = [
    'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js',
    'frontend/src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalContextV114284272.js',
    'frontend/src/meta/domain/scm/purchaseOrder/domain/qualifiedMaterialPriceV114284272.js',
    'frontend/src/meta/providers/purchaseOrderLifecycleDetailProviderV114284272.js',
    'frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue',
  ].map(path => readFileSync(resolve(root, path), 'utf8')).join('\n')
  for (const forbidden of ['createGateGovernedPurchaseOrders', 'createScmPurchaseOrder',
    'issueScmPurchaseOrder', 'submitApproval(', 'approvePurchaseOrder(',
    'updateMaterialMaster', 'localStorage.', 'sessionStorage.']) {
    assert.equal(sources.includes(forbidden), false, forbidden)
  }
  assert.ok(sources.includes('materialMasterAutoUpdate: false'))
  assert.ok(sources.includes('businessWriteCount: 0'))
})

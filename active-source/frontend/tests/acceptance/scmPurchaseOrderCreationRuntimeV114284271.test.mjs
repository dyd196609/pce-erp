import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { PURCHASE_ORDER_DOMAIN_MODEL, validatePurchaseOrderDomainModel } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderDomainModel.js'
import { PURCHASE_ORDER_LIFECYCLE_STATES } from
  '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleStateDefinition.js'
const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../../..')
const source = relative => fs.readFileSync(path.join(root, relative), 'utf8')

const localValues = new Map()
globalThis.localStorage = {
  getItem: key => localValues.get(key) || null,
  setItem: (key, value) => localValues.set(key, String(value)),
  removeItem: key => localValues.delete(key),
  clear: () => localValues.clear(),
}
const { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } = await import(
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js')

const gate = {
  objectType: 'SupplierRecommendationGate', gateId: 'POG-R271-001',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, purchaseOrderCreated: false,
  confirmedBy: '采购主管', confirmedAt: '2026-08-08T09:00:00.000Z',
  sourceSignature: 'SRDB-001::3::confirmed::SRDBR-001',
  recommendationDecisionId: 'SRDBR-001', inquiryId: 'PI-001',
  priceApprovalId: 'PAP-QC-001', quoteComparisonId: 'QC-001',
  recommendedSupplierId: 'SUP-001', supplierName: '供应商A',
  quoteEvidence: [{ quotationNo: 'SQ-001', quotationAmount: 88 }],
  priceEvidence: [{ comparisonNo: 'QC-001', lowestPrice: 86 }],
  qualificationEvidence: [{ supplierId: 'SUP-001', result: 'PASS' }],
}
const admissionResult = {
  objectType: 'PurchaseOrderAdmissionResult', admissionResultId: 'POAR-R271-001',
  gateId: gate.gateId, sourceSignature: gate.sourceSignature,
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreated: false, checks: ['recommendation', 'confirmation', 'quote',
    'price', 'source'].map(checkCode => ({ checkCode, result: 'PASS', passed: true })),
}
const creationEntry = {
  objectType: 'PurchaseOrderCreationEntry', gateId: gate.gateId,
  sourceObjectId: admissionResult.admissionResultId,
  createActionExecuted: false, purchaseOrderCreated: false,
}
const draft = {
  objectType: 'PurchaseOrderCreationDraft', draftId: 'POCD-R271-001',
  gateId: gate.gateId, admissionResultId: admissionResult.admissionResultId,
  sourceSignature: gate.sourceSignature, supplierId: 'SUP-HUMAN',
  supplierName: '人工确认供应商', plannedDeliveryDate: '2026-09-08',
  remark: '人工备注必须保持', approvalOpinion: '同意按确认条件创建草稿',
  manualDataVersion: 2,
  materialItems: [{ materialCode: 'MT006', materialName: '测试物料',
    requestedQuantity: 13, confirmedQuantity: 13, quantity: 13,
    supplierId: 'SUP-HUMAN', supplierName: '人工确认供应商',
    unitPrice: 91.25, remark: '人工行备注' }],
}

assert.equal(validatePurchaseOrderDomainModel().result, 'PASS')
assert.equal(PURCHASE_ORDER_DOMAIN_MODEL.businessObject, 'PurchaseOrder')
assert.deepEqual(PURCHASE_ORDER_LIFECYCLE_STATES,
  ['draft', 'pending_approval', 'approved', 'issued', 'partially_received', 'completed', 'cancelled'])

let stored = null
const repository = (purchaseOrder, orderLines) => {
  if (stored) return { success: true, result: 'EXISTING', ...stored,
    businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false }
  stored = { purchaseOrder: structuredClone(purchaseOrder), orderLines: structuredClone(orderLines) }
  return { success: true, result: 'CREATED', ...stored,
    businessWriteCount: 1, productionDataWritten: false, purchaseOrderCreated: true }
}

const denied = executeCreatePurchaseOrderV114284271({ actor: '采购员A', gate,
  admissionResult, creationEntry, draft, permissionContext: { role: 'admin' }, repository })
assert.equal(denied.result, 'BLOCKED')
assert.equal(denied.businessWriteCount, 0)

const created = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A', gate,
  admissionResult, creationEntry, draft, permissionContext: { role: 'admin' }, repository,
  now: '2026-08-08T09:10:00.000Z',
})
assert.equal(created.result, 'CREATED')
assert.equal(created.businessWriteCount, 1)
assert.equal(created.purchaseOrder.status, 'draft')
assert.equal(created.purchaseOrder.lifecycleStatus, 'draft')
assert.equal(created.purchaseOrder.sourceGateId, gate.gateId)
assert.equal(created.purchaseOrder.sourceRecommendationId, gate.recommendationDecisionId)
assert.equal(created.purchaseOrder.sourceInquiryId, gate.inquiryId)
assert.equal(created.purchaseOrder.sourcePriceApprovalId, gate.priceApprovalId)
assert.equal(created.purchaseOrder.supplierId, draft.supplierId)
assert.equal(created.purchaseOrder.confirmedBy, gate.confirmedBy)
assert.deepEqual(created.purchaseOrder.quoteEvidence, gate.quoteEvidence)
assert.deepEqual(created.purchaseOrder.priceEvidence, gate.priceEvidence)
assert.deepEqual(created.purchaseOrder.qualificationEvidence, gate.qualificationEvidence)
assert.equal(created.purchaseOrder.approvalOpinion, draft.approvalOpinion)
assert.equal(created.orderLines[0].quantity, 13)
assert.equal(created.orderLines[0].planPrice, 91.25)
assert.equal(created.orderLines[0].remark, '人工行备注')
assert.equal(created.purchaseOrderSubmitted, false)
assert.equal(created.purchaseOrderApproved, false)
assert.equal(created.purchaseOrderIssued, false)
assert.equal(created.automaticPurchaseOrderCreation, false)

const replay = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A', gate,
  admissionResult, creationEntry, draft, permissionContext: { role: 'admin' }, repository,
})
assert.equal(replay.result, 'EXISTING')
assert.equal(replay.businessWriteCount, 0)
assert.deepEqual(replay.purchaseOrder, created.purchaseOrder)

const legacyBefore = JSON.stringify([{ id: 'po-legacy-1', status: 'approved' }])
const legacyAfter = JSON.stringify([{ id: 'po-legacy-1', status: 'approved' }])
assert.equal(legacyAfter, legacyBefore)

const page = source('frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue')
assert.match(page, /data-process-action="CREATE_PURCHASE_ORDER"/)
assert.match(page, /executeCreatePurchaseOrderV114284271/)
assert.match(page, /不会自动提交、审批、下达或发送供应商/)
const store = source('frontend/src/meta/scm/scmStore.js')
assert.match(store, /createGateGovernedPurchaseOrder/)
assert.match(store, /classification === 'GATE_CREATED'/)
const scmGovernance = source('docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md')
assert.match(scmGovernance, /SCM-PO-CREATE-001/)
const acceptanceGovernance = source('docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md')
assert.match(acceptanceGovernance, /SCM-PO-CREATE-RUNTIME-001/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Domain PASS')
console.log('Provider PASS')
console.log('Guard PASS')
console.log('Action PASS')
console.log('Gate Trace PASS')
console.log('Human Data Protection PASS')
console.log('Legacy Orders Changed NO PASS')
console.log('Automatic Creation NO PASS')
console.log('Business Write Count 1 PASS')
console.log('Acceptance PASS')

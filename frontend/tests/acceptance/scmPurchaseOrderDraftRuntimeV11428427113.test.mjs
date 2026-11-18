import assert from 'node:assert/strict'
import fs from 'node:fs'

import { createPurchaseOrderCreationDraftStoreV114284262,
  SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113,
  PURCHASE_ORDER_DRAFT_STATUSES_V11428427113 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'
import { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'
import { CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationFinalCheckV114284271146.js'

assert.deepEqual(PURCHASE_ORDER_DRAFT_STATUSES_V11428427113,
  ['editing', 'confirmed', 'ready_for_creation'])

const gate = { objectType: 'SupplierRecommendationGate', gateId: 'POG-DRAFT-001',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, purchaseOrderCreated: false,
  confirmedBy: '采购主管', confirmedAt: '2026-08-08T14:00:00.000Z',
  sourceSignature: 'DRAFT::1', purchaseRequestId: 'PR-DRAFT-001',
  inquiryId: 'PI-DRAFT-001', quoteComparisonId: 'QC-DRAFT-001',
  priceApprovalId: 'PAP-DRAFT-001', recommendationDecisionId: 'SRD-DRAFT-001',
  recommendedSupplierId: 'SUP-A', supplierName: '供应商A',
  recommendationItems: [{ materialCode: 'MT-DRAFT', materialName: '草稿测试物料',
    requestedQuantity: 100, selectedSupplierCode: 'SUP-A', selectedSupplierName: '供应商A',
    selectedPrice: 8, quoteComparisonIds: ['QC-DRAFT-001'],
    sourcePriceApprovalIds: ['PAP-DRAFT-001'], supplierCandidates: [
      { supplierCode: 'SUP-A', supplierName: '供应商A', quotePrice: 8 } ] }] }
const admissionResult = { objectType: 'PurchaseOrderAdmissionResult',
  admissionResultId: 'POAR-DRAFT-001', gateId: gate.gateId,
  sourceSignature: gate.sourceSignature, status: 'READY_FOR_PURCHASE_ORDER',
  purchaseOrderCreationAllowed: true, purchaseOrderCreated: false,
  checks: ['a', 'b', 'c', 'd', 'e'].map(checkCode =>
    ({ checkCode, result: 'PASS', passed: true })) }
const creationEntry = { objectType: 'PurchaseOrderCreationEntry', gateId: gate.gateId,
  sourceObjectId: admissionResult.admissionResultId, createActionExecuted: false,
  purchaseOrderCreated: false }
const guard = { result: 'PASS', gateId: gate.gateId,
  admissionResultId: admissionResult.admissionResultId }
let storageValue = ''
const store = createPurchaseOrderCreationDraftStoreV114284262({ storage: {
  getItem: () => storageValue,
  setItem: (_key, value) => { storageValue = value },
} })

const draft = store.resolve({ gate, admissionResult })
assert.equal(draft.objectType, 'PurchaseOrderDraft')
assert.equal(draft.legacyObjectType, 'PurchaseOrderCreationDraft')
assert.equal(draft.draftStatus, 'editing')
assert.equal(draft.savedToStore, false)

draft.plannedDeliveryDate = '2026-09-15'
draft.approvalOpinion = '同意按人工草稿创建'
draft.remark = '人工备注必须保持'
draft.materialItems[0].confirmedQuantity = 80
draft.materialItems[0].confirmedPrice = 8.5
draft.materialItems[0].confirmedDeliveryDate = '2026-09-15'
draft.materialItems[0].remark = '人工行备注'

const reduced = store.save(draft, {
  actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard, now: '2026-08-08T14:10:00.000Z',
})
assert.equal(reduced.draftStatus, 'confirmed')
assert.equal(reduced.readinessStatus, 'ready_for_creation')
assert.equal(reduced.savedToStore, true)
assert.equal(reduced.materialItems[0].quantityAdjustmentReason, '')
assert.equal(reduced.materialItems[0].quantityAdjustedBy, '采购员A')
assert.equal(reduced.materialItems[0].quantityAdjustmentHistory.length, 1)

const increasedWithoutReason = structuredClone(reduced)
increasedWithoutReason.materialItems[0].confirmedQuantity = 120
assert.throws(() => store.save(increasedWithoutReason, {
  actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard,
}), /请输入调整原因/)
assert.equal(store.resolve({ gate, admissionResult }).materialItems[0].confirmedQuantity, 80)

increasedWithoutReason.materialItems[0].quantityAdjustmentReason = '最小采购包装'
const increased = store.save(increasedWithoutReason, {
  actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard, now: '2026-08-08T14:20:00.000Z',
})
assert.equal(increased.materialItems[0].confirmedQuantity, 120)
assert.equal(increased.materialItems[0].quantityAdjustmentReason, '最小采购包装')
assert.equal(increased.materialItems[0].quantityAdjustedBy, '采购员A')
assert.equal(increased.materialItems[0].quantityAdjustedAt, '2026-08-08T14:20:00.000Z')

const reloaded = store.resolve({ gate: { ...gate, recommendationItems: [
  { ...gate.recommendationItems[0], requestedQuantity: 999, selectedPrice: 99 } ] },
admissionResult })
assert.equal(reloaded.materialItems[0].confirmedQuantity, 120)
assert.equal(reloaded.materialItems[0].confirmedPrice, 8.5)
assert.equal(reloaded.materialItems[0].confirmedDeliveryDate, '2026-09-15')
assert.equal(reloaded.materialItems[0].quantityAdjustmentReason, '最小采购包装')
assert.equal(reloaded.remark, '人工备注必须保持')

const unsaved = structuredClone(increased)
unsaved.savedToStore = false
unsaved.draftStatus = 'editing'
const unsavedOutcome = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A', gate,
  admissionResult, creationEntry, draft: unsaved, permissionContext: { role: 'admin' },
  repository: () => { throw new Error('must not write') },
})
assert.equal(unsavedOutcome.result, 'BLOCKED')
assert.equal(unsavedOutcome.businessWriteCount, 0)

const changedAfterSave = structuredClone(increased)
changedAfterSave.materialItems[0].confirmedPrice = 9.5
assert.throws(() => store.markReadyForCreation(changedAfterSave, {
  actionCode: CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113,
  actor: '采购员A', guard,
}), /存在未保存修改/)

const inventoryConfirmed = store.confirmInventory(increased, {
  actionCode: CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146,
  actor: '采购员A', guard, materialCode: increased.materialItems[0].materialCode,
  confirmationRemark: '库存接口未接入，已人工核对。',
})
const ready = store.markReadyForCreation(inventoryConfirmed, {
  actionCode: CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113,
  actor: '采购员A', guard, now: '2026-08-08T14:30:00.000Z',
})
assert.equal(ready.draftStatus, 'ready_for_creation')
let writeCount = 0
const created = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A', gate,
  admissionResult, creationEntry, draft: ready, permissionContext: { role: 'admin' },
  repository: (purchaseOrder, orderLines) => {
    writeCount += 1
    return { success: true, result: 'CREATED', purchaseOrder, orderLines,
      businessWriteCount: 1, productionDataWritten: false, purchaseOrderCreated: true }
  },
})
assert.equal(created.result, 'CREATED')
assert.equal(writeCount, 1)
assert.equal(created.purchaseOrder.status, 'draft')
assert.equal(created.orderLines[0].quantity, 120)
assert.equal(created.orderLines[0].quantityAdjustmentReason, '最小采购包装')

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
assert.match(page, /保存采购订单草稿/)
assert.match(page, /确认数量超过建议数量时必填/)
assert.match(page, /CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Draft Model PASS')
console.log('Quantity Rule PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('Create Guard PASS')
console.log('Business Write Count 0 BEFORE CREATE PASS')
console.log('Acceptance PASS')

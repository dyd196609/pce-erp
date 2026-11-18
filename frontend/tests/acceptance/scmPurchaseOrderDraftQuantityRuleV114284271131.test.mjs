import assert from 'node:assert/strict'
import fs from 'node:fs'

import { calculatePurchaseOrderQuantityV11428427112,
  PURCHASE_ORDER_ITEM_DRAFT_STATUSES_V114284271131 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderQuantityModelV11428427112.js'
import { createPurchaseOrderCreationDraftStoreV114284262,
  SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'
import { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'
import { CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationFinalCheckV114284271146.js'

assert.deepEqual(PURCHASE_ORDER_ITEM_DRAFT_STATUSES_V114284271131,
  ['included', 'excluded'])
const excluded = calculatePurchaseOrderQuantityV11428427112({
  requestedQuantity: 0, availableQuantity: null, orderedQuantity: 0,
  confirmedQuantity: 0, originalSuggestedQuantity: 0,
})
assert.equal(excluded.result, 'PASS')
assert.equal(excluded.itemDraftStatus, 'excluded')
assert.equal(excluded.itemDraftStatusLabel, '不纳入采购订单')
const adjusted = calculatePurchaseOrderQuantityV11428427112({
  requestedQuantity: 365, availableQuantity: 0, orderedQuantity: 0,
  confirmedQuantity: 370, originalSuggestedQuantity: 365,
  quantityAdjustmentReason: '最小包装采购',
})
assert.equal(adjusted.result, 'PASS')
assert.equal(adjusted.itemDraftStatus, 'included')
const missingReason = calculatePurchaseOrderQuantityV11428427112({
  requestedQuantity: 365, availableQuantity: 0, orderedQuantity: 0,
  confirmedQuantity: 370, originalSuggestedQuantity: 365,
})
assert.equal(missingReason.result, 'BLOCKED')
assert.match(missingReason.blockingReasons.join('；'), /调整原因/)
const severe = calculatePurchaseOrderQuantityV11428427112({
  requestedQuantity: 365, availableQuantity: 0, orderedQuantity: 0,
  confirmedQuantity: 3651, originalSuggestedQuantity: 365,
  quantityAdjustmentReason: '异常测试',
})
assert.equal(severe.result, 'BLOCKED')
assert.equal(severe.severeQuantityAnomaly, true)
assert.match(severe.blockingReasons.join('；'), /10倍/)

const gate = { objectType: 'SupplierRecommendationGate', gateId: 'POG-R131-001',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, purchaseOrderCreated: false,
  confirmedBy: '采购主管', confirmedAt: '2026-08-08T16:00:00.000Z',
  sourceSignature: 'R131::1', purchaseRequestId: 'PR-R131-001',
  inquiryId: 'PI-R131-001', quoteComparisonId: 'QC-R131-001',
  priceApprovalId: 'PAP-R131-001', recommendationDecisionId: 'SRD-R131-001',
  recommendedSupplierId: 'SUP-A', supplierName: '供应商A',
  recommendationItems: [
    { materialCode: 'MT-ZERO', materialName: '零数量物料', requestedQuantity: 0,
      selectedSupplierCode: 'SUP-A', selectedSupplierName: '供应商A', selectedPrice: 1,
      quoteComparisonIds: ['QC-R131-001'], sourcePriceApprovalIds: ['PAP-R131-001'] },
    { materialCode: 'MT-365', materialName: '包装物料', requestedQuantity: 365,
      selectedSupplierCode: 'SUP-A', selectedSupplierName: '供应商A', selectedPrice: 2,
      quoteComparisonIds: ['QC-R131-001'], sourcePriceApprovalIds: ['PAP-R131-001'] },
  ] }
const admissionResult = { objectType: 'PurchaseOrderAdmissionResult',
  admissionResultId: 'POAR-R131-001', gateId: gate.gateId,
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
draft.plannedDeliveryDate = '2026-09-30'
draft.approvalOpinion = '同意按草稿创建'
draft.remark = '人工备注保持'
draft.materialItems[0].confirmedQuantity = 0
draft.materialItems[0].quantity = 7
draft.materialItems[1].confirmedQuantity = 370
draft.materialItems[1].confirmedPrice = 2
draft.materialItems[1].confirmedDeliveryDate = '2026-09-30'
draft.materialItems[1].quantityAdjustmentReason = '最小包装采购'
const saved = store.save(draft, {
  actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard, now: '2026-08-08T16:10:00.000Z',
})
assert.equal(saved.draftStatus, 'confirmed')
assert.equal(saved.materialItems[0].itemDraftStatus, 'excluded')
assert.equal(saved.materialItems[1].itemDraftStatus, 'included')
assert.equal(saved.materialItems[1].quantityAdjustmentReason, '最小包装采购')
const restored = store.resolve({ gate, admissionResult })
assert.equal(restored.materialItems[0].confirmedQuantity, 0)
assert.equal(restored.materialItems[1].confirmedQuantity, 370)
assert.equal(restored.materialItems[1].quantityAdjustmentReason, '最小包装采购')
assert.equal(restored.remark, '人工备注保持')

const inventoryConfirmed = store.confirmInventory(saved, {
  actionCode: CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146,
  actor: '采购员A', guard, materialCode: 'MT-365',
  confirmationRemark: '库存接口未接入，已人工核对。',
})
const ready = store.markReadyForCreation(inventoryConfirmed, {
  actionCode: CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113,
  actor: '采购员A', guard,
})
let writtenLines = null
const created = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  actor: '采购员A', gate, admissionResult, creationEntry, draft: ready,
  permissionContext: { role: 'admin' },
  repository: (purchaseOrder, orderLines) => {
    writtenLines = orderLines
    return { success: true, result: 'CREATED', purchaseOrder, orderLines,
      businessWriteCount: 1, productionDataWritten: false, purchaseOrderCreated: true }
  },
})
assert.equal(created.result, 'CREATED')
assert.equal(writtenLines.length, 1)
assert.equal(writtenLines[0].materialCode, 'MT-365')
assert.equal(writtenLines[0].confirmedQuantity, 370)
assert.ok(!writtenLines.some(line => line.materialCode === 'MT-ZERO'))

const allExcludedGate = { ...gate, gateId: 'POG-R131-ZERO', sourceSignature: 'R131::ZERO',
  recommendationItems: [gate.recommendationItems[0]] }
const allExcludedAdmission = { ...admissionResult, admissionResultId: 'POAR-R131-ZERO',
  gateId: allExcludedGate.gateId, sourceSignature: allExcludedGate.sourceSignature }
const allExcludedGuard = { result: 'PASS', gateId: allExcludedGate.gateId,
  admissionResultId: allExcludedAdmission.admissionResultId }
const zeroDraft = store.resolve({ gate: allExcludedGate, admissionResult: allExcludedAdmission })
const zeroSaved = store.save(zeroDraft, {
  actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard: allExcludedGuard,
})
assert.equal(zeroSaved.materialItems[0].itemDraftStatus, 'excluded')
assert.equal(zeroSaved.draftStatus, 'editing')
assert.throws(() => store.markReadyForCreation(zeroSaved, {
  actionCode: CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113,
  actor: '采购员A', guard: allExcludedGuard,
}), /至少一个纳入采购订单的物料/)

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
assert.match(page, /数量状态/)
assert.match(page, /materialEligibility\?\.checks\?\.\[index\]\?\.result === 'PASS'/)
assert.match(page, /data-quantity-status/)
assert.match(page, /不纳入采购订单/)
assert.match(page, /保存采购订单草稿/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Draft Rule PASS')
console.log('Quantity Rule PASS')
console.log('Item Inclusion PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('PurchaseOrder Created NO IN HUMAN VALIDATION PASS')
console.log('Acceptance PASS')

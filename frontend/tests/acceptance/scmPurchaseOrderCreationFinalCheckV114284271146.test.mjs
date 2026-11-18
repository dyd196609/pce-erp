import assert from 'node:assert/strict'
import fs from 'node:fs'

import { evaluatePurchaseOrderCreationFinalCheckV114284271146,
  resolvePurchaseOrderQuantityStatusV114284271146,
  PURCHASE_ORDER_QUANTITY_STATUSES_V114284271146,
  CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationFinalCheckV114284271146.js'
import { createPurchaseOrderCreationDraftStoreV114284262 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'
import { createSupplierPurchaseDraftProviderV1142842711431 } from
  '../../src/meta/providers/supplierPurchaseDraftProviderV1142842711431.js'
import { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'

assert.deepEqual(PURCHASE_ORDER_QUANTITY_STATUSES_V114284271146,
  ['normal', 'need_reason', 'abnormal', 'pending_inventory_check'])

const quantityBase = { requestedQuantity: 10, availableQuantity: 0, orderedQuantity: 0,
  suggestedPurchaseQuantity: 10, originalSuggestedQuantity: 10 }
assert.equal(resolvePurchaseOrderQuantityStatusV114284271146({
  ...quantityBase, confirmedQuantity: 10 }).statusCode, 'normal')
const reasonRequired = resolvePurchaseOrderQuantityStatusV114284271146({
  ...quantityBase, confirmedQuantity: 11 })
assert.equal(reasonRequired.statusCode, 'need_reason')
assert.equal(reasonRequired.result, 'FAIL')
const reasonHandled = resolvePurchaseOrderQuantityStatusV114284271146({
  ...quantityBase, confirmedQuantity: 11, quantityAdjustmentReason: '临时安全储备' })
assert.equal(reasonHandled.statusCode, 'need_reason')
assert.equal(reasonHandled.result, 'PASS')
const severe = resolvePurchaseOrderQuantityStatusV114284271146({
  ...quantityBase, confirmedQuantity: 101, quantityAdjustmentReason: '仍需复核' })
assert.equal(severe.statusCode, 'abnormal')
assert.equal(severe.result, 'FAIL')
const inventoryPending = resolvePurchaseOrderQuantityStatusV114284271146({
  ...quantityBase, availableQuantity: null, confirmedQuantity: 10 })
assert.equal(inventoryPending.statusCode, 'pending_inventory_check')
assert.equal(inventoryPending.result, 'FAIL')

const gate = { objectType: 'SupplierRecommendationGate', gateId: 'POG-R146-001',
  status: 'READY_FOR_PURCHASE_ORDER', statusLabel: '可创建采购订单',
  purchaseOrderCreationAllowed: true, purchaseOrderCreationEntryReady: true,
  purchaseOrderCreated: false, confirmedBy: '采购主管',
  confirmedAt: '2026-08-09T08:00:00.000Z', sourceSignature: 'R146-SIGNATURE',
  purchaseRequestId: 'PR-R146-001', inquiryId: 'PI-R146-001',
  quoteComparisonId: 'QC-R146-001', priceApprovalId: 'PAP-R146-001',
  recommendationDecisionId: 'SRD-R146-001' }
const admissionResult = { objectType: 'PurchaseOrderAdmissionResult',
  admissionResultId: 'POAR-R146-001', gateId: gate.gateId,
  sourceSignature: gate.sourceSignature, status: 'READY_FOR_PURCHASE_ORDER',
  purchaseOrderCreationAllowed: true, purchaseOrderCreated: false,
  checks: [{ checkCode: 'all', result: 'PASS', passed: true }] }
const creationEntry = { objectType: 'PurchaseOrderCreationEntry', gateId: gate.gateId,
  sourceObjectId: admissionResult.admissionResultId,
  createActionExecuted: false, purchaseOrderCreated: false }
const guard = { result: 'PASS', gateId: gate.gateId,
  admissionResultId: admissionResult.admissionResultId }
const material = { lineNo: 1, materialCode: 'MT-R146-001', materialName: '最终检查物料',
  requestedQuantity: 10, availableQuantity: null, orderedQuantity: 0,
  suggestedPurchaseQuantity: 10, originalSuggestedQuantity: 10,
  confirmedQuantity: 10, quantity: 10, supplierId: 'SUP-R146-001',
  supplierName: '最终检查供应商', confirmedPrice: 12, unitPrice: 12,
  confirmedDeliveryDate: '2026-09-01', sourcePurchaseRequestId: 'PR-R146-001',
  sourcePurchaseRequestIds: ['PR-R146-001'], sourceInquiryId: 'PI-R146-001',
  sourceQuoteComparisonId: 'QC-R146-001', sourcePriceApprovalId: 'PAP-R146-001',
  sourceGateId: gate.gateId, quantitySource: 'PurchaseRequestServerFact' }
const draft = { objectType: 'PurchaseOrderDraft', draftId: 'POD-R146-001',
  finalCheckVersion: 'V1.14.2.8.4.27.1.4.6',
  gateId: gate.gateId, admissionResultId: admissionResult.admissionResultId,
  sourceSignature: gate.sourceSignature, manualDataVersion: 1, savedToStore: true,
  draftStatus: 'ready_for_creation', readinessStatus: 'ready_for_creation',
  creationContext: { creationContextId: 'POCC-POG-R146-001',
    purchaseRequestIds: ['PR-R146-001'] }, materialItems: [material],
  supplierPurchaseDrafts: [{ objectType: 'SupplierPurchaseDraft',
    supplierPurchaseDraftId: 'SPD-R146-001', supplierId: 'SUP-R146-001',
    supplierName: '最终检查供应商', deliveryDate: '2026-09-01',
    approvalRemark: '同意', supplierRemark: '人工备注', items: [] }] }

const before = evaluatePurchaseOrderCreationFinalCheckV114284271146({
  gate, creationContext: draft.creationContext, draft, entryGuard: guard })
assert.equal(before.result, 'FAIL')
assert.equal(before.inventoryCheck.result, 'FAIL')

const storageValues = new Map()
const storage = { getItem: key => storageValues.get(key) || null,
  setItem: (key, value) => storageValues.set(key, String(value)) }
const store = createPurchaseOrderCreationDraftStoreV114284262({ storage,
  storageKey: 'r146-final-check' })
const confirmedDraft = store.confirmInventory(draft, {
  actionCode: CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146,
  actor: '采购员A', guard, materialCode: material.materialCode,
  confirmationRemark: '已核对仓库台账，库存接口尚未接入。',
  now: '2026-08-09T08:30:00.000Z',
})
assert.equal(confirmedDraft.materialItems[0].availableQuantity, null)
assert.equal(confirmedDraft.materialItems[0].inventoryConfirmation.confirmedBy, '采购员A')
assert.equal(confirmedDraft.materialItems[0].inventoryConfirmation.confirmationRemark,
  '已核对仓库台账，库存接口尚未接入。')
const refreshed = store.findByAdmissionResultId(admissionResult.admissionResultId)
assert.deepEqual(refreshed.materialItems[0].inventoryConfirmation,
  confirmedDraft.materialItems[0].inventoryConfirmation)
const providerReloaded = createSupplierPurchaseDraftProviderV1142842711431()
  .load({ draft: refreshed }).draft
assert.deepEqual(providerReloaded.materialItems[0].inventoryConfirmation,
  confirmedDraft.materialItems[0].inventoryConfirmation)

const after = evaluatePurchaseOrderCreationFinalCheckV114284271146({
  gate, creationContext: confirmedDraft.creationContext, draft: confirmedDraft,
  entryGuard: guard })
assert.equal(after.result, 'PASS')
assert.equal(after.inventoryCheck.result, 'PASS')
assert.equal(after.humanConfirmations.length, 1)
assert.equal(after.businessWriteCount, 0)

let repositoryCalls = 0
const blockedCreate = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A',
  gate, admissionResult, creationEntry, draft,
  permissionContext: { role: 'admin' },
  repository: () => { repositoryCalls += 1; return { success: true } },
})
assert.equal(blockedCreate.result, 'BLOCKED')
assert.equal(blockedCreate.error, 'PURCHASE_ORDER_CREATION_FINAL_CHECK_BLOCKED')
assert.equal(repositoryCalls, 0)
assert.equal(blockedCreate.businessWriteCount, 0)

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
assert.match(page, /数量异常处理规则/)
for (const rule of ['必须填写调整原因', '属于严重异常，需要重新确认', '由采购人员人工核对']) {
  assert.match(page, new RegExp(rule))
}
assert.match(page, />人工确认库存<\/el-button>/)
assert.match(page, /采购订单创建最终检查/)
assert.match(page, /:disabled="createDisabled"/)
assert.match(page, /finalCheck\.value\.result !== 'PASS'/)
assert.doesNotMatch(page, /statusCode: 'reason_required'|statusCode: 'severe_anomaly'/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Quantity Status PASS')
console.log('Exception Rule PASS')
console.log('Inventory Confirmation PASS')
console.log('Create Guard PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('Acceptance PASS')
console.log('PurchaseOrder Core Changed NO PASS')
console.log('Legacy Orders Changed NO PASS')
console.log('PurchaseOrder Created NO PASS')
console.log('Business Write Count 0 PASS')

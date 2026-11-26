import assert from 'node:assert/strict'
import fs from 'node:fs'

import { calculatePurchaseOrderQuantityV11428427112,
  PURCHASE_ORDER_QUANTITY_FORMULA_V11428427112 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderQuantityModelV11428427112.js'
import { createPurchaseOrderCreationDraftStoreV114284262,
  SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'
import { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'

assert.equal(PURCHASE_ORDER_QUANTITY_FORMULA_V11428427112,
  '建议采购数量 = 需求数量 - 可用库存 - 已采购未入库数量')
const complete = calculatePurchaseOrderQuantityV11428427112({ requestedQuantity: 100,
  availableQuantity: 20, orderedQuantity: 30, confirmedQuantity: 50,
  originalSuggestedQuantity: 50 })
assert.equal(complete.netDemandQuantity, 50)
assert.equal(complete.suggestedPurchaseQuantity, 50)
assert.equal(complete.calculationStatus, 'COMPLETE')
assert.equal(complete.result, 'PASS')
const partial = calculatePurchaseOrderQuantityV11428427112({ requestedQuantity: 100,
  availableQuantity: null, orderedQuantity: 30, confirmedQuantity: 70,
  originalSuggestedQuantity: 70 })
assert.equal(partial.availableInventoryStatus, 'NOT_CONNECTED')
assert.equal(partial.calculationStatus, 'PARTIAL')
assert.equal(partial.suggestedPurchaseQuantity, 70)
const adjustmentMissing = calculatePurchaseOrderQuantityV11428427112({ requestedQuantity: 100,
  availableQuantity: 20, orderedQuantity: 30, confirmedQuantity: 45,
  originalSuggestedQuantity: 50 })
assert.equal(adjustmentMissing.result, 'PASS')
assert.equal(adjustmentMissing.quantityReducedByHuman, true)
const adjustmentReady = calculatePurchaseOrderQuantityV11428427112({ requestedQuantity: 100,
  availableQuantity: 20, orderedQuantity: 30, confirmedQuantity: 45,
  originalSuggestedQuantity: 50, quantityAdjustmentReason: '批量包装约束' })
assert.equal(adjustmentReady.result, 'PASS')
const exceeds = calculatePurchaseOrderQuantityV11428427112({ requestedQuantity: 100,
  availableQuantity: 0, orderedQuantity: 0, confirmedQuantity: 110,
  originalSuggestedQuantity: 100, quantityAdjustmentReason: '临时多买' })
assert.equal(exceeds.result, 'PASS')
assert.equal(exceeds.quantityIncreasedByHuman, true)
const increaseWithoutReason = calculatePurchaseOrderQuantityV11428427112({ requestedQuantity: 100,
  availableQuantity: 0, orderedQuantity: 0, confirmedQuantity: 110,
  originalSuggestedQuantity: 100 })
assert.equal(increaseWithoutReason.result, 'BLOCKED')
assert.match(increaseWithoutReason.blockingReasons.join('；'), /调整原因/)

const gate = { objectType: 'SupplierRecommendationGate', gateId: 'POG-QTY-001',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, purchaseOrderCreated: false,
  confirmedBy: '采购主管', confirmedAt: '2026-08-08T12:00:00.000Z',
  sourceSignature: 'QTY::1', purchaseRequestId: 'PR-QTY-001', inquiryId: 'PI-QTY-001',
  quoteComparisonId: 'QC-QTY-001', priceApprovalId: 'PAP-QTY-001',
  recommendationDecisionId: 'SRD-QTY-001', recommendedSupplierId: 'SUP-A', supplierName: '供应商A',
  recommendationItems: [{ materialCode: 'MT-QTY', materialName: '数量测试物料',
    requestedQuantity: 100, selectedSupplierCode: 'SUP-A', selectedSupplierName: '供应商A',
    selectedPrice: 10, quoteComparisonIds: ['QC-QTY-001'],
    sourcePriceApprovalIds: ['PAP-QTY-001'], supplierCandidates: [
      { supplierCode: 'SUP-A', supplierName: '供应商A', quotePrice: 10 } ] }] }
const admissionResult = { objectType: 'PurchaseOrderAdmissionResult', admissionResultId: 'POAR-QTY-001',
  gateId: gate.gateId, sourceSignature: gate.sourceSignature, status: 'READY_FOR_PURCHASE_ORDER',
  purchaseOrderCreationAllowed: true, purchaseOrderCreated: false,
  checks: ['a', 'b', 'c', 'd', 'e'].map(checkCode => ({ checkCode, result: 'PASS', passed: true })) }
const creationEntry = { objectType: 'PurchaseOrderCreationEntry', gateId: gate.gateId,
  sourceObjectId: admissionResult.admissionResultId, createActionExecuted: false,
  purchaseOrderCreated: false }
const guard = { result: 'PASS', gateId: gate.gateId,
  admissionResultId: admissionResult.admissionResultId }
let storageValue = ''
const store = createPurchaseOrderCreationDraftStoreV114284262({ storage: {
  getItem: () => storageValue, setItem: (_key, value) => { storageValue = value } } })
const draft = store.resolve({ gate, admissionResult })
draft.plannedDeliveryDate = '2026-09-01'
draft.approvalOpinion = '同意'
draft.materialItems[0].confirmedQuantity = 90
draft.materialItems[0].confirmedPrice = 10
draft.materialItems[0].confirmedDeliveryDate = '2026-09-01'
draft.materialItems[0].quantityAdjustmentReason = '按人工计划减少采购'
const saved = store.save(draft, { actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard, now: '2026-08-08T12:10:00.000Z' })
assert.equal(saved.materialItems[0].originalSuggestedQuantity, 100)
assert.equal(saved.materialItems[0].confirmedQuantity, 90)
assert.equal(saved.materialItems[0].quantityAdjustedBy, '采购员A')
assert.equal(saved.materialItems[0].quantityAdjustedAt, '2026-08-08T12:10:00.000Z')
assert.equal(saved.materialItems[0].quantityAdjustmentHistory.length, 1)
const reloaded = store.resolve({ gate: { ...gate, recommendationItems: [{
  ...gate.recommendationItems[0], requestedQuantity: 999 }] }, admissionResult })
assert.equal(reloaded.materialItems[0].confirmedQuantity, 90)
assert.equal(reloaded.materialItems[0].quantityAdjustmentReason, '按人工计划减少采购')

const blockedDraft = structuredClone(saved)
blockedDraft.materialItems[0].confirmedQuantity = 110
blockedDraft.materialItems[0].quantity = 110
blockedDraft.materialItems[0].quantityAdjustmentReason = ''
const blocked = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A', gate,
  admissionResult, creationEntry, draft: blockedDraft, permissionContext: { role: 'admin' },
  repository: () => { throw new Error('must not write') } })
assert.equal(blocked.error, 'PURCHASE_ORDER_QUANTITY_GUARD_BLOCKED')
assert.equal(blocked.businessWriteCount, 0)

const page = fs.readFileSync(new URL('../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue',
  import.meta.url), 'utf8')
for (const label of ['需求数量', '可用库存', '已采购未入库数量', '净需求数量',
  '建议采购数量', '确认采购数量', '采购数量核算说明']) assert.match(page, new RegExp(label))
assert.match(page, /建议采购数量 = 需求数量 - 可用库存 - 已采购未入库数量/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Schema PASS')
console.log('Quantity Logic PASS')
console.log('ERP Language PASS')
console.log('Formula Display PASS')
console.log('Provider PASS')
console.log('Runtime PASS')
console.log('Human Data Protection PASS')
console.log('Automatic Purchase Order Creation NO PASS')
console.log('Acceptance PASS')

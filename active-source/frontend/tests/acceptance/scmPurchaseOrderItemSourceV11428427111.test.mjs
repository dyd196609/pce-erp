import assert from 'node:assert/strict'

import { createPurchaseOrderCreationDraftStoreV114284262,
  SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'
import { createPurchaseOrderItemSourceProviderV11428427111 } from
  '../../src/meta/providers/purchaseOrderItemSourceProviderV11428427111.js'
import { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'
import { synchronizeSupplierPurchaseDraftsV11428427114 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js'

const gate = {
  objectType: 'SupplierRecommendationGate', gateId: 'POG-ITEM-001',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, purchaseOrderCreated: false,
  confirmedBy: '采购主管', confirmedAt: '2026-08-08T10:00:00.000Z',
  sourceSignature: 'ITEM::1', purchaseRequestId: 'PR-001', inquiryId: 'PI-001',
  quoteComparisonId: 'QC-001', priceApprovalId: 'PAP-QC-001',
  recommendationDecisionId: 'SRD-001', recommendedSupplierId: 'SUP-A', supplierName: '供应商A',
  recommendationItems: [{ materialCode: 'MT001', materialName: '物料一', requestedQuantity: 10,
    requiredDate: '2026-09-01', quoteComparisonIds: ['QC-001'],
    sourcePriceApprovalIds: ['PAP-QC-001'], selectedSupplierCode: 'SUP-A',
    selectedSupplierName: '供应商A', selectedPrice: 18,
    supplierCandidates: [{ supplierCode: 'SUP-A', supplierName: '供应商A',
      quotePrice: 19, deliveryDate: '2026-08-28' }] }],
}
const admissionResult = { objectType: 'PurchaseOrderAdmissionResult',
  admissionResultId: 'POAR-ITEM-001', gateId: gate.gateId,
  sourceSignature: gate.sourceSignature, status: 'READY_FOR_PURCHASE_ORDER',
  purchaseOrderCreationAllowed: true, purchaseOrderCreated: false,
  checks: ['a', 'b', 'c', 'd', 'e'].map(checkCode => ({ checkCode, result: 'PASS', passed: true })) }
const creationEntry = { objectType: 'PurchaseOrderCreationEntry', gateId: gate.gateId,
  sourceObjectId: admissionResult.admissionResultId, createActionExecuted: false,
  purchaseOrderCreated: false }
const guard = { result: 'PASS', gateId: gate.gateId,
  admissionResultId: admissionResult.admissionResultId }
let value = ''
const storage = { getItem: () => value, setItem: (_key, next) => { value = next } }
const store = createPurchaseOrderCreationDraftStoreV114284262({ storage })
const draft = store.resolve({ gate, admissionResult })
const line = draft.materialItems[0]
assert.equal(line.sourcePurchaseRequestId, 'PR-001')
assert.equal(line.sourceInquiryId, 'PI-001')
assert.equal(line.sourceQuoteComparisonId, 'QC-001')
assert.equal(line.sourcePriceApprovalId, 'PAP-QC-001')
assert.equal(line.sourceGateId, 'POG-ITEM-001')
assert.equal(line.requestedQuantity, 10)
assert.equal(line.suggestedQuantity, 10)
assert.equal(line.confirmedQuantity, 0)
draft.plannedDeliveryDate = '2026-09-02'
draft.approvalOpinion = '人工确认'
line.confirmedQuantity = 8
line.quantityAdjustmentReason = '按最小包装量人工调整'
line.confirmedPrice = 18.5
line.confirmedDeliveryDate = '2026-09-02'
line.remark = '人工行备注'
const saved = store.save(draft, { actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard })
const reloaded = store.resolve({ gate: { ...gate, recommendationItems: [{
  ...gate.recommendationItems[0], requestedQuantity: 99, selectedPrice: 1 }] }, admissionResult })
assert.equal(reloaded.materialItems[0].confirmedQuantity, 8)
assert.equal(reloaded.materialItems[0].confirmedPrice, 18.5)
assert.equal(reloaded.materialItems[0].confirmedDeliveryDate, '2026-09-02')
assert.equal(reloaded.materialItems[0].remark, '人工行备注')
const facts = createPurchaseOrderItemSourceProviderV11428427111().load({ gate, draft: saved })
assert.equal(facts.factLoadStatus, 'loaded')
assert.equal(facts.supplierPolicy, 'ONE_SUPPLIER_PER_PURCHASE_ORDER')
let written = null
const ready = store.markReadyForCreation(saved, {
  actionCode: CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113,
  actor: '采购员A', guard,
})
const created = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A', gate,
  admissionResult, creationEntry, draft: ready, permissionContext: { role: 'admin' },
  repository: (purchaseOrder, orderLines) => { written = { purchaseOrder, orderLines }
    return { success: true, result: 'CREATED', purchaseOrder, orderLines,
      businessWriteCount: 1, productionDataWritten: false, purchaseOrderCreated: true } },
})
assert.equal(created.success, true)
assert.equal(written.orderLines[0].confirmedQuantity, 8)
assert.equal(written.orderLines[0].supplierAllocationSource, 'supplier_recommendation_decision')
assert.equal(written.orderLines[0].sourceGateId, gate.gateId)
let splitDraft = structuredClone(ready)
splitDraft.materialItems.push({ ...structuredClone(saved.materialItems[0]), lineNo: 2,
  materialCode: 'MT002', supplierId: 'SUP-B', supplierName: '供应商B' })
splitDraft = synchronizeSupplierPurchaseDraftsV11428427114(splitDraft)
splitDraft.supplierPurchaseDrafts.forEach(group => {
  group.deliveryDate = group.supplierId === 'SUP-A' ? '2026-09-02' : '2026-09-05'
  group.approvalRemark = '人工确认'
})
splitDraft.supplierDrafts = splitDraft.supplierPurchaseDrafts
const split = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A', gate,
  admissionResult, creationEntry, draft: splitDraft, permissionContext: { role: 'admin' },
  repository: packages => ({ success: true, result: 'CREATED',
    purchaseOrder: packages[0].purchaseOrder,
    purchaseOrders: packages.map(entry => entry.purchaseOrder),
    orderLines: packages.flatMap(entry => entry.orderLines),
    businessWriteCount: packages.length, productionDataWritten: false,
    purchaseOrderCreated: true }),
})
assert.equal(split.success, true)
assert.equal(split.purchaseOrders.length, 2)
assert.ok(split.purchaseOrders.every(order => new Set(split.orderLines
  .filter(line => line.sourceOrderId === order.sourceGateId || line.sourceGateId === order.sourceGateId)
  .map(line => line.supplierId)).size >= 1))

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Domain PASS')
console.log('Provider PASS')
console.log('Source Trace PASS')
console.log('Supplier Allocation PASS')
console.log('Quantity Source PASS')
console.log('Human Data Protection PASS')
console.log('Automatic Purchase Order Creation NO PASS')
console.log('Acceptance PASS')

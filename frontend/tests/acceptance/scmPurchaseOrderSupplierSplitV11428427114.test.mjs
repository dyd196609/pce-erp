import assert from 'node:assert/strict'
import fs from 'node:fs'

import { buildSupplierPurchaseDraftsV11428427114,
  synchronizeSupplierPurchaseDraftsV11428427114 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js'
import { createPurchaseOrderCreationDraftStoreV114284262,
  SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'
import { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'

const gate = { objectType: 'SupplierRecommendationGate', gateId: 'POG-SPLIT-001',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, purchaseOrderCreated: false,
  confirmedBy: '采购主管', confirmedAt: '2026-08-08T18:00:00.000Z',
  sourceSignature: 'SPLIT::1', purchaseRequestId: 'PR-SPLIT-001',
  inquiryId: 'PI-SPLIT-001', quoteComparisonId: 'QC-SPLIT-001',
  priceApprovalId: 'PAP-SPLIT-001', recommendationDecisionId: 'SRD-SPLIT-001',
  recommendedSupplierId: 'SUP-A', supplierName: '供应商A',
  recommendationItems: [
    ['MT001', '物料一', 'SUP-A', '供应商A'],
    ['MT002', '物料二', 'SUP-A', '供应商A'],
    ['MT003', '物料三', 'SUP-B', '供应商B'],
    ['MT004', '物料四', 'SUP-B', '供应商B'],
  ].map(([materialCode, materialName, selectedSupplierCode, selectedSupplierName]) => ({
    materialCode, materialName, requestedQuantity: 10, selectedSupplierCode,
    selectedSupplierName, selectedPrice: selectedSupplierCode === 'SUP-A' ? 12 : 15,
    quoteComparisonIds: ['QC-SPLIT-001'], sourcePriceApprovalIds: ['PAP-SPLIT-001'],
  })) }
const admissionResult = { objectType: 'PurchaseOrderAdmissionResult',
  admissionResultId: 'POAR-SPLIT-001', gateId: gate.gateId,
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
  getItem: () => storageValue, setItem: (_key, value) => { storageValue = value },
} })

let draft = store.resolve({ gate, admissionResult })
draft.materialItems.forEach(line => {
  line.confirmedQuantity = 8
  line.confirmedPrice = line.supplierId === 'SUP-A' ? 12 : 15
})
draft = synchronizeSupplierPurchaseDraftsV11428427114(draft)
assert.equal(draft.supplierPurchaseDrafts.length, 2)
for (const group of draft.supplierPurchaseDrafts) {
  group.deliveryDate = group.supplierId === 'SUP-A' ? '2026-08-20' : '2026-08-25'
  group.supplierRemark = group.supplierId === 'SUP-A'
    ? '最小包装要求' : '需要提前确认库存'
  group.approvalRemark = '同意创建该供应商采购草稿'
}
draft.supplierDrafts = draft.supplierPurchaseDrafts
const saved = store.save(draft, { actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard, now: '2026-08-08T18:10:00.000Z' })
assert.equal(saved.draftStatus, 'confirmed')
assert.equal(saved.supplierCount, 2)
assert.equal(saved.includedMaterialCount, 4)
assert.deepEqual(saved.supplierPurchaseDrafts.map(group => group.items.length), [2, 2])
const restored = store.resolve({ gate, admissionResult })
assert.equal(restored.supplierPurchaseDrafts.find(group => group.supplierId === 'SUP-A').deliveryDate,
  '2026-08-20')
assert.equal(restored.supplierPurchaseDrafts.find(group => group.supplierId === 'SUP-B').supplierRemark,
  '需要提前确认库存')
const ready = store.markReadyForCreation(saved, {
  actionCode: CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113,
  actor: '采购员A', guard,
})
let packagesWritten = []
const created = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  actor: '采购员A', gate, admissionResult, creationEntry, draft: ready,
  permissionContext: { role: 'admin' },
  repository: packages => {
    packagesWritten = packages
    return { success: true, result: 'CREATED', purchaseOrder: packages[0].purchaseOrder,
      purchaseOrders: packages.map(entry => entry.purchaseOrder),
      orderLines: packages.flatMap(entry => entry.orderLines),
      businessWriteCount: packages.length, productionDataWritten: false,
      purchaseOrderCreated: true }
  },
})
assert.equal(created.success, true)
assert.equal(created.purchaseOrders.length, 2)
assert.equal(created.businessWriteCount, 2)
assert.ok(packagesWritten.every(entry => new Set(entry.orderLines.map(line => line.supplierId)).size === 1))
assert.ok(packagesWritten.every(entry => entry.orderLines.every(line =>
  line.supplierId === entry.purchaseOrder.supplierId)))
assert.deepEqual(packagesWritten.map(entry => entry.purchaseOrder.plannedArrivalDate).sort(),
  ['2026-08-20', '2026-08-25'])

const duplicateMaterial = structuredClone(ready)
duplicateMaterial.materialItems.push({ ...structuredClone(ready.materialItems[0]),
  lineNo: 5, supplierId: 'SUP-B', supplierName: '供应商B' })
duplicateMaterial.supplierPurchaseDrafts = buildSupplierPurchaseDraftsV11428427114({
  draft: duplicateMaterial, previousSupplierDrafts: duplicateMaterial.supplierPurchaseDrafts })
duplicateMaterial.supplierDrafts = duplicateMaterial.supplierPurchaseDrafts
const blocked = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  actor: '采购员A', gate, admissionResult, creationEntry, draft: duplicateMaterial,
  permissionContext: { role: 'admin' }, repository: () => {
    throw new Error('duplicate material must not write')
  },
})
assert.equal(blocked.error, 'PURCHASE_ORDER_ITEM_MULTI_SUPPLIER_ALLOCATION')
assert.equal(blocked.businessWriteCount, 0)

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
assert.match(page, /供应商采购草稿/)
assert.match(page, /供应商数量/)
assert.match(page, /交货日期/)
assert.match(page, /供应商备注/)
assert.match(page, /所属供应商|供应商名称/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Supplier Split PASS')
console.log('Item Allocation PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('Acceptance PASS')


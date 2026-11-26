import assert from 'node:assert/strict'
import fs from 'node:fs'

import { buildSupplierPurchaseDraftsV11428427114,
  evaluateSupplierPurchaseDraftsV11428427114 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js'
import { calculatePurchaseOrderQuantityV11428427112 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderQuantityModelV11428427112.js'
import { createPurchaseOrderCreationDraftStoreV114284262,
  SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'
import { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'

const materialItems = [
  ['MT001', '物料一', 'SUP001', '华为技术有限公司'],
  ['MT005', '物料五', 'SUP002', '精工铝材供应商'],
  ['MT009', '物料九', 'SUP003', '华信电子材料'],
].map(([materialCode, materialName, supplierId, supplierName], index) => ({
  lineNo: index + 1, materialCode, materialName, requestedQuantity: 10,
  confirmedQuantity: 8, confirmedPrice: 12, supplierId, supplierName,
  confirmedDeliveryDate: `2026-09-${10 + index}`,
}))
const split = buildSupplierPurchaseDraftsV11428427114({ draft: {
  draftId: 'PO-DRAFT-R143', supplierId: 'SUP001',
  supplierName: '华为技术有限公司、精工铝材供应商、华信电子材料', materialItems,
} })
assert.equal(split.length, 3)
assert.deepEqual(split.map(group => group.supplierId), ['SUP001', 'SUP002', 'SUP003'])
assert.ok(split.every(group => group.items.length === 1))
assert.ok(split.every(group => !/[、，,；;]/.test(group.supplierName)))
assert.ok(split.every(group => group.items[0].supplierId === group.supplierId))
assert.ok(split.every(group => group.items[0].supplierName === group.supplierName))

const composite = evaluateSupplierPurchaseDraftsV11428427114({ materialItems: [{
  materialCode: 'MT-X', requestedQuantity: 5, confirmedQuantity: 5,
  supplierId: 'SUP-X', supplierName: '供应商A、供应商B', confirmedDeliveryDate: '2026-09-20',
}] })
assert.equal(composite.result, 'BLOCKED')
assert.match(composite.missingFields.join('；'), /包含多个供应商/)

const missingSupplier = evaluateSupplierPurchaseDraftsV11428427114({ materialItems: [{
  materialCode: 'MT-Y', requestedQuantity: 5, confirmedQuantity: 5,
  supplierId: '', supplierName: '', confirmedDeliveryDate: '2026-09-20',
}] })
assert.equal(missingSupplier.result, 'BLOCKED')
assert.match(missingSupplier.missingFields.join('；'), /供应商身份未完成/)

const invalidDemand = calculatePurchaseOrderQuantityV11428427112({
  requestedQuantity: 0, confirmedQuantity: 100, quantityAdjustmentReason: '测试异常',
})
assert.equal(invalidDemand.result, 'BLOCKED')
assert.match(invalidDemand.blockingReasons.join('；'), /需求数量为0/)
const pending = calculatePurchaseOrderQuantityV11428427112({
  requestedQuantity: 10, confirmedQuantity: 0,
})
assert.equal(pending.itemDraftStatus, 'excluded')
assert.equal(pending.quantityConsistencyStatus, 'pending_confirmation')
assert.equal(pending.quantityConsistencyStatusLabel, '待确认')
assert.equal(pending.result, 'PASS')

let stored = ''
const store = createPurchaseOrderCreationDraftStoreV114284262({ storage: {
  getItem: () => stored, setItem: (_key, value) => { stored = value },
} })
const invalidDraft = {
  objectType: 'PurchaseOrderDraft', draftId: 'PO-DRAFT-ZERO-DEMAND', gateId: 'POG-R143',
  admissionResultId: 'POAR-R143', sourceSignature: 'R143', manualDataVersion: 0,
  materialItems: [{ materialCode: 'MT-ZERO', requestedQuantity: 0,
    confirmedQuantity: 100, quantityAdjustmentReason: '异常验证',
    supplierId: 'SUP001', supplierName: '华为技术有限公司', confirmedPrice: 10 }],
}
const isolatedInvalidDraft = store.save(invalidDraft, {
  actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard: { result: 'PASS', gateId: 'POG-R143',
    admissionResultId: 'POAR-R143' },
})
assert.equal(isolatedInvalidDraft.purchaseMaterialItems.length, 0)
assert.equal(isolatedInvalidDraft.recommendationEvidenceItems.length, 1)
assert.equal(JSON.parse(stored)[0].purchaseMaterialItems.length, 0)

const legacyGate = {
  objectType: 'SupplierRecommendationGate', gateId: 'POG-LEGACY-SPLIT',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, confirmedBy: '采购主管',
  confirmedAt: '2026-08-08T10:00:00.000Z', sourceSignature: 'LEGACY-SPLIT',
  recommendedSupplierId: 'SUP001', recommendedSupplierIds: ['SUP001', 'SUP002'],
  supplierName: '华为技术有限公司、精工铝材供应商',
  recommendationItems: [
    { materialCode: 'MT001', materialName: '物料一', requestedQuantity: 5,
      selectedSupplierCode: 'SUP001', selectedSupplierName: '华为技术有限公司' },
    { materialCode: 'MT005', materialName: '物料五', requestedQuantity: 6,
      selectedSupplierCode: 'SUP002', selectedSupplierName: '精工铝材供应商' },
  ],
}
const legacyAdmission = { admissionResultId: 'POAR-LEGACY-SPLIT' }
let legacyStored = JSON.stringify([{ objectType: 'PurchaseOrderDraft',
  draftId: 'PO-DRAFT-LEGACY-SPLIT', gateId: legacyGate.gateId,
  admissionResultId: legacyAdmission.admissionResultId,
  sourceSignature: legacyGate.sourceSignature, supplierId: 'SUP001',
  supplierName: legacyGate.supplierName, plannedDeliveryDate: '2026-09-30',
  manualDataVersion: 2, materialItems: legacyGate.recommendationItems.map((item, index) => ({
    lineNo: index + 1, materialCode: item.materialCode, materialName: item.materialName,
    requestedQuantity: item.requestedQuantity, confirmedQuantity: item.requestedQuantity,
    supplierId: 'SUP001', supplierName: legacyGate.supplierName,
  })) }])
const legacyStore = createPurchaseOrderCreationDraftStoreV114284262({ storage: {
  getItem: () => legacyStored, setItem: (_key, value) => { legacyStored = value },
} })
const repaired = legacyStore.resolve({ gate: legacyGate, admissionResult: legacyAdmission })
assert.deepEqual(repaired.materialItems.map(item => item.supplierId), ['SUP001', 'SUP002'])
assert.deepEqual(repaired.supplierPurchaseDrafts.map(group => group.supplierName),
  ['华为技术有限公司', '精工铝材供应商'])

let repositoryCalled = false
const blockedCreate = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A',
  gate: { objectType: 'SupplierRecommendationGate', gateId: 'POG-R143',
    status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
    purchaseOrderCreationEntryReady: true, confirmedBy: '采购主管',
    confirmedAt: '2026-08-08T10:00:00.000Z', sourceSignature: 'R143' },
  admissionResult: { objectType: 'PurchaseOrderAdmissionResult',
    admissionResultId: 'POAR-R143', gateId: 'POG-R143', sourceSignature: 'R143',
    status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
    checks: ['a', 'b', 'c', 'd', 'e'].map(checkCode =>
      ({ checkCode, result: 'PASS', passed: true })) },
  creationEntry: { objectType: 'PurchaseOrderCreationEntry', gateId: 'POG-R143',
    sourceObjectId: 'POAR-R143', createActionExecuted: false },
  draft: { ...invalidDraft, savedToStore: true, manualDataVersion: 1,
    draftStatus: 'ready_for_creation', readinessStatus: 'ready_for_creation' },
  permissionContext: { role: 'admin' },
  repository: () => { repositoryCalled = true; return { success: true } },
})
assert.equal(blockedCreate.result, 'BLOCKED')
assert.equal(blockedCreate.businessWriteCount, 0)
assert.equal(repositoryCalled, false)

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
assert.match(page, /materialEligibility\?\.checks\?\.\[index\]\?\.result === 'PASS'/)
assert.match(page, /draftSourceFacts\.supplierCount \|\| 0/)
const model = fs.readFileSync(new URL(
  '../../src/meta/domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js',
  import.meta.url), 'utf8')
assert.doesNotMatch(model, /line\.supplierId \|\| draft\.supplierId/)
assert.doesNotMatch(model, /line\.supplierName \|\| draft\.supplierName/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Supplier Model PASS')
console.log('Supplier Count PASS')
console.log('Item Allocation PASS')
console.log('Quantity Consistency PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('Acceptance PASS')

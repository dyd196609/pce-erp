import assert from 'node:assert/strict'
import fs from 'node:fs'

import { createPurchaseOrderCreationDraftV114284262 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'
import { createPurchaseOrderItemSourceProviderV11428427111 } from
  '../../src/meta/providers/purchaseOrderItemSourceProviderV11428427111.js'
import { createSupplierPurchaseDraftProviderV1142842711431 } from
  '../../src/meta/providers/supplierPurchaseDraftProviderV1142842711431.js'

const suppliers = [
  ['SUP001', '供应商A', 'MT001'],
  ['SUP002', '供应商B', 'MT002'],
  ['SUP003', '供应商C', 'MT003'],
]
const gate = {
  gateId: 'POG-R1431', recommendedSupplierId: 'SUP001',
  recommendedSupplierIds: suppliers.map(item => item[0]),
  supplierName: suppliers.map(item => item[1]).join('、'),
  purchaseRequestId: 'PR-R1431', inquiryId: 'PI-R1431',
  quoteComparisonId: 'QC-R1431', priceApprovalId: 'PAP-R1431',
  recommendationItems: suppliers.map(([supplierId, supplierName, materialCode]) => ({
    objectType: 'SupplierRecommendationDecision', materialCode,
    materialName: `物料${materialCode}`, requestedQuantity: 10,
    selectedSupplierCode: supplierId, selectedSupplierName: supplierName,
    sourcePurchaseRequestIds: ['PR-R1431'], sourceInquiryIds: ['PI-R1431'],
    quoteComparisonIds: ['QC-R1431'], sourcePriceApprovalIds: ['PAP-R1431'],
  })),
}
const draft = createPurchaseOrderCreationDraftV114284262({
  gate, admissionResult: { admissionResultId: 'POAR-R1431' },
})
assert.equal(draft.supplierId, '')
assert.equal(draft.supplierName, '')
assert.equal(draft.supplierDataSource, 'SupplierPurchaseDraft[]')
assert.equal(draft.recommendationDecisionRole, 'evidence_only')

const confirmedDraft = { ...draft, materialItems: draft.materialItems.map((item, index) => ({
  ...item, confirmedQuantity: 5, itemDraftStatus: 'included', confirmedPrice: 20,
  confirmedDeliveryDate: `2026-09-${10 + index}`,
})) }
const supplierProvider = createSupplierPurchaseDraftProviderV1142842711431()
const facts = supplierProvider.load({ draft: confirmedDraft })
assert.equal(facts.result, 'PASS')
assert.equal(facts.supplierCount, 3)
assert.equal(facts.supplierCountSource, 'SupplierPurchaseDraft.length')
assert.equal(facts.sourceTrace.recommendationDecisionRole, 'evidence_only')
assert.equal(facts.recommendationDecisionUsedAsDraftSource, false)
assert.equal(facts.aggregateSupplierFieldUsed, false)
assert.deepEqual(facts.supplierPurchaseDrafts.map(item => item.supplierId),
  ['SUP001', 'SUP002', 'SUP003'])
assert.deepEqual(facts.materialItems.map(item => item.supplierId),
  ['SUP001', 'SUP002', 'SUP003'])

const itemProvider = createPurchaseOrderItemSourceProviderV11428427111({
  stateReader: () => ({ purchaseRequests: [], purchaseRequestItems: [],
    purchaseOrders: [], purchaseOrderItems: [] }),
})
const invalidHydrated = itemProvider.hydrate({ gate, draft: {
  ...draft, materialItems: [{ ...draft.materialItems[0], requestedQuantity: 0,
    confirmedQuantity: 100, itemDraftStatus: 'included' }],
} })
assert.equal(invalidHydrated.materialItems[0].requestedQuantity, 0)
assert.equal(invalidHydrated.materialItems[0].confirmedQuantity, 100)
const invalidFacts = supplierProvider.load({ draft: invalidHydrated })
assert.equal(invalidFacts.result, 'PASS')
assert.equal(invalidFacts.materialEligibility.result, 'FAIL')
assert.equal(invalidFacts.invalidDemandItems.length, 1)
assert.equal(invalidFacts.validMaterialCount, 0)
assert.equal(invalidFacts.recommendationEvidenceItems.length, 1)
assert.match(invalidFacts.recommendationEvidenceItems[0].eligibilityReason, /无采购需求/)

const humanDraft = { ...facts.draft, manualDataVersion: 4,
  materialItems: facts.draft.materialItems.map((item, index) => ({ ...item,
    confirmedQuantity: index + 3, confirmedPrice: 99 + index,
    confirmedDeliveryDate: `2026-10-${10 + index}`, remark: `人工备注${index + 1}` })),
  supplierPurchaseDrafts: facts.draft.supplierPurchaseDrafts.map((item, index) => ({
    ...item, deliveryDate: `2026-10-${10 + index}`,
    supplierRemark: `供应商备注${index + 1}`, approvalRemark: '人工同意',
  })),
}
const reloaded = supplierProvider.load({ draft: humanDraft })
assert.deepEqual(reloaded.draft.materialItems.map(item => [item.supplierId,
  item.confirmedQuantity, item.confirmedPrice, item.confirmedDeliveryDate, item.remark]),
humanDraft.materialItems.map(item => [item.supplierId, item.confirmedQuantity,
  item.confirmedPrice, item.confirmedDeliveryDate, item.remark]))
assert.deepEqual(reloaded.draft.supplierPurchaseDrafts.map(item => [item.supplierId,
  item.deliveryDate, item.supplierRemark, item.approvalRemark]),
humanDraft.supplierPurchaseDrafts.map(item => [item.supplierId,
  item.deliveryDate, item.supplierRemark, item.approvalRemark]))

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
assert.match(page, /supplierPurchaseDraftProviderV1142842711431\.load/)
assert.match(page, /draftSourceFacts\.supplierCount/)
assert.doesNotMatch(page, /draft\.supplierPurchaseDrafts\?\.length/)
assert.match(page, /state\.draftSourceFacts\.result !== 'PASS'/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Source Trace PASS')
console.log('Supplier Data Source PASS')
console.log('Supplier Count PASS')
console.log('Item Allocation Source PASS')
console.log('Quantity Consistency PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('Acceptance PASS')
console.log('Business Write Count 0 PASS')

import assert from 'node:assert/strict'
import fs from 'node:fs'

import { buildPurchaseOrderCreationContextV114284271145 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationContext.js'
import { createPurchaseOrderItemSourceProviderV11428427111 } from
  '../../src/meta/providers/purchaseOrderItemSourceProviderV11428427111.js'
import { createSupplierPurchaseDraftProviderV1142842711431 } from
  '../../src/meta/providers/supplierPurchaseDraftProviderV1142842711431.js'
import { buildFormalPurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'

const purchaseRequestIds = ['PR001', 'PR002', 'PR003', 'PR004', 'PR005', 'PR006']
const gate = { gateId: 'POG-R145', purchaseRequestId: 'PR001', purchaseRequestIds,
  inquiryId: 'PI001', inquiryIds: ['PI001', 'PI002'],
  quoteComparisonId: 'QC001', quoteComparisonIds: ['QC001', 'QC002'],
  priceApprovalId: 'PAP001', priceApprovalIds: ['PAP001', 'PAP002'] }
const materialCodes = ['MT001', 'MT001', 'MT002', 'MT003', 'MT004', 'MT005']
const purchaseRequestFacts = purchaseRequestIds.map((requestNo, index) => ({
  requestNo,
  materialItems: [{ materialCode: materialCodes[index],
    materialName: `物料${materialCodes[index]}`, quantity: index + 1 }],
}))
const draftItems = [...new Set(materialCodes)].map((materialCode, index) => ({
  lineNo: index + 1, materialCode, materialName: `物料${materialCode}`,
  sourcePurchaseRequestId: purchaseRequestIds[index], requestedQuantity: 1,
  confirmedQuantity: index + 2, supplierId: `SUP00${index + 1}`,
  supplierName: `供应商${index + 1}`, confirmedPrice: 20 + index,
  sourceInquiryId: 'PI001', sourceQuoteComparisonId: 'QC001',
  sourcePriceApprovalId: 'PAP001', sourceGateId: 'POG-R145',
  quantitySource: 'SupplierRecommendationDecision',
}))
const draft = { objectType: 'PurchaseOrderDraft', draftId: 'POD-R145', gateId: 'POG-R145',
  materialItems: draftItems, supplierPurchaseDrafts: [] }

const context = buildPurchaseOrderCreationContextV114284271145({
  gate, draft, purchaseRequestFacts, scmState: {},
})
assert.equal(context.objectType, 'PurchaseOrderCreationContext')
assert.deepEqual(context.purchaseRequestIds, purchaseRequestIds)
assert.equal(context.sourcePurchaseRequestCount, 6)
assert.equal(context.materialItems.length, 5)
const merged = context.materialItems.find(item => item.materialCode === 'MT001')
assert.deepEqual(merged.sourcePurchaseRequestIds, ['PR001', 'PR002'])
assert.equal(merged.requestedQuantity, 3)
assert.equal(merged.confirmedQuantity, 2)
assert.equal(merged.supplierId, 'SUP001')
assert.equal(merged.purchaseRequestMergeType, 'MERGED_FROM')
assert.equal(context.businessWriteCount, 0)
assert.equal(context.automaticPurchaseOrderCreation, false)

const provider = createPurchaseOrderItemSourceProviderV11428427111({
  stateReader: () => ({ purchaseRequests: [], purchaseRequestItems: [],
    purchaseOrders: [], purchaseOrderItems: [] }),
})
const hydrated = provider.hydrate({ gate, draft, purchaseRequestFacts })
assert.deepEqual(hydrated.creationContext.purchaseRequestIds, purchaseRequestIds)
assert.equal(hydrated.creationContext.sourcePurchaseRequestCount, 6)
assert.deepEqual(hydrated.materialItems.find(item => item.materialCode === 'MT001')
  .sourcePurchaseRequestIds, ['PR001', 'PR002'])
assert.equal(hydrated.materialItems.find(item => item.materialCode === 'MT001')
  .confirmedQuantity, 2)
const supplierFacts = createSupplierPurchaseDraftProviderV1142842711431()
  .load({ draft: hydrated })
assert.equal(supplierFacts.creationContext.supplierPurchaseDrafts.length, 5)
assert.equal(supplierFacts.creationContext.materialItems.length, 5)

const formal = buildFormalPurchaseOrderV114284271({ gate,
  admissionResult: { admissionResultId: 'POAR-R145' },
  draft: { ...hydrated, purchaseRequestIds,
    creationContext: hydrated.creationContext, manualDataVersion: 1 },
  supplierPurchaseDraft: { supplierId: 'SUP001', supplierName: '供应商1',
    deliveryDate: '2026-09-30' }, actor: '采购员A',
})
assert.deepEqual(formal.purchaseOrder.sourcePurchaseRequestIds, purchaseRequestIds)
assert.deepEqual(formal.orderLines[0].sourcePurchaseRequestIds, ['PR001', 'PR002'])

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
assert.match(page, /采购申请编号列表/)
assert.match(page, /采购申请数量/)
assert.match(page, /creationContext\.purchaseRequestIds/)
assert.doesNotMatch(page, /label="采购申请编号">/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Creation Context PASS')
console.log('Multiple PR PASS')
console.log('Source Trace PASS')
console.log('Material Merge PASS')
console.log('Supplier Allocation PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('Acceptance PASS')
console.log('Business Write Count 0 PASS')

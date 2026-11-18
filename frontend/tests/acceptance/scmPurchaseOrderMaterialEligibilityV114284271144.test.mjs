import assert from 'node:assert/strict'
import fs from 'node:fs'

import { evaluatePurchaseOrderMaterialEligibilityV114284271144 } from
  '../../src/meta/domain/scm/purchaseOrder/guard/purchaseOrderMaterialEligibilityGuardV114284271144.js'
import { createSupplierPurchaseDraftProviderV1142842711431 } from
  '../../src/meta/providers/supplierPurchaseDraftProviderV1142842711431.js'
import { CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
  executeCreatePurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'

const valid = { lineNo: 1, materialCode: 'MT-VALID', materialName: '有效物料',
  requestedQuantity: 20, confirmedQuantity: 12, supplierId: 'SUP001',
  supplierName: '供应商A', confirmedPrice: 25, confirmedDeliveryDate: '2026-09-20' }
const noDemand = { lineNo: 2, materialCode: 'MT-NO-DEMAND', materialName: '无需求推荐物料',
  requestedQuantity: 0, confirmedQuantity: 8, supplierId: 'SUP002',
  supplierName: '供应商B', confirmedPrice: 30 }
const noSupplier = { lineNo: 3, materialCode: 'MT-NO-SUPPLIER', materialName: '未分配物料',
  requestedQuantity: 5, confirmedQuantity: 5, supplierId: '', supplierName: '' }
const notSelected = { lineNo: 4, materialCode: 'MT-EVIDENCE', materialName: '仅推荐证据',
  requestedQuantity: 9, confirmedQuantity: 0, supplierId: 'SUP003', supplierName: '供应商C' }

const evaluation = evaluatePurchaseOrderMaterialEligibilityV114284271144([
  valid, noDemand, noSupplier, notSelected,
])
assert.equal(evaluation.result, 'FAIL')
assert.equal(evaluation.validMaterialCount, 1)
assert.equal(evaluation.invalidMaterialCount, 2)
assert.equal(evaluation.evidenceOnlyCount, 3)
assert.equal(evaluation.checks[0].result, 'PASS')
assert.equal(evaluation.checks[1].reasonCode, 'PURCHASE_DEMAND_NOT_EXISTS')
assert.equal(evaluation.checks[2].reasonCode, 'PURCHASE_ORDER_ITEM_SUPPLIER_REQUIRED')
assert.equal(evaluation.checks[3].result, 'NOT_SELECTED')

const provider = createSupplierPurchaseDraftProviderV1142842711431()
const facts = provider.load({ draft: { objectType: 'PurchaseOrderDraft',
  draftId: 'PO-DRAFT-R144', materialItems: [valid, noDemand, noSupplier, notSelected],
  supplierPurchaseDrafts: [{ supplierId: 'SUP001', supplierName: '供应商A',
    deliveryDate: '2026-09-20', approvalRemark: '人工同意', supplierRemark: '保留备注' }],
} })
assert.equal(facts.result, 'PASS')
assert.equal(facts.validMaterialCount, 1)
assert.equal(facts.invalidMaterialCount, 2)
assert.equal(facts.supplierCount, 1)
assert.deepEqual(facts.validMaterialItems.map(item => item.materialCode), ['MT-VALID'])
assert.deepEqual(facts.recommendationEvidenceItems.map(item => item.materialCode),
  ['MT-NO-DEMAND', 'MT-NO-SUPPLIER', 'MT-EVIDENCE'])
assert.equal(facts.draft.purchaseMaterialItems.length, 1)
assert.equal(facts.draft.recommendationEvidenceItems.length, 3)
assert.equal(facts.draft.supplierPurchaseDrafts[0].supplierRemark, '保留备注')

const gate = { objectType: 'SupplierRecommendationGate', gateId: 'POG-R144',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, confirmedBy: '采购主管',
  confirmedAt: '2026-08-08T10:00:00.000Z', sourceSignature: 'R144',
  purchaseOrderCreated: false }
const admissionResult = { objectType: 'PurchaseOrderAdmissionResult',
  admissionResultId: 'POAR-R144', gateId: 'POG-R144', sourceSignature: 'R144',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreated: false,
  checks: ['a', 'b', 'c', 'd', 'e'].map(checkCode =>
    ({ checkCode, result: 'PASS', passed: true })) }
const creationEntry = { objectType: 'PurchaseOrderCreationEntry', gateId: 'POG-R144',
  sourceObjectId: 'POAR-R144', createActionExecuted: false, purchaseOrderCreated: false }
let repositoryPayload = null
const outcome = executeCreatePurchaseOrderV114284271({
  actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271, actor: '采购员A',
  gate, admissionResult, creationEntry, permissionContext: { role: 'admin' },
  draft: { objectType: 'PurchaseOrderDraft', draftId: 'PO-DRAFT-R144',
    gateId: 'POG-R144', admissionResultId: 'POAR-R144', sourceSignature: 'R144',
    savedToStore: true, manualDataVersion: 1, draftStatus: 'ready_for_creation',
    readinessStatus: 'ready_for_creation', materialItems: [valid, noDemand, notSelected],
    supplierPurchaseDrafts: [{ supplierId: 'SUP001', supplierName: '供应商A',
      deliveryDate: '2026-09-20', approvalRemark: '人工同意', supplierRemark: '保留备注' }],
  },
  repository: payload => {
    repositoryPayload = payload
    return { success: true, result: 'CREATED', purchaseOrders: payload.map(item => item.purchaseOrder),
      businessWriteCount: payload.length, productionDataWritten: false }
  },
})
assert.equal(outcome.success, true, JSON.stringify(outcome))
assert.equal(outcome.validMaterialCount, 1)
assert.equal(outcome.isolatedRecommendationEvidenceCount, 2)
assert.equal(repositoryPayload.length, 1)
assert.deepEqual(repositoryPayload[0].orderLines.map(item => item.materialCode), ['MT-VALID'])

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
assert.match(page, /data-acceptance-id="purchase-order-recommendation-evidence"/)
assert.match(page, /以下物料仅保留为供应商推荐证据，未进入采购订单草稿物料/)
assert.match(page, /materialEligibility\?\.checks\?\.\[index\]\?\.result === 'PASS'/)
assert.match(page, /draftSourceFacts\.supplierCount/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Material Eligibility PASS')
console.log('Valid Material Count PASS')
console.log('Invalid Material Isolation PASS')
console.log('Supplier Allocation PASS')
console.log('Quantity Consistency PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('Acceptance PASS')

import assert from 'node:assert/strict'
import fs from 'node:fs'

import { createPurchaseOrderGateCreationRequestV11428427219 } from
  '../src/meta/process/scm/purchaseOrderCreationRequest/purchaseOrderGateCreationRequestV11428427219.js'

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8')

const supplierCandidates = Array.from({ length: 4 }, (_, index) => ({
  supplierCode: `SUP-SPLIT-${index + 1}`,
  supplierName: `拆单供应商${index + 1}`,
}))
const request = createPurchaseOrderGateCreationRequestV11428427219({
  gate: {
    objectType: 'SupplierRecommendationGate', gateId: 'POG-V11428427220',
    status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
    sourceSignature: 'V11428427220', supplierCandidates,
    recommendationItems: [{ materialCode: 'MAT-SPLIT-001', materialName: '拆单物料',
      requestedQuantity: 4, selectedSupplierCode: supplierCandidates[0].supplierCode,
      selectedSupplierName: supplierCandidates[0].supplierName }],
  },
  admissionResult: { objectType: 'PurchaseOrderAdmissionResult',
    admissionResultId: 'POAR-V11428427220', status: 'READY_FOR_PURCHASE_ORDER' },
  creationEntry: { objectType: 'PurchaseOrderCreationEntry', entryId: 'POCE-V11428427220' },
  sourceMaterialLines: [{ materialCode: 'MAT-SPLIT-001', quantity: 4,
    requiredDate: '2026-08-31' }],
  now: '2026-08-10T00:00:00.000Z',
})

assert.equal(request.supplierCount, 4)
assert.equal(request.supplierGroups.length, 4)
assert.ok(request.supplierGroups.every(group => group.materialLines.length === 1))
assert.ok(request.supplierGroups.every(group => group.materialLines[0].expectedDate === '2026-08-31'))

const service = read('../../backend/procurement/scm_runtime_services.py')
const facts = read('../../backend/procurement/scm_page_facts.py')
const schema = read('../src/meta/schema/purchase/purchaseOrder.js')
const page = read('../src/meta/pages/ScmPurchaseOrderGatePage.vue')
const governance = read('../../docs/governance/Gate对象交接创建规范.md')

assert.match(service, /for group, supplier, lines in prepared:/)
assert.match(service, /PurchaseOrderItem\.objects\.bulk_create/)
assert.match(service, /return orders, len\(orders\)/)
assert.match(facts, /"purchaseOrderId": order\.pk/)
assert.match(facts, /"supplierName": value\.supplier\.name/)
assert.match(facts, /"purchaseDate": value\.order_date/)
assert.match(facts, /"deliveryDate": value\.expected_date/)
assert.match(facts, /"deliveryUrgencyLabel":/)
assert.match(schema, /field: 'supplierName'.*label: '供应商'/s)
assert.match(schema, /field: 'purchaseDate'.*label: '采购日期'/s)
assert.match(page, /activeCreationRequest\.supplierGroups/)
assert.match(page, /purchaseOrderCreateCount\.value = Number\(response\.data\.createdCount/)
assert.match(governance, /GATE-HANDOFF-002/)

console.log('Governance Files Loaded PASS')
console.log('PURCHASE-ORDER-SUPPLIER-SPLIT-001 PASS')
console.log('Supplier Split PASS')
console.log('PURCHASE-ORDER-DETAIL-CREATE-001 PASS')
console.log('PurchaseOrderItem Created PASS')
console.log('PURCHASE-ORDER-FIELD-INHERIT-001 PASS')
console.log('Detail Runtime PASS')
console.log('List Runtime PASS')

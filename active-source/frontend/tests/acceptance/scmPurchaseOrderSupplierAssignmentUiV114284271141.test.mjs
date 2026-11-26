import assert from 'node:assert/strict'
import fs from 'node:fs'

import { buildSupplierPurchaseDraftsV11428427114,
  synchronizeSupplierPurchaseDraftsV11428427114 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js'
import { buildFormalPurchaseOrdersV11428427114 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'

const page = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
const supplierArea = page.slice(page.indexOf('data-acceptance-id="supplier-purchase-drafts"'),
  page.indexOf('<div class="section-heading">', page.indexOf('</section>',
    page.indexOf('data-acceptance-id="supplier-purchase-drafts"'))))

assert.match(page, /供应商采购草稿信息/)
assert.match(supplierArea, /PceEnterpriseListTable/)
assert.match(supplierArea, /primary-field="supplierId" primary-label="供应商编码"/)
for (const label of ['供应商名称', '交货日期', '审批意见', '备注']) {
  assert.match(supplierArea, new RegExp(`label="${label}"`))
}
assert.doesNotMatch(supplierArea, /label="物料数量"|label="采购金额"|label="总金额"/)
assert.match(page, /PceEnterpriseListTable/)
assert.match(page, /PceBusinessStatus/)
assert.match(page, /PCE-ENTERPRISE-LIST-CONTRACT-V1\.1|createPceEnterpriseListContract/)
assert.match(page, /field: 'supplierName'.*filterType: 'select'/s)
assert.match(page, /field: 'materialCode'.*filterType: 'text'/s)
assert.match(page, /field: 'materialName'.*filterType: 'text'/s)
assert.match(page, /primary-field="materialCode"/)
assert.match(page, /prop="materialName" label="物料名称" fixed="left"/)
assert.match(page, /<template #actions=/)
assert.match(page, /<el-select :model-value="row\.supplierId"/)
assert.match(page, /v-for="option in supplierDraftOptions"/)
assert.match(page, /supplier_recommendation_decision: '供应商推荐确认'/)
assert.doesNotMatch(page, /<el-input v-model="row\.supplierId"/)
assert.doesNotMatch(page, /<el-input v-model="row\.supplierName"/)

const draft = {
  draftId: 'PO-DRAFT-UI-001', gateId: 'POG-UI-001', manualDataVersion: 3,
  supplierPurchaseDrafts: [
    { supplierPurchaseDraftId: 'SPD-A', supplierId: 'SUP-A', supplierName: '供应商A',
      deliveryDate: '2026-08-13', approvalRemark: '同意A', supplierRemark: '备注A', items: [] },
    { supplierPurchaseDraftId: 'SPD-B', supplierId: 'SUP-B', supplierName: '供应商B',
      deliveryDate: '2026-08-20', approvalRemark: '同意B', supplierRemark: '备注B', items: [] },
  ],
  materialItems: [
    { lineNo: 1, materialCode: 'MT001', materialName: '物料一', requestedQuantity: 5, confirmedQuantity: 5,
      confirmedPrice: 10, supplierId: 'SUP-A', supplierName: '供应商A' },
    { lineNo: 2, materialCode: 'MT005', materialName: '物料五', requestedQuantity: 7, confirmedQuantity: 7,
      confirmedPrice: 20, supplierId: 'SUP-B', supplierName: '供应商B' },
  ],
}
const synchronized = synchronizeSupplierPurchaseDraftsV11428427114(draft)
assert.equal(synchronized.supplierPurchaseDrafts.length, 2)
assert.equal(synchronized.supplierPurchaseDrafts[0].approvalRemark, '同意A')
assert.equal(synchronized.supplierPurchaseDrafts[1].supplierRemark, '备注B')

const reassigned = structuredClone(synchronized)
reassigned.materialItems[0].supplierId = 'SUP-B'
reassigned.materialItems[0].supplierName = '供应商B'
reassigned.materialItems[0].supplierAllocationSource = '人工分配（供应商采购草稿）'
const resynchronized = synchronizeSupplierPurchaseDraftsV11428427114(reassigned)
assert.equal(resynchronized.supplierPurchaseDrafts.length, 1)
assert.equal(resynchronized.supplierPurchaseDrafts[0].supplierId, 'SUP-B')
assert.equal(resynchronized.supplierPurchaseDrafts[0].items.length, 2)
assert.equal(resynchronized.materialItems[0].supplierAllocationSource, '人工分配（供应商采购草稿）')

const activeGroups = buildSupplierPurchaseDraftsV11428427114({ draft: resynchronized })
assert.equal(activeGroups.length, 1)
const formalOrders = buildFormalPurchaseOrdersV11428427114({
  gate: { gateId: 'POG-UI-001' }, admissionResult: {}, draft: resynchronized,
  actor: '采购员A', now: '2026-08-08T20:00:00.000Z',
})
assert.equal(formalOrders.length, 1)
assert.equal(formalOrders[0].purchaseOrder.supplierId, 'SUP-B')
assert.ok(formalOrders[0].orderLines.every(line => line.supplierId === 'SUP-B'))

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Supplier List PASS')
console.log('Item Allocation PASS')
console.log('List Runtime PASS')
console.log('Human Data Protection PASS')
console.log('Acceptance PASS')

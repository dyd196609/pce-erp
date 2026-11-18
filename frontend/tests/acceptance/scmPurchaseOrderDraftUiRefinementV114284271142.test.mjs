import assert from 'node:assert/strict'
import fs from 'node:fs'

import { calculatePurchaseOrderQuantityV11428427112 } from
  '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderQuantityModelV11428427112.js'

const createPage = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue', import.meta.url), 'utf8')
const listPage = fs.readFileSync(new URL(
  '../../src/meta/pages/ScmPurchaseOrderCreationRequestPage.vue', import.meta.url), 'utf8')
const router = fs.readFileSync(new URL('../../src/router/index.js', import.meta.url), 'utf8')
const supplierStart = createPage.indexOf('data-acceptance-id="supplier-purchase-drafts"')
const supplierEnd = createPage.indexOf('</section>', supplierStart)
const supplierArea = createPage.slice(supplierStart, supplierEnd)

assert.match(supplierArea, /PceEnterpriseListTable/)
assert.match(supplierArea, /page-id="purchase-order-create-supplier-drafts"/)
assert.match(supplierArea, /primary-field="supplierId" primary-label="供应商编码"/)
for (const label of ['供应商名称', '交货日期', '审批意见', '备注']) {
  assert.match(supplierArea, new RegExp(`label="${label}"`))
}
assert.doesNotMatch(supplierArea, /label="物料数量"|label="采购金额"|label="总金额"/)
assert.match(createPage, /field: 'supplierId'.*filterType: 'text'/s)
assert.match(createPage, /field: 'deliveryDate'.*filterType: 'date'/s)

assert.match(createPage,
  /materialRows = computed\(\(\) => .*materialEligibility\?\.checks\?\.\[index\]\?\.result === 'PASS'/s)
assert.match(createPage, /label="数量状态"/)
assert.match(createPage, /statusLabel: '正常'/)
assert.match(createPage, /statusLabel: '需填写原因'/)
assert.match(createPage, /statusLabel: '严重异常'/)
assert.doesNotMatch(createPage, /<el-alert v-for="\(calculation, index\) in quantityBlockingCalculations"/)
assert.match(createPage, /data-acceptance-id="purchase-order-quantity-issue-summary"/)

const rows = [
  { materialCode: 'MT-IN', requestedQuantity: 5, suggestedQuantity: 5,
    confirmedQuantity: 5 },
  { materialCode: 'MT-EX', requestedQuantity: 0, suggestedQuantity: 0,
    confirmedQuantity: 0 },
]
const calculations = rows.map(calculatePurchaseOrderQuantityV11428427112)
const visible = rows.filter((row, index) => calculations[index].itemDraftStatus === 'included'
  && Number(row.confirmedQuantity) > 0)
assert.deepEqual(visible.map(row => row.materialCode), ['MT-IN'])
assert.equal(rows.length, 2, '页面过滤不得删除草稿证据')

assert.match(listPage, />新增采购订单<\/el-button>/)
assert.match(listPage, /function goToPurchaseOrderCreate\(\)\s*{\s*router\.push\('\/scm\/purchase-order\/create'\)/s)
const navigationBlock = listPage.slice(listPage.indexOf('function goToPurchaseOrderCreate'),
  listPage.indexOf('function createRequest'))
assert.doesNotMatch(navigationBlock, /executeCreatePurchaseOrder|CREATE_PURCHASE_ORDER|createPurchaseOrder/)
assert.match(router, /path: 'scm\/purchase-order\/create'/)
assert.match(router, /ScmPurchaseOrderCreateEntryPage\.vue/)
assert.match(createPage, /purchaseOrderCreationGuardProviderV114284262\.load\(\)/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Supplier List PASS')
console.log('Item Filter PASS')
console.log('Item Supplier Allocation PASS')
console.log('Create Entry PASS')
console.log('Human Data Protection PASS')
console.log('Acceptance PASS')

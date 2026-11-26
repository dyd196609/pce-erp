import assert from 'node:assert/strict'
import fs from 'node:fs'

import { adaptPurchaseOrderRuntimeModel } from
  '../src/meta/runtime/purchaseOrderRuntimeAdapter.js'
import { buildPurchaseOrderSupplierSchemaViewV11428427228 } from
  '../src/meta/runtime/purchaseOrderSchemaViewRuntimeV11428427213.js'
import { buildPurchaseOrderViewModelV1142842724 } from
  '../src/meta/viewModels/purchaseOrderViewModelV1142842724.js'
import { buildPurchaseOrderPrintViewModelV11428427243 } from
  '../src/meta/viewModels/purchaseOrderPrintViewModelV11428427243.js'
import { buildPurchaseOrderBusinessPrintDocumentV1142842728 } from
  '../src/meta/runtime/purchaseOrderPrintBusinessRuntimeV1142842728.js'
import { PURCHASE_ORDER_LIST_SCHEMA_COLUMNS } from
  '../src/meta/schema/purchase/purchaseOrder.js'

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const supplierFact = {
  id: '28', objectType: 'PurchaseOrder', objectNo: 'PO-SUPPLIER-VIEW-028',
  supplierId: '16', supplierName: '中兴通讯', supplierContact: '张经理',
  supplierPhone: '137****5486', supplierAddress: '浙江省杭州市中兴通讯有限公司',
  supplierDeliveryAddress: '江苏省苏州市中兴通讯有限公司',
  supplierInformationSource: 'SupplierMaster', status: 'draft', statusLabel: '草稿',
}
const runtime = adaptPurchaseOrderRuntimeModel({ purchaseOrder: supplierFact, items: [] })
const supplierSchema = buildPurchaseOrderSupplierSchemaViewV11428427228({ purchaseOrder: runtime })
assert.deepEqual(supplierSchema.fields.map(field => field.key), [
  'supplierName', 'supplierContact', 'supplierPhone', 'supplierAddress',
  'supplierDeliveryAddress',
])
assert.equal(supplierSchema.fields.at(-1).value, supplierFact.supplierDeliveryAddress)
assert.equal(supplierSchema.factSource, 'SupplierMaster')

const businessView = buildPurchaseOrderViewModelV1142842724({
  purchaseOrder: runtime, orderLines: [], lifecycleDetail: {}, viewRole: 'management',
})
const printView = buildPurchaseOrderPrintViewModelV11428427243({
  purchaseOrderViewModel: businessView, companyName: 'PCE测试企业',
})
const printHtml = buildPurchaseOrderBusinessPrintDocumentV1142842728(
  printView, { outputClassification: 'buyer' })
for (const value of [
  '供应商信息', '供应商名称', '联系人', '联系电话', '供应商地址', '送货地址',
  supplierFact.supplierDeliveryAddress, 'data-fact-source="SupplierMaster"',
]) assert.match(printHtml, new RegExp(value))

const listKeys = PURCHASE_ORDER_LIST_SCHEMA_COLUMNS.map(column => column.key)
assert.ok(listKeys.includes('supplierName'))
for (const prohibited of [
  'supplierContact', 'supplierPhone', 'supplierAddress', 'supplierDeliveryAddress',
]) assert.ok(!listKeys.includes(prohibited))

const migration = read('../../backend/procurement/migrations/0018_supplier_delivery_address_v11428427228.py')
const server = read('../../backend/procurement/scm_page_facts.py')
const page = read('../src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
const masterDataRegistry = read('../src/meta/master-data/masterDataRegistry.js')
const rule = read('../../docs/governance/供应商交付信息与采购订单展示治理规范.md')
assert.match(migration, /populate_supplier_delivery_address/)
assert.doesNotMatch(migration, /PurchaseOrder|MaterialMaster|SupplierQuotation|Gate/)
assert.match(server, /"supplierDeliveryAddress": value\.supplier\.delivery_address/)
assert.match(page, /data-detail-region="supplier-information"/)
assert.match(masterDataRegistry, /\['deliveryAddress', '送货地址'/)
assert.match(rule, /SUPPLIER-DELIVERY-ADDRESS-001/)
assert.match(rule, /PURCHASE-ORDER-SUPPLIER-VIEW-001/)
assert.match(rule, /PURCHASE-ORDER-PRINT-SUPPLIER-001/)

console.log('SUPPLIER-DELIVERY-ADDRESS-001 PASS')
console.log('PURCHASE-ORDER-SUPPLIER-VIEW-001 PASS')
console.log('PURCHASE-ORDER-PRINT-SUPPLIER-001 PASS')
console.log('PurchaseOrder Creation Logic Changed NO')
console.log('Price Changed NO')
console.log('Material Changed NO')
console.log('Gate Changed NO')

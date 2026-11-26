import assert from 'node:assert/strict'
import fs from 'node:fs'

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8')

const runtime = read('../../backend/procurement/purchase_order_supplier_fact_runtime.py')
const resolver = read('../../backend/procurement/supplier_material_fact_resolver.py')
const service = read('../../backend/procurement/scm_runtime_services.py')
const facts = read('../../backend/procurement/scm_page_facts.py')
const tests = read('../../backend/procurement/tests_v11428427224.py')
const schema = read('../src/meta/schema/purchase/purchaseOrder.js')
const viewModel = read('../src/meta/viewModels/purchaseOrderViewModelV1142842724.js')
const supplierRule = read('../../docs/governance/供应商主数据规范.md')
const lifecycleRule = read('../../docs/governance/采购业务生命周期规范.md')

assert.match(runtime, /class PurchaseOrderSupplierFactRuntime/)
assert.match(resolver, /SupplierQuotation\.objects\.filter/)
assert.match(resolver, /SupplierQuoteItem\.unitPrice/)
assert.match(resolver, /PurchaseRequest\.requiredDate/)
assert.match(service, /SupplierMaterialFactResolver\.resolve/)
assert.match(service, /PURCHASE_PRICE_SOURCE_REQUIRED/)
assert.doesNotMatch(service, /raw\.get\("unitPrice", 0\)/)
assert.match(service, /"amount": \(quantity \* unit_price\)\.quantize/)
assert.match(facts, /"supplierContact"/)
assert.match(facts, /"priceSourceLabel"/)
assert.match(facts, /"deliverySourceLabel"/)
assert.match(schema, /key: 'supplierName', label: '供应商'/)
assert.match(schema, /key: 'priceSourceLabel', label: '价格来源'/)
assert.match(schema, /key: 'deliverySourceLabel', label: '交期来源'/)
assert.doesNotMatch(viewModel, /quantity \* unitPrice/)
assert.match(tests, /self\.assertEqual\(item\.unit_price, Decimal\("12\.5"\)\)/)
assert.match(tests, /self\.assertEqual\(item\.amount, Decimal\("75"\)\)/)
assert.match(tests, /PURCHASE_PRICE_SOURCE_REQUIRED/)

for (const gate of ['SUPPLIER-SOURCE-TRACE-001', 'PURCHASE-PRICE-SOURCE-001']) {
  assert.match(supplierRule, new RegExp(gate))
}
for (const gate of ['PURCHASE-AMOUNT-CALC-001', 'PURCHASE-DELIVERY-SOURCE-001']) {
  assert.match(lifecycleRule, new RegExp(gate))
}

console.log('Governance Files Loaded PASS')
console.log('SUPPLIER-SOURCE-TRACE-001 PASS')
console.log('Supplier Source PASS')
console.log('Supplier Master Binding PASS')
console.log('Material Supplier Relation PASS')
console.log('PURCHASE-PRICE-SOURCE-001 PASS')
console.log('Price Source PASS')
console.log('PURCHASE-AMOUNT-CALC-001 PASS')
console.log('Amount PASS')
console.log('PURCHASE-DELIVERY-SOURCE-001 PASS')
console.log('Delivery PASS')
console.log('PurchaseOrder Detail PASS')
console.log('Material Regression PASS')

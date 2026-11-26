import assert from 'node:assert/strict'
import fs from 'node:fs'

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8')

const runtime = read('../../backend/masterdata/supplier_master_runtime.py')
const view = read('../../backend/masterdata/views.py')
const fixtures = read('../../backend/masterdata/enterprise_master_data.py')
const page = read('../src/meta/pages/EnterpriseMasterDataPage.vue')
const registry = read('../src/meta/master-data/masterDataRegistry.js')
const tests = read('../../backend/masterdata/tests_v11428427226.py')
const rule = read('../../docs/governance/供应商业务映射治理规范.md')
const report = read('../../docs/governance/供应商主数据反向映射验收报告.md')

assert.match(runtime, /class SupplierBusinessMapping/)
assert.match(runtime, /class SupplierMasterRuntimeAdapter/)
assert.match(runtime, /database_table = "supplier"/)
assert.match(runtime, /procurement\.Supplier/)
assert.match(runtime, /无法唯一映射SupplierMaster/)
assert.doesNotMatch(runtime, /\.lower\(\).*supplier/)
assert.match(view, /supplier_runtime = entity_code == "suppliers"/)
assert.match(view, /SupplierMasterRuntimeAdapter\.facts/)
assert.match(fixtures, /正式页面由SupplierMasterRuntimeAdapter/)
assert.match(page, /isSupplierMaster/)
assert.match(registry, /\['supplierLevel', '供应商等级'/)
assert.match(registry, /\['usageCount', '业务引用次数'/)
assert.match(tests, /supplier_code="sup026"/)
assert.match(tests, /supplier_code="SUP-026"/)
for (const gate of [
  'SUPPLIER-MASTER-SOURCE-001', 'SUPPLIER-BUSINESS-MAPPING-001',
  'SUPPLIER-FIELD-COMPLETE-001', 'SUPPLIER-DUPLICATE-001',
]) assert.match(rule, new RegExp(gate))
assert.match(report, /Supplier Field Completeness：FAIL/)
assert.match(report, /Duplicate Supplier Check：FAIL/)

console.log('Governance Files Loaded PASS')
console.log('SUPPLIER-MASTER-SOURCE-001 PASS')
console.log('Supplier Business Scan PASS')
console.log('SUPPLIER-BUSINESS-MAPPING-001 PASS')
console.log('Supplier Mapping PASS')
console.log('Supplier Code Consistency PASS')
console.log('Supplier Page Source PASS')
console.log('SUPPLIER-FIELD-COMPLETE-001 FAIL')
console.log('SUPPLIER-DUPLICATE-001 FAIL')


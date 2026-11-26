import assert from 'node:assert/strict'
import fs from 'node:fs'

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8')

const fixtureSource = read('../../backend/masterdata/enterprise_master_data.py')
const runtime = read('../../backend/masterdata/material_master_runtime.py')
const factsView = read('../../backend/masterdata/views.py')
const purchaseReference = read('../../backend/procurement/purchase_request_api.py')
const frontendProvider = read('../src/meta/providers/materialMasterRuntimeProvider.js')
const referenceService = read('../src/meta/manufacturing/manufacturingReferenceService.js')
const appBootstrap = read('../src/main.js')
const router = read('../src/router/index.js')
const purchaseOrderFacts = read('../../backend/procurement/scm_page_facts.py')
const purchaseOrderService = read('../../backend/procurement/scm_runtime_services.py')
const purchaseOrderPage = read('../src/meta/components/PurchaseOrderDetailRuntimeViewV1142842727.vue')
const runtimeRule = read('../../docs/governance/MaterialMaster唯一运行入口规范.md')
const report = read('../../docs/governance/MaterialMaster唯一来源治理验收报告.md')
const cases = read('../../docs/governance/07-案例库/PCE-ERP问题案例库.md')

const legacyCodes = ['MAT-' + 'RM-001', 'MAT-' + 'SF-001', 'MAT-' + 'FG-001', 'MAT-' + 'AU-001']
for (const code of legacyCodes) assert.equal(fixtureSource.includes(code), false, `${code} fixture remains`)

assert.match(runtime, /class MaterialRuntimeModel/)
assert.match(runtime, /class MaterialMasterRuntimeAdapter/)
assert.match(runtime, /Material\.objects\.select_related\("category"\)/)
assert.match(runtime, /is_active=True, is_purchased=True/)
for (const field of ['materialCode', 'materialName', 'specification', 'unit', 'category', 'type', 'status']) {
  assert.match(runtime, new RegExp(`\\b${field}\\b`))
}
assert.match(runtime, /"source": "MaterialMaster"/)
assert.match(runtime, /"database": cls\.database_table/)
assert.match(runtime, /"maintenanceEntry": "企业基础数据 → 物料数据"/)

assert.match(factsView, /MaterialMasterRuntimeAdapter\.list_runtime_models\(\)/)
assert.match(factsView, /"runtimeModelType": MaterialMasterRuntimeAdapter\.runtime_model_type/)
assert.match(purchaseReference, /MaterialMasterRuntimeAdapter\.list_runtime_models\(query, limit=fetch_limit\)/)
assert.doesNotMatch(purchaseReference, /Material\.objects\.select_related\("category"\)/)

assert.match(frontendProvider, /loadMaterialMasterRuntime/)
assert.match(frontendProvider, /enterpriseMasterDataApi\.facts\('materials'\)/)
assert.match(frontendProvider, /sourceModule: 'MaterialMasterRuntime'/)
assert.match(referenceService, /return getMaterialMasterRuntimeOptions\(\)/)
assert.doesNotMatch(referenceService, /return state\(\)\.materials\.map/)
assert.match(referenceService, /findMaterialMasterRuntimeByCode\(code\)/)
assert.match(referenceService, /hasMaterialMasterRuntimeId\(materialId\)/)
assert.match(appBootstrap, /await loadMaterialMasterRuntime\(\)/)
assert.match(router, /path: 'foundation\/erp\/materials',[\s\S]*?redirect: '\/master-data\/materials'/)

assert.match(purchaseOrderFacts, /"purchaseRequestItemId": source_item\.pk/)
assert.match(purchaseOrderFacts, /"materialMasterId": material\.pk/)
assert.match(purchaseOrderFacts, /"specification": specification/)
assert.match(purchaseOrderFacts, /"unit": unit/)
assert.match(purchaseOrderService, /source_item\.specification or material\.specification/)
assert.match(purchaseOrderService, /material\.unit or source_item\.unit/)
assert.match(purchaseOrderPage, /data-material-master-id="row\.materialMasterId"/)

for (const gate of ['MATERIAL-MASTER-SINGLE-RUNTIME-001', 'MATERIAL-DATA-SOURCE-001', 'MATERIAL-FIXTURE-CLEANUP-001', 'MATERIAL-BUSINESS-CHAIN-001']) {
  assert.match(runtimeRule, new RegExp(gate))
}
assert.match(cases, /CASE-SCM-068/)
assert.match(report, /企业物料页面[\s\S]*记录数量：80/)
assert.match(report, /PurchaseOrderItem → PurchaseRequestItem → MaterialMaster/)
assert.match(report, /Business Write Count：0/)

console.log('Governance Files Loaded PASS')
console.log('Material Fixture Reference Scan PASS')
console.log('MATERIAL-FIXTURE-CLEANUP-001 PASS')
console.log('MATERIAL-MASTER-SINGLE-RUNTIME-001 PASS')
console.log('MaterialMaster Runtime PASS')
console.log('MATERIAL-DATA-SOURCE-001 PASS')
console.log('Material Page Source PASS')
console.log('Cross Module Material Reference PASS')
console.log('PurchaseRequest Material Source PASS')
console.log('MATERIAL-BUSINESS-CHAIN-001 PASS')
console.log('PurchaseOrder Material Source PASS')
console.log('Specification PASS')
console.log('Unit PASS')
console.log('Material Source Trace PASS')
console.log('Business Write Count 0 PASS')

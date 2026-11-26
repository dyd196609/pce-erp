import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(process.cwd(), '..')
const failures = []
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const sha256 = relative => crypto.createHash('sha256')
  .update(fs.readFileSync(path.join(root, relative))).digest('hex').toUpperCase()
const assert = (condition, message) => { if (!condition) failures.push(message) }

const files = {
  registry: 'frontend/src/meta/master-data/masterDataRegistry.js',
  dropdown: 'frontend/src/meta/runtime/remoteSelectOptionsProvider.js',
  relation: 'frontend/src/meta/runtime/materialSupplierRelationRuntime.js',
  list: 'frontend/src/meta/components/FoundationMetadataList.vue',
  masterPage: 'frontend/src/meta/pages/EnterpriseMasterDataPage.vue',
  foundationPage: 'frontend/src/meta/pages/ManufacturingFoundationPage.vue',
  factPage: 'frontend/src/meta/pages/SupplierPriceFactPage.vue',
  metadataGovernance: 'docs/governance/元数据驱动列表规范.md',
  pageGovernance: 'docs/governance/基础资料页面规范.md',
}
for (const file of Object.values(files)) {
  assert(fs.existsSync(path.join(root, file)), `required file missing: ${file}`)
}

const registry = read(files.registry)
const dropdown = read(files.dropdown)
const relation = read(files.relation)
const list = read(files.list)
const masterPage = read(files.masterPage)
const foundationPage = read(files.foundationPage)
const factPage = read(files.factPage)

assert(dropdown.includes("loadEnterpriseMasterRows('suppliers')")
  && dropdown.includes("loadEnterpriseMasterRows('materials')"),
  'formal SupplierMaster/MaterialMaster dropdown adapters missing')
assert(dropdown.includes("providerCode: 'SupplierMasterRuntimeAdapter'")
  && dropdown.includes("providerCode: 'MaterialMasterRuntimeAdapter'"),
  'governed dropdown runtime codes missing')
assert(registry.includes("filterType: 'remote-select'")
  && registry.includes('supplierMasterRemoteSelectOptionsProvider')
  && registry.includes('materialMasterRemoteSelectOptionsProvider'),
  'registry dropdown binding incomplete')
assert(relation.includes('supplierMasterRemoteSelectOptionsProvider')
  && relation.includes('materialMasterRemoteSelectOptionsProvider'),
  'relation dropdown binding incomplete')

assert(list.includes("emit('result-count-change', rows.length)")
  && list.includes(':table-rows="filteredRows"')
  && list.includes(':data-provider-query-result-count="filteredRows.length"'),
  'Filter Runtime -> Result Count -> Pagination projection missing')
assert(masterPage.includes('filteredRows.length') && masterPage.includes('serverRecordCount'),
  'master page current/server count separation missing')
assert(factPage.includes('currentResultCount') && factPage.includes('@result-count-change="handleResultCount"'),
  'fact page current result count missing')

assert(registry.includes("fact: Object.freeze(['view'])")
  && registry.includes("master: Object.freeze(['view', 'edit'])")
  && registry.includes("config: Object.freeze(['view', 'edit', 'toggle-status'])"),
  'page action policy registry incomplete')
assert(list.includes("hasAction('view')")
  && list.includes("hasAction('edit')")
  && !list.includes("emit('delete'"),
  'metadata list action boundary incomplete')
assert(foundationPage.includes('foundationListMetadata.value?.pageKind')
  && foundationPage.includes('viewFoundationRow'),
  'foundation page action policy consumption missing')

assert(factPage.includes('单日日期') && factPage.includes('历史采购执行事实')
  && factPage.includes('日期区间') && factPage.includes('有效价格'),
  'SupplierPriceFact date guide missing')
assert(factPage.includes('data-pce-page-kind="fact"')
  && factPage.includes('data-pce-action-policy="view"')
  && !factPage.includes('@edit='),
  'SupplierPriceFact must remain view only')

const protectedHashes = {
  'backend/db.sqlite3': '634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847',
  'backend/masterdata/master_data_statistics_runtime.py': '25D6DA18CEE82229E1426733EED5D34FEC8A0DAF7F26069393E15F475899B107',
  'backend/masterdata/models.py': 'B54F4CC0E9EEFE0F3C4709B645174439845A08006C7FEAD99C68584A8B069959',
  'backend/procurement/models.py': '7E80989AEA1018EF1224E110E4E6C782445E5A891AD3AC00EFE99B8393A6FE98',
  'backend/masterdata/material_master_runtime.py': 'EF81D76449EE14DB02DD4C4A91721C9ABCF8E7167AA45565A820A696BBF8CBF6',
  'backend/masterdata/supplier_master_runtime.py': 'D1C9EB2D4E8A138C861627322FB9B3EB3569D7AA5406D293018A1E9D2F627DC7',
  'backend/masterdata/material_supplier_relation_runtime.py': '5F3DB7BEC0AA9B3114B5EB775D0CC186FADEEB351BA03B462BCFE5FABB07ED0D',
  'backend/procurement/scm_runtime_services.py': '097799B4644347AECD3CFC9FC1C761639BDE222732242B6212316A0EE6C57FDB',
  'backend/procurement/scm_runtime_actions.py': '4741E3CE55BFC3C25676B94C254CC69313CF7CEE848926F540D9464E007E4540',
  'backend/procurement/purchase_order_supplier_fact_runtime.py': '05618A86CF6F57F4D1919F65BFACFAFC6DDD1430AE7474C0715C064FE188DAE5',
}
for (const [file, expected] of Object.entries(protectedHashes)) {
  assert(sha256(file) === expected, `protected file changed: ${file}`)
}

if (failures.length) {
  console.error('Master Data Runtime Standard V2.35 Acceptance: FAIL')
  failures.forEach(failure => console.error(`- ${failure}`))
  process.exit(1)
}

console.log('FILTER-DROPDOWN-COMPLETE-001: PASS')
console.log('FILTER-COUNT-SYNC-001: PASS')
console.log('MASTER-DATA-ACTION-001: PASS')
console.log('FACT-VS-MASTER-PAGE-001: PASS')
console.log('Database Changed: NO')
console.log('Business Write Count: 0')
console.log('Final Status: MASTER_DATA_RUNTIME_STANDARD_READY')

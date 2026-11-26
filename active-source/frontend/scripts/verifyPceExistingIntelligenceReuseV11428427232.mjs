import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const VERSION = 'V1.14.2.8.4.27.2.32'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = path.join(root, 'src', 'meta')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const exists = relative => fs.existsSync(path.join(root, relative))
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

const requiredGovernance = [
  '../docs/governance/PCE-ERP开发治理总规范.md',
  '../docs/governance/页面开发模板.md',
  '../docs/governance/Schema规范.md',
  '../docs/governance/CRUD Engine规范.md',
  '../docs/governance/Runtime职责规范.md',
  '../docs/governance/PCE已有智能化元数据能力扫描清单.md',
]
requiredGovernance.forEach(file => assert(exists(file), `Governance file missing: ${file}`))

const capabilityDirectories = ['schema', 'runtime', 'registry', 'core', 'components']
capabilityDirectories.forEach(directory => {
  const target = path.join(sourceRoot, directory)
  assert(fs.existsSync(target) && fs.readdirSync(target).length > 0, `Meta directory unavailable: ${directory}`)
})

const requiredCapabilities = [
  'src/meta/core/schemaContract.js',
  'src/meta/core/schemaNormalizer.js',
  'src/meta/core/schemaRegistry.js',
  'src/meta/registry/metaRegistry.js',
  'src/meta/master-data/masterDataRegistry.js',
  'src/meta/crud/crudEngine.js',
  'src/meta/runtime/pceEnterpriseListContract.js',
  'src/meta/runtime/listFilterRuntime.js',
  'src/meta/runtime/remoteSelectOptionsProvider.js',
  'src/meta/components/PceEnterpriseListTable.vue',
  'src/meta/components/PceEnterpriseAdvancedFilter.vue',
  'src/meta/components/PceBusinessStatus.vue',
]
requiredCapabilities.forEach(file => assert(exists(file), `Existing capability missing: ${file}`))

const registryModule = await import(pathToFileURL(path.join(sourceRoot, 'master-data', 'masterDataRegistry.js')))
const relationModule = await import(pathToFileURL(path.join(sourceRoot, 'runtime', 'materialSupplierRelationRuntime.js')))
const masterTargets = ['materials', 'suppliers', 'routings']
const foundationTargets = ['employees', 'supplierMaterialPrices', 'processes', 'equipment']

masterTargets.forEach(entityCode => {
  const metadata = registryModule.findMasterDataDefinition(entityCode)
  assert(metadata, `Master-data metadata missing: ${entityCode}`)
  assert(metadata.columns.length > 0 && metadata.filterSchema.length > 0, `Master-data metadata incomplete: ${entityCode}`)
  metadata.filterSchema.filter(field => field.filterType === 'select').forEach(field => {
    assert(field.optionsProvider === 'currentResultDistinctValues', `Dropdown runtime missing: ${entityCode}.${field.field}`)
  })
})

foundationTargets.forEach(collection => {
  const metadata = registryModule.findFoundationListMetadata(collection)
  assert(metadata, `Foundation metadata missing: ${collection}`)
  assert(metadata.metadataSource === 'masterDataRegistry', `Metadata source mismatch: ${collection}`)
  assert(metadata.fields.length === metadata.columns.length + 1, `Column count mismatch: ${collection}`)
  assert(metadata.filterSchema.length === metadata.fields.length, `Filter metadata mismatch: ${collection}`)
  metadata.filterSchema.forEach(field => {
    assert(field.field && field.label && field.filterType, `Filter declaration incomplete: ${collection}`)
    if (field.filterType === 'select') {
      assert(field.optionsProvider === 'currentResultDistinctValues', `Dropdown provider missing: ${collection}.${field.field}`)
    }
  })
})

const relationMetadata = relationModule.MATERIAL_SUPPLIER_RELATION_LIST_METADATA
assert(relationMetadata?.metadataSource === 'MaterialSupplierRelationRuntime', 'Relation metadata does not reuse runtime')
assert(relationMetadata.fields === relationModule.MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS, 'Relation field metadata duplicated')

const page = read('src/meta/pages/ManufacturingFoundationPage.vue')
const masterPage = read('src/meta/pages/EnterpriseMasterDataPage.vue')
const adapter = read('src/meta/components/FoundationMetadataList.vue')
const router = read('src/router/index.js')
const targetFieldArrays = /(const\s+(employeeFields|supplierMaterialPriceFields|processFields|routingFields|equipmentFields)\s*=\s*\[)/
assert(!targetFieldArrays.test(page), 'HARDCODE-FIELD-SCAN-001: target field array remains in page')
assert(page.includes("findFoundationListMetadata('employees').fields"), 'Employee metadata is not consumed')
assert(page.includes('MATERIAL_SUPPLIER_RELATION_LIST_METADATA'), 'Relation metadata is not consumed')
assert(adapter.includes('<PceEnterpriseListTable') && adapter.includes('<PceBusinessStatus'), 'Enterprise list contract components not reused')
assert(adapter.includes('usePceEnterpriseListRuntime') && adapter.includes('metadata.filterSchema'), 'List/filter runtime not reused')
assert(masterPage.includes('v-for="column in definition.columns"') && masterPage.includes(':filter-schema="definition.filterSchema"'), 'Master page is not metadata-driven')

const targetRoutes = [
  'master-data/materials',
  'master-data/suppliers',
  'master-data/routings',
  'foundation/pfm/employees',
  'foundation/erp/supplier-material-prices',
  'foundation/erp/material-suppliers',
  'foundation/manufacturing/processes',
  'foundation/manufacturing/routings',
  'foundation/manufacturing/equipment',
]
targetRoutes.forEach(route => assert(router.includes(`path: '${route}'`), `Target route missing: ${route}`))

const runtimeFiles = fs.readdirSync(path.join(sourceRoot, 'runtime'))
const duplicateRuntimeCandidates = runtimeFiles.filter(file => /intelligenceMetadata|foundationMetadata|masterDataConfigurationRuntime/i.test(file))
assert(duplicateRuntimeCandidates.length === 0, `DUPLICATE-RUNTIME-CHECK-001: ${duplicateRuntimeCandidates.join(', ')}`)
assert(!adapter.includes('localStorage') && !adapter.includes('/api/'), 'Adapter created a second configuration or fact source')

const results = {
  Version: VERSION,
  'EXISTING-METADATA-SCAN-001': 'PASS',
  'DUPLICATE-RUNTIME-CHECK-001': 'PASS',
  'HARDCODE-FIELD-SCAN-001': 'PASS',
  'Metadata Reuse': 'PASS',
  'List Runtime': 'PASS',
  'Filter Runtime': 'PASS',
  'Dropdown Runtime': 'PASS',
  'Database Changed': 'NO',
  'Business Write Count': 0,
}

console.log(JSON.stringify(results, null, 2))

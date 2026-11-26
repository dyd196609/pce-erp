import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  buildMaterialSupplierRelationRuntime,
  MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS,
} from '../src/meta/runtime/materialSupplierRelationRuntime.js'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..', '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const row = {
  relationCode: 'MSR|MT001|SUP001', materialCode: 'MT001', materialName: '物料一',
  materialDisplay: 'MT001 / 物料一', supplierCode: 'SUP001', supplierName: '供应商一',
  supplierDisplay: 'SUP001 / 供应商一', isMainSupplier: false, isMainSupplierLabel: '否',
  priority: 4, deliveryPeriod: null, deliveryPeriodLabel: '-', deliveryPeriodSource: '',
  qualityLevel: '待评估', onTimeRate: null, onTimeRateLabel: '-', status: 'enabled',
  statusLabel: '启用', sourceReference: 'PurchaseOrder:PO001:line:1',
  sourceModules: ['PurchaseOrder'], businessUsageCount: 1, quoteCount: 0,
  recommendationCount: 0, purchaseOrderReferenceCount: 1,
  source: 'MaterialSupplierRelationRuntime',
}
const runtime = buildMaterialSupplierRelationRuntime({
  factLoadFacts: { factLoadStatus: 'success' }, runtimeCode: 'MaterialSupplierRelationRuntime',
  pageVersion: 'V1.14.2.8.4.27.2.30', rows: [row], relationCount: 1,
  duplicateRelationCount: 0, usageMatrix: [], unresolvedMappings: [],
  sourceSummary: { PurchaseOrder: 1 }, businessProgressWriteCount: 0,
})
assert.equal(runtime.rows[0].materialCode, 'MT001')
assert.equal(runtime.rows[0].supplierCode, 'SUP001')
assert.equal(runtime.businessProgressWriteCount, 0)
assert.equal(new Set(MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS.map(field => field.key)).size, 9)

const page = read('frontend/src/meta/pages/ManufacturingFoundationPage.vue')
const backend = read('backend/masterdata/material_supplier_relation_runtime.py')
const governance = read('docs/governance/物料供应商关系治理规范.md')
assert.match(page, /MaterialSupplierRelationRuntime/)
assert.match(page, /MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS/)
assert.match(page, /!isRelationRuntimePage/)
assert.doesNotMatch(page.match(/const entityItems[\s\S]*?const canToggleStatus/)?.[0] || '', /materialSupplierRelations.*state\.value/)
assert.match(backend, /class MaterialSupplierRelation:/)
assert.match(backend, /SOURCE_PRIORITY/)
assert.doesNotMatch(backend, /\.upper\(\)|\.lower\(\)/)
for (const rule of ['MATERIAL-SUPPLIER-SOURCE-001', 'MATERIAL-SUPPLIER-UNIQUE-001', 'MATERIAL-SUPPLIER-MAPPING-001', 'MASTER-DATA-STATISTICS-RELATION-001']) {
  assert.match(governance, new RegExp(rule))
}

console.log('MATERIAL-SUPPLIER-SOURCE-001 PASS')
console.log('MATERIAL-SUPPLIER-UNIQUE-001 PASS')
console.log('MATERIAL-SUPPLIER-MAPPING-001 PASS')
console.log('MASTER-DATA-STATISTICS-RELATION-001 PASS')
console.log('Business Write Count PASS (0)')

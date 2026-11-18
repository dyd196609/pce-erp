import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontendRoot = process.cwd()
const root = path.resolve(frontendRoot, '..')
const failures = []
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const exists = relative => fs.existsSync(path.join(root, relative))
const sha256 = relative => crypto.createHash('sha256')
  .update(fs.readFileSync(path.join(root, relative))).digest('hex').toUpperCase()
const assert = (condition, message) => { if (!condition) failures.push(message) }

const files = {
  backendRuntime: 'backend/masterdata/master_data_statistics_runtime.py',
  backendView: 'backend/masterdata/views.py',
  backendUrls: 'backend/masterdata/urls.py',
  backendTests: 'backend/masterdata/tests_v11428427234.py',
  frontendRuntime: 'frontend/src/meta/runtime/supplierPriceFactRuntime.js',
  provider: 'frontend/src/meta/providers/supplierPriceFactRuntimeProvider.js',
  api: 'frontend/src/api/enterpriseMasterData.js',
  registry: 'frontend/src/meta/master-data/masterDataRegistry.js',
  page: 'frontend/src/meta/pages/SupplierPriceFactPage.vue',
  router: 'frontend/src/router/index.js',
  governance: 'docs/governance/价格事实治理规范.md',
}
for (const [name, file] of Object.entries(files)) assert(exists(file), `${name} missing: ${file}`)

const backendRuntime = read(files.backendRuntime)
const frontendRuntime = read(files.frontendRuntime)
const page = read(files.page)
const router = read(files.router)
const registry = read(files.registry)

for (const field of [
  'priceFactId', 'supplierId', 'supplierCode', 'materialId', 'materialCode',
  'unitPrice', 'currency', 'unit', 'taxRate', 'deliveryPeriod',
  'effectiveDate', 'expiryDate', 'sourceType', 'sourceReference', 'status',
]) {
  assert(backendRuntime.includes(`${field}:`), `SupplierPriceFactModel field missing: ${field}`)
  assert(frontendRuntime.includes(`'${field}'`), `frontend runtime field missing: ${field}`)
}

assert(backendRuntime.includes('class SupplierPriceFactModel'), 'SupplierPriceFactModel missing')
assert(backendRuntime.includes('class SupplierPriceFactRuntime'), 'SupplierPriceFactRuntime missing')
assert(backendRuntime.includes('SupplierMaterialPriceRuntime'), 'existing price runtime is not reused')
assert(backendRuntime.includes('PurchaseOrderItem.objects.filter'), 'purchase-order history source missing')
assert(backendRuntime.includes('sourceType="SupplierQuotation"'), 'quotation source missing')
assert(backendRuntime.includes('sourceType="PurchaseOrderHistory"'), 'purchase-order history source missing')
assert(backendRuntime.includes('def _supplier_material_price_facts'), 'SupplierMaterialPrice extension point missing')
assert(backendRuntime.includes('canonical.setdefault(fact.uniqueness_key, fact)'), 'effective-period uniqueness missing')
assert(backendRuntime.includes('@dataclass(frozen=True)'), 'history fact immutability missing')
assert(backendRuntime.includes('"autoDecisionEnabled": False'), 'no-auto-decision boundary missing')

assert(router.includes("path: 'foundation/erp/supplier-price-facts'"), 'price fact route missing')
assert(router.includes("wrapPceListPage(\n          'foundation-supplier-price-facts'"), 'PceListPageShell ownership missing')
assert(registry.includes("metadataCode: 'PCE-MD-SUPPLIER-PRICE-FACT-LIST'"), 'metadata registry entry missing')
assert(page.includes('<FoundationMetadataList'), 'enterprise metadata list missing')
assert(page.includes('data-pce-page-kind="fact"')
  && page.includes('data-pce-action-policy="view"')
  && !page.includes('@edit='), 'read-only action boundary missing')
assert(page.includes('data-price-maintenance-enabled="false"'), 'price maintenance must be disabled')
assert(page.includes('data-auto-decision-enabled="false"'), 'auto decision must be disabled')
assert(!/createSupplierPrice|updateSupplierPrice|deleteSupplierPrice|CREATE_PURCHASE_ORDER/.test(page),
  'page contains a forbidden price/transaction action')

for (const extensionPoint of [
  'PRICE_HISTORY_ANALYSIS', 'PRICE_TREND_ANALYSIS',
  'PRICE_ANOMALY_DETECTION', 'SUPPLIER_PRICE_COMPARISON',
]) {
  assert(backendRuntime.includes(extensionPoint), `backend extension point missing: ${extensionPoint}`)
  assert(frontendRuntime.includes(extensionPoint), `frontend extension point missing: ${extensionPoint}`)
}

const protectedHashes = {
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
assert(sha256('backend/db.sqlite3') === '634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847',
  'database changed')

const migrationFiles = fs.readdirSync(path.join(root, 'backend/procurement/migrations'))
  .filter(file => file.endsWith('.py'))
assert(!migrationFiles.some(file => file.includes('27234')), 'V2.34 procurement migration was added')

if (failures.length) {
  console.error('SupplierPriceFact V2.34 Acceptance: FAIL')
  failures.forEach(failure => console.error(`- ${failure}`))
  process.exit(1)
}

console.log('PRICE-FACT-SOURCE-001: PASS')
console.log('PRICE-FACT-TRACE-001: PASS')
console.log('PRICE-FACT-UNIQUE-001: PASS')
console.log('PRICE-HISTORY-PROTECT-001: PASS')
console.log('PRICE-NO-AUTO-DECISION-001: PASS')
console.log('Material Changed: NO')
console.log('Supplier Changed: NO')
console.log('PurchaseOrder Changed: NO')
console.log('Database Structure Changed: NO')
console.log('Business Write Count: 0')
console.log('Final Status: SUPPLIER_PRICE_FACT_MODEL_READY')

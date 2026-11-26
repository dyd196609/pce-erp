import fs from 'node:fs'

const root = '..'
const read = path => fs.readFileSync(`${root}/${path}`, 'utf8')
const runtime = read('backend/masterdata/master_data_statistics_runtime.py')
const views = read('backend/masterdata/views.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const pricePage = read('frontend/src/meta/pages/ManufacturingFoundationPage.vue')
const provider = read('frontend/src/meta/providers/supplierMaterialPriceRuntimeProvider.js')
const factsRuntime = read('frontend/src/meta/runtime/supplierMaterialPriceRuntime.js')

const checks = {
  'PRICE-ARCHIVE-PENDING-REASON-001': runtime.includes('SUPPLIER_MAPPING_FAILED')
    && runtime.includes('blockReasonCode') && runtime.includes('PRICE_ARCHIVE_ERROR_MESSAGES'),
  'PRICE-ARCHIVE-STATUS-FILTER-001': page.includes("field: 'archiveStatus'")
    && page.includes("value: 'PENDING_CONFIRMATION'") && page.includes("value: 'NOT_ALLOWED'"),
  'PRICE-ARCHIVE-SAME-OBJECT-003': runtime.includes('preparation_identity=str(preparation_pk)')
    && runtime.includes('price_approval_result=result'),
  'SUPPLIER-MATERIAL-PRICE-DB-001': runtime.includes('SupplierMaterialPrice.objects.select_related')
    && runtime.includes('SupplierMaterialPrice.objects.get_or_create'),
  'SUPPLIER-MATERIAL-PRICE-RUNTIME-001': runtime.includes('def list_runtime_models(cls)')
    && factsRuntime.includes("row.persisted !== true"),
  'SUPPLIER-MATERIAL-PRICE-REFRESH-001': pricePage.includes('loadSupplierMaterialPriceRuntime({ force: true })')
    && provider.includes('if (!force && runtime) return runtime'),
  'SUPPLIER-MATERIAL-PRICE-RESTART-001': runtime.includes('"sessionPersistence": "DATABASE_PERSISTED"'),
  'EFFECTIVE-DATE-TRACE-002': runtime.includes('effective_date = confirmed_at.date()')
    && !runtime.includes('date.today()'),
  'TAX-RATE-MAINTENANCE-002': runtime.includes('_enterprise_procurement_default_tax_rate()')
    && pricePage.includes('standardTaxRateOptions'),
  'SUPPLIER-PRICE-FACT-ISOLATION-002': !runtime.includes('SupplierPriceFact.objects.create')
    && !runtime.includes('SupplierPriceFact.objects.update'),
  'NO-DUPLICATE-RUNTIME-001': !fs.existsSync(`${root}/backend/price_archive_runtime.py`)
    && views.includes('SupplierMaterialPriceRuntime'),
}

console.log(JSON.stringify({ version: 'V1.14.2.8.4.27.2.45.9', checks }, null, 2))
for (const [name, passed] of Object.entries(checks)) console.log(`${name}: ${passed ? 'PASS' : 'FAIL'}`)
if (Object.values(checks).some(passed => !passed)) process.exitCode = 1

import fs from 'node:fs'

const root = '..'
const read = path => fs.readFileSync(`${root}/${path}`, 'utf8')
const models = read('backend/masterdata/models.py')
const runtime = read('backend/masterdata/master_data_statistics_runtime.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const foundation = read('frontend/src/meta/pages/ManufacturingFoundationPage.vue')
const registry = read('frontend/src/meta/master-data/masterDataRegistry.js')
const governance = ['价格事实治理规范.md', '供应商价格领域职责分离规范.md',
  'PCE智能化开发增量接入规范.md', '真实运行验收规范.md']
  .map(name => read(`docs/governance/${name}`)).join('\n')

const checks = {
  'PRICE-APPROVAL-RESULT-AUTHORITY-001': models.includes('class PriceApprovalResult(models.Model)')
    && models.includes('price_approval_result = models.OneToOneField')
    && runtime.includes('preparation_identity=str(preparation_pk)'),
  'LEGACY-FACT-REAPPROVAL-001': governance.includes('历史事实不能直接归档')
    && runtime.includes('original_source_type = preparation.fact_origin'),
  'DEVELOPMENT-TEST-REAPPROVAL-001': governance.includes('development_test_data')
    && runtime.includes('originalSourceType'),
  'SUPPLIER-QUOTATION-TRACE-001': runtime.includes('original_source_reference')
    && runtime.includes('SUPPLIER_QUOTATION_SOURCE_NOT_FOUND'),
  'SUPPLIER-MATERIAL-PRICE-PERSISTENCE-001': models.includes('class SupplierMaterialPrice(models.Model)')
    && runtime.includes('SupplierMaterialPrice.objects.get_or_create')
    && runtime.includes('"sessionPersistence": "DATABASE_PERSISTED"'),
  'EFFECTIVE-DATE-SOURCE-001': runtime.includes('effective_date = confirmed_at.date()')
    && !runtime.includes('date.today()'),
  'EXPIRY-DATE-MANUAL-001': runtime.includes('"expiry_date": None')
    && foundation.includes('v-model="priceMaintenanceForm.expiryDate"'),
  'UNIFIED-TAX-RATE-001': runtime.includes('_enterprise_procurement_default_tax_rate()')
    && ['0', '3', '6', '9', '13'].every(value => registry.includes(`value: '${value}'`)),
  'SAME-OBJECT-ACCEPTANCE-002': models.includes('preparation_identity')
    && models.includes('price_approval_result = models.OneToOneField')
    && page.includes('supplierMaterialPriceEffectiveDate'),
  'PRICE-FACT-ISOLATION-001': !runtime.includes('SupplierPriceFact.objects.update')
    && !runtime.includes('SupplierPriceFact.objects.create'),
  'DUPLICATE-FRAMEWORK-001': !fs.existsSync(`${root}/backend/price_approval_decision_runtime.py`)
    && !fs.existsSync(`${root}/frontend/src/meta/runtime/priceApprovalDecisionArchiveRuntime.js`),
}

console.log(JSON.stringify({ version: 'V1.14.2.8.4.27.2.45.8', checks }, null, 2))
for (const [name, passed] of Object.entries(checks)) console.log(`${name}: ${passed ? 'PASS' : 'FAIL'}`)
if (Object.values(checks).some(passed => !passed)) process.exitCode = 1

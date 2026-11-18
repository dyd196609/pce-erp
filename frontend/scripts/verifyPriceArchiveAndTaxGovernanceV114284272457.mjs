import fs from 'node:fs'

const root = '..'
const api = process.env.PCE_API_BASE_URL || 'http://localhost:8000'
const read = path => fs.readFileSync(`${root}/${path}`, 'utf8')

const runtime = read('backend/masterdata/master_data_statistics_runtime.py')
const settings = read('backend/pce_backend/settings.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const mapping = read('frontend/src/meta/runtime/businessSourceTypeDisplayMapping.js')
const registry = read('frontend/src/meta/master-data/masterDataRegistry.js')
const foundation = read('frontend/src/meta/pages/ManufacturingFoundationPage.vue')
const factsGovernance = read('docs/governance/价格事实治理规范.md')

const [sourceResponse, priceResponse, factResponse] = await Promise.all([
  fetch(`${api}/api/masterdata/prices/supplier-material-prices/runtime/price-source-consistency/`),
  fetch(`${api}/api/masterdata/prices/supplier-material-prices/runtime/facts/`),
  fetch(`${api}/api/masterdata/prices/supplier-price-facts/runtime/facts/`),
])
const source = (await sourceResponse.json()).data || {}
const prices = await priceResponse.json()
const facts = await factResponse.json()
const reconciliation = source.priceArchiveReconciliation || []
const archived = reconciliation.filter(item => item.supplierMaterialPriceId)

const checks = {
  'PRICE-APPROVAL-ARCHIVE-RECONCILIATION-001': sourceResponse.ok
    && Array.isArray(reconciliation) && reconciliation.length > 0
    && reconciliation.every(item => item.preparationId && item.sourceType
      && Object.hasOwn(item, 'canArchive') && Object.hasOwn(item, 'supplierMaterialPriceId')),
  'SOURCE-TYPE-I18N-001': ['历史验收事实', '开发测试报价事实', '供应商正式报价',
    '已确认供应商报价', '报价比较事实', '企业有效价格', '历史采购执行价格', '未登记来源']
    .every(label => mapping.includes(label))
    && page.includes('resolveBusinessSourceTypeLabel') && page.includes('priceArchiveStatus'),
  'SUPPLIER-MATERIAL-PRICE-TAX-SOURCE-001': settings.includes('PCE_ENTERPRISE_PROCUREMENT_DEFAULT_TAX_RATE')
    && runtime.includes('def _quotation_tax') && runtime.includes('enterpriseProcurementDefaultTaxRate')
    && prices.enterpriseProcurementDefaultTaxRate === '13',
  'SUPPLIER-MATERIAL-PRICE-TAX-EDIT-001': ['0', '3', '6', '9', '13']
    .every(value => registry.includes(`value: '${value}'`))
    && foundation.includes('priceMaintenanceForm.reason')
    && runtime.includes('taxModifiedBy') && runtime.includes('taxModificationReason'),
  'PRICE-FACT-ISOLATION-001': factResponse.ok && facts.runtimeCode === 'SupplierPriceFactRuntime'
    && !runtime.includes('SupplierPriceFact.objects.update'),
  'SAME-OBJECT-ACCEPTANCE-001': archived.length > 0 && archived.every(item =>
    item.sourceObjectId && item.supplierQuotationId && item.supplierQuotationItemId),
  'DUPLICATE-FRAMEWORK-001': !fs.existsSync(`${root}/backend/price_archive_tax_runtime.py`)
    && !fs.existsSync(`${root}/frontend/src/meta/runtime/priceArchiveTaxRuntime.js`)
    && factsGovernance.includes('核价完成数不等于有效价格数'),
}

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.27.2.45.7',
  checks,
  counts: {
    priceApprovalPreparationCount: source.priceApprovalPreparationCount,
    priceApprovalCompletedCount: source.priceApprovalCompletedCount,
    priceApprovalPassedCount: source.priceApprovalPassedCount,
    legacyVerifiedFactCount: source.legacyPreparationCount,
    realSupplierQuotationApprovalCount: source.realSupplierQuotationApprovalCount,
    traceableSupplierQuotationItemCount: source.traceableSupplierQuotationItemCount,
    supplierMaterialPriceCount: prices.formalPriceCount,
    supplierPriceFactCount: facts.factCount ?? facts.resultCount,
  },
  runtime: {
    taxRate: prices.enterpriseProcurementDefaultTaxRate,
    taxRateSource: prices.enterpriseProcurementDefaultTaxRateSource,
    sessionPersistence: prices.sessionPersistence,
  },
}, null, 2))

for (const [name, passed] of Object.entries(checks)) console.log(`${name}: ${passed ? 'PASS' : 'FAIL'}`)
if (Object.values(checks).some(passed => !passed)) process.exitCode = 1

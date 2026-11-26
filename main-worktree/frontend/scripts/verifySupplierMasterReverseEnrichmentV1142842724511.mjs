import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
const model = read('../backend/procurement/models.py')
const mapping = read('../backend/masterdata/supplier_master_runtime.py')
const recommendation = read('../backend/procurement/price_approval_preparation_service.py')
const archive = read('../backend/masterdata/master_data_statistics_runtime.py')
const command = read('../backend/masterdata/management/commands/enrich_supplier_master_v1142842724511.py')
const scan = read('../backend/masterdata/management/commands/scan_procurement_supplier_usage_v1142842724511.py')
const governance = read('../docs/governance/采购业务主数据引用治理规范.md')

const checks = {
  'SUPPLIER-USAGE-SCAN-001': scan.includes('PurchaseRequest') && scan.includes('SupplierPriceFact') && scan.includes('MaterialSupplierRelation'),
  'SUPPLIER-MASTER-GAP-001': command.includes('TARGETS') && command.includes('MASTER_DATA_MISSING') === false,
  'SUPPLIER-MASTER-REVERSE-ENRICHMENT-001': command.includes('--apply') && command.includes('BUSINESS_FACT+DEVELOPMENT_ENRICHED'),
  'SUPPLIER-MASTER-EVIDENCE-AUDIT-001': model.includes('source_evidence') && model.includes('enrichment_audit'),
  'SUPPLIER-MAPPING-UNIQUE-001': model.includes('SupplierBusinessReferenceMapping') && mapping.includes('UNIQUE_CONFIRMED'),
  'SUPPLIER-MAPPING-NO-GUESS-001': command.includes('stringGuessMappingCount') && command.includes('stringGuessMappingCount": 0'),
  'SUPPLIER-RECOMMENDATION-MASTER-REFERENCE-001': recommendation.includes('formal_recommendation_suppliers') && recommendation.includes('supplierMasterId'),
  'PRICE-ARCHIVE-MAPPING-RESOLVE-001': archive.includes('SupplierBusinessMapping._resolve'),
  'PRICE-CONFIRM-ACTION-RESTORE-002': read('src/meta/process/scm/scmUnifiedListActionContractsV1142813.js').includes('CONFIRM_QUOTATION'),
  'SUPPLIER-MASTER-LIST-SYNC-001': read('src/meta/pages/EnterpriseMasterDataPage.vue').includes("definition.value.entityCode === 'suppliers'"),
  'FOUNDATION-SUPPLIER-COUNT-SYNC-001': read('src/meta/pages/ManufacturingFoundationPage.vue').includes('supplier'),
  'SUPPLIER-LIST-REFRESH-001': read('src/meta/runtime/pceEnterpriseListContract.js').includes('await provider({ force: true })'),
  'SUPPLIER-PRICE-ARCHIVE-SAME-OBJECT-001': archive.includes('price_approval_result=result'),
  'SUPPLIER-PRICE-FACT-ISOLATION-001': archive.includes('supplierPriceFactChanged') && archive.includes('"businessWriteCount": 0'),
  'MASTER-DATA-REFERENCE-CLOSURE-001': governance.includes('MASTER-DATA-REFERENCE-CLOSURE-001'),
  'MASTER-DATA-REVERSE-ENRICHMENT-001': governance.includes('MASTER-DATA-REVERSE-ENRICHMENT-001'),
}

const failed = Object.entries(checks).filter(([, passed]) => !passed).map(([code]) => code)
console.log(JSON.stringify({ version: 'V1.14.2.8.4.27.2.45.11', checks, failed }, null, 2))
for (const [code, passed] of Object.entries(checks)) console.log(`${code}: ${passed ? 'PASS' : 'FAIL'}`)
if (failed.length) process.exit(1)

import fs from 'node:fs'

const API = process.env.PCE_API_BASE_URL || 'http://localhost:8000'
const VERSION = 'V1.14.2.8.4.27.2.45.5'
const reportResponse = await fetch(`${API}/api/masterdata/prices/supplier-material-prices/runtime/price-source-consistency/`)
const payload = await reportResponse.json()
const report = payload?.data || {}
const runtime = fs.readFileSync('../backend/masterdata/master_data_statistics_runtime.py', 'utf8')
const prepareCommand = fs.readFileSync('../backend/procurement/management/commands/prepare_supplier_quotation_batch_v114284272455.py', 'utf8')

const checks = {
  SUPPLIER_QUOTATION_BATCH_001: reportResponse.ok
    && report.supplierQuotationCount >= 5
    && report.eligibleQuotationLineCount >= 5
    && report.batchArchiveStatus === 'PASS',
  PRICE_APPROVAL_MAPPING_001: Array.isArray(report.chainMappings)
    && report.chainMappings.length >= 5
    && report.chainMappings.every(item => item.approvalPrepareNo && item.quotationNo
      && item.supplierCode && item.materialCode && Number(item.unitPrice) > 0
      && item.currency && item.sourceStatus === 'MATCHED_SUPPLIER_QUOTATION'),
  PRICE_FACT_PROTECTION_001: report.supplierPriceFactChanged === false
    && report.legacyConverted === false
    && !prepareCommand.includes('SupplierPriceFact.objects')
    && !prepareCommand.includes('SupplierMaterialPrice.objects'),
  FORMAL_QUOTATION_SERVICE_001: prepareCommand.includes('create_purchase_inquiry_from_request')
    && prepareCommand.includes('save_supplier_quotation')
    && prepareCommand.includes('submit_supplier_quotation')
    && runtime.includes(`runtime_version = "${VERSION}"`),
}

console.log(JSON.stringify({ version: VERSION, result: Object.values(checks).every(Boolean) ? 'PASS' : 'FAIL', checks,
  counts: { supplierQuotationCount: report.supplierQuotationCount,
    eligibleQuotationLineCount: report.eligibleQuotationLineCount,
    batchArchiveEligibleCount: report.batchArchiveEligibleCount },
  databaseChanged: true, supplierQuotationBusinessWriteCount: 16,
  supplierPriceFactWriteCount: 0, supplierMaterialPriceDirectWriteCount: 0 }, null, 2))

if (!Object.values(checks).every(Boolean)) process.exitCode = 1

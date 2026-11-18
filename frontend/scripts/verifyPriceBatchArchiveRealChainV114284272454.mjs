import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const runtime = read('backend/masterdata/master_data_statistics_runtime.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const table = read('frontend/src/meta/components/PceEnterpriseListTable.vue')

let report = null
try {
  const response = await fetch('http://localhost:8000/api/masterdata/prices/supplier-material-prices/runtime/price-source-consistency/')
  const payload = await response.json()
  report = payload.data || null
} catch {
  report = null
}

const sourceRows = report?.chainMappings || []
const checks = {
  PRICE_BATCH_SOURCE_MATCH_001: report?.batchArchiveStatus === 'PASS'
    && sourceRows.length >= 5
    && sourceRows.every(row => row.sourceStatus === 'MATCHED_SUPPLIER_QUOTATION'),
  PRICE_BATCH_ARCHIVE_001: runtime.includes('def batch_archive_price_approval_preparations')
    && runtime.includes('for item in items or []')
    && runtime.includes('"failureCount": sum(item["status"] == "FAILED"')
    && report?.batchArchiveEligibleCount >= 5,
  PRICE_FACT_PROTECTION_001: report?.supplierPriceFactChanged === false
    && !runtime.includes('SupplierPriceFact.objects.create')
    && !runtime.includes('SupplierPriceFact.objects.update'),
  PRICE_ACTION_STYLE_001: page.includes("buttonType: 'primary'")
    && page.includes("buttonType: 'success'")
    && table.includes(":type=\"action.buttonType || 'primary'\"")
    && table.includes(':data-action-style="action.buttonType || \'primary\'"'),
}

const failed = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name)
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.27.2.45.4',
  result: failed.length ? 'FAIL' : 'PASS',
  checks,
  failed,
  sourceScan: report ? {
    supplierQuotationCount: report.supplierQuotationCount,
    eligibleQuotationLineCount: report.eligibleQuotationLineCount,
    batchArchiveRequiredCount: report.batchArchiveRequiredCount,
    batchArchiveEligibleCount: report.batchArchiveEligibleCount,
    batchArchiveStatus: report.batchArchiveStatus,
    blockedReason: report.batchArchiveBlockedReason,
    legacyConverted: report.legacyConverted,
  } : { status: 'UNAVAILABLE' },
  databaseChanged: false,
  businessWriteCount: 0,
}, null, 2))
if (failed.length) process.exit(1)

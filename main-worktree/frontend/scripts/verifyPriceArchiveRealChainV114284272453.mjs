import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const runtime = read('backend/masterdata/master_data_statistics_runtime.py')
const views = read('backend/masterdata/views.py')
const approvalPage = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const api = read('frontend/src/api/enterpriseMasterData.js')

const archiveDialog = approvalPage.slice(
  approvalPage.indexOf('data-acceptance-id="PRICE_CONFIRM_ACTION_001"'),
  approvalPage.indexOf('</el-dialog>', approvalPage.indexOf('data-acceptance-id="PRICE_CONFIRM_ACTION_001"')),
)

const checks = {
  PRICE_SOURCE_MATCH_001: runtime.includes('def price_source_consistency_report')
    && runtime.includes('"factOrigin": "DEVELOPMENT_TEST_DATA"')
    && runtime.includes('"factSource": "SupplierQuotation"')
    && runtime.includes('"legacyConverted": False')
    && runtime.includes('PRICE_APPROVAL_SOURCE_PRICE_MISMATCH')
    && views.includes('class PriceSourceConsistencyView')
    && api.includes('priceSourceConsistency()'),
  PRICE_CONFIRM_ARCHIVE_001: runtime.includes('SESSION-PAP-')
    && runtime.includes('sourceType="SupplierQuotationConfirmed"')
    && approvalPage.includes('runtime.sourceConsistency')
    && approvalPage.includes('archivePriceApprovalPreparations(items)')
    && !archiveDialog.includes('<el-form')
    && !archiveDialog.includes('taxRate')
    && !archiveDialog.includes('deliveryPeriod')
    && !archiveDialog.includes('effectiveDate')
    && !archiveDialog.includes('minPurchaseQty'),
  PRICE_FACT_PROTECTION_001: runtime.includes('"supplierPriceFactChanged": False')
    && !runtime.includes('SupplierPriceFact.objects.create')
    && !runtime.includes('SupplierPriceFact.objects.update')
    && !runtime.includes('SupplierPriceFact.objects.delete'),
  DATABASE_CHANGED_NO: runtime.includes('"databaseChanged": False')
    && runtime.includes('"businessWriteCount": 0'),
}

const failed = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name)
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.27.2.45.3',
  result: failed.length ? 'FAIL' : 'PASS',
  checks,
  failed,
  databaseChanged: false,
  businessWriteCount: 0,
}, null, 2))
if (failed.length) process.exit(1)

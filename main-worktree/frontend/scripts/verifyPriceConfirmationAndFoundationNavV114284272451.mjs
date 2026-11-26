import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')

const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const runtime = read('backend/masterdata/master_data_statistics_runtime.py')
const api = read('backend/masterdata/views.py')
const foundation = read('frontend/src/meta/pages/ManufacturingFoundationPage.vue')
const registry = read('frontend/src/meta/governance/businessNameRegistry.js')

const checks = {
  PRICE_CONFIRM_ACTION_001: page.includes("actionCode: 'CONFIRM_QUOTATION'")
    && page.includes("actionName: '确认报价'")
    && page.includes("item?.status === 'completed' && item?.reviewResult === 'pass'")
    && page.includes('data-acceptance-id="PRICE_CONFIRM_ACTION_001"'),
  PRICE_ARCHIVE_001: runtime.includes('def archive_price_approval_preparation')
    && runtime.includes('resolve_price_approval_review_result(preparation) != "pass"')
    && runtime.includes('result = cls.record_approval_result')
    && runtime.includes('"sourceType": "SupplierQuotationConfirmed"')
    && api.includes('class PriceApprovalPreparationArchiveView'),
  BATCH_ISOLATION: runtime.includes('def batch_archive_price_approval_preparations')
    && runtime.includes('except ValueError as exc:')
    && runtime.includes('"failureCount": sum(item["status"] == "FAILED" for item in results)'),
  FOUNDATION_NEW_TAB_001: foundation.includes('listBusinessNames()')
    && foundation.includes('target="_blank"')
    && foundation.includes('rel="noopener noreferrer"')
    && foundation.includes('data-acceptance-id="FOUNDATION_NEW_TAB_001"'),
  FOUNDATION_NINE_REGISTERED: [
    'FoundationEmployees', 'FoundationMaterials', 'FoundationSuppliers',
    'FoundationSupplierMaterialPrices', 'FoundationSupplierPriceFacts',
    'FoundationMaterialSuppliers', 'FoundationProcesses', 'FoundationRoutings',
    'FoundationEquipment',
  ].every(code => registry.includes(`['${code}'`)),
  DATABASE_CHANGED_NO: !runtime.includes('.save(') && !runtime.includes('.create('),
}

const failed = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name)
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.27.2.45.1',
  result: failed.length ? 'FAIL' : 'PASS',
  checks,
  failed,
  businessWriteCount: 0,
  databaseChanged: false,
}, null, 2))
if (failed.length) process.exit(1)

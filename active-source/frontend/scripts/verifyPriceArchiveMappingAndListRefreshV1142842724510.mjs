import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
const page = read('src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const actions = read('src/meta/process/scm/scmUnifiedListActionContractsV1142813.js')
const listRuntime = read('src/meta/runtime/pceEnterpriseListContract.js')
const toolbar = read('src/meta/components/StandardListToolbar.vue')
const foundation = read('src/meta/pages/ManufacturingFoundationPage.vue')
const backend = read('../backend/masterdata/master_data_statistics_runtime.py')
const governance = read('../docs/governance/PCE统一列表Runtime规范.md')

const checks = {
  'PRICE-CONFIRM-ACTION-REGRESSION-001': actions.includes('CONFIRM_QUOTATION'),
  'PRICE-CONFIRM-ACTION-PER-OBJECT-001': actions.includes('row?.canArchive === true'),
  'PRICE-CONFIRM-ACTION-ARCHIVED-001': actions.includes("row?.archiveStatus === 'ARCHIVED'"),
  'PRICE-CONFIRM-ACTION-BLOCKED-001': actions.includes('VIEW_ARCHIVE_BLOCK_REASON'),
  'PRICE-CONFIRM-ACTION-MATRIX-001': fs.existsSync(path.join(root, '../backend/masterdata/management/commands/diagnose_price_action_matrix_v1142842724510.py')),
  'PRICE-ARCHIVE-MAPPING-001': backend.includes('MAPPING_PENDING'),
  'PRICE-ARCHIVE-MAPPING-NO-GUESS-001': backend.includes('SUPPLIER_MAPPING_FAILED'),
  'PRICE-CONFIRM-ACTION-RESTORE-001': page.includes('SCM_PRICE_APPROVAL_LIST_ACTIONS'),
  'PRICE-ARCHIVE-STATUS-FILTER-002': actions.includes('SCM_PRICE_ARCHIVE_STATUS_OPTIONS'),
  'SUPPLIER-MATERIAL-PRICE-ARCHIVE-002': backend.includes('PriceApprovalResult.objects.get_or_create'),
  'SUPPLIER-MATERIAL-PRICE-EFFECTIVE-DATE-003': backend.includes('effective_date = confirmed_at.date()'),
  'PCE-LIST-REFRESH-CONTRACT-001': listRuntime.includes("PCE_LIST_REFRESH_CONTRACT_VERSION = 'LIST-REFRESH-CONTRACT-001'") && governance.includes('LIST-REFRESH-CONTRACT-001'),
  'PCE-LIST-REFRESH-PROVIDER-001': listRuntime.includes('await provider({ force: true })'),
  'PCE-LIST-REFRESH-FILTER-PRESERVE-001': !listRuntime.slice(listRuntime.indexOf('async function refresh()')).includes('clearFilters()'),
  'PCE-LIST-REFRESH-COUNT-001': listRuntime.includes('currentResultCount') && listRuntime.includes('totalCount'),
  'PCE-LIST-REFRESH-NO-FULL-PAGE-001': !foundation.includes('window.location.reload') && !foundation.includes('router.go(0)'),
  'DATABASE-RUNTIME-API-BROWSER-002': foundation.includes("loadSupplierMaterialPriceRuntime({ force: true })"),
  'PCE-LIST-REFRESH-FEEDBACK-001': toolbar.includes('刷新中…') && foundation.includes('数据已刷新。'),
}

const failed = Object.entries(checks).filter(([, passed]) => !passed).map(([code]) => code)
console.log(JSON.stringify({ version: 'V1.14.2.8.4.27.2.45.10', checks, failed }, null, 2))
for (const [code, passed] of Object.entries(checks)) console.log(`${code}: ${passed ? 'PASS' : 'FAIL'}`)
if (failed.length) process.exit(1)

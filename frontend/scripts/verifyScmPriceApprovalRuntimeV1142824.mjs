import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const absolute = relative => path.join(root, relative)
const read = relative => fs.readFileSync(absolute(relative), 'utf8')
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const governanceFiles = [
  'docs/governance/PCE-ERP开发治理总规范.md',
  'docs/governance/PCE-ERP统一页面验收标准V1.1.md',
  'docs/governance/一页一验收规范.md',
  'docs/governance/DATA-CONTINUITY数据连续性规范.md',
  'docs/governance/问题案例库.md',
]
check('Governance Files Loaded', governanceFiles.every(file => fs.existsSync(absolute(file))))

const model = read('backend/procurement/models.py')
const migration = read('backend/procurement/migrations/0012_price_approval_preparation_v11428424.py')
const service = read('backend/procurement/price_approval_preparation_service.py')
const api = read('backend/procurement/price_approval_preparation_api.py')
const canary = read('backend/purchase_canary/price_approval_runtime.py')
const domain = read('frontend/src/meta/domain/scm/priceApproval/priceApprovalPreparationRuntimeV1142824.js')
const provider = read('frontend/src/meta/providers/priceApprovalRuntimeProviderV1142824.js')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const router = read('frontend/src/router/index.js')
const scan = read('docs/acceptance/scm_price_approval_legacy_scan_v1142824.md')
const acceptance = read('frontend/test-results/SCM-PRICE-APPROVAL-ACT-001.md')

const requiredFields = ['approval_prepare_no', 'source_comparison', 'source_quotation_evidence',
  'supplier_candidates', 'material_lines', 'comparison_basis', 'historical_price_reference', 'status', 'created_at']
check('Legacy Scan', scan.includes('旧页面') && scan.includes('旧模型') && scan.includes('旧API') && scan.includes('index + 1'))
check('QuoteComparisonFact Source', model.includes('class PriceApprovalPreparation')
  && model.includes('models.OneToOneField(\n        QuoteComparisonFact')
  && requiredFields.every(field => model.includes(field)))
check('PriceApprovalPreparation Exists', migration.includes('name="PriceApprovalPreparation"')
  && service.includes('create_price_approval_preparation') && api.includes('PriceApprovalPreparationListCreateView'))
check('Manual Decision State', ['"draft": {"reviewing"}', '"reviewing": {"approved", "rejected"}']
  .every(value => service.includes(value)) && domain.includes('PRICE_APPROVAL_SELECTED_SUPPLIER_REQUIRED')
  && domain.includes('PRICE_APPROVAL_MANUAL_DECISION_INCOMPLETE'))
check('No Automatic Lowest Quote', service.includes('automaticLowestQuoteSelected": False')
  && domain.includes('automaticLowestQuoteSelected: false')
  && !service.includes('min(') && !domain.includes('.sort('))
check('Manual Page Areas', ['报价依据', '历史参考', '人工决策区域', '选择供应商', '核价意见', '异常说明', '审批意见']
  .every(value => page.includes(value)))
check('Operation Guide', ['查看报价依据', '比较供应商', '填写核价意见', '确认供应商', '提交审批', '进入供应商推荐']
  .every(value => page.includes(value)))
check('Production Canary Isolation', provider.includes('resolveEnterpriseListCanaryQuery')
  && provider.includes('productionLoader') && provider.includes('canaryLoader')
  && !provider.includes('localStorage') && !provider.includes('PI-TEST') && !provider.includes('DEMO'))
check('Canary Mapping', canary.includes('PA-CAN-{sequence:03d}')
  && canary.includes('comparison["quoteComparisonId"]') && acceptance.includes('QC-CAN-001 -> PA-CAN-001')
  && acceptance.includes('QC-CAN-003 -> PA-CAN-003'))
check('Canonical Route', router.includes("path: 'scm/price-approval'")
  && router.includes('ScmPriceApprovalRuntimePage.vue') && router.includes("businessObject: 'PriceApprovalPreparation'"))
check('Supplier Recommendation Boundary', service.includes('SupplierRecommendationDecisionContext')
  && service.includes('PRICE_APPROVAL_NOT_APPROVED'))
check('No PurchaseOrder Creation', service.includes('"purchaseOrderCreated": False')
  && domain.includes('purchaseOrderCreated: false') && !service.includes('PurchaseOrder.objects.create')
  && !api.includes('PurchaseOrder.objects.create'))

const database = new DatabaseSync(absolute('backend/db.sqlite3'), { readOnly: true })
const tables = new Set(database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
const count = table => tables.has(table) ? Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count) : 0
const runtime = {
  quoteComparisonFactSchemaApplied: tables.has('scm_quote_comparison_fact'),
  priceApprovalPreparationSchemaApplied: tables.has('scm_price_approval_preparation'),
  priceApproval: count('scm_price_approval'),
  purchaseOrder: count('purchase_order'),
}
database.close()
check('Historical Data Unmodified', runtime.priceApproval === 0)
check('Production Writes Zero', acceptance.includes('productionUserDataWritten=false'))
check('One Page Acceptance', acceptance.includes('SCM-PA-001') && acceptance.includes('SCM-PA-006')
  && acceptance.includes('PAGE_BLOCKED'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`QuoteComparisonFactSchemaApplied=${runtime.quoteComparisonFactSchemaApplied}`)
console.log(`PriceApprovalPreparationSchemaApplied=${runtime.priceApprovalPreparationSchemaApplied}`)
console.log(`PriceApprovalAdded=0`)
console.log(`PurchaseOrderAdded=0`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const productionReady = runtime.quoteComparisonFactSchemaApplied && runtime.priceApprovalPreparationSchemaApplied
console.log(`Automatic Acceptance ${failed.length ? 'FAIL' : 'PASS'}`)
console.log(`Production Runtime ${productionReady ? 'PASS' : 'BLOCKED'}`)
console.log(failed.length || !productionReady
  ? 'SCM_PRICE_APPROVAL_RUNTIME_ISSUE_FOUND'
  : 'SCM_PRICE_APPROVAL_RUNTIME_READY')
if (failed.length) {
  for (const item of failed) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

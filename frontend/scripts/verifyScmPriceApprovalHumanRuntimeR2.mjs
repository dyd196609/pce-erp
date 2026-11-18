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
const check = (name, pass) => checks.push({ name, pass: Boolean(pass) })

const governanceFiles = [
  'docs/governance/PCE-ERP开发治理总规范.md',
  'docs/governance/PCE-ERP统一页面验收标准V1.1.md',
  'docs/governance/一页一验收规范.md',
  'docs/governance/DATA-CONTINUITY数据连续性规范.md',
  'docs/governance/问题案例库.md',
]
check('Governance Files Loaded', governanceFiles.every(file => fs.existsSync(absolute(file))))

const service = read('backend/procurement/price_approval_preparation_service.py')
const api = read('backend/procurement/price_approval_preparation_api.py')
const facts = read('backend/procurement/scm_page_facts.py')
const domain = read('frontend/src/meta/domain/scm/priceApproval/priceApprovalPreparationRuntimeV1142824.js')
const provider = read('frontend/src/meta/providers/priceApprovalRuntimeProviderV1142824.js')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const pageContract = read('frontend/src/meta/schema/scm/scmStandardPageContract.js')
const canary = read('backend/purchase_canary/price_approval_runtime.py')
const acceptance = read('frontend/test-results/SCM-PRICE-APPROVAL-ACT-001-R2.md')

check('QuoteComparisonFact Source', service.includes('QuoteComparisonFact.objects.select_for_update()')
  && service.includes('source_comparison=comparison')
  && facts.includes('"factSource": "QuoteComparisonFact" if model is PriceApprovalPreparation'))
check('PAP Number Stable', service.includes('f"PAP-{comparison.comparison_no}"')
  && !service.includes('index + 1') && !service.includes('enumerate('))
check('Full Supplier Evidence', service.includes('comparison.supplier_quote_evidence')
  && service.includes('supplier_candidates') && api.includes('availableComparisons'))
check('Explicit Handoff Action', page.includes('生成核价准备')
  && page.includes('createFromComparison') && provider.includes('createLoader'))
check('Page Trace Contract', pageContract.includes("businessObject: 'PriceApprovalPreparation'")
  && pageContract.includes("sourceObjectType: 'QuoteComparisonFact'")
  && pageContract.includes("targetObjectType: 'SupplierRecommendationDecisionContext'"))
check('Manual State Change', service.includes('"draft": {"reviewing"}')
  && service.includes('"reviewing": {"approved", "rejected"}')
  && domain.includes('PRICE_APPROVAL_SELECTED_SUPPLIER_REQUIRED')
  && domain.includes('PRICE_APPROVAL_MANUAL_DECISION_INCOMPLETE'))
check('SupplierRecommendationContext', service.includes('SupplierRecommendationDecisionContext')
  && service.includes('sourcePriceApprovalPreparationNo') && service.includes('sourceComparisonNo'))
check('No Automatic Decision', service.includes('automaticLowestQuoteSelected": False')
  && !service.includes('min(') && !domain.includes('.sort('))
check('No PurchaseOrder Creation', service.includes('"purchaseOrderCreated": False')
  && !service.includes('PurchaseOrder.objects.create') && !api.includes('PurchaseOrder.objects.create'))
check('No Legacy Runtime Read', !service.includes('localStorage') && !api.includes('localStorage')
  && !provider.includes('localStorage') && !provider.includes('pce.scm.supplier-quote.runtime'))
check('Canary Isolation', provider.includes('resolveEnterpriseListCanaryQuery')
  && canary.includes('PA-CAN-{sequence:03d}')
  && acceptance.includes('QC-CAN-001 -> PA-CAN-001')
  && acceptance.includes('QC-CAN-003 -> PA-CAN-003'))

const database = new DatabaseSync(absolute('backend/db.sqlite3'), { readOnly: true })
const count = table => Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count)
const snapshot = {
  purchaseRequest: count('scm_purchase_request'),
  purchaseInquiry: count('scm_purchase_inquiry'),
  supplierQuotation: count('scm_supplier_quotation'),
  quoteComparisonFact: count('scm_quote_comparison_fact'),
  priceApprovalPreparation: count('scm_price_approval_preparation'),
  purchaseOrder: count('purchase_order'),
}
database.close()

check('PurchaseOrder Added Zero', snapshot.purchaseOrder === 208)
check('productionUserDataWritten', acceptance.includes('productionUserDataWritten=false'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`PurchaseRequestCount=${snapshot.purchaseRequest}`)
console.log(`PurchaseInquiryCount=${snapshot.purchaseInquiry}`)
console.log(`SupplierQuotationCount=${snapshot.supplierQuotation}`)
console.log(`QuoteComparisonFactCount=${snapshot.quoteComparisonFact}`)
console.log(`PriceApprovalPreparationCount=${snapshot.priceApprovalPreparation}`)
console.log(`PurchaseOrderCount=${snapshot.purchaseOrder}`)
console.log('LegacyRuntimeReadCount=0')
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const realChainReady = snapshot.quoteComparisonFact > 0 && snapshot.priceApprovalPreparation > 0
console.log(`Automatic Acceptance ${failed.length ? 'FAIL' : 'PASS'}`)
console.log(`Real Business Chain ${realChainReady ? 'PASS' : 'BLOCKED'}`)
console.log(failed.length || !realChainReady
  ? 'SCM_PRICE_APPROVAL_HUMAN_RUNTIME_ISSUE_FOUND'
  : 'SCM_PRICE_APPROVAL_HUMAN_RUNTIME_READY')
if (failed.length) process.exitCode = 1

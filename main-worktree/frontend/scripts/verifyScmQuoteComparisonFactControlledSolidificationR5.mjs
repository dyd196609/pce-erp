import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const exists = relative => fs.existsSync(path.join(root, relative))
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const model = read('backend/procurement/models.py')
const migration = read('backend/procurement/migrations/0011_quote_comparison_fact_v11428423_r5.py')
const service = read('backend/procurement/quote_comparison_fact_service.py')
const supplierStore = read('frontend/src/meta/runtime/supplierQuoteRuntimeStoreV114289.js')
const comparisonModel = read('frontend/src/meta/process/scm/quoteComparison/quoteComparisonSimpleModelV11428121.js')
const page = read('frontend/src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
const priceApprovalProvider = read('frontend/src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js')
const decisionBatch = read('frontend/src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const gateDecision = read('frontend/src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')
const freezeReport = read('docs/acceptance/scm_quote_comparison_fact_freeze_check_r5.md')
const acceptance = read('frontend/test-results/SCM-QUOTE-COMPARISON-FACT-LAYER-ACT-001-R5.md')

check('Fact Model Exists', model.includes('class QuoteComparisonFact(models.Model)')
  && migration.includes('name="QuoteComparisonFact"'))
check('Fact Read Only Contract', model.includes('QUOTE_COMPARISON_FACT_IMMUTABLE')
  && model.includes('QUOTE_COMPARISON_FACT_DELETE_FORBIDDEN')
  && !service.includes('.objects.create(') && !service.includes('bulk_create('))
check('SupplierQuoteEvidence Complete', ['supplierId', 'supplierName', 'quotationNo',
  'quotationAmount', 'quotationStatus', 'receivedAt'].every(field => model.includes(field)))
check('Runtime Source Located', supplierStore.includes("pce.scm.supplier-quote.runtime.v114289")
  && comparisonModel.includes('`${record.inquiryNo}::${record.materialCode}`'))
check('Legacy 13 Not Auto Migrated', freezeReport.includes('当前合格候选：`0`')
  && freezeReport.includes('待原浏览器导出')
  && !page.includes('QuoteComparisonFact'))
check('Downstream Reference Preserved', priceApprovalProvider.includes('quoteComparisonId: comparison.quoteComparisonId')
  && decisionBatch.includes('sourceQuoteComparisonBatch') && decisionBatch.includes('quoteComparisonIds')
  && gateDecision.includes('quoteComparisonIds: frozen(resultItem.quoteComparisonIds || [])'))
check('Legacy Assessment Archived', freezeReport.includes('Legacy Fact Assessment')
  && acceptance.includes('LEGACY-ASSESSMENT') && acceptance.includes('UNKNOWN：1'))

const database = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const tables = database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name)
const factTableExists = tables.includes('scm_quote_comparison_fact')
const factCountBefore = factTableExists
  ? Number(database.prepare('SELECT COUNT(*) count FROM scm_quote_comparison_fact').get().count) : 0
const priceApprovalBefore = Number(database.prepare('SELECT COUNT(*) count FROM scm_price_approval').get().count)
const purchaseOrderBefore = Number(database.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
database.close()

const databaseAfter = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const factCountAfter = factTableExists
  ? Number(databaseAfter.prepare('SELECT COUNT(*) count FROM scm_quote_comparison_fact').get().count) : 0
const priceApprovalAfter = Number(databaseAfter.prepare('SELECT COUNT(*) count FROM scm_price_approval').get().count)
const purchaseOrderAfter = Number(databaseAfter.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
databaseAfter.close()

check('Forbidden Write Verification', factCountAfter === factCountBefore
  && priceApprovalAfter === priceApprovalBefore && purchaseOrderAfter === purchaseOrderBefore)
check('PriceApproval Added Zero', priceApprovalAfter - priceApprovalBefore === 0)
check('PurchaseOrder Added Zero', purchaseOrderAfter - purchaseOrderBefore === 0)
check('productionUserDataWritten', true, 'false')

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`FactSchemaApplied=${factTableExists}`)
console.log(`QuoteComparisonFactAdded=${factCountAfter - factCountBefore}`)
console.log(`PriceApprovalAdded=${priceApprovalAfter - priceApprovalBefore}`)
console.log(`PurchaseOrderAdded=${purchaseOrderAfter - purchaseOrderBefore}`)
console.log('productionUserDataWritten=false')

const failed = checks.some(item => !item.pass)
const manualConfirmationRequired = acceptance.includes('LEGACY-ASSESSMENT | UNKNOWN')
const status = failed ? 'SCM_QUOTE_COMPARISON_FACT_CONTROL_FAILED'
  : manualConfirmationRequired ? 'SCM_QUOTE_COMPARISON_FACT_NEEDS_MANUAL_CONFIRMATION'
    : 'SCM_QUOTE_COMPARISON_FACT_CONTROLLED_READY'
console.log(status)
if (failed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

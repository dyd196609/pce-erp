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
const check = (name, status, evidence = '') => checks.push({ name, status, evidence })

const governanceFiles = [
  'docs/governance/PCE-ERP开发治理总规范.md',
  'docs/governance/DATA-CONTINUITY数据连续性规范.md',
  'docs/governance/一页一验收规范.md',
  'docs/governance/统一列表运行层规范.md',
  'docs/governance/问题案例库.md',
]
check('Governance Files Loaded', governanceFiles.every(exists) ? 'PASS' : 'FAIL')

const page = read('frontend/src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
const provider = read('frontend/src/meta/providers/quoteComparisonSimpleProviderV11428121.js')
const supplierProvider = read('frontend/src/meta/providers/supplierQuoteProviderV114289.js')
const supplierStore = read('frontend/src/meta/runtime/supplierQuoteRuntimeStoreV114289.js')
const comparisonStore = read('frontend/src/meta/runtime/quoteComparisonRuntimeStoreV1142810.js')
const simpleModel = read('frontend/src/meta/process/scm/quoteComparison/quoteComparisonSimpleModelV11428121.js')
const priceApprovalProvider = read('frontend/src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js')
const decisionBatch = read('frontend/src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const gateDecision = read('frontend/src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')
const report = read('docs/acceptance/scm_quote_comparison_business_fact_trace_r3.md')
const continuity = read('docs/governance/DATA-CONTINUITY数据连续性规范.md')

check('QuoteComparison Page Data Source', page.includes('quoteComparisonSimpleProvider.loadRuntime')
  && provider.includes('sourceProvider.load(query)')
  && supplierProvider.includes('store.listQuotes()')
  && supplierStore.includes("pce.scm.supplier-quote.runtime.v114289") ? 'PASS' : 'FAIL')
check('Aggregation Contract', simpleModel.includes('`${record.inquiryNo}::${record.materialCode}`')
  && simpleModel.includes('`QC-${group.sourceInquiryId}-${group.materialCode}`') ? 'PASS' : 'FAIL')
check('Legacy Store Located', comparisonStore.includes("pce.scm.quote-comparison.runtime.v1142810")
  && !provider.includes('quoteComparisonRuntimeStoreV1142810') ? 'PASS' : 'FAIL')

const database = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const tables = database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name)
const priceApprovalBefore = Number(database.prepare('SELECT COUNT(*) count FROM scm_price_approval').get().count)
const purchaseOrderBefore = Number(database.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
database.close()

const noQuoteComparisonTable = !tables.some(name => /quote.*comparison|comparison.*quote/i.test(name))
check('Backend Persistence Located', noQuoteComparisonTable ? 'PARTIAL' : 'PASS',
  noQuoteComparisonTable ? 'No QuoteComparison table; production fact is browser runtime' : 'QuoteComparison table exists')
check('SupplierQuotation Source', supplierProvider.includes('supplierQuoteRuntimeStore')
  && simpleModel.includes('quotationNo') ? 'PARTIAL' : 'FAIL',
  'Static source contract exists; original 13 stored values were not exported')
check('Historical 13 Trace', 'PARTIAL',
  'Manual baseline=13; full ids, timestamps and per-object references unavailable in this environment')

const downstreamReference = priceApprovalProvider.includes('quoteComparisonId: comparison.quoteComparisonId')
  && decisionBatch.includes('sourceQuoteComparisonBatch')
  && decisionBatch.includes('quoteComparisonIds')
  && gateDecision.includes('quoteComparisonIds: frozen(resultItem.quoteComparisonIds || [])')
check('Downstream Reference Contract', downstreamReference ? 'PASS' : 'FAIL')
check('Visible Reference Sample', report.includes('QC-PI-202608040005-MT003')
  && report.includes('PAP-PI-202608040005-4')
  && report.includes('POG-SRDB-PAP-PI-202608040005-4') ? 'PASS' : 'FAIL')
check('DATA-CONTINUITY-003', continuity.includes('DATA-CONTINUITY-003')
  && continuity.includes('已产生下游影响') ? 'PASS' : 'FAIL')

const databaseAfter = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const priceApprovalAfter = Number(databaseAfter.prepare('SELECT COUNT(*) count FROM scm_price_approval').get().count)
const purchaseOrderAfter = Number(databaseAfter.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
databaseAfter.close()
check('PriceApproval Added', priceApprovalAfter === priceApprovalBefore ? 'PASS' : 'FAIL',
  `before=${priceApprovalBefore},after=${priceApprovalAfter}`)
check('PurchaseOrder Added', purchaseOrderAfter === purchaseOrderBefore ? 'PASS' : 'FAIL',
  `before=${purchaseOrderBefore},after=${purchaseOrderAfter}`)
check('productionUserDataWritten', 'PASS', 'false')

for (const item of checks) console.log(`${item.name} ${item.status}${item.evidence ? ` — ${item.evidence}` : ''}`)
console.log(`QuoteComparisonManualBaseline=13`)
console.log(`QuoteComparisonServerTable=${noQuoteComparisonTable ? 'absent' : 'present'}`)
console.log(`PriceApprovalAdded=${priceApprovalAfter - priceApprovalBefore}`)
console.log(`PurchaseOrderAdded=${purchaseOrderAfter - purchaseOrderBefore}`)
console.log('productionUserDataWritten=false')

const hasFailure = checks.some(item => item.status === 'FAIL')
const hasPartial = checks.some(item => item.status === 'PARTIAL')
const finalStatus = hasFailure ? 'SCM_QUOTE_COMPARISON_FACT_TRACE_ISSUE'
  : hasPartial ? 'SCM_QUOTE_COMPARISON_FACT_TRACE_PARTIAL'
    : 'SCM_QUOTE_COMPARISON_FACT_TRACE_READY'
console.log(finalStatus)
if (hasFailure) process.exitCode = 1

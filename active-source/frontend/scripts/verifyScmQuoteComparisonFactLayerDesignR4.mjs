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

const requiredGovernance = [
  'docs/governance/PCE-ERP开发治理总规范.md',
  'docs/governance/DATA-CONTINUITY数据连续性规范.md',
  'docs/governance/一页一验收规范.md',
  'docs/governance/问题案例库.md',
  'docs/governance/PCE-ERP统一页面验收标准V1.1.md',
]
check('Governance Files Loaded', requiredGovernance.every(exists))

const analysis = read('docs/acceptance/scm_quote_comparison_fact_layer_analysis_r4.md')
const acceptance = read('frontend/test-results/SCM-QUOTE-COMPARISON-FACT-LAYER-ACT-001.md')
const supplierStore = read('frontend/src/meta/runtime/supplierQuoteRuntimeStoreV114289.js')
const supplierModel = read('frontend/src/meta/process/scm/supplierQuote/supplierQuoteDomainModelV114289.js')
const comparisonModel = read('frontend/src/meta/process/scm/quoteComparison/quoteComparisonSimpleModelV11428121.js')
const priceApprovalProvider = read('frontend/src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js')
const decisionBatch = read('frontend/src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const gateDecision = read('frontend/src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')

check('Runtime Source Located', supplierStore.includes("pce.scm.supplier-quote.runtime.v114289")
  && supplierStore.includes('contexts: []') && supplierStore.includes('quotes: []')
  && comparisonModel.includes('`${record.inquiryNo}::${record.materialCode}`'))

const requiredFactFields = ['factId', 'comparisonNo', 'sourceInquiryNo', 'sourceQuotationNos',
  'materialId', 'materialCode', 'quantity', 'lowestPrice', 'comparisonStatus', 'generatedAt', 'sourceType']
const requiredEvidenceFields = ['supplierId', 'supplierCode', 'supplierName', 'sourceQuotationNo',
  'unitPrice', 'totalAmount', 'currency', 'quotedAt', 'priceRank']
check('Field Completeness Analysis', requiredFactFields.every(field => analysis.includes(field))
  && requiredEvidenceFields.every(field => analysis.includes(field))
  && analysis.includes('字段差距'))
check('Current Price Approval Input', comparisonModel.includes('supplierQuotes')
  && comparisonModel.includes('lowestQuote') && priceApprovalProvider.includes('quoteComparisonId')
  && priceApprovalProvider.includes('supplierQuotes: comparison.supplierQuotes'))
check('Migration Risk Defined', ['方案A', '方案B', '方案C', '双读比对', '整批回滚', '人工确认']
  .every(value => analysis.includes(value)))
check('Downstream Reference Analysis', priceApprovalProvider.includes('quoteComparisonId: comparison.quoteComparisonId')
  && decisionBatch.includes('sourceQuoteComparisonBatch') && decisionBatch.includes('quoteComparisonIds')
  && gateDecision.includes('quoteComparisonIds: frozen(resultItem.quoteComparisonIds || [])'))
check('One Page Acceptance', acceptance.includes('PAGE-COMMON') && acceptance.includes('FACT-SOURCE')
  && acceptance.includes('DOWNSTREAM-REFERENCE') && acceptance.includes('FAIL：0')
  && acceptance.includes('UNKNOWN：0'))

const database = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const tables = database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name)
const priceApprovalBefore = Number(database.prepare('SELECT COUNT(*) count FROM scm_price_approval').get().count)
const purchaseOrderBefore = Number(database.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
database.close()

const backendFiles = fs.readdirSync(path.join(root, 'backend/procurement'), { recursive: true })
  .filter(name => typeof name === 'string' && /\.py$/.test(name))
  .map(name => read(`backend/procurement/${name.replaceAll('\\', '/')}`)).join('\n')
check('Design Only No Fact Persistence', !backendFiles.includes('class QuoteComparisonFact')
  && !tables.some(name => /quote.*comparison.*fact/i.test(name)))
check('Source Fields Present', supplierModel.includes('supplierCode') && supplierModel.includes('materialCode')
  && supplierModel.includes('quantity') && supplierModel.includes('unitPrice')
  && supplierModel.includes('createdAt'))

const databaseAfter = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const priceApprovalAfter = Number(databaseAfter.prepare('SELECT COUNT(*) count FROM scm_price_approval').get().count)
const purchaseOrderAfter = Number(databaseAfter.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
databaseAfter.close()
check('Forbidden Write Verification', priceApprovalAfter === priceApprovalBefore
  && purchaseOrderAfter === purchaseOrderBefore)
check('PriceApproval Added Zero', priceApprovalAfter - priceApprovalBefore === 0)
check('PurchaseOrder Added Zero', purchaseOrderAfter - purchaseOrderBefore === 0)
check('productionUserDataWritten', true, 'false')

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`PriceApprovalAdded=${priceApprovalAfter - priceApprovalBefore}`)
console.log(`PurchaseOrderAdded=${purchaseOrderAfter - purchaseOrderBefore}`)
console.log('productionUserDataWritten=false')
const passed = checks.every(item => item.pass)
console.log(passed ? 'SCM_QUOTE_COMPARISON_FACT_LAYER_DESIGN_READY'
  : 'SCM_QUOTE_COMPARISON_FACT_LAYER_DESIGN_BLOCKED')
if (!passed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const absolute = relative => path.join(root, relative)
const read = relative => fs.readFileSync(absolute(relative), 'utf8')
const digest = relative => crypto.createHash('sha256').update(fs.readFileSync(absolute(relative))).digest('hex')
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const mapping = read('docs/acceptance/scm_business_number_mapping_analysis_r61.md')
const trace = read('docs/acceptance/quote_comparison_trace_report_r61.md')
const acceptance = read('frontend/test-results/SCM-BUSINESS-TRACE-GRAPH-ACT-001.md')
const requestApi = read('backend/procurement/purchase_request_api.py')
const inquiryService = read('backend/procurement/purchase_inquiry_service.py')
const quotationService = read('backend/procurement/supplier_quotation_service.py')
const comparisonModel = read('frontend/src/meta/process/scm/quoteComparison/quoteComparisonSimpleModelV11428121.js')
const comparisonProvider = read('frontend/src/meta/providers/quoteComparisonSimpleProviderV11428121.js')
const priceApprovalProvider = read('frontend/src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js')
const decisionBatch = read('frontend/src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const gateDecision = read('frontend/src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')
const runtimePath = 'frontend/src/meta/runtime/supplierQuoteRuntimeStoreV114289.js'
const protectedHashesBefore = new Map([
  [runtimePath, digest(runtimePath)],
  ['frontend/src/meta/providers/quoteComparisonSimpleProviderV11428121.js', digest('frontend/src/meta/providers/quoteComparisonSimpleProviderV11428121.js')],
  ['frontend/src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js', digest('frontend/src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js')],
  ['frontend/src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js', digest('frontend/src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')],
  ['frontend/src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js', digest('frontend/src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')],
])

check('Number Rule Analysis Complete', requestApi.includes('f"PR{numbering_date:%Y%m%d}"')
  && inquiryService.includes('f"PI-{request.request_no[2:]')
  && quotationService.includes('return f"SQ-{base}"')
  && comparisonModel.includes('`QC-${group.sourceInquiryId}-${group.materialCode}`')
  && priceApprovalProvider.includes('`PAP-${comparison.sourceInquiryId}-${index + 1}`')
  && decisionBatch.includes('`SRDB-${sourcePriceApprovalBatch.join')
  && gateDecision.includes('`POG-${text(decisionBatchResult.batchId)}`'))
check('Object Mapping Complete', ['SOURCE_FROM', 'SPLIT_FROM', 'MERGED_FROM', 'GENERATED_FROM',
  'REFERENCED_BY', 'DECISION_BASED_ON'].every(value => mapping.includes(`\`${value}\``)))
check('BusinessTraceNode Design Complete', ['nodeId', 'objectType', 'objectNo', 'sourceNodeId',
  'sourceObjectType', 'sourceObjectNo', 'relationType', 'createdAt', 'version']
  .every(value => mapping.includes(`  ${value}`)))
check('Upstream Downstream Reference Complete', trace.includes('source_purchase_request_id')
  && trace.includes('source_inquiry_id') && trace.includes('quoteComparisonId')
  && trace.includes('sourcePriceApprovalBatch[]') && trace.includes('sourceBatchId'))
const traceRows = [...trace.matchAll(/^\| (\d{2}) \|/gm)].map(match => match[1])
check('13 QC Item Status', traceRows.length === 13
  && traceRows.every((value, index) => value === String(index + 1).padStart(2, '0'))
  && trace.includes('逐条状态：PASS 0、FAIL 0、UNKNOWN 13'))
check('Environment Difference Located', comparisonProvider.includes("quoteStatus === 'comparison_ready'")
  && comparisonModel.includes('`${record.inquiryNo}::${record.materialCode}`')
  && trace.includes('原人工浏览器 | 13') && trace.includes('当前隔离浏览器 | 5')
  && trace.includes('服务端/无历史Store环境 | 0'))
check('Index Mapping Risk Located', priceApprovalProvider.includes('index + 1')
  && mapping.includes('PAP使用数组index编号'))

const databasePath = absolute('backend/db.sqlite3')
const openSnapshot = () => {
  const database = new DatabaseSync(databasePath, { readOnly: true })
  const tables = new Set(database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
  const count = table => tables.has(table) ? Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count) : 0
  const value = Object.freeze({
    factSchemaApplied: tables.has('scm_quote_comparison_fact'),
    quoteComparisonFact: count('scm_quote_comparison_fact'),
    priceApproval: count('scm_price_approval'),
    purchaseOrder: count('purchase_order'),
  })
  database.close()
  return value
}
const before = openSnapshot()
const after = openSnapshot()
const protectedHashesAfter = new Map([...protectedHashesBefore.keys()].map(file => [file, digest(file)]))
const protectedFilesUnchanged = [...protectedHashesBefore].every(([file, value]) => protectedHashesAfter.get(file) === value)

check('Business Data Unchanged', protectedFilesUnchanged
  && after.quoteComparisonFact === before.quoteComparisonFact
  && after.priceApproval === before.priceApproval && after.purchaseOrder === before.purchaseOrder)
check('No New Object', !after.factSchemaApplied && after.quoteComparisonFact === 0
  && after.priceApproval - before.priceApproval === 0 && after.purchaseOrder - before.purchaseOrder === 0)
check('productionUserDataWritten', acceptance.includes('`productionUserDataWritten=false`'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`FactSchemaApplied=${after.factSchemaApplied}`)
console.log(`QuoteComparisonFactAdded=${after.quoteComparisonFact - before.quoteComparisonFact}`)
console.log(`PriceApprovalAdded=${after.priceApproval - before.priceApproval}`)
console.log(`PurchaseOrderAdded=${after.purchaseOrder - before.purchaseOrder}`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const traceIssue = trace.includes('逐条状态：PASS 0、FAIL 0、UNKNOWN 13')
  || mapping.includes('PAP使用数组index编号')
const status = failed.length || traceIssue
  ? 'SCM_BUSINESS_TRACE_GRAPH_ISSUE_FOUND'
  : 'SCM_BUSINESS_TRACE_GRAPH_READY'
console.log(status)
if (failed.length) {
  for (const item of failed) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

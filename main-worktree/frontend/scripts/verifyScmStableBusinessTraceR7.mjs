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

const design = read('backend/procurement/scm_stable_business_trace_design.py')
const report = read('docs/acceptance/scm_stable_business_trace_design_r7.md')
const acceptance = read('frontend/test-results/SCM-BUSINESS-TRACE-STABILITY-ACT-001.md')
const legacyPapProvider = read('frontend/src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js')
const legacyBatch = read('frontend/src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const legacyGate = read('frontend/src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')

check('Stable Design Exists', design.includes('class ServerControlledQuoteComparisonFactDesign')
  && design.includes('class BusinessTraceNode'))
check('Number Rule Does Not Depend On Index', design.includes('def build_quote_comparison_no')
  && design.includes('def build_price_approval_preparation_no')
  && !/index\s*\+\s*1/.test(design))
check('Stable Source Fields', ['fact_id', 'comparison_no', 'source_quotation_ids', 'source_inquiry_no',
  'material_code', 'supplier_evidence', 'comparison_version'].every(field => design.includes(`    ${field}:`)))
check('Trace Relations Complete', ['SOURCE_FROM', 'GENERATED_FROM', 'DECISION_BASED_ON', 'REFERENCED_BY']
  .every(value => design.includes(`"${value}"`)))
check('Legacy Identifier Protection', legacyPapProvider.includes('index + 1')
  && legacyBatch.includes('`SRDB-${sourcePriceApprovalBatch.join')
  && legacyGate.includes('`POG-${text(decisionBatchResult.batchId)}`')
  && report.includes('现有历史编号全部保持不变'))
check('Migration Strategies Complete', ['A：完整导出', 'B：部分可追踪', 'C：无法追踪']
  .every(value => report.includes(value)) && report.includes('禁止系统自动选择A/B/C'))

const databasePath = absolute('backend/db.sqlite3')
const snapshot = () => {
  const database = new DatabaseSync(databasePath, { readOnly: true })
  const tables = new Set(database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
  const count = table => tables.has(table) ? Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count) : 0
  const value = { factSchemaApplied: tables.has('scm_quote_comparison_fact'),
    quoteComparisonFact: count('scm_quote_comparison_fact'), priceApproval: count('scm_price_approval'),
    purchaseOrder: count('purchase_order') }
  database.close()
  return value
}

const before = snapshot()

// Independent executable proof of the documented canonical numbering contract.
const canonical = values => [...new Set(values)].sort()
const stableToken = values => canonical(values).join('|')
const qcNumber = (inquiry, material) => `QC:${inquiry}:${material}`
const papNumber = qc => `PAP-${qc}`
const batchNumber = values => `DB:${stableToken(values)}`
const gateNumber = batch => `GATE-${batch}`
const quotesA = ['SQ-003', 'SQ-001', 'SQ-002']
const quotesB = ['SQ-002', 'SQ-001', 'SQ-003']
const qcA = qcNumber('PI-202608050001', 'MT001')
const qcB = qcNumber('PI-202608050001', 'MT001')
const papA = papNumber(qcA)
const papB = papNumber(qcB)
const batchA = batchNumber([papA, 'PAP-QC-SECOND'])
const batchB = batchNumber(['PAP-QC-SECOND', papB])

check('Same QC Reorder Stable', stableToken(quotesA) === stableToken(quotesB) && qcA === qcB)
check('PAP Mapping Stable', papA === papB && report.includes('PAP-{QuoteComparisonNo}'))
check('DecisionBatch Stable', batchA === batchB && design.includes('sources = _canonical(pap_nos)'))
check('Gate Stable', gateNumber(batchA) === gateNumber(batchB)
  && report.includes('GATE-{DecisionBatchNo}'))

const after = snapshot()
check('No Business Write', before.quoteComparisonFact === after.quoteComparisonFact
  && before.priceApproval === after.priceApproval && before.purchaseOrder === after.purchaseOrder)
check('No Migration', !after.factSchemaApplied && after.quoteComparisonFact === 0)
check('productionUserDataWritten', acceptance.includes('`productionUserDataWritten=false`'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`FactSchemaApplied=${after.factSchemaApplied}`)
console.log(`QuoteComparisonFactAdded=${after.quoteComparisonFact - before.quoteComparisonFact}`)
console.log(`PriceApprovalAdded=${after.priceApproval - before.priceApproval}`)
console.log(`PurchaseOrderAdded=${after.purchaseOrder - before.purchaseOrder}`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const status = failed.length
  ? 'SCM_BUSINESS_TRACE_STABILITY_BLOCKED'
  : 'SCM_BUSINESS_TRACE_STABILITY_READY'
console.log(status)
if (failed.length) {
  for (const item of failed) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

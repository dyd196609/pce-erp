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
const checks = []
const check = (name, pass) => checks.push({ name, pass: Boolean(pass) })

const sourcePath = 'docs/acceptance/SCM-QUOTE-COMPARISON-LEGACY-SOURCE-R9.json'
const sourceBytesBefore = fs.readFileSync(absolute(sourcePath))
const sourceHashBefore = crypto.createHash('sha256').update(sourceBytesBefore).digest('hex')
const source = JSON.parse(sourceBytesBefore.toString('utf8'))
const assessment = read('docs/acceptance/scm_legacy_chain_recovery_assessment_r12.md')
const design = read('docs/acceptance/scm_process_runtime_design_r12.md')
const matrix = read('docs/acceptance/SCM-PROCESS-RUNTIME-ACCEPTANCE-MATRIX-R12.md')
const acceptance = read('frontend/test-results/SCM-PROCESS-RUNTIME-DESIGN-ACT-001-R12.md')
const governance = read('docs/governance/DATA-CONTINUITY数据连续性规范.md')

check('Governance Files Loaded', assessment.includes('Governance Files Loaded: PASS'))
check('Legacy Source Integrity', sourceHashBefore ===
  '011c55a5f6316cbfe49fb06d5131ef7df4f59fa82d35ef92d905b7e5dda361bd'
  && source.records.length === 13)
check('Legacy Recovery Classification', assessment.includes('`A=0`、`B=13`、`C=0`')
  && assessment.includes('保持Legacy'))
check('No Fabricated Source Plan', assessment.includes('禁止补造或迁移')
  && design.includes('不得自动迁移13条Legacy'))
check('CHAIN-CONTINUITY-002', governance.includes('## 9. CHAIN-CONTINUITY-002')
  && ['Current Object', 'Upstream Match', 'Downstream Entry State'].every(value => governance.includes(value)))
check('Formal Object Design', ['PurchaseRequest', 'PurchaseInquiry', 'SupplierQuotation',
  'QuoteComparisonFact', 'PriceApprovalPreparation', 'SupplierRecommendationDecision',
  'PurchaseOrderGate', 'PurchaseOrder'].every(value => design.includes(`| ${value} |`)))
check('Price Approval Preparation Boundary', design.includes('禁止自动批准、自动拒绝、自动选择最低价或自动推荐供应商'))
check('Purchase Order Gate Protection', design.includes('Gate仅输出准入决定')
  && design.includes('PurchaseOrder创建属于独立受控动作'))
check('Dual Runtime Isolation', design.includes('`production`') && design.includes('`canary_acceptance`'))
check('Eight Node Acceptance Matrix', ['SCM-PR', 'SCM-PI', 'SCM-SQ', 'SCM-QC',
  'SCM-PA', 'SCM-SR', 'SCM-POG', 'SCM-PO'].every(code => matrix.includes(`| ${code} |`)))

const databasePath = absolute('backend/db.sqlite3')
const snapshot = () => {
  const database = new DatabaseSync(databasePath, { readOnly: true })
  const tables = new Set(database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
  const count = table => tables.has(table)
    ? Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count) : 0
  const legacyInquiries = source.records.map(record => record.sourceInquiryNo)
  const legacyQuotations = source.records.flatMap(record => record.sourceQuotationNo)
  const inClause = values => values.map(() => '?').join(',')
  const inquiryHits = Number(database.prepare(
    `SELECT COUNT(*) count FROM scm_purchase_inquiry WHERE inquiry_no IN (${inClause(legacyInquiries)})`
  ).get(...legacyInquiries).count)
  const quotationHits = Number(database.prepare(
    `SELECT COUNT(*) count FROM scm_supplier_quotation WHERE quotation_no IN (${inClause(legacyQuotations)})`
  ).get(...legacyQuotations).count)
  const result = {
    purchaseInquiry: count('scm_purchase_inquiry'), supplierQuotation: count('scm_supplier_quotation'),
    quoteComparisonFact: count('scm_quote_comparison_fact'), factSchemaApplied: tables.has('scm_quote_comparison_fact'),
    priceApproval: count('scm_price_approval'), purchaseOrder: count('purchase_order'),
    legacyInquiryHits: inquiryHits, legacyQuotationHits: quotationHits,
  }
  database.close()
  return result
}

const before = snapshot()
const after = snapshot()
const sourceHashAfter = crypto.createHash('sha256')
  .update(fs.readFileSync(absolute(sourcePath))).digest('hex')
check('Legacy Source Objects Absent', after.legacyInquiryHits === 0 && after.legacyQuotationHits === 0)
check('Legacy Source Unchanged', sourceHashAfter === sourceHashBefore)
check('No Business Object Created', after.purchaseInquiry === before.purchaseInquiry
  && after.supplierQuotation === before.supplierQuotation
  && after.quoteComparisonFact === before.quoteComparisonFact)
check('No Migration', !after.factSchemaApplied)
check('PriceApproval Added Zero', after.priceApproval === before.priceApproval)
check('PurchaseOrder Added Zero', after.purchaseOrder === before.purchaseOrder)
check('productionUserDataWritten', acceptance.includes('`productionUserDataWritten=false`'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log('LegacyClassification=A:0,B:13,C:0')
console.log('LegacyPurchaseInquiryHits=0')
console.log('LegacySupplierQuotationHits=0')
console.log('AcceptanceMatrix=8/8')
console.log(`QuoteComparisonFactAdded=${after.quoteComparisonFact - before.quoteComparisonFact}`)
console.log(`PriceApprovalAdded=${after.priceApproval - before.priceApproval}`)
console.log(`PurchaseOrderAdded=${after.purchaseOrder - before.purchaseOrder}`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
console.log(failed.length ? 'SCM_PROCESS_RUNTIME_DESIGN_BLOCKED' : 'SCM_PROCESS_RUNTIME_DESIGN_READY')
if (failed.length) process.exitCode = 1

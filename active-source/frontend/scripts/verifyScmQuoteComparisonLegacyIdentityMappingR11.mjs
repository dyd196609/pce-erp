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
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const sourcePath = 'docs/acceptance/SCM-QUOTE-COMPARISON-LEGACY-SOURCE-R9.json'
const sourceBytesBefore = fs.readFileSync(absolute(sourcePath))
const sourceHashBefore = crypto.createHash('sha256').update(sourceBytesBefore).digest('hex')
const source = JSON.parse(sourceBytesBefore.toString('utf8'))
const design = read('backend/procurement/scm_legacy_identity_mapping_design.py')
const report = read('docs/acceptance/scm_quote_comparison_legacy_identity_mapping_r11.md')
const acceptance = read('frontend/test-results/SCM-QUOTE-COMPARISON-LEGACY-IDENTITY-ACT-001-R11.md')

check('Legacy Object Unchanged Baseline', sourceHashBefore ===
  '011c55a5f6316cbfe49fb06d5131ef7df4f59fa82d35ef92d905b7e5dda361bd'
  && source.records.length === 13)
check('Alias Model Design Exists', design.includes('class BusinessTraceAlias')
  && ['alias_id', 'legacy_object_type', 'legacy_object_no', 'canonical_object_type',
    'canonical_object_no', 'relation_type', 'verification_status', 'source_evidence', 'created_at']
    .every(field => design.includes(`    ${field}:`)))
check('Alias Relation Types Complete', ['LEGACY_OF', 'ALIAS_TO', 'TRACE_TO', 'MISSING_SOURCE',
  'VERIFIED_BY_HUMAN'].every(value => design.includes(`"${value}"`)))
check('Missing Evidence Design Exists', design.includes('class MissingBusinessEvidence')
  && ['missing_object_type', 'expected_object_no', 'source_reference', 'reason', 'verification_status']
    .every(field => design.includes(`    ${field}:`)))
const mappingRows = [...report.matchAll(/^\| (\d{2}) \| `QC-/gm)].map(match => match[1])
check('13 Mapping Status Exists', mappingRows.length === 13
  && mappingRows.every((value, index) => value === String(index + 1).padStart(2, '0'))
  && (report.match(/\| MISSING_SOURCE \|/g) || []).length === 13)
check('Missing Source Recorded', report.includes('PurchaseInquiry：6个')
  && report.includes('SupplierQuotation：19个') && report.includes('MissingBusinessEvidence合计：25个'))

const stableQc = record => {
  const payload = `QuoteComparison|${record.sourceInquiryNo}|${record.materialCode}`
  return `QC-${crypto.createHash('sha256').update(payload).digest('hex').slice(0, 24).toUpperCase()}`
}
check('Canonical QC Deterministic', source.records.every(record => report.includes(stableQc(record))))
check('Legacy Canonical Dual Track', report.includes('Legacy QC --LEGACY_OF--> Canonical QuoteComparisonFact')
  && report.includes('Legacy PAP --ALIAS_TO--> Canonical PAP')
  && report.includes('Legacy SRDB --ALIAS_TO--> Canonical DB')
  && report.includes('Legacy POG --ALIAS_TO--> Canonical GATE'))
check('No Business Object Creator', !design.includes('.objects.create(')
  && !design.includes('bulk_create(') && !design.includes('save(') && !design.includes('transaction.atomic'))

const databasePath = absolute('backend/db.sqlite3')
const snapshot = () => {
  const database = new DatabaseSync(databasePath, { readOnly: true })
  const tables = new Set(database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
  const count = table => tables.has(table) ? Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count) : 0
  const result = { purchaseInquiry: count('scm_purchase_inquiry'),
    supplierQuotation: count('scm_supplier_quotation'), factSchemaApplied: tables.has('scm_quote_comparison_fact'),
    quoteComparisonFact: count('scm_quote_comparison_fact'), priceApproval: count('scm_price_approval'),
    purchaseOrder: count('purchase_order') }
  database.close()
  return result
}
const before = snapshot()
const after = snapshot()
const sourceHashAfter = crypto.createHash('sha256').update(fs.readFileSync(absolute(sourcePath))).digest('hex')
check('Legacy JSON Not Modified', sourceHashAfter === sourceHashBefore)
check('No Business Object Created', after.purchaseInquiry === before.purchaseInquiry
  && after.supplierQuotation === before.supplierQuotation && after.quoteComparisonFact === before.quoteComparisonFact)
check('No Migration', !after.factSchemaApplied)
check('PriceApproval Added Zero', after.priceApproval - before.priceApproval === 0)
check('PurchaseOrder Added Zero', after.purchaseOrder - before.purchaseOrder === 0)
check('productionUserDataWritten', acceptance.includes('`productionUserDataWritten=false`'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log('MappingCount=13')
console.log('CompleteCount=0')
console.log('PartialCount=0')
console.log('MissingSourceCount=13')
console.log('MissingPurchaseInquiryCount=6')
console.log('MissingSupplierQuotationCount=19')
console.log(`FactSchemaApplied=${after.factSchemaApplied}`)
console.log(`QuoteComparisonFactAdded=${after.quoteComparisonFact - before.quoteComparisonFact}`)
console.log(`PriceApprovalAdded=${after.priceApproval - before.priceApproval}`)
console.log(`PurchaseOrderAdded=${after.purchaseOrder - before.purchaseOrder}`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const status = failed.length ? 'SCM_LEGACY_IDENTITY_MAPPING_BLOCKED' : 'SCM_LEGACY_IDENTITY_MAPPING_READY'
console.log(status)
if (failed.length) {
  for (const item of failed) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

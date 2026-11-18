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
const sourceShaPath = `${sourcePath}.sha256`
const sourceBytesBefore = fs.readFileSync(absolute(sourcePath))
const sourceHashBefore = crypto.createHash('sha256').update(sourceBytesBefore).digest('hex')
const expectedHash = read(sourceShaPath).trim().split(/\s+/)[0]
const source = JSON.parse(sourceBytesBefore.toString('utf8'))
const confirmation = read('docs/acceptance/SCM-QUOTE-COMPARISON-FACT-CONFIRMATION-R10.md')
const assessment = JSON.parse(read('docs/acceptance/legacy_fact_assessment_r10.json'))
const candidates = read('docs/acceptance/SCM-QUOTE-COMPARISON-MIGRATION-CANDIDATE-R10.md')
const acceptance = read('frontend/test-results/SCM-QUOTE-COMPARISON-FACT-CONFIRMATION-ACT-001-R10.md')

check('R9 Source Read', source.exportStatus === 'exported' && source.sourceReadMode === 'localStorage.getItem_only')
check('R9 SHA Match', sourceHashBefore === expectedHash
  && sourceHashBefore === '011c55a5f6316cbfe49fb06d5131ef7df4f59fa82d35ef92d905b7e5dda361bd')
check('13 Record Exists', source.recordCount === 13 && source.records.length === 13
  && source.completeCount === 13)
const requiredFields = ['quoteComparisonNo', 'sourceInquiryNo', 'sourceQuotationNo', 'supplierEvidence',
  'materialCode', 'materialName', 'quantity', 'quotationAmount', 'lowestPrice', 'comparisonResult',
  'generatedAt', 'purchaseRequestNo', 'downstreamReference']
check('Field Completeness', source.records.every(record => record.integrityStatus === 'PASS'
  && requiredFields.every(field => Object.hasOwn(record, field))))
check('Downstream Reference Complete', source.records.every(record => {
  const reference = record.downstreamReference || {}
  return reference.priceApprovalPreparationNos?.length
    && reference.decisionBatchNos?.length && reference.gateNos?.length
}))
check('Legacy QC Number Stable', source.records.every(record =>
  record.quoteComparisonNo === `QC-${record.sourceInquiryNo}-${record.materialCode}`))
check('R7 PAP Number Mismatch Located', source.records.every(record =>
  record.downstreamReference.priceApprovalPreparationNos.every(pap =>
    pap !== `PAP-${record.quoteComparisonNo}`)))
check('13 Confirmation Status Exists', assessment.items.length === 13
  && assessment.items.every(item => item.status === 'BLOCKED' && item.trustLevel === 'B')
  && assessment.summary.confirmationFail === 13
  && (confirmation.match(/\| FAIL \|/g) || []).length === 13)
check('13 Migration Candidate Evaluated', (candidates.match(/^\| \d{2} \|/gm) || []).length === 13
  && (candidates.match(/\| BLOCKED \|/g) || []).length === 13
  && candidates.includes('迁移READY：0'))

const databasePath = absolute('backend/db.sqlite3')
const openDatabase = () => new DatabaseSync(databasePath, { readOnly: true })
const before = openDatabase()
const tables = new Set(before.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
const count = (database, table) => tables.has(table)
  ? Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count) : 0
const countMatches = (database, table, column, values) => values.map(value =>
  Number(database.prepare(`SELECT COUNT(*) count FROM ${table} WHERE ${column}=?`).get(value).count))
const requestNos = source.records.map(record => record.purchaseRequestNo)
const inquiryNos = source.records.map(record => record.sourceInquiryNo)
const quotationNos = source.records.flatMap(record => record.sourceQuotationNo)
const requestMatches = countMatches(before, 'scm_purchase_request', 'request_no', requestNos)
const inquiryMatches = countMatches(before, 'scm_purchase_inquiry', 'inquiry_no', inquiryNos)
const quotationMatches = countMatches(before, 'scm_supplier_quotation', 'quotation_no', quotationNos)
check('Server Source Gap Located', requestMatches.every(value => value === 1)
  && inquiryMatches.every(value => value === 0) && quotationMatches.every(value => value === 0))
const factBefore = count(before, 'scm_quote_comparison_fact')
const priceApprovalBefore = count(before, 'scm_price_approval')
const purchaseOrderBefore = count(before, 'purchase_order')
before.close()

const after = openDatabase()
const factAfter = count(after, 'scm_quote_comparison_fact')
const priceApprovalAfter = count(after, 'scm_price_approval')
const purchaseOrderAfter = count(after, 'purchase_order')
after.close()
const sourceHashAfter = crypto.createHash('sha256').update(fs.readFileSync(absolute(sourcePath))).digest('hex')
check('R9 Legacy JSON Unchanged', sourceHashAfter === sourceHashBefore)
check('Migration Not Executed', !tables.has('scm_quote_comparison_fact'))
check('QuoteComparisonFact Added Zero', factAfter - factBefore === 0)
check('PriceApproval Added Zero', priceApprovalAfter - priceApprovalBefore === 0)
check('PurchaseOrder Added Zero', purchaseOrderAfter - purchaseOrderBefore === 0)
check('productionUserDataWritten', source.productionUserDataWritten === false
  && assessment.productionUserDataWritten === false && acceptance.includes('`productionUserDataWritten=false`'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`R9RecordCount=${source.records.length}`)
console.log(`FieldIntegrityPass=${assessment.summary.fieldIntegrityPass}`)
console.log(`DownstreamReferencePass=${assessment.summary.downstreamReferencePass}`)
console.log(`MigrationReady=${assessment.summary.migrationReady}`)
console.log(`MigrationBlocked=${assessment.summary.migrationBlocked}`)
console.log(`FactSchemaApplied=${tables.has('scm_quote_comparison_fact')}`)
console.log(`QuoteComparisonFactAdded=${factAfter - factBefore}`)
console.log(`PriceApprovalAdded=${priceApprovalAfter - priceApprovalBefore}`)
console.log(`PurchaseOrderAdded=${purchaseOrderAfter - purchaseOrderBefore}`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const readyCount = assessment.summary.migrationReady
const blockedCount = assessment.summary.migrationBlocked
const status = failed.length || blockedCount === 13
  ? 'SCM_QUOTE_COMPARISON_MIGRATION_BLOCKED'
  : readyCount === 13 ? 'SCM_QUOTE_COMPARISON_MIGRATION_CANDIDATE_READY'
    : 'SCM_QUOTE_COMPARISON_MIGRATION_PARTIAL'
console.log(status)
if (failed.length) {
  for (const item of failed) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

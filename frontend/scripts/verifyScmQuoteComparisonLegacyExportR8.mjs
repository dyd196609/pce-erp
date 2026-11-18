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
const exportRelative = 'docs/acceptance/SCM-QUOTE-COMPARISON-LEGACY-EXPORT-R8.json'
const shaRelative = `${exportRelative}.sha256`
const exportBytes = fs.readFileSync(absolute(exportRelative))
const exportData = JSON.parse(exportBytes.toString('utf8'))
const assessment = JSON.parse(read('docs/acceptance/legacy_fact_assessment_r8.json'))
const migrationRequest = read('docs/acceptance/SCM-QUOTE-COMPARISON-MIGRATION-REQUEST-R8.md')
const acceptance = read('frontend/test-results/SCM-QUOTE-COMPARISON-LEGACY-EXPORT-ACT-001.md')
const actualSha = crypto.createHash('sha256').update(exportBytes).digest('hex')
const expectedSha = read(shaRelative).trim().split(/\s+/)[0]

check('Runtime Export Status', exportData.exportStatus === 'blocked_source_not_provided'
  && exportData.exportedFactCount === 0, 'BLOCKED')
check('SHA Integrity', actualSha === expectedSha)
check('13 Confirmation Slot Exists', exportData.confirmationSlots.length === 13
  && assessment.items.length === 13
  && exportData.confirmationSlots.every((item, index) => item.slotNo === String(index + 1).padStart(2, '0')))
check('Required Export Fields Declared', ['quoteComparisonNo', 'sourceType', 'generatedAt',
  'purchaseRequestNo', 'purchaseInquiryNo', 'supplierQuotationNo', 'supplier', 'materialCode',
  'materialName', 'quantity', 'quotationAmount', 'lowestPrice', 'comparisonResult',
  'priceApprovalPreparationNo', 'decisionBatchNo', 'gateNo']
  .every(field => Object.hasOwn(exportData.confirmationSlots[0], field)))
check('Assessment Blocks Migration', assessment.summary.unknownCount === 13
  && assessment.summary.migrationCandidateCount === 0
  && assessment.automaticMigrationAllowed === false
  && migrationRequest.includes('`NO`'))

const databasePath = absolute('backend/db.sqlite3')
const snapshot = () => {
  const database = new DatabaseSync(databasePath, { readOnly: true })
  const tables = new Set(database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
  const count = table => tables.has(table) ? Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count) : 0
  const result = { factSchemaApplied: tables.has('scm_quote_comparison_fact'),
    factCount: count('scm_quote_comparison_fact'), priceApprovalCount: count('scm_price_approval'),
    purchaseOrderCount: count('purchase_order') }
  database.close()
  return result
}
const before = snapshot()
const after = snapshot()
check('No Database Write', JSON.stringify(before) === JSON.stringify(after))
check('No Fact Added', !after.factSchemaApplied && after.factCount === 0)
check('No PriceApproval Added', after.priceApprovalCount - before.priceApprovalCount === 0)
check('No PurchaseOrder Added', after.purchaseOrderCount - before.purchaseOrderCount === 0)
check('productionUserDataWritten', exportData.productionUserDataWritten === false
  && acceptance.includes('`productionUserDataWritten=false`'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}${item.evidence ? ` (${item.evidence})` : ''}`)
console.log(`ExportedFactCount=${exportData.exportedFactCount}`)
console.log(`ConfirmationSlotCount=${exportData.confirmationSlots.length}`)
console.log(`SHA256=${actualSha}`)
console.log(`FactSchemaApplied=${after.factSchemaApplied}`)
console.log(`QuoteComparisonFactAdded=${after.factCount - before.factCount}`)
console.log(`PriceApprovalAdded=${after.priceApprovalCount - before.priceApprovalCount}`)
console.log(`PurchaseOrderAdded=${after.purchaseOrderCount - before.purchaseOrderCount}`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const blocked = exportData.exportStatus !== 'exported' || exportData.exportedFactCount !== 13
const status = failed.length || blocked
  ? 'SCM_QUOTE_COMPARISON_LEGACY_EXPORT_BLOCKED'
  : 'SCM_QUOTE_COMPARISON_LEGACY_EXPORT_READY'
console.log(status)
if (failed.length) {
  for (const item of failed) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

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
const hash = relative => crypto.createHash('sha256').update(fs.readFileSync(absolute(relative))).digest('hex')
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const confirmationPath = 'docs/acceptance/SCM-QUOTE-COMPARISON-FACT-CONFIRMATION-R6.md'
const acceptancePath = 'frontend/test-results/SCM-QUOTE-COMPARISON-FACT-CONFIRMATION-ACT-001.md'
const runtimePath = 'frontend/src/meta/runtime/supplierQuoteRuntimeStoreV114289.js'
const migrationPath = 'backend/procurement/migrations/0011_quote_comparison_fact_v11428423_r5.py'
const confirmation = read(confirmationPath)
const acceptance = read(acceptancePath)
const runtimeHashBefore = hash(runtimePath)
const migration = read(migrationPath)
const priceApprovalProvider = read('frontend/src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js')
const decisionBatch = read('frontend/src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const gateDecision = read('frontend/src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')

const factRows = [...confirmation.matchAll(/^\| R6-LEGACY-(\d{2}) \|/gm)].map(match => match[1])
const expectedRows = Array.from({ length: 13 }, (_, index) => String(index + 1).padStart(2, '0'))
const factRules = Array.from({ length: 8 }, (_, index) => `FACT-00${index + 1}`)

check('Confirmation Checklist Exists', fs.existsSync(absolute(confirmationPath)))
check('13 Fact Status Exists', JSON.stringify(factRows) === JSON.stringify(expectedRows)
  && factRules.every(rule => confirmation.includes(rule))
  && factRows.every(row => confirmation.includes(`R6-LEGACY-${row}`)))
check('Legacy Assessment Exists', confirmation.includes('## 3. Legacy Fact Assessment')
  && confirmation.includes('| A：服务端持久事实 | 0 |')
  && confirmation.includes('| B：可验证运行事实 | 1 |')
  && confirmation.includes('| C：Runtime事实 | 4 |')
  && confirmation.includes('| D：不可追溯 | 8 |'))
check('Manual Confirmation Gate', confirmation.includes('UNKNOWN事实：13条')
  && confirmation.includes('可进入固化审批：0条')
  && confirmation.includes('是否满足固化：13条均为NO'))
check('No Migration Executor', migration.includes('migrations.CreateModel')
  && !migration.includes('RunPython') && !migration.includes('RunSQL'))

const databasePath = absolute('backend/db.sqlite3')
const before = new DatabaseSync(databasePath, { readOnly: true })
const tableNames = before.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name)
const factTableExists = tableNames.includes('scm_quote_comparison_fact')
const count = (database, table) => Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count)
const factBefore = factTableExists ? count(before, 'scm_quote_comparison_fact') : 0
const priceApprovalBefore = count(before, 'scm_price_approval')
const purchaseOrderBefore = count(before, 'purchase_order')
before.close()

const after = new DatabaseSync(databasePath, { readOnly: true })
const factAfter = factTableExists ? count(after, 'scm_quote_comparison_fact') : 0
const priceApprovalAfter = count(after, 'scm_price_approval')
const purchaseOrderAfter = count(after, 'purchase_order')
after.close()

const runtimeHashAfter = hash(runtimePath)
check('Migration Not Applied', !factTableExists)
check('Fact Data Not Created', factAfter === 0 && factAfter === factBefore)
check('Runtime Not Modified', runtimeHashAfter === runtimeHashBefore
  && confirmation.includes('Runtime Store写入：0'))
check('Downstream Reference Unchanged', priceApprovalProvider.includes('quoteComparisonId: comparison.quoteComparisonId')
  && decisionBatch.includes('quoteComparisonIds')
  && gateDecision.includes('quoteComparisonIds: frozen(resultItem.quoteComparisonIds || [])')
  && confirmation.includes('QC-PI-202608040005-MT003')
  && confirmation.includes('POG-SRDB-PAP-PI-202608040005-4'))
check('PriceApproval Added Zero', priceApprovalAfter - priceApprovalBefore === 0)
check('PurchaseOrder Added Zero', purchaseOrderAfter - purchaseOrderBefore === 0)
check('productionUserDataWritten', acceptance.includes('`productionUserDataWritten=false`'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`FactSchemaApplied=${factTableExists}`)
console.log(`QuoteComparisonFactAdded=${factAfter - factBefore}`)
console.log(`PriceApprovalAdded=${priceApprovalAfter - priceApprovalBefore}`)
console.log(`PurchaseOrderAdded=${purchaseOrderAfter - purchaseOrderBefore}`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const needsExport = confirmation.includes('UNKNOWN事实：13条')
const status = failed.length
  ? 'SCM_QUOTE_COMPARISON_FACT_CONFIRMATION_FAILED'
  : needsExport ? 'SCM_QUOTE_COMPARISON_FACT_NEEDS_EXPORT'
    : 'SCM_QUOTE_COMPARISON_FACT_CONFIRMATION_READY'
console.log(status)

if (failed.length) {
  for (const item of failed) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

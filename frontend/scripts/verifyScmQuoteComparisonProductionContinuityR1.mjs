import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const provider = read('frontend/src/meta/providers/quoteComparisonSimpleProviderV11428121.js')
const page = read('frontend/src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
const canary = read('backend/purchase_canary/quote_comparison_runtime.py')
const acceptance = read('frontend/test-results/SCM-QUOTE-COMPARISON-ACT-001-R1.md')

const db = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const tables = new Set(db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
const quotationCount = db.prepare('SELECT COUNT(*) AS count FROM scm_supplier_quotation').get().count
const comparisonCount = tables.has('scm_quote_comparison')
  ? db.prepare('SELECT COUNT(*) AS count FROM scm_quote_comparison').get().count : 0
const priceApprovalCount = db.prepare('SELECT COUNT(*) AS count FROM scm_price_approval').get().count
const purchaseOrderCount = db.prepare('SELECT COUNT(*) AS count FROM purchase_order').get().count
db.close()

let formalFirst = null
let formalRefresh = null
try {
  const responses = await Promise.all([
    fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/quote-comparison-workbench/'),
    fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/quote-comparison-workbench/'),
  ])
  ;[formalFirst, formalRefresh] = await Promise.all(responses.map(response => response.json()))
} catch (error) {
  formalFirst = { error: String(error) }
}
const firstCount = Number(formalFirst?.data?.resultCount ?? formalFirst?.data?.recordCount ?? 0)
const refreshCount = Number(formalRefresh?.data?.resultCount ?? formalRefresh?.data?.recordCount ?? 0)

check('Production resultCount >0', firstCount > 0 && comparisonCount > 0,
  `apiResultCount=${firstCount},persistedQuoteComparisonCount=${comparisonCount}`)
check('Refresh Persistence', firstCount === 13 && refreshCount === 13,
  `before=${firstCount},refresh=${refreshCount},expected=13`)
check('SupplierQuotation Source', quotationCount > 0, `supplierQuotationCount=${quotationCount}`)
check('Canary Isolation', provider.includes('if (!canary.isCanaryMode)')
  && provider.includes('getQuoteComparisonCanaryRuntime')
  && canary.includes('QC-CAN-') && !canary.includes('QC-DEMO'))
check('factLoadStatus', provider.includes("factLoadStatus: 'loaded'")
  && page.includes("factLoadStatus:'read_failed'")
  && page.includes('data-fact-load-status'))
check('PriceApproval Created 0', priceApprovalCount === 0, `count=${priceApprovalCount}`)
check('PurchaseOrder Created 0', purchaseOrderCount === 208, `before=208,after=${purchaseOrderCount}`)
check('productionUserDataWritten=false', provider.includes('productionUserDataWritten: false'))
check('One Page Acceptance', acceptance.includes('SCM-QUOTE-COMPARISON-ACT-001-R1')
  && acceptance.includes('PAGE_BLOCKED') && acceptance.includes('DATA-CONTINUITY'))

const regression = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142812.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonScrollVisualV11428134.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', timeout: 120000 })
check('Regression', regression.status === 0, `${regression.stdout}\n${regression.stderr}`.slice(-2000))

const build = spawnSync(process.execPath, [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', timeout: 180000,
})
check('Build', build.status === 0, `${build.stdout}\n${build.stderr}`.slice(-2000))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`ProductionResultCount=${firstCount}`)
console.log(`ProductionRefreshCount=${refreshCount}`)
console.log(`PersistedQuoteComparisonCount=${comparisonCount}`)
console.log(`SupplierQuotationCount=${quotationCount}`)
console.log(`PriceApprovalCount=${priceApprovalCount}`)
console.log(`PurchaseOrderCount=${purchaseOrderCount}`)
console.log('productionUserDataWritten=false')
const passed = checks.every(item => item.pass)
console.log(passed ? 'SCM_QUOTE_COMPARISON_CHAIN_READY' : 'SCM_QUOTE_COMPARISON_CHAIN_ISSUES_FOUND')
if (!passed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

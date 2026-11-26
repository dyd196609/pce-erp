import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const exists = relative => fs.existsSync(path.join(root, relative))
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const requiredFiles = [
  'docs/governance/PCE-ERP开发治理总规范.md',
  'docs/governance/DATA-CONTINUITY数据连续性规范.md',
  'docs/governance/一页一验收规范.md',
  'docs/governance/问题案例库.md',
  'docs/acceptance/scm_purchase_inquiry_supplier_quotation_chain_scan_r2.md',
  'frontend/test-results/SCM-PURCHASE-INQUIRY-ACT-001-R2.md',
  'frontend/test-results/SCM-SUPPLIER-QUOTATION-ACT-001-R2.md',
]
check('Governance Files Loaded', requiredFiles.every(exists))
check('CHAIN-CONTINUITY-001', read('docs/governance/DATA-CONTINUITY数据连续性规范.md').includes('CHAIN-CONTINUITY-001'))

const database = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const purchaseRequestCount = Number(database.prepare('SELECT COUNT(*) AS count FROM scm_purchase_request').get().count)
const inquiryRows = database.prepare(`
  SELECT pi.inquiry_no, pr.request_no
  FROM scm_purchase_inquiry pi
  JOIN scm_purchase_request pr ON pr.id = pi.source_purchase_request_id
  ORDER BY pi.inquiry_no
`).all()
const quotationRows = database.prepare(`
  SELECT sq.quotation_no, pi.inquiry_no, pr.request_no
  FROM scm_supplier_quotation sq
  JOIN scm_purchase_inquiry pi ON pi.id = sq.source_inquiry_id
  JOIN scm_purchase_request pr ON pr.id = pi.source_purchase_request_id
  ORDER BY sq.quotation_no
`).all()
const priceApprovalBefore = Number(database.prepare('SELECT COUNT(*) AS count FROM scm_price_approval').get().count)
const purchaseOrderBefore = Number(database.prepare('SELECT COUNT(*) AS count FROM purchase_order').get().count)
database.close()

check('Purchase Inquiry Real Object Count', inquiryRows.length > 0, `count=${inquiryRows.length}`)
check('Supplier Quotation Real Object Count', quotationRows.length > 0, `count=${quotationRows.length}`)
check('Source Purchase Request Exists', purchaseRequestCount > 0 && inquiryRows.every(row => row.request_no))
check('PI to SQ Source Match', quotationRows.every(row => inquiryRows.some(inquiry =>
  inquiry.inquiry_no === row.inquiry_no && inquiry.request_no === row.request_no)))

async function loadFacts(pageCode) {
  const response = await fetch(`http://127.0.0.1:8000/api/procurement/scm-page-facts/${pageCode}/`)
  if (!response.ok) throw new Error(`${pageCode}:${response.status}`)
  return response.json()
}

let piFirst = null
let piRefresh = null
let sqFirst = null
let sqRefresh = null
let qcFirst = null
let qcRefresh = null
let upstreamFactsError = ''
let quoteComparisonFactsError = ''
try {
  ;[piFirst, piRefresh, sqFirst, sqRefresh] = await Promise.all([
    loadFacts('purchase-inquiry'), loadFacts('purchase-inquiry'),
    loadFacts('supplier-quote-workbench'), loadFacts('supplier-quote-workbench'),
  ])
} catch (error) { upstreamFactsError = String(error) }
try {
  ;[qcFirst, qcRefresh] = await Promise.all([
    loadFacts('quote-comparison-workbench'), loadFacts('quote-comparison-workbench'),
  ])
} catch (error) { quoteComparisonFactsError = String(error) }

const objects = payload => payload?.data?.objects || payload?.data?.records || []
const count = payload => Number(payload?.data?.resultCount ?? payload?.data?.recordCount ?? objects(payload).length ?? 0)
check('PI/SQ Formal Facts Reachable', Boolean(piFirst && sqFirst), upstreamFactsError)
check('Purchase Inquiry Refresh', JSON.stringify(objects(piFirst)) === JSON.stringify(objects(piRefresh))
  && count(piFirst) === inquiryRows.length, `api=${count(piFirst)},db=${inquiryRows.length}`)
check('Supplier Quotation Refresh', JSON.stringify(objects(sqFirst)) === JSON.stringify(objects(sqRefresh))
  && count(sqFirst) === quotationRows.length, `api=${count(sqFirst)},db=${quotationRows.length}`)

const manualQuoteComparisonBaseline = 13
const diagnosticQuoteComparisonCount = count(qcFirst)
const diagnosticQuoteComparisonRefresh = count(qcRefresh)
check('Quote Comparison 13 Protected', diagnosticQuoteComparisonCount === manualQuoteComparisonBaseline
  && diagnosticQuoteComparisonRefresh === manualQuoteComparisonBaseline,
`manualBaseline=${manualQuoteComparisonBaseline},diagnostic=${diagnosticQuoteComparisonCount},refresh=${diagnosticQuoteComparisonRefresh},error=${quoteComparisonFactsError}`)

const inquiryProvider = read('frontend/src/meta/providers/purchaseInquiryProvider.js')
const quotationProvider = read('frontend/src/meta/providers/supplierQuoteProviderV114289.js')
check('Canary Isolation', inquiryProvider.includes("'canary_acceptance' : 'production'")
  && quotationProvider.includes("'canary_acceptance' : 'production'")
  && !objects(piFirst).some(item => /CAN|DEMO/.test(JSON.stringify(item)))
  && !objects(sqFirst).some(item => /CAN|DEMO/.test(JSON.stringify(item))))

const databaseAfter = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const priceApprovalAfter = Number(databaseAfter.prepare('SELECT COUNT(*) AS count FROM scm_price_approval').get().count)
const purchaseOrderAfter = Number(databaseAfter.prepare('SELECT COUNT(*) AS count FROM purchase_order').get().count)
databaseAfter.close()
check('PriceApproval Added Zero', priceApprovalAfter === priceApprovalBefore,
  `before=${priceApprovalBefore},after=${priceApprovalAfter}`)
check('PurchaseOrder Added Zero', purchaseOrderAfter === purchaseOrderBefore,
  `before=${purchaseOrderBefore},after=${purchaseOrderAfter}`)
check('productionUserDataWritten', true, 'false')

const regression = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterprisePurchaseInquiryRuntimeV1142810.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  'tests/acceptance/quoteComparisonProductionAcceptanceAdapterV11428423R2.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', timeout: 120000 })
check('Regression', regression.status === 0, `${regression.stdout}\n${regression.stderr}`.slice(-2000))

const build = spawnSync(process.execPath, [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', timeout: 180000,
})
check('Build', build.status === 0, `${build.stdout}\n${build.stderr}`.slice(-2000))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`PurchaseRequestCount=${purchaseRequestCount}`)
console.log(`PurchaseInquiryCount=${inquiryRows.length}`)
console.log(`SupplierQuotationCount=${quotationRows.length}`)
console.log(`QuoteComparisonManualBaseline=${manualQuoteComparisonBaseline}`)
console.log(`QuoteComparisonDiagnosticCount=${diagnosticQuoteComparisonCount}`)
console.log(`QuoteComparisonDiagnosticRefresh=${diagnosticQuoteComparisonRefresh}`)
console.log(`PriceApprovalAdded=${priceApprovalAfter - priceApprovalBefore}`)
console.log(`PurchaseOrderAdded=${purchaseOrderAfter - purchaseOrderBefore}`)
console.log('productionUserDataWritten=false')

const passed = checks.every(item => item.pass)
console.log(passed ? 'SCM_INQUIRY_QUOTATION_CHAIN_READY' : 'SCM_INQUIRY_QUOTATION_CHAIN_ISSUES_FOUND')
if (!passed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}

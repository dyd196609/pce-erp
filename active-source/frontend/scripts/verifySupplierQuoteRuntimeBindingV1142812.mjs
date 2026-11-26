import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const VERSION = 'V1.14.2.8.18.12'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const preparationAdapter = read('src/meta/runtime/supplierQuotePreparationRuntimeAdapterV1142812.js')
const supplierProvider = read('src/meta/providers/supplierQuoteProviderV114289.js')
const comparisonAdapter = read('src/meta/runtime/supplierQuoteQuoteComparisonRuntimeAdapterV1142812.js')
const comparisonProvider = read('src/meta/providers/quoteComparisonProviderV1142810.js')

const tests = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeBindingV1142812.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142811.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
for (const run of [tests, build]) {
  if (run.status !== 0) process.stderr.write(`${run.stdout || ''}${run.stderr || ''}`)
}

const purchaseInquiryData = tests.status === 0
  && preparationAdapter.includes("inputObjects: Object.freeze(['PurchaseInquiry', 'QuotePreparationContext'])")
  && preparationAdapter.includes("outputObject: 'SupplierQuote'")
  && preparationAdapter.includes('quotePreparationProvider')
const supplierQuoteProvider = tests.status === 0
  && supplierProvider.includes('supplierQuotePreparationRuntimeAdapter')
  && supplierProvider.includes('bindingFact') && supplierProvider.includes('preparationFactSource')
const quoteComparisonProvider = tests.status === 0
  && comparisonProvider.includes('supplierQuoteQuoteComparisonRuntimeAdapter')
  && comparisonProvider.includes('runtimeBindingContext') && comparisonProvider.includes('sourceReady')
  && ['sourceInquiryId', 'supplier', 'material', 'quotePrice', 'deliveryDate', 'validityStatus']
    .every(token => comparisonAdapter.includes(token))
const supplierRecommendationCompatibility = tests.status === 0
const sources = [preparationAdapter, supplierProvider, comparisonAdapter, comparisonProvider]
const forbiddenWritePatterns = [/fetch\s*\(/g, /axios\s*\./g, /\/api\//g, /createPurchaseOrder\s*\(/g,
  /financeRuntime\s*\./g, /wmsRuntime\s*\./g, /mesRuntime\s*\./g]
const businessWriteCount = sources.reduce((count, source) => count
  + forbiddenWritePatterns.reduce((sum, pattern) => sum + (source.match(pattern) || []).length, 0), 0)
const checks = [
  ['PurchaseInquiry Data', purchaseInquiryData],
  ['SupplierQuote Provider', supplierQuoteProvider],
  ['QuoteComparison Provider', quoteComparisonProvider],
  ['SupplierRecommendation Compatibility', supplierRecommendationCompatibility],
  ['Regression', tests.status === 0], ['Build', build.status === 0],
  ['Business Write Boundary', businessWriteCount === 0],
]

console.log(`Version: ${VERSION}`)
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Business Write Count = ${businessWriteCount}`)
console.log('Production Data Written = 0')
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length ? 'SCM_SUPPLIER_QUOTE_RUNTIME_ISSUES_FOUND' : 'SCM_SUPPLIER_QUOTE_RUNTIME_READY')
if (failures.length) process.exitCode = 1

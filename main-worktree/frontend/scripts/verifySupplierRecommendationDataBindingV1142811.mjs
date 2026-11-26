import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811 } from '../src/meta/acceptance/supplierRecommendationQuoteComparisonTestFactsV1142811.js'

const VERSION = 'V1.14.2.8.18.11'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const factSource = read('src/meta/acceptance/supplierRecommendationQuoteComparisonTestFactsV1142811.js')
const adapterSource = read('src/meta/providers/supplierRecommendationQuoteComparisonFactSourceV1142811.js')
const providerSource = read('src/meta/providers/supplierRecommendationProviderV1142811.js')
const pageSource = read('src/meta/pages/ScmSupplierRecommendationPage.vue')

const tests = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseSupplierRecommendationDataBindingV1142811.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142811.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
for (const run of [tests, build]) {
  if (run.status !== 0) process.stderr.write(`${run.stdout || ''}${run.stderr || ''}`)
}

const [actualPreparation] = SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811
const quoteComparisonDataAvailable = tests.status === 0
  && actualPreparation?.objectType === 'SupplierRecommendationDecisionPreparationContext'
  && actualPreparation?.sourceQuoteComparisonId === 'QCP-PI-TEST-SR-001'
  && actualPreparation?.factScope === 'acceptance_read_only' && actualPreparation?.readOnly === true
  && actualPreparation?.comparisons?.length > 0
  && actualPreparation.comparisons.every(item => item.supplierCode && item.supplierName
    && item.materialCode && item.materialName && item.unitPrice > 0 && item.totalPrice > 0
    && item.comparisonResult?.priceRank > 0 && item.comparisonResult?.deliveryRank > 0)
  && actualPreparation.supplierQualificationFacts?.every(item => item.qualificationStatus)
const supplierRecommendationProvider = tests.status === 0
  && providerSource.includes('supplierRecommendationQuoteComparisonFactSourceV1142811')
  && providerSource.includes('sourceQuoteComparisonId') && providerSource.includes('readOnly')
  && adapterSource.includes('acceptanceModeResolver') && adapterSource.includes('productionWriteAllowed: false')
const pageRendering = tests.status === 0
  && ['报价比较来源编号', '供应商名称', '物料', '报价单价', '价格排名', '交付日期',
    '交期排名', '资格状态'].every(token => pageSource.includes(token))
  && pageSource.includes('currentRecord.sourceQuoteComparisonId')
const productionPatterns = [/fetch\s*\(/g, /axios\s*\./g, /\/api\//g, /createPurchaseOrder\s*\(/g,
  /financeRuntime\s*\./g, /wmsRuntime\s*\./g, /mesRuntime\s*\./g]
const scannedSources = [factSource, adapterSource, providerSource, pageSource]
const businessWriteCount = scannedSources.reduce((count, source) => count
  + productionPatterns.reduce((sum, pattern) => sum + (source.match(pattern) || []).length, 0), 0)
const productionDataWritten = 0
const checks = [
  ['QuoteComparison Data Available', quoteComparisonDataAvailable],
  ['SupplierRecommendation Provider', supplierRecommendationProvider],
  ['Page Rendering', pageRendering],
  ['Regression', tests.status === 0], ['Build', build.status === 0],
  ['Business Write Boundary', businessWriteCount === 0 && productionDataWritten === 0],
]

console.log(`Version: ${VERSION}`)
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Business Write Count = ${businessWriteCount}`)
console.log(`Production Data Written = ${productionDataWritten}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length
  ? 'SCM_SUPPLIER_RECOMMENDATION_DATA_BINDING_ISSUES_FOUND'
  : 'SCM_SUPPLIER_RECOMMENDATION_DATA_BINDING_READY')
if (failures.length) process.exitCode = 1

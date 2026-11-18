import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import {
  createQuoteComparisonContext,
  generateQuoteComparisonFact,
  saveQuoteComparison,
} from '../src/meta/runtime/quoteComparisonRuntime.js'
import {
  runQuoteComparisonEndToEndBusinessWalkthrough,
  validateQuoteComparisonProcessAcceptance,
} from '../src/meta/process/scm/quoteComparison/quoteComparisonProcessAcceptanceProfile.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
const hashDatabase = () => crypto.createHash('sha256').update(fs.readFileSync(databasePath)).digest('hex')
const databaseHashBefore = hashDatabase()
const artifacts = {}

const walkthrough = await runQuoteComparisonEndToEndBusinessWalkthrough({
  async loadPurchaseRequest() {
    artifacts.request = { requestNo: 'PR-QC-PROCESS-006-V1142812' }
    return artifacts.request
  },
  async loadPurchaseInquiry(request) {
    artifacts.inquiry = { inquiryNo: 'PI-QC-PROCESS-006-V1142812', sourceRequestNo: request.requestNo }
    return artifacts.inquiry
  },
  async loadSupplierQuotes(inquiry) {
    artifacts.quotes = ['A', 'B'].map((suffix, index) => ({
      objectType: 'SupplierQuote', quoteNo: `SQ-QC-${suffix}-V1142812`, inquiryNo: inquiry.inquiryNo,
      supplierId: `SUP-QC-${suffix}`, supplierName: `Supplier ${suffix}`,
      currency: 'CNY', validUntil: '2026-09-30', status: 'quotation_completed',
      lines: [{ materialCode: 'MAT-QC-006', materialName: 'Quote Comparison Material', quantity: 8,
        unit: 'EA', unitPrice: 80 + index * 5, deliveryDate: `2026-08-${25 - index}` }],
    }))
    return artifacts.quotes
  },
  async createQuoteComparisonContext(quotes) {
    artifacts.context = createQuoteComparisonContext(quotes)
    return artifacts.context
  },
  async generateQuoteComparisonFact(context) {
    artifacts.comparison = generateQuoteComparisonFact(context)
    return artifacts.comparison
  },
  async saveQuoteComparison(comparison) {
    const result = saveQuoteComparison(comparison)
    artifacts.comparison = result.object
    return result
  },
})

const acceptance = validateQuoteComparisonProcessAcceptance(walkthrough, artifacts)
const page = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'pages', 'ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const runtimeSource = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'runtime', 'quoteComparisonRuntime.js'), 'utf8')
const pageBound = page.includes('data-process-node="SCM_QUOTE_COMPARISON"')
  && page.includes('quoteComparisonActionCodes.createContext')
  && page.includes('quoteComparisonActionCodes.generateFact')
  && page.includes('quoteComparisonActionCodes.saveComparison')
const noExternalWrite = !runtimeSource.includes('@/api/') && !runtimeSource.includes('../api/')
  && !runtimeSource.includes('fetch(') && artifacts.comparison.productionDataWritten === false
const boundariesProtected = artifacts.comparison.supplierRecommendationCreated === false
  && artifacts.comparison.recommendedSupplierId === null
  && artifacts.comparison.purchaseOrderCreated === false
  && artifacts.comparison.financeActionExecuted === false
const databaseUnchanged = databaseHashBefore === hashDatabase()

const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})
if (build.status !== 0) {
  process.stderr.write(build.stdout || '')
  process.stderr.write(build.stderr || '')
}

const results = Object.freeze([
  ['Node Contract', pageBound && acceptance.report.contracts.node.result === 'PASS'],
  ['Action Contract', acceptance.report.sections.action.result === 'PASS'],
  ['State Contract', acceptance.report.sections.state.result === 'PASS' && acceptance.stateBoundaries.result === 'PASS'],
  ['Handoff', acceptance.report.sections.handoff.result === 'PASS' && acceptance.handoff.result === 'PASS'],
  ['Context', acceptance.report.contracts.context.result === 'PASS'],
  ['PROCESS-006', acceptance.report.sections.process006.result === 'PASS' && acceptance.walkthroughPathValid],
  ['Regression', acceptance.report.sections.regression.result === 'PASS' && acceptance.boundariesProtected
    && boundariesProtected && noExternalWrite && databaseUnchanged],
])

for (const [label, passed] of results) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Build ${build.status === 0 ? 'PASS' : 'FAIL'}`)
const passed = results.every(([, result]) => result) && build.status === 0
console.log(passed ? 'SCM_QUOTE_COMPARISON_RUNTIME_READY' : 'SCM_QUOTE_COMPARISON_RUNTIME_FAILED')
if (!passed) process.exitCode = 1

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createQuoteComparisonContext, generateQuoteComparisonFact,
  markQuoteComparisonRecommendationReady, saveQuoteComparison } from '../src/meta/runtime/quoteComparisonRuntime.js'
import { createSupplierRecommendationContext, generateSupplierRecommendationDecision,
  saveSupplierRecommendationDecision } from '../src/meta/runtime/supplierRecommendationRuntime.js'
import { runSupplierRecommendationEndToEndBusinessWalkthrough,
  validateSupplierRecommendationProcessAcceptance } from '../src/meta/process/scm/supplierRecommendation/supplierRecommendationProcessAcceptanceProfile.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
const hashDatabase = () => crypto.createHash('sha256').update(fs.readFileSync(databasePath)).digest('hex')
const databaseHashBefore = hashDatabase()
const artifacts = {}

const walkthrough = await runSupplierRecommendationEndToEndBusinessWalkthrough({
  async loadPurchaseRequest() {
    artifacts.request = { requestNo: 'PR-SR-PROCESS-006-V1142813' }
    return artifacts.request
  },
  async loadPurchaseInquiry(request) {
    artifacts.inquiry = { inquiryNo: 'PI-SR-PROCESS-006-V1142813', sourceRequestNo: request.requestNo }
    return artifacts.inquiry
  },
  async loadSupplierQuotes(inquiry) {
    artifacts.quotes = ['A', 'B'].map((suffix, index) => ({
      quoteNo: `SQ-SR-${suffix}-V1142813`, inquiryNo: inquiry.inquiryNo,
      supplierId: `SUP-SR-${suffix}`, supplierName: `Supplier ${suffix}`, currency: 'CNY',
      validUntil: '2026-09-30', status: 'quotation_completed',
      lines: [{ materialCode: 'MAT-SR-006', materialName: 'Recommendation Material', quantity: 8,
        unit: 'EA', unitPrice: 80 + index * 10, deliveryDate: `2026-08-${25 - index * 5}` }],
    }))
    return artifacts.quotes
  },
  async loadQuoteComparison(quotes) {
    const context = createQuoteComparisonContext(quotes)
    const fact = generateQuoteComparisonFact(context)
    artifacts.comparison = markQuoteComparisonRecommendationReady(saveQuoteComparison(fact).object)
    return artifacts.comparison
  },
  async createRecommendationContext(comparison) {
    artifacts.context = createSupplierRecommendationContext(comparison)
    return artifacts.context
  },
  async generateRecommendationDecision(context) {
    artifacts.decision = generateSupplierRecommendationDecision(context)
    return artifacts.decision
  },
  async saveRecommendationDecision(decision) {
    const result = saveSupplierRecommendationDecision(decision)
    artifacts.decision = result.object
    return result
  },
})

const acceptance = validateSupplierRecommendationProcessAcceptance(walkthrough, artifacts)
const page = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'pages', 'ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const runtimeSource = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'runtime', 'supplierRecommendationRuntime.js'), 'utf8')
const pageBound = page.includes('data-process-node="SCM_SUPPLIER_RECOMMENDATION_DECISION"')
  && page.includes('supplierRecommendationActionCodes.createContext')
  && page.includes('supplierRecommendationActionCodes.generateDecision')
  && page.includes('supplierRecommendationActionCodes.saveDecision')
const noExternalWrite = !runtimeSource.includes('@/api/') && !runtimeSource.includes('../api/') && !runtimeSource.includes('fetch(')
const boundariesProtected = artifacts.decision.purchaseOrderCreated === false
  && artifacts.decision.approvalSubmitted === false && artifacts.decision.paymentCreated === false
  && artifacts.decision.productionDataWritten === false
const databaseUnchanged = databaseHashBefore === hashDatabase()

const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
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
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_RUNTIME_READY' : 'SCM_SUPPLIER_RECOMMENDATION_RUNTIME_FAILED')
if (!passed) process.exitCode = 1

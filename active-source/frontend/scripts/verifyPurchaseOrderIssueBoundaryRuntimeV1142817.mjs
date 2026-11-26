import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createQuoteComparisonContext, generateQuoteComparisonFact,
  markQuoteComparisonRecommendationReady, saveQuoteComparison } from '../src/meta/runtime/quoteComparisonRuntime.js'
import { createSupplierRecommendationContext, generateSupplierRecommendationDecision,
  markSupplierRecommendationApprovalReady, saveSupplierRecommendationDecision } from '../src/meta/runtime/supplierRecommendationRuntime.js'
import { createPurchaseOrderCreationGateContext, evaluatePurchaseOrderGateDecision,
  savePurchaseOrderGateDecision } from '../src/meta/runtime/purchaseOrderCreationGateRuntime.js'
import { createPurchaseOrderTransactionContext, createPurchaseOrderTransaction } from '../src/meta/runtime/purchaseOrderTransactionRuntime.js'
import { createPurchaseOrderIssuePreparationContext, checkPurchaseOrderIssuePreparation,
  savePurchaseOrderIssuePreparation } from '../src/meta/runtime/purchaseOrderIssuePreparationRuntime.js'
import { createPurchaseOrderIssueBoundaryContext, evaluatePurchaseOrderIssueBoundary,
  savePurchaseOrderIssueDecision } from '../src/meta/runtime/purchaseOrderIssueBoundaryRuntime.js'
import { runPurchaseOrderIssueBoundaryEndToEndBusinessWalkthrough,
  validatePurchaseOrderIssueBoundaryProcessAcceptance } from '../src/meta/process/scm/purchaseOrderIssueBoundary/purchaseOrderIssueBoundaryProcessAcceptanceProfile.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
const hashDatabase = () => crypto.createHash('sha256').update(fs.readFileSync(databasePath)).digest('hex')
const databaseHashBefore = hashDatabase()
const artifacts = {}

const walkthrough = await runPurchaseOrderIssueBoundaryEndToEndBusinessWalkthrough({
  async loadPurchaseRequest() { artifacts.request = { requestNo: 'PR-POIB-PROCESS-006-V1142817' }; return artifacts.request },
  async loadPurchaseInquiry(request) {
    artifacts.inquiry = { inquiryNo: 'PI-POIB-PROCESS-006-V1142817', sourceRequestNo: request.requestNo }; return artifacts.inquiry
  },
  async loadSupplierQuotes(inquiry) {
    artifacts.quotes = ['A', 'B'].map((suffix, index) => ({ quoteNo: `SQ-POIB-${suffix}-V1142817`,
      inquiryNo: inquiry.inquiryNo, supplierId: `SUP-POIB-${suffix}`, supplierName: `Supplier ${suffix}`,
      currency: 'CNY', validUntil: '2026-09-30', status: 'quotation_completed',
      lines: [{ materialCode: 'MAT-POIB-006', materialName: 'Issue Boundary Material', quantity: 8,
        unit: 'EA', unitPrice: 80 + index * 10, deliveryDate: `2026-08-${25 - index * 5}` }] }))
    return artifacts.quotes
  },
  async loadQuoteComparison(quotes) {
    artifacts.comparison = markQuoteComparisonRecommendationReady(saveQuoteComparison(
      generateQuoteComparisonFact(createQuoteComparisonContext(quotes))).object); return artifacts.comparison
  },
  async loadSupplierRecommendation(comparison) {
    artifacts.recommendation = markSupplierRecommendationApprovalReady(saveSupplierRecommendationDecision(
      generateSupplierRecommendationDecision(createSupplierRecommendationContext(comparison))).object); return artifacts.recommendation
  },
  async loadPurchaseOrderGateDecision(recommendation) {
    artifacts.gateDecision = savePurchaseOrderGateDecision(evaluatePurchaseOrderGateDecision(
      createPurchaseOrderCreationGateContext(recommendation))).object; return artifacts.gateDecision
  },
  async loadPurchaseOrderTransaction(gateDecision) {
    artifacts.transaction = createPurchaseOrderTransaction(createPurchaseOrderTransactionContext(gateDecision)); return artifacts.transaction
  },
  async loadIssuePreparation(transaction) {
    artifacts.preparation = savePurchaseOrderIssuePreparation(checkPurchaseOrderIssuePreparation(
      createPurchaseOrderIssuePreparationContext(transaction))).object; return artifacts.preparation
  },
  async createIssueBoundaryContext(preparation) {
    artifacts.context = createPurchaseOrderIssueBoundaryContext(preparation); return artifacts.context
  },
  async evaluateIssuePermission(context) {
    artifacts.decision = evaluatePurchaseOrderIssueBoundary(context); return artifacts.decision
  },
  async saveIssueDecision(decision) {
    const result = savePurchaseOrderIssueDecision(decision); artifacts.decision = result.object; return result
  },
})

const acceptance = validatePurchaseOrderIssueBoundaryProcessAcceptance(walkthrough, artifacts)
const page = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'pages', 'ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const runtimeSource = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'runtime', 'purchaseOrderIssueBoundaryRuntime.js'), 'utf8')
const pageBound = page.includes('data-process-node="SCM_PURCHASE_ORDER_ISSUE_BOUNDARY"')
  && page.includes('purchaseOrderIssueBoundaryActionCodes.createContext')
  && page.includes('purchaseOrderIssueBoundaryActionCodes.evaluatePermission')
  && page.includes('purchaseOrderIssueBoundaryActionCodes.saveDecision')
const noExternalWrite = !runtimeSource.includes('@/api/') && !runtimeSource.includes('../api/') && !runtimeSource.includes('fetch(')
const boundariesProtected = artifacts.decision.purchaseOrderIssued === false
  && artifacts.decision.supplierSent === false && artifacts.decision.goodsReceived === false
  && artifacts.decision.inventoryPosted === false && artifacts.decision.invoiceCreated === false
  && artifacts.decision.paymentCreated === false && artifacts.decision.productionDataWritten === false
const databaseUnchanged = databaseHashBefore === hashDatabase()

const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
})
if (build.status !== 0) { process.stderr.write(build.stdout || ''); process.stderr.write(build.stderr || '') }

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
console.log(passed ? 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_RUNTIME_READY' : 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_RUNTIME_FAILED')
if (!passed) process.exitCode = 1

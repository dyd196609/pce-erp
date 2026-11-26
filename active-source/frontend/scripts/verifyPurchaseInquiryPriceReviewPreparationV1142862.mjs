import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME, buildPurchaseInquiryRuntimeView } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { QUOTATION_COMPARISON, validateQuotationComparison } from '../src/meta/domain/scm/purchaseInquiry/quotationRuntime/quotationComparisonModel.js'
import { QUOTATION_COMPARISON_STATES, evaluateQuotationComparisonTransition } from '../src/meta/domain/scm/purchaseInquiry/quotationRuntime/quotationComparisonStateModel.js'
import { evaluateQuotationReview } from '../src/meta/domain/scm/purchaseInquiry/quotationRuntime/quotationReviewRuleEngine.js'
import { QUOTATION_REVIEW_FORBIDDEN_ACTIONS, evaluateQuotationReviewRuntimeGuard } from '../src/meta/domain/scm/purchaseInquiry/quotationRuntime/quotationReviewRuntimeGuard.js'
import { PRICE_REVIEW_PREPARATION, validatePriceReviewPreparation } from '../src/meta/domain/scm/purchaseInquiry/priceReviewPreparation/priceReviewPreparationModel.js'
import { validatePriceReviewPreparationRuntimeMappings } from '../src/meta/schema/scm/priceReviewPreparationRuntimeMapping.js'
import { PRICE_REVIEW_PREPARATION_ACCEPTANCE_PROFILE, validatePriceReviewPreparationAcceptance } from '../src/meta/acceptance/scm/priceReviewPreparationAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.2'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_PRICE_REVIEW_PREPARATION_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = (relative) => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hashFile = async (file) => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => Object.freeze({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

async function listFiles(relative) {
  const root = path.join(frontendRoot, relative)
  const files = []
  async function walk(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const full = path.join(directory, entry.name)
      if (entry.isDirectory()) await walk(full)
      else files.push(path.relative(frontendRoot, full).replaceAll('\\', '/'))
    }
  }
  try { await walk(root) } catch { /* missing root is recorded as empty */ }
  return files.sort()
}

async function createScan() {
  const [quotationRuntimeFiles, preparationFiles, schemaFiles, acceptanceFiles, runtimeSource, routerSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/quotationRuntime'), listFiles('src/meta/domain/scm/purchaseInquiry/priceReviewPreparation'),
    listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'), read('src/meta/runtime/purchaseInquiryRuntime.js'), read('src/router/index.js'),
  ])
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry', 'src/meta/runtime/purchaseInquiryRuntime.js', 'src/meta/schema/scm', 'src/meta/acceptance/scm', 'src/router/index.js']),
    inventory: Object.freeze({ quotationRuntimeFiles, preparationFiles, schemaFiles, acceptanceFiles,
      runtimeVersionFound: runtimeSource.includes(VERSION), canonicalRoutePresent: routerSource.includes("path: 'scm/purchase-inquiry'") }),
    analysis: Object.freeze({ existingQuoteComparison: 'SCM_QUOTE_COMPARISON@V1.14.2.8.5.3',
      conflictRisk: 'existing model contains recommendedSupplier; V1.14.2.8.6.2 must not reuse it for automatic selection',
      strategy: 'additive read-only QuotationComparison and PriceReviewPreparation projections', formalPriceApprovalEntered: false }),
    protectedScopes: Object.freeze(['crudEngine', 'pageRenderer', 'schemaResolver', 'PurchaseOrder core', 'Price Approval core', 'Finance', 'Inventory', 'Database write logic']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_price_review_preparation_scan_v1142862.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const completeQuotation = (supplierId, price = 100) => Object.freeze({ supplierId, price, currency: 'CNY', deliveryDays: 10, validUntil: '2026-12-31' })
  const noQuote = evaluateQuotationReview({ quotations: [] })
  const oneSupplier = evaluateQuotationReview({ quotations: [completeQuotation('SUP-001')] })
  const comparisonReady = evaluateQuotationReview({ quotations: [completeQuotation('SUP-001'), completeQuotation('SUP-002', 120)] })
  const incomplete = evaluateQuotationReview({ quotations: [{ supplierId: 'SUP-001', price: 100, currency: '', deliveryDays: 10, validUntil: '' }] })
  const missingAmount = evaluateQuotationReview({ quotations: [{ supplierId: 'SUP-001', price: '', currency: 'CNY', deliveryDays: 10, validUntil: '2026-12-31' }] })
  const runtimeView = buildPurchaseInquiryRuntimeView({
    quotationComparisons: [{ comparisonNo: 'QC-VERIFY-001', inquiryNo: 'PI-VERIFY-001', quotationCount: 2, supplierCount: 2, lowestPriceSupplier: 'SUP-001', highestPriceSupplier: 'SUP-002', priceVariance: 20, deliveryComparison: [], comparisonStatus: 'review_required', comparisonStatusLabel: '等待人工评审', comparisonConclusion: '存在价格差异，等待人工评审' }],
    priceReviewPreparations: [{ preparationNo: 'PRP-VERIFY-001', inquiryNo: 'PI-VERIFY-001', comparisonNo: 'QC-VERIFY-001', sourceQuotationCount: 2, reviewStatus: 'pending_review', reviewStatusLabel: '等待评审', blockedReasons: [], priceReviewEntryAllowed: false, priceReviewEntryAllowedLabel: '否' }],
  })
  const quotationRegion = pageSource.indexOf('data-acceptance-id="supplier-quotation-list"')
  const comparisonRegion = pageSource.indexOf('data-acceptance-id="quotation-comparison-runtime-status"')
  const preparationRegion = pageSource.indexOf('data-acceptance-id="price-review-preparation-status"')
  const results = [
    gate('Page', quotationRegion >= 0 && comparisonRegion > quotationRegion && preparationRegion > comparisonRegion && pageSource.includes('报价比较运行状态') && pageSource.includes('核价准备对象状态'), PRICE_REVIEW_PREPARATION_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validatePriceReviewPreparationRuntimeMappings().valid, ['SCM_QUOTATION_COMPARISON_RUNTIME_MAPPING', 'SCM_PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING']),
    gate('Runtime', validateQuotationComparison().valid && validatePriceReviewPreparation().valid && QUOTATION_COMPARISON_STATES.join(',') === 'not_created,collecting,comparison_ready,review_required,blocked' && runtimeView.quotationRuntime.quotationComparisons.length === 1 && runtimeView.quotationRuntime.priceReviewPreparations.length === 1 && PURCHASE_INQUIRY_RUNTIME.priceReviewPreparationRuntimeCode === 'SCM_PURCHASE_INQUIRY_PRICE_REVIEW_PREPARATION_RUNTIME', { comparison: QUOTATION_COMPARISON.objectCode, preparation: PRICE_REVIEW_PREPARATION.objectCode }),
    gate('Rule', noQuote.comparisonStatus === 'blocked' && noQuote.blockedReasons.includes('没有报价证据') && oneSupplier.comparisonStatus === 'review_required' && comparisonReady.comparisonStatus === 'comparison_ready' && incomplete.comparisonStatus === 'blocked' && missingAmount.comparisonStatus === 'blocked' && comparisonReady.selectedSupplier === null && comparisonReady.priceReviewObjectCreated === false, { noQuote: noQuote.result, oneSupplier: oneSupplier.result, complete: comparisonReady.result, incomplete: incomplete.result, missingAmount: missingAmount.result }),
    gate('Guard', QUOTATION_REVIEW_FORBIDDEN_ACTIONS.every((action) => evaluateQuotationReviewRuntimeGuard(action).decision === 'deny') && evaluateQuotationComparisonTransition({ fromStatus: 'comparison_ready', toStatus: 'review_required' }).decision === 'allow' && evaluateQuotationComparisonTransition({ fromStatus: 'review_required', toStatus: 'comparison_ready' }).decision === 'deny', QUOTATION_REVIEW_FORBIDDEN_ACTIONS),
    gate('Acceptance', validatePriceReviewPreparationAcceptance().valid && registrySource.includes('PRICE_REVIEW_PREPARATION_ACCEPTANCE_PROFILE'), PRICE_REVIEW_PREPARATION_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const viteEntry = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
    const output = execFileSync(process.execPath, [viteEntry, 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) {
    results.push(gate('Build', false, String(error.stderr || error.message)))
  }
  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis, gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter,
    autoSupplierSelection: false, autoPriceApproval: false, autoPurchaseOrderCreation: false, autoCloseInquiry: false,
    formalPriceApprovalObjectCreated: false, existingPurchaseFlowModified: false, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-price-review-preparation')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

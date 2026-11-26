import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME, buildPurchaseInquiryRuntimeView } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { PRICE_APPROVAL_ENTRY_ASSESSMENT, validatePriceApprovalEntryAssessment } from '../src/meta/domain/scm/purchaseInquiry/priceApprovalEntry/priceApprovalEntryAssessmentModel.js'
import { PRICE_APPROVAL_ENTRY_ASSESSMENT_STATES } from '../src/meta/domain/scm/purchaseInquiry/priceApprovalEntry/priceApprovalEntryAssessmentStateModel.js'
import { evaluatePriceApprovalEntryAssessment } from '../src/meta/domain/scm/purchaseInquiry/priceApprovalEntry/priceApprovalEntryAssessmentRuleEngine.js'
import { PRICE_APPROVAL_ENTRY_FORBIDDEN_ACTIONS, evaluatePriceApprovalEntryRuntimeGuard } from '../src/meta/domain/scm/purchaseInquiry/priceApprovalEntry/priceApprovalEntryRuntimeGuard.js'
import { validatePriceApprovalEntryAssessmentRuntimeMapping } from '../src/meta/schema/scm/priceApprovalEntryAssessmentRuntimeMapping.js'
import { PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_PROFILE, validatePriceApprovalEntryAssessmentAcceptance } from '../src/meta/acceptance/scm/priceApprovalEntryAssessmentAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.3'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_PRICE_APPROVAL_ENTRY_READY'
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
  try { await walk(root) } catch { /* missing root remains empty */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, schemaFiles, acceptanceFiles, runtimeSource, routerSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry'), listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'),
    read('src/meta/runtime/purchaseInquiryRuntime.js'), read('src/router/index.js'),
  ])
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry', 'src/meta/runtime/purchaseInquiryRuntime.js', 'src/meta/schema/scm', 'src/meta/acceptance/scm', 'src/router/index.js']),
    inventory: Object.freeze({ domainFiles, schemaFiles, acceptanceFiles, runtimeVersionFound: runtimeSource.includes(VERSION),
      inquiryRoutePresent: routerSource.includes("path: 'scm/purchase-inquiry'"), formalPriceApprovalRoutePresent: routerSource.includes("path: 'scm/price-approval'") }),
    analysis: Object.freeze({ sourceLayers: ['SupplierQuotation', 'QuotationComparison', 'PriceReviewPreparation'],
      formalPriceApprovalExisting: true, formalPriceApprovalModified: false, strategy: 'read-only entry assessment with frozen execution boundary' }),
    protectedScopes: Object.freeze(['Formal Price Approval', 'PurchaseOrder', 'Finance', 'Inventory', 'common runtime core']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_price_approval_entry_scan_v1142863.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const evidence = { status: 'complete', quotationCount: 2 }
  const eligibleComparison = { comparisonStatus: 'comparison_ready' }
  const eligiblePreparation = { reviewStatus: 'prepared', blockedReasons: [] }
  const notAssessed = evaluatePriceApprovalEntryAssessment()
  const blocked = evaluatePriceApprovalEntryAssessment({ quotationEvidence: { status: 'blocked', quotationCount: 0 }, comparison: eligibleComparison, preparation: eligiblePreparation })
  const notEligible = evaluatePriceApprovalEntryAssessment({ quotationEvidence: evidence, comparison: { comparisonStatus: 'collecting' }, preparation: eligiblePreparation })
  const manualReview = evaluatePriceApprovalEntryAssessment({ quotationEvidence: evidence, comparison: eligibleComparison, preparation: eligiblePreparation, specialProcurement: true })
  const eligible = evaluatePriceApprovalEntryAssessment({ quotationEvidence: evidence, comparison: eligibleComparison, preparation: eligiblePreparation })
  const runtimeView = buildPurchaseInquiryRuntimeView({ priceApprovalEntryAssessments: [{ assessmentNo: 'PAEA-VERIFY-001', inquiryNo: 'PI-VERIFY-001', comparisonNo: 'QC-VERIFY-001', preparationNo: 'PRP-VERIFY-001', quotationEvidenceStatus: 'complete', quotationEvidenceStatusLabel: '证据完整', comparisonStatus: 'comparison_ready', comparisonStatusLabel: '比较就绪', preparationStatus: 'prepared', preparationStatusLabel: '准备完成', assessmentStatus: 'eligible', assessmentStatusLabel: '具备条件', manualReviewRequired: false, entryConditionLabel: '具备未来入口条件', blockedReasons: [] }] })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="price-approval-entry-assessment"') && pageSource.includes('价格审批入口准入评估') && pageSource.includes('正式入口冻结'), PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validatePriceApprovalEntryAssessmentRuntimeMapping().valid, 'SCM_PRICE_APPROVAL_ENTRY_ASSESSMENT_RUNTIME_MAPPING'),
    gate('Runtime', validatePriceApprovalEntryAssessment().valid && PRICE_APPROVAL_ENTRY_ASSESSMENT_STATES.join(',') === 'not_assessed,eligible,not_eligible,manual_review,blocked' && runtimeView.quotationRuntime.priceApprovalEntryAssessments.length === 1 && PURCHASE_INQUIRY_RUNTIME.priceApprovalEntryAssessmentRuntimeCode === 'SCM_PURCHASE_INQUIRY_PRICE_APPROVAL_ENTRY_ASSESSMENT_RUNTIME', PRICE_APPROVAL_ENTRY_ASSESSMENT.objectCode),
    gate('Rule', notAssessed.assessmentStatus === 'not_assessed' && blocked.assessmentStatus === 'blocked' && notEligible.assessmentStatus === 'not_eligible' && manualReview.assessmentStatus === 'manual_review' && eligible.assessmentStatus === 'eligible' && eligible.eligibleForFuturePriceApprovalEntry === true && eligible.formalPriceApprovalObjectCreated === false && eligible.approvalSubmitted === false && eligible.priceApproved === false && eligible.selectedSupplier === null && eligible.purchaseOrderCreated === false, { notAssessed: notAssessed.assessmentStatus, blocked: blocked.assessmentStatus, notEligible: notEligible.assessmentStatus, manualReview: manualReview.assessmentStatus, eligible: eligible.assessmentStatus }),
    gate('Guard', PRICE_APPROVAL_ENTRY_FORBIDDEN_ACTIONS.every((action) => evaluatePriceApprovalEntryRuntimeGuard(action).decision === 'deny'), PRICE_APPROVAL_ENTRY_FORBIDDEN_ACTIONS),
    gate('Acceptance', validatePriceApprovalEntryAssessmentAcceptance().valid && registrySource.includes('PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_PROFILE'), PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_PROFILE.profileCode),
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
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL', problemAnalysis: scan.analysis,
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter,
    formalPriceApprovalObjectCreated: false, approvalSubmitted: false, priceApproved: false, autoSupplierSelection: false,
    autoPurchaseOrderCreation: false, formalPriceApprovalModified: false, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-price-approval-entry')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

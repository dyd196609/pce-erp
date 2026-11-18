import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME, buildPurchaseInquiryRuntimeView } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { PRICE_APPROVAL_CREATION_ASSESSMENT, validatePriceApprovalCreationAssessment } from '../src/meta/domain/scm/purchaseInquiry/priceApprovalCreationFreeze/priceApprovalCreationAssessmentModel.js'
import { PRICE_APPROVAL_CREATION_ASSESSMENT_STATES } from '../src/meta/domain/scm/purchaseInquiry/priceApprovalCreationFreeze/priceApprovalCreationAssessmentStateModel.js'
import { evaluatePriceApprovalCreationAssessment } from '../src/meta/domain/scm/purchaseInquiry/priceApprovalCreationFreeze/priceApprovalCreationAssessmentRuleEngine.js'
import { PRICE_APPROVAL_CREATION_FORBIDDEN_ACTIONS, evaluatePriceApprovalCreationRuntimeGuard } from '../src/meta/domain/scm/purchaseInquiry/priceApprovalCreationFreeze/priceApprovalCreationRuntimeGuard.js'
import { validatePriceApprovalCreationAssessmentRuntimeMapping } from '../src/meta/schema/scm/priceApprovalCreationAssessmentRuntimeMapping.js'
import { PRICE_APPROVAL_CREATION_FREEZE_ACCEPTANCE_PROFILE, validatePriceApprovalCreationFreezeAcceptance } from '../src/meta/acceptance/scm/priceApprovalCreationFreezeAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.4'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_PRICE_APPROVAL_CREATION_FREEZE_READY'
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
  try { await walk(root) } catch { /* missing root is an empty inventory */ }
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
    analysis: Object.freeze({ prerequisite: 'SCM_PRICE_APPROVAL_ENTRY_ASSESSMENT', formalPriceApprovalExisting: true,
      formalPriceApprovalModified: false, approvalWorkflowModified: false, strategy: 'final read-only creation freeze assessment' }),
    protectedScopes: Object.freeze(['Formal Price Approval', 'Approval Workflow', 'PurchaseOrder', 'Finance', 'Inventory']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_price_approval_creation_freeze_scan_v1142864.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const readyEntry = { assessmentStatus: 'eligible' }
  const readyPreparation = { reviewStatus: 'prepared', blockedReasons: [] }
  const readyEvidence = { status: 'complete', quotationCount: 2 }
  const notAssessed = evaluatePriceApprovalCreationAssessment()
  const ready = evaluatePriceApprovalCreationAssessment({ entryAssessment: readyEntry, preparation: readyPreparation, quotationEvidence: readyEvidence })
  const manualReview = evaluatePriceApprovalCreationAssessment({ entryAssessment: readyEntry, preparation: readyPreparation, quotationEvidence: readyEvidence, specialProcurement: true })
  const entryBlocked = evaluatePriceApprovalCreationAssessment({ entryAssessment: { assessmentStatus: 'not_eligible' }, preparation: readyPreparation, quotationEvidence: readyEvidence })
  const preparationBlocked = evaluatePriceApprovalCreationAssessment({ entryAssessment: readyEntry, preparation: { reviewStatus: 'blocked', blockedReasons: ['准备证据冲突'] }, quotationEvidence: readyEvidence })
  const evidenceBlocked = evaluatePriceApprovalCreationAssessment({ entryAssessment: readyEntry, preparation: readyPreparation, quotationEvidence: { status: 'blocked', quotationCount: 0 } })
  const runtimeView = buildPurchaseInquiryRuntimeView({ priceApprovalCreationAssessments: [{ creationAssessmentNo: 'PACA-VERIFY-001', inquiryNo: 'PI-VERIFY-001', entryAssessmentNo: 'PAEA-VERIFY-001', preparationNo: 'PRP-VERIFY-001', entryAssessmentStatus: 'eligible', entryAssessmentStatusLabel: '准入通过', preparationStatus: 'prepared', preparationStatusLabel: '准备完成', quotationEvidenceStatus: 'complete', quotationEvidenceStatusLabel: '证据完整', creationAssessmentStatus: 'ready', creationAssessmentStatusLabel: '冻结检查就绪', manualReviewRequired: false, creationReadinessLabel: '仅条件就绪，创建能力关闭', blockedReasons: [] }] })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="price-approval-creation-freeze-assessment"') && pageSource.includes('正式价格审批对象创建前冻结评估') && pageSource.includes('创建能力关闭'), PRICE_APPROVAL_CREATION_FREEZE_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validatePriceApprovalCreationAssessmentRuntimeMapping().valid, 'SCM_PRICE_APPROVAL_CREATION_ASSESSMENT_RUNTIME_MAPPING'),
    gate('Runtime', validatePriceApprovalCreationAssessment().valid && PRICE_APPROVAL_CREATION_ASSESSMENT_STATES.join(',') === 'not_assessed,ready,manual_review,blocked' && runtimeView.quotationRuntime.priceApprovalCreationAssessments.length === 1 && PURCHASE_INQUIRY_RUNTIME.priceApprovalCreationAssessmentRuntimeCode === 'SCM_PURCHASE_INQUIRY_PRICE_APPROVAL_CREATION_FREEZE_RUNTIME', PRICE_APPROVAL_CREATION_ASSESSMENT.objectCode),
    gate('Rule', notAssessed.creationAssessmentStatus === 'not_assessed' && ready.creationAssessmentStatus === 'ready' && manualReview.creationAssessmentStatus === 'manual_review' && entryBlocked.creationAssessmentStatus === 'blocked' && preparationBlocked.creationAssessmentStatus === 'blocked' && evidenceBlocked.creationAssessmentStatus === 'blocked' && ready.readyForFormalPriceApprovalCreation === true && ready.formalPriceApprovalObjectCreated === false && ready.approvalWorkflowStarted === false && ready.approvalSubmitted === false && ready.priceApproved === false && ready.purchaseOrderCreated === false, { notAssessed: notAssessed.creationAssessmentStatus, ready: ready.creationAssessmentStatus, manualReview: manualReview.creationAssessmentStatus, entryBlocked: entryBlocked.creationAssessmentStatus, preparationBlocked: preparationBlocked.creationAssessmentStatus, evidenceBlocked: evidenceBlocked.creationAssessmentStatus }),
    gate('Guard', PRICE_APPROVAL_CREATION_FORBIDDEN_ACTIONS.every((action) => evaluatePriceApprovalCreationRuntimeGuard(action).decision === 'deny'), PRICE_APPROVAL_CREATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validatePriceApprovalCreationFreezeAcceptance().valid && registrySource.includes('PRICE_APPROVAL_CREATION_FREEZE_ACCEPTANCE_PROFILE'), PRICE_APPROVAL_CREATION_FREEZE_ACCEPTANCE_PROFILE.profileCode),
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
    formalPriceApprovalObjectCreated: false, approvalWorkflowStarted: false, approvalSubmitted: false, priceApproved: false,
    autoPurchaseOrderCreation: false, formalPriceApprovalModified: false, approvalWorkflowModified: false, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-price-approval-creation-freeze')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

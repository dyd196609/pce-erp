import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT, validateFormalPriceApprovalFinalReleaseAgreement } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementModel.js'
import { FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_CHECKLIST, evaluateFormalPriceApprovalFinalReleaseAgreementChecklist } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementChecklist.js'
import { evaluateFormalPriceApprovalFinalReleaseAgreement } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalFinalReleaseAgreementGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementGuard.js'
import { FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_PROFILE, validateFormalPriceApprovalReleaseAgreementAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalReleaseAgreementAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.13'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, modelSource, checklistSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementChecklist.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementGuard.js'),
  ])
  const dependencyImportSource = `${modelSource}\n${checklistSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  const executionOrPersistenceImports = /dataGateway|transactionEngine|workflowEngine|commandDispatcher/i.test(dependencyImportSource)
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    scope: Object.freeze([
      'src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject',
      'src/meta/runtime',
      'src/meta/schema/scm',
      'src/meta/acceptance/scm',
    ]),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles,
      agreementModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementModel.js'),
      checklistPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAgreementChecklist.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SANDBOX + SCM_FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION',
      designTarget: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT.agreementCode,
      checklistItemCount: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_CHECKLIST.length,
      requesterReviewerSeparationRequired: true,
      reviewerExecutorSeparationRequired: true,
      agreementIsExecution: false,
      executionOrPersistenceImports,
      strategy: 'human responsibility agreement with segregated roles and a non-executable seven-item checklist',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object instances', 'Command execution', 'Approval Workflow', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_release_agreement_scan_v11428613.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const agreementInput = Object.freeze({
    agreementRequested: true,
    requesterId: 'requester-a',
    reviewerId: 'reviewer-b',
    executorRoleId: 'executor-role-c',
    finalReleaseStatus: 'ready',
    sandboxStatus: 'completed',
    humanConfirmationStatus: 'confirmed_design_only',
    responsibilityAcknowledged: true,
    reviewMode: 'human',
  })
  const notRequested = evaluateFormalPriceApprovalFinalReleaseAgreement({})
  const agreed = evaluateFormalPriceApprovalFinalReleaseAgreement(agreementInput)
  const pending = evaluateFormalPriceApprovalFinalReleaseAgreement({ ...agreementInput, responsibilityAcknowledged: false })
  const sameRequesterReviewer = evaluateFormalPriceApprovalFinalReleaseAgreement({ ...agreementInput, reviewerId: 'requester-a' })
  const sameReviewerExecutor = evaluateFormalPriceApprovalFinalReleaseAgreement({ ...agreementInput, executorRoleId: 'reviewer-b' })
  const automaticReview = evaluateFormalPriceApprovalFinalReleaseAgreement({ ...agreementInput, reviewMode: 'automatic' })
  const checklist = evaluateFormalPriceApprovalFinalReleaseAgreementChecklist({
    ...agreementInput,
    requesterReviewerSeparated: true,
    reviewerExecutorSeparated: true,
  })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-final-release-agreement"')
      && pageSource.includes('最终人工放行责任协议')
      && pageSource.includes('Requester ≠ Reviewer')
      && pageSource.includes('Reviewer ≠ Executor')
      && pageSource.includes('Agreement ≠ Execution'), FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalFinalReleaseAgreement().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT.persistenceMode === 'none', {
        agreementFields: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT.fields,
        lifecycle: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT.lifecycle,
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFinalReleaseAgreementCode === FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT.agreementCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFinalReleaseAgreementExecutionPermission === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFinalReleaseAgreementInstanceCount === 0
      && FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT.agreementInstanceCount === 0
      && FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_CHECKLIST.length === 7
      && checklist.complete === true, {
        agreementCode: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT.agreementCode,
        checklistItemCount: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_CHECKLIST.length,
        agreementInstanceCount: 0,
      }),
    gate('Rule', notRequested.evaluatedStatus === 'not_requested'
      && agreed.evaluatedStatus === 'agreed_design_only'
      && agreed.requesterReviewerSeparated === true
      && agreed.reviewerExecutorSeparated === true
      && pending.evaluatedStatus === 'pending_review'
      && sameRequesterReviewer.evaluatedStatus === 'rejected'
      && sameRequesterReviewer.requesterReviewerSeparated === false
      && sameReviewerExecutor.evaluatedStatus === 'rejected'
      && sameReviewerExecutor.reviewerExecutorSeparated === false
      && automaticReview.evaluatedStatus === 'rejected'
      && [notRequested, agreed, pending, sameRequesterReviewer, sameReviewerExecutor, automaticReview].every((result) => result.agreementInstanceCreated === false
        && result.executionPermissionGranted === false
        && result.commandExecuted === false
        && result.formalPriceApprovalObjectCreated === false
        && result.approvalWorkflowStarted === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false), {
        agreed: agreed.evaluatedStatus,
        pending: pending.evaluatedStatus,
        requesterReviewerConflict: sameRequesterReviewer.evaluatedStatus,
        reviewerExecutorConflict: sameReviewerExecutor.evaluatedStatus,
        automaticReview: automaticReview.evaluatedStatus,
      }),
    gate('Guard', evaluateFormalPriceApprovalFinalReleaseAgreementGuard({ action: 'reviewAgreement', requesterId: 'requester-a', reviewerId: 'reviewer-b', executorRoleId: 'executor-c', reviewMode: 'human' }).decision === 'allow_agreement_review_only'
      && evaluateFormalPriceApprovalFinalReleaseAgreementGuard({ action: 'reviewAgreement', requesterId: 'same', reviewerId: 'same', executorRoleId: 'executor-c', reviewMode: 'human' }).decision === 'deny'
      && evaluateFormalPriceApprovalFinalReleaseAgreementGuard({ action: 'reviewAgreement', requesterId: 'requester-a', reviewerId: 'reviewer-b', executorRoleId: 'reviewer-b', reviewMode: 'human' }).decision === 'deny'
      && evaluateFormalPriceApprovalFinalReleaseAgreementGuard({ action: 'reviewAgreement', requesterId: 'requester-a', reviewerId: 'reviewer-b', executorRoleId: 'executor-c', reviewMode: 'automatic' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalFinalReleaseAgreementGuard({ action })
        return result.decision === 'deny' && result.executionPermissionGranted === false && result.formalPriceApprovalObjectCreated === false
      }), FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalReleaseAgreementAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_PROFILE.profileCode),
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
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.executionOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis,
    gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    checklistItemCount: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_CHECKLIST.length,
    requesterEqualsReviewerAllowed: false,
    reviewerEqualsExecutorAllowed: false,
    agreementIsExecution: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    agreementPersisted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-release-agreement')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

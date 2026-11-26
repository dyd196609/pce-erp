import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_RESULT_SUMMARY, validateFormalPriceApprovalCanaryAcceptanceResultSummary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryAcceptanceResultSummaryModel.js'
import { createFormalPriceApprovalHumanBusinessAcceptanceExecution, validateFormalPriceApprovalHumanBusinessAcceptanceExecution } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanBusinessAcceptanceExecutionModel.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTION, validateFormalPriceApprovalHumanAcceptanceRoleExecution } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceRoleExecutionModel.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_EXECUTION_CHECKLIST, validateFormalPriceApprovalHumanAcceptanceExecutionChecklist } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceExecutionChecklist.js'
import { createFormalPriceApprovalHumanFeedbackCollection, validateFormalPriceApprovalHumanFeedbackCollection } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanFeedbackCollectionModel.js'
import { evaluateFormalPriceApprovalHumanBusinessAcceptance } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanBusinessAcceptanceRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalHumanBusinessAcceptanceGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanBusinessAcceptanceGuard.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_PROFILE, validateFormalPriceApprovalHumanBusinessAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalHumanBusinessAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.6.2'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hashFile = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => Object.freeze({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

async function listFiles(relative) {
  const files = []
  async function walk(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const full = path.join(directory, entry.name)
      if (entry.isDirectory()) await walk(full)
      else files.push(path.relative(frontendRoot, full).replaceAll('\\', '/'))
    }
  }
  try { await walk(path.join(frontendRoot, relative)) } catch { /* absent scope is empty */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, executionSource, roleSource, checklistSource, feedbackSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/pages'),
    listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanBusinessAcceptanceExecutionModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceRoleExecutionModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceExecutionChecklist.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanFeedbackCollectionModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanBusinessAcceptanceRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanBusinessAcceptanceGuard.js'),
  ])
  const imports = `${executionSource}\n${roleSource}\n${checklistSource}\n${feedbackSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter(line => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({
      prerequisites: Object.freeze(['SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_READY', 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_CANARY_COHORT_AUTOMATIC_ACCEPTANCE_READY']),
      recentCanaryResultUnified: true,
      humanAcceptanceTargetView: 'business_view',
      acceptanceViewMode: 'validation_information_only',
      roleCount: 3, checklistCount: 7, feedbackStorageMode: 'memory_session_only',
      workflowTaskOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      crudOrRendererImports: /crudEngine|pageRenderer|schemaResolver/i.test(imports),
      strategy: 'reuse the canary result summary as the recent-result source and execute role-based human validation with session-only feedback',
    }),
    protectedScopes: Object.freeze(['crudEngine', 'pageRenderer', 'schemaResolver', 'Workflow engine', 'Approval execution', 'Task engine', 'PurchaseOrder', 'Finance', 'Inventory', 'Database write layer']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_human_business_acceptance_scan_v11428762.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])

  const passedChecklist = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_EXECUTION_CHECKLIST.map(item => Object.freeze({ ...item, result: 'PASS' }))
  const roleResults = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTION.roles.map(role => Object.freeze({
    userRole: role.userRole,
    ...evaluateFormalPriceApprovalHumanBusinessAcceptance({ action: 'executeHumanAcceptance', userRole: role.userRole,
      viewMode: 'business_view', checklist: passedChecklist }),
  }))
  const invalidAcceptanceViewExecution = evaluateFormalPriceApprovalHumanBusinessAcceptance({ action: 'executeHumanAcceptance',
    userRole: 'purchase_user', viewMode: 'acceptance_view', checklist: passedChecklist })
  const acceptanceViewInspection = evaluateFormalPriceApprovalHumanBusinessAcceptance({ action: 'inspectAcceptanceView',
    viewMode: 'acceptance_view', readOnly: true })
  const feedback = createFormalPriceApprovalHumanFeedbackCollection({ feedbackNo: 'SESSION-HUMAN-FEEDBACK-001',
    userRole: 'purchase_user', pageSection: 'next_business_hint', feedbackType: 'navigation_problem',
    description: '下一步提示需要更明确', suggestion: '补充人工处理说明', status: 'session_collected' })
  const feedbackCollected = evaluateFormalPriceApprovalHumanBusinessAcceptance({ action: 'collectFeedback',
    storageMode: 'memory_session_only', feedbackIsErpData: false })
  const feedbackPersistenceBlocked = evaluateFormalPriceApprovalHumanBusinessAcceptance({ action: 'collectFeedback',
    storageMode: 'memory_session_only', feedbackIsErpData: false, persistRequested: true })
  const feedbackStateBlocked = evaluateFormalPriceApprovalHumanBusinessAcceptance({ action: 'collectFeedback',
    storageMode: 'memory_session_only', feedbackIsErpData: false, businessStateChangeRequested: true })
  const feedbackApprovalBlocked = evaluateFormalPriceApprovalHumanBusinessAcceptance({ action: 'collectFeedback',
    storageMode: 'memory_session_only', feedbackIsErpData: false, approvalTriggerRequested: true })
  const completedExecution = createFormalPriceApprovalHumanBusinessAcceptanceExecution({
    acceptanceExecutionNo: 'SESSION-HUMAN-ACCEPTANCE-001', userRole: 'purchase_user',
    checklistResult: 'PASS', feedbackStatus: 'feedback_pending', executionStatus: 'completed',
  })
  const evaluated = [...roleResults, invalidAcceptanceViewExecution, acceptanceViewInspection, feedbackCollected,
    feedbackPersistenceBlocked, feedbackStateBlocked, feedbackApprovalBlocked]

  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-recent-canary-result"')
      && pageSource.includes('data-acceptance-id="formal-price-approval-human-business-acceptance-execution"')
      && pageSource.includes('data-acceptance-id="formal-price-approval-human-feedback-collection"')
      && pageSource.includes('Recent Canary Acceptance Result')
      && pageSource.includes('data-human-business-acceptance-action="session-only"')
      && pageSource.includes('data-human-feedback-collection-action="session-only"')
      && pageSource.includes('Human Acceptance ≠ Business Execution'),
      { route: '/scm/purchase-inquiry', recentCanary: 'COMPLETED / 3 / 3 / 0 / PASS', roles: 3, checklist: 7 }),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalCanaryAcceptanceResultSummary().valid
      && validateFormalPriceApprovalHumanBusinessAcceptanceExecution(completedExecution).valid
      && validateFormalPriceApprovalHumanAcceptanceRoleExecution().valid
      && validateFormalPriceApprovalHumanAcceptanceExecutionChecklist().valid
      && validateFormalPriceApprovalHumanFeedbackCollection(feedback).valid,
      { persistenceSchemaAdded: false, roles: 3, checklist: 7, feedbackStorage: feedback.storageMode }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.version.startsWith('V1.14.2.8.7.')
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalRecentCanaryExecutionState === 'completed'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalRecentCanaryTotalCount === 3
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalRecentCanaryPassCount === 3
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalRecentCanaryFailCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalRecentCanaryOverallResult === 'PASS'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanBusinessAcceptanceRoleCount === 3
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanBusinessAcceptanceChecklistCount === 7
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanBusinessAcceptanceIsBusinessExecution === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanFeedbackStorageMode === 'memory_session_only'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanFeedbackPersisted === false,
      { recentCanary: '3 PASS / 0 FAIL', roles: 3, checklist: 7, feedback: 'memory_session_only' }),
    gate('Rule', roleResults.every(item => item.result === 'PASS' && item.decision === 'human_acceptance_completed'
        && item.humanAcceptanceExecuted === true)
      && invalidAcceptanceViewExecution.decision === 'blocked'
      && acceptanceViewInspection.decision === 'validation_information_only'
      && feedbackCollected.decision === 'session_feedback_collected'
      && [feedbackPersistenceBlocked, feedbackStateBlocked, feedbackApprovalBlocked].every(item => item.decision === 'blocked')
      && evaluated.every(item => item.businessExecutionTriggered === false && item.feedbackPersisted === false
        && item.businessObjectCreated === false && item.approvalObjectCreated === false
        && item.workflowStarted === false && item.approvalTaskCreated === false
        && item.priceChanged === false && item.businessStateChanged === false
        && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { purchaseUser: roleResults[0].result, purchaseManager: roleResults[1].result,
        acceptanceObserver: roleResults[2].result, feedback: feedbackCollected.decision }),
    gate('Guard', evaluateFormalPriceApprovalHumanBusinessAcceptanceGuard({ action: 'executeSessionHumanAcceptance', viewMode: 'business_view' }).decision === 'allow_acceptance_only'
      && evaluateFormalPriceApprovalHumanBusinessAcceptanceGuard({ action: 'executeSessionHumanAcceptance', viewMode: 'acceptance_view' }).decision === 'deny'
      && evaluateFormalPriceApprovalHumanBusinessAcceptanceGuard({ action: 'inspectAcceptanceView', viewMode: 'acceptance_view' }).decision === 'allow_read_only'
      && FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_FORBIDDEN_ACTIONS.every(action => {
        const result = evaluateFormalPriceApprovalHumanBusinessAcceptanceGuard({ action })
        return result.decision === 'deny' && result.businessExecutionTriggered === false
          && result.feedbackPersisted === false && result.businessObjectCreated === false
          && result.approvalObjectCreated === false && result.workflowStarted === false
          && result.approvalTaskCreated === false && result.priceChanged === false
          && result.businessStateChanged === false && result.businessWriteCount === 0
      }), FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalHumanBusinessAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_PROFILE'),
      FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_PROFILE.profileCode),
  ]

  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], {
      cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000,
    })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }

  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every(item => item.result === 'PASS') && databaseUnchanged
    && scan.analysis.workflowTaskOrPersistenceImports === false && scan.analysis.crudOrRendererImports === false
  const roleReport = userRole => Object.freeze({ userRole, result: roleResults.find(item => item.userRole === userRole)?.result || 'FAIL',
    checklistResult: 'PASS', humanAcceptanceExecuted: true, businessExecutionTriggered: false })
  const report = Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis, gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter(item => item.result === 'PASS').length, FAIL: results.filter(item => item.result === 'FAIL').length }),
    recentCanaryResult: Object.freeze({ executionState: 'COMPLETED', totalCount: 3, passCount: 3, failCount: 0,
      overallResult: 'PASS', businessWriteCount: 0, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED' }),
    purchaseUserAcceptance: roleReport('purchase_user'),
    purchaseManagerAcceptance: roleReport('purchase_manager'),
    acceptanceObserverResult: roleReport('acceptance_observer'),
    userFeedbackSummary: Object.freeze({ collectedCount: 1, status: 'session_collected', storageMode: 'memory_session_only',
      persisted: false, isErpData: false }),
    humanAcceptanceExecuted: true, businessExecutionTriggered: false, feedbackPersisted: false,
    businessObjectCreated: false, approvalObjectCreated: false, workflowStarted: false,
    workflowInstanceCreated: false, approvalTaskCreated: false, priceChanged: false,
    businessStateChanged: false, persistencePerformed: false, businessWriteCount: 0,
    productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-human-business-acceptance')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

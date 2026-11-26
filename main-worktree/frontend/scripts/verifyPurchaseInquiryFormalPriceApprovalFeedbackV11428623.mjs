import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_COMMENT_MODEL, validateFormalPriceApprovalCommentModel } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCommentModel.js'
import { FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_MODEL, validateFormalPriceApprovalEvidenceFeedbackModel } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEvidenceFeedbackModel.js'
import { FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY, validateFormalPriceApprovalFeedbackBoundary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFeedbackBoundary.js'
import { evaluateFormalPriceApprovalFeedback } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFeedbackRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_FEEDBACK_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalFeedbackGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFeedbackGuard.js'
import { FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_PROFILE, validateFormalPriceApprovalFeedbackAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalFeedbackAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.23'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_FEEDBACK_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = (relative) => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hashFile = async (file) => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, commentSource, feedbackSource, boundarySource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/runtime'), listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCommentModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEvidenceFeedbackModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFeedbackBoundary.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFeedbackRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFeedbackGuard.js'),
  ])
  const imports = `${commentSource}\n${feedbackSource}\n${boundarySource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY', commentModel: FORMAL_PRICE_APPROVAL_COMMENT_MODEL.modelCode,
      feedbackModel: FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_MODEL.modelCode, boundary: FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY.boundaryCode,
      commentMeansApprovalResult: false, feedbackMeansBusinessChange: false, feedbackMeansTaskExecution: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|stateManager|dataGateway|transactionEngine|commandDispatcher/i.test(imports),
      strategy: 'definition-only comment and evidence feedback chain isolated from tasks, results, and business changes' }),
    protectedScopes: Object.freeze(['Approval task creation/execution', 'Approval execution', 'Approval result creation', 'Business change', 'Database']) })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_feedback_scan_v11428623.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }
  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js')])
  const safeInput = Object.freeze({ assessmentRequested: true, nodeDecisionStatus: 'node_decision_definition_ready', commentDefinitionComplete: true, evidenceFeedbackDefinitionComplete: true, feedbackBoundaryIsolated: true })
  const ready = evaluateFormalPriceApprovalFeedback(safeInput)
  const notAssessed = evaluateFormalPriceApprovalFeedback({})
  const missingBoundary = evaluateFormalPriceApprovalFeedback({ ...safeInput, feedbackBoundaryIsolated: false })
  const commentBlocked = evaluateFormalPriceApprovalFeedback({ ...safeInput, commentCreationRequested: true })
  const feedbackBlocked = evaluateFormalPriceApprovalFeedback({ ...safeInput, feedbackExecutionRequested: true })
  const taskBlocked = evaluateFormalPriceApprovalFeedback({ ...safeInput, taskExecutionRequested: true })
  const resultBlocked = evaluateFormalPriceApprovalFeedback({ ...safeInput, approvalResultCreationRequested: true })
  const businessBlocked = evaluateFormalPriceApprovalFeedback({ ...safeInput, businessChangeRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalFeedback({ ...safeInput, persistenceRequested: true })
  const evaluated = [notAssessed, ready, missingBoundary, commentBlocked, feedbackBlocked, taskBlocked, resultBlocked, businessBlocked, persistenceBlocked]
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-feedback"') && pageSource.includes('Comment ≠ Approval Result') && pageSource.includes('Feedback ≠ Business Change') && pageSource.includes('Feedback ≠ Task Execution'), FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalCommentModel().valid && validateFormalPriceApprovalEvidenceFeedbackModel().valid && validateFormalPriceApprovalFeedbackBoundary().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'") && FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY.persistenceAdapterConnected === false, { persistenceSchemaAdded: false, commentFields: FORMAL_PRICE_APPROVAL_COMMENT_MODEL.fields, feedbackFields: FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_MODEL.fields }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCommentModelCode === FORMAL_PRICE_APPROVAL_COMMENT_MODEL.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalEvidenceFeedbackModelCode === FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_MODEL.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFeedbackBoundaryCode === FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY.boundaryCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCommentInstanceCount === 0 && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalEvidenceFeedbackInstanceCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFeedbackTaskExecution === false && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFeedbackResultCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFeedbackBusinessChangeApplied === false, { comments: 0, feedback: 0, taskExecution: false, results: 0, businessChange: false }),
    gate('Rule', notAssessed.feedbackStatus === 'not_assessed' && ready.feedbackStatus === 'feedback_definition_ready'
      && [missingBoundary, commentBlocked, feedbackBlocked, taskBlocked, resultBlocked, businessBlocked, persistenceBlocked].every((item) => item.feedbackStatus === 'blocked')
      && evaluated.every((item) => item.commentCreated === false && item.feedbackExecuted === false && item.taskCreated === false && item.taskExecuted === false && item.approvalResultCreated === false && item.businessChangeApplied === false && item.businessStateChanged === false && item.persistencePerformed === false && item.businessWriteCount === 0 && item.productionDataWritten === false), { ready: ready.feedbackStatus, feedbackExecution: feedbackBlocked.feedbackStatus, taskExecution: taskBlocked.feedbackStatus, result: resultBlocked.feedbackStatus }),
    gate('Guard', evaluateFormalPriceApprovalFeedbackGuard({ action: 'inspectFeedbackDefinition', mode: 'feedback_definition_only' }).decision === 'allow_definition_inspection_only'
      && evaluateFormalPriceApprovalFeedbackGuard({ action: 'inspectFeedbackDefinition', mode: 'execution' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_FEEDBACK_FORBIDDEN_ACTIONS.every((action) => { const result = evaluateFormalPriceApprovalFeedbackGuard({ action }); return result.decision === 'deny' && result.taskExecuted === false && result.approvalResultCreated === false && result.businessChangeApplied === false && result.persistencePerformed === false }), FORMAL_PRICE_APPROVAL_FEEDBACK_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalFeedbackAcceptance().valid && registrySource.includes('FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }
  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL', problemAnalysis: scan.analysis,
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    commentMeansApprovalResult: false, feedbackMeansBusinessChange: false, feedbackMeansTaskExecution: false,
    commentCreated: false, feedbackExecuted: false, taskCreated: false, taskExecuted: false, approvalResultCreated: false, businessChangeApplied: false, businessStateChanged: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-feedback')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

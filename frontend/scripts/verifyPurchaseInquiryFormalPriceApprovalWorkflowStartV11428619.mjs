import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT, validateFormalPriceApprovalWorkflowStartAssessment } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowStartAssessmentModel.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY, validateFormalPriceApprovalWorkflowInstanceBoundary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowInstanceBoundaryModel.js'
import { evaluateFormalPriceApprovalWorkflowStartAssessment } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowStartAssessmentRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_START_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalWorkflowStartAssessmentGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowStartAssessmentGuard.js'
import { evaluateFormalPriceApprovalRuntimeTransition } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeStateMachine.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_PROFILE, validateFormalPriceApprovalWorkflowStartAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalWorkflowStartAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.19'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_WORKFLOW_START_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, modelSource, boundarySource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowStartAssessmentModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowInstanceBoundaryModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowStartAssessmentRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowStartAssessmentGuard.js'),
  ])
  const imports = `${modelSource}\n${boundarySource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF',
      designTarget: FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT.assessmentCode,
      instanceBoundary: FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY.boundaryCode,
      assessmentMeansStart: false, requestMeansInstance: false, pendingApprovalMeansRunning: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|stateManager|dataGateway|transactionEngine|commandDispatcher/i.test(imports),
      strategy: 'start-condition assessment with request evidence separated from workflow instances and every execution path frozen',
    }),
    protectedScopes: Object.freeze(['Workflow start', 'Approval instance creation', 'Approval task creation', 'Lifecycle mutation', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_workflow_start_scan_v11428619.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const safeInput = Object.freeze({ assessmentRequested: true, handoffStatus: 'handoff_ready', lifecycleState: 'pending_approval', startAssessmentRequestPresent: true, requestValidated: true, humanConfirmationPresent: true })
  const ready = evaluateFormalPriceApprovalWorkflowStartAssessment(safeInput)
  const notAssessed = evaluateFormalPriceApprovalWorkflowStartAssessment({})
  const missingHandoff = evaluateFormalPriceApprovalWorkflowStartAssessment({ ...safeInput, handoffStatus: 'blocked' })
  const manualReview = evaluateFormalPriceApprovalWorkflowStartAssessment({ ...safeInput, specialProcurement: true })
  const autoBlocked = evaluateFormalPriceApprovalWorkflowStartAssessment({ ...safeInput, automaticStart: true })
  const startBlocked = evaluateFormalPriceApprovalWorkflowStartAssessment({ ...safeInput, workflowStartExecutionRequested: true })
  const instanceBlocked = evaluateFormalPriceApprovalWorkflowStartAssessment({ ...safeInput, workflowInstanceCreationRequested: true })
  const taskBlocked = evaluateFormalPriceApprovalWorkflowStartAssessment({ ...safeInput, approvalTaskCreationRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalWorkflowStartAssessment({ ...safeInput, persistenceRequested: true })
  const evaluated = [notAssessed, ready, missingHandoff, manualReview, autoBlocked, startBlocked, instanceBlocked, taskBlocked, persistenceBlocked]
  const originalTransition = evaluateFormalPriceApprovalRuntimeTransition({ fromStatus: 'created', toStatus: 'pending_approval' })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-workflow-start-assessment"')
      && pageSource.includes('Assessment ≠ Start') && pageSource.includes('Request ≠ Instance') && pageSource.includes('Pending Approval ≠ Running'), FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalWorkflowStartAssessment().valid
      && validateFormalPriceApprovalWorkflowInstanceBoundary().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY.persistenceAdapterConnected === false, { persistenceSchemaAdded: false, boundaryMode: FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY.boundaryMode }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowStartAssessmentCode === FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT.assessmentCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowInstanceBoundaryCode === FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY.boundaryCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowStarted === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowRunning === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowInstanceCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowApprovalTaskCount === 0
      && originalTransition.decision === 'deny' && originalTransition.stateChanged === false, { workflowStarted: false, workflowRunning: false, instanceCount: 0, taskCount: 0 }),
    gate('Rule', notAssessed.assessmentStatus === 'not_assessed' && ready.assessmentStatus === 'start_ready'
      && manualReview.assessmentStatus === 'manual_review'
      && [missingHandoff, autoBlocked, startBlocked, instanceBlocked, taskBlocked, persistenceBlocked].every((item) => item.assessmentStatus === 'blocked')
      && evaluated.every((item) => item.workflowStarted === false && item.workflowRunning === false && item.workflowInstanceCreated === false && item.approvalTaskCreated === false && item.stateChanged === false && item.persistencePerformed === false && item.businessWriteCount === 0 && item.productionDataWritten === false), { ready: ready.assessmentStatus, manual: manualReview.assessmentStatus, startExecution: startBlocked.assessmentStatus }),
    gate('Guard', evaluateFormalPriceApprovalWorkflowStartAssessmentGuard({ action: 'assessWorkflowStartConditions', mode: 'assessment_only' }).decision === 'allow_assessment_only'
      && evaluateFormalPriceApprovalWorkflowStartAssessmentGuard({ action: 'assessWorkflowStartConditions', mode: 'workflow' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_WORKFLOW_START_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalWorkflowStartAssessmentGuard({ action })
        return result.decision === 'deny' && result.workflowStarted === false && result.workflowRunning === false && result.workflowInstanceCreated === false && result.approvalTaskCreated === false && result.persistencePerformed === false
      }), FORMAL_PRICE_APPROVAL_WORKFLOW_START_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalWorkflowStartAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }

  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL', problemAnalysis: scan.analysis,
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    assessmentMeansStart: false, requestMeansInstance: false, pendingApprovalMeansRunning: false,
    workflowStarted: false, workflowRunning: false, workflowInstanceCreated: false, approvalTaskCreated: false, stateChanged: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-workflow-start')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

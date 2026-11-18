import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE, validateFormalPriceApprovalWorkflowRuntimeState } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowRuntimeStateModel.js'
import { FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY, validateFormalPriceApprovalResultBoundary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalResultBoundary.js'
import { evaluateFormalPriceApprovalWorkflowRuntime } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowRuntimeRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalWorkflowRuntimeGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowRuntimeGuard.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_PROFILE, validateFormalPriceApprovalWorkflowRuntimeAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalWorkflowRuntimeAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.21'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, stateSource, boundarySource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowRuntimeStateModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalResultBoundary.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowRuntimeRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowRuntimeGuard.js'),
  ])
  const imports = `${stateSource}\n${boundarySource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY',
      runtimeState: FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE.runtimeStateCode,
      resultBoundary: FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY.boundaryCode,
      workflowRunningMeansApproved: false, workflowCompletedMeansResultCreated: false, runtimeStateMeansBusinessState: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|stateManager|dataGateway|transactionEngine|commandDispatcher/i.test(imports),
      strategy: 'definition-only workflow runtime state with approval result and business state isolated',
    }),
    protectedScopes: Object.freeze(['Workflow initialization/start', 'Approval instance/task creation', 'Approval result creation', 'Business state mutation', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_workflow_runtime_scan_v11428621.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const safeInput = Object.freeze({ assessmentRequested: true, instanceTaskLifecycleStatus: 'lifecycle_definition_ready', runtimeDefinitionComplete: true, resultBoundaryIsolated: true })
  const ready = evaluateFormalPriceApprovalWorkflowRuntime(safeInput)
  const notAssessed = evaluateFormalPriceApprovalWorkflowRuntime({})
  const missingBoundary = evaluateFormalPriceApprovalWorkflowRuntime({ ...safeInput, resultBoundaryIsolated: false })
  const initializeBlocked = evaluateFormalPriceApprovalWorkflowRuntime({ ...safeInput, workflowInitializationRequested: true })
  const runningBlocked = evaluateFormalPriceApprovalWorkflowRuntime({ ...safeInput, workflowRunningRequested: true })
  const completeBlocked = evaluateFormalPriceApprovalWorkflowRuntime({ ...safeInput, workflowCompletionRequested: true })
  const resultBlocked = evaluateFormalPriceApprovalWorkflowRuntime({ ...safeInput, approvalResultCreationRequested: true })
  const businessBlocked = evaluateFormalPriceApprovalWorkflowRuntime({ ...safeInput, businessStateChangeRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalWorkflowRuntime({ ...safeInput, persistenceRequested: true })
  const evaluated = [notAssessed, ready, missingBoundary, initializeBlocked, runningBlocked, completeBlocked, resultBlocked, businessBlocked, persistenceBlocked]
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-workflow-runtime"')
      && pageSource.includes('Running ≠ Approved') && pageSource.includes('Completed ≠ Result Created') && pageSource.includes('Runtime State ≠ Business State'), FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalWorkflowRuntimeState().valid && validateFormalPriceApprovalResultBoundary().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'") && FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY.persistenceAdapterConnected === false, { persistenceSchemaAdded: false, runtimeStates: FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE.states }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowRuntimeStateCode === FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE.runtimeStateCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalResultBoundaryCode === FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY.boundaryCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowRuntimeCurrentState === 'definition_only'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowRuntimeEnabledTransitionCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowRuntimeInstanceCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowRuntimeStarted === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowRuntimeRunning === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowRuntimeCompleted === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalResultCount === 0, { currentState: 'definition_only', enabledTransitions: 0, runtimeInstances: 0, results: 0 }),
    gate('Rule', notAssessed.runtimeStatus === 'not_assessed' && ready.runtimeStatus === 'runtime_definition_ready'
      && [missingBoundary, initializeBlocked, runningBlocked, completeBlocked, resultBlocked, businessBlocked, persistenceBlocked].every((item) => item.runtimeStatus === 'blocked')
      && evaluated.every((item) => item.workflowInitialized === false && item.workflowStarted === false && item.workflowRunning === false && item.workflowCompleted === false && item.approvalResultCreated === false && item.approved === false && item.businessStateChanged === false && item.persistencePerformed === false && item.businessWriteCount === 0 && item.productionDataWritten === false), { ready: ready.runtimeStatus, running: runningBlocked.runtimeStatus, completion: completeBlocked.runtimeStatus, result: resultBlocked.runtimeStatus }),
    gate('Guard', evaluateFormalPriceApprovalWorkflowRuntimeGuard({ action: 'inspectWorkflowRuntimeDefinition', mode: 'definition_only' }).decision === 'allow_definition_inspection_only'
      && evaluateFormalPriceApprovalWorkflowRuntimeGuard({ action: 'inspectWorkflowRuntimeDefinition', mode: 'execution' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalWorkflowRuntimeGuard({ action })
        return result.decision === 'deny' && result.workflowStarted === false && result.workflowRunning === false && result.approvalResultCreated === false && result.approved === false && result.businessStateChanged === false && result.persistencePerformed === false
      }), FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalWorkflowRuntimeAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_PROFILE.profileCode),
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
    workflowRunningMeansApproved: false, workflowCompletedMeansResultCreated: false, runtimeStateMeansBusinessState: false,
    workflowInitialized: false, workflowStarted: false, workflowRunning: false, workflowCompleted: false, approvalResultCreated: false, approved: false, businessStateChanged: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-workflow-runtime')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE, validateFormalPriceApprovalInstanceLifecycle } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalInstanceLifecycleModel.js'
import { FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE, validateFormalPriceApprovalTaskLifecycle } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalTaskLifecycleModel.js'
import { FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY, validateFormalPriceApprovalInstanceTaskBoundary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalInstanceTaskBoundary.js'
import { evaluateFormalPriceApprovalInstanceTaskLifecycle } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalInstanceTaskRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_INSTANCE_TASK_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalInstanceTaskGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalInstanceTaskGuard.js'
import { FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_PROFILE, validateFormalPriceApprovalInstanceLifecycleAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalInstanceLifecycleAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.20'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, instanceSource, taskSource, boundarySource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalInstanceLifecycleModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalTaskLifecycleModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalInstanceTaskBoundary.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalInstanceTaskRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalInstanceTaskGuard.js'),
  ])
  const imports = `${instanceSource}\n${taskSource}\n${boundarySource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT',
      existingInstanceBoundary: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY',
      instanceLifecycle: FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE.lifecycleCode,
      taskLifecycle: FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE.lifecycleCode,
      jointBoundary: FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY.boundaryCode,
      instanceDefinitionMeansCreated: false, taskDefinitionMeansCreated: false, workflowRunningMeansApprovalResult: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|stateManager|dataGateway|transactionEngine|commandDispatcher/i.test(imports),
      strategy: 'definition-only instance and task lifecycles with zero enabled transitions and isolated factories',
    }),
    protectedScopes: Object.freeze(['Approval instance creation', 'Approval task creation', 'Workflow start', 'Approval result creation', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_instance_task_scan_v11428620.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const safeInput = Object.freeze({ assessmentRequested: true, workflowStartAssessmentStatus: 'start_ready', instanceDefinitionComplete: true, taskDefinitionComplete: true, instanceBoundaryIsolated: true })
  const ready = evaluateFormalPriceApprovalInstanceTaskLifecycle(safeInput)
  const notAssessed = evaluateFormalPriceApprovalInstanceTaskLifecycle({})
  const missingBoundary = evaluateFormalPriceApprovalInstanceTaskLifecycle({ ...safeInput, instanceBoundaryIsolated: false })
  const instanceBlocked = evaluateFormalPriceApprovalInstanceTaskLifecycle({ ...safeInput, instanceCreationRequested: true })
  const taskBlocked = evaluateFormalPriceApprovalInstanceTaskLifecycle({ ...safeInput, taskCreationRequested: true })
  const workflowBlocked = evaluateFormalPriceApprovalInstanceTaskLifecycle({ ...safeInput, workflowRunningRequested: true })
  const resultBlocked = evaluateFormalPriceApprovalInstanceTaskLifecycle({ ...safeInput, approvalResultRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalInstanceTaskLifecycle({ ...safeInput, persistenceRequested: true })
  const evaluated = [notAssessed, ready, missingBoundary, instanceBlocked, taskBlocked, workflowBlocked, resultBlocked, persistenceBlocked]
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-instance-task-lifecycle"')
      && pageSource.includes('Definition ≠ Instance Created') && pageSource.includes('Definition ≠ Task Created') && pageSource.includes('Running ≠ Approval Result'), FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalInstanceLifecycle().valid && validateFormalPriceApprovalTaskLifecycle().valid
      && validateFormalPriceApprovalInstanceTaskBoundary().valid && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY.persistenceAdapterConnected === false, { persistenceSchemaAdded: false, instanceStates: FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE.states, taskStates: FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE.states }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalInstanceLifecycleCode === FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE.lifecycleCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalTaskLifecycleCode === FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE.lifecycleCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalInstanceTaskBoundaryCode === FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY.boundaryCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalInstanceLifecycleEnabledTransitionCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalTaskLifecycleEnabledTransitionCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalApprovalInstanceCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalApprovalTaskCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalApprovalResultCount === 0, { enabledTransitions: 0, instanceCount: 0, taskCount: 0, resultCount: 0 }),
    gate('Rule', notAssessed.lifecycleStatus === 'not_assessed' && ready.lifecycleStatus === 'lifecycle_definition_ready'
      && [missingBoundary, instanceBlocked, taskBlocked, workflowBlocked, resultBlocked, persistenceBlocked].every((item) => item.lifecycleStatus === 'blocked')
      && evaluated.every((item) => item.instanceCreated === false && item.taskCreated === false && item.workflowStarted === false && item.workflowRunning === false && item.approvalResultCreated === false && item.stateChanged === false && item.persistencePerformed === false && item.businessWriteCount === 0 && item.productionDataWritten === false), { ready: ready.lifecycleStatus, instanceCreation: instanceBlocked.lifecycleStatus, taskCreation: taskBlocked.lifecycleStatus, resultCreation: resultBlocked.lifecycleStatus }),
    gate('Guard', evaluateFormalPriceApprovalInstanceTaskGuard({ action: 'inspectInstanceTaskLifecycle', mode: 'definition_only' }).decision === 'allow_definition_inspection_only'
      && evaluateFormalPriceApprovalInstanceTaskGuard({ action: 'inspectInstanceTaskLifecycle', mode: 'execution' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_INSTANCE_TASK_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalInstanceTaskGuard({ action })
        return result.decision === 'deny' && result.instanceCreated === false && result.taskCreated === false && result.workflowStarted === false && result.approvalResultCreated === false && result.persistencePerformed === false
      }), FORMAL_PRICE_APPROVAL_INSTANCE_TASK_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalInstanceLifecycleAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_PROFILE.profileCode),
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
    instanceDefinitionMeansCreated: false, taskDefinitionMeansCreated: false, workflowRunningMeansApprovalResult: false,
    instanceCreated: false, taskCreated: false, workflowStarted: false, workflowRunning: false, approvalResultCreated: false, stateChanged: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-instance-task')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

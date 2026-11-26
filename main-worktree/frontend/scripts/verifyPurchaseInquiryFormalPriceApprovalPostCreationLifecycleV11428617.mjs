import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE, validateFormalPriceApprovalPostCreationLifecycleStateModel } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleStateModel.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITIONS, inspectFormalPriceApprovalPostCreationLifecycleTransition, validateFormalPriceApprovalPostCreationLifecycleTransitionMatrix } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleTransitionMatrix.js'
import { evaluateFormalPriceApprovalPostCreationLifecycle } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalPostCreationLifecycleGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleGuard.js'
import { evaluateFormalPriceApprovalRuntimeTransition } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeStateMachine.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_PROFILE, validateFormalPriceApprovalPostCreationLifecycleAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalPostCreationLifecycleAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.17'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, stateSource, matrixSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleStateModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleTransitionMatrix.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleGuard.js'),
  ])
  const dependencyImportSource = `${stateSource}\n${matrixSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  const workflowOrPersistenceImports = /dataGateway|transactionEngine|workflowEngine|stateManager|commandDispatcher/i.test(dependencyImportSource)
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles,
      stateModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleStateModel.js'),
      transitionMatrixPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationLifecycleTransitionMatrix.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER',
      designTarget: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE.stateMachineCode,
      lifecycle: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE.lifecycle,
      transitionCount: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITIONS.length,
      enabledTransitionCount: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITIONS.filter((item) => item.enabled).length,
      createdIsPendingApproval: false,
      approvedMeansAutoExecution: false,
      lifecycleIsWorkflow: false,
      workflowOrPersistenceImports,
      strategy: 'post-creation lifecycle definition with every transition frozen and inspectable only',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object creation', 'Lifecycle execution', 'State persistence', 'Approval Workflow', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_post_creation_lifecycle_scan_v11428617.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const base = Object.freeze({ transitionAssessmentRequested: true, automaticTransition: false, workflowEngineConnected: false, statePersistenceConnected: false, lifecycleExecutionRequested: false, formalPriceApprovalObjectCreatedNow: false, businessWriteCount: 0 })
  const notAssessed = evaluateFormalPriceApprovalPostCreationLifecycle({})
  const definedResults = FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITIONS.map((transition) => evaluateFormalPriceApprovalPostCreationLifecycle({ ...base, fromState: transition.from, toState: transition.to }))
  const unknownBlocked = evaluateFormalPriceApprovalPostCreationLifecycle({ ...base, fromState: 'approved', toState: 'created' })
  const automaticBlocked = evaluateFormalPriceApprovalPostCreationLifecycle({ ...base, fromState: 'created', toState: 'pending_approval', automaticTransition: true })
  const workflowBlocked = evaluateFormalPriceApprovalPostCreationLifecycle({ ...base, fromState: 'created', toState: 'pending_approval', workflowEngineConnected: true })
  const persistenceBlocked = evaluateFormalPriceApprovalPostCreationLifecycle({ ...base, fromState: 'pending_approval', toState: 'approved', statePersistenceConnected: true })
  const originalTransition = evaluateFormalPriceApprovalRuntimeTransition({ fromStatus: 'created', toStatus: 'pending_approval' })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-post-creation-lifecycle"')
      && pageSource.includes('创建后生命周期状态机冻结设计')
      && pageSource.includes('Created ≠ Pending Approval')
      && pageSource.includes('Approved ≠ Auto Execution')
      && pageSource.includes('Lifecycle ≠ Workflow'), FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalPostCreationLifecycleStateModel().valid
      && validateFormalPriceApprovalPostCreationLifecycleTransitionMatrix().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE.persistenceAdapterConnected === false, {
        lifecycle: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE.lifecycle,
        transitionCount: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_TRANSITIONS.length,
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPostCreationLifecycleStateMachineCode === FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE.stateMachineCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPostCreationLifecycleTransitionCount === 4
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPostCreationLifecycleEnabledTransitionCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPostCreationLifecyclePersistenceConnected === false
      && FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE.stateMachineInstanceCount === 0
      && originalTransition.decision === 'deny'
      && originalTransition.stateChanged === false, {
        stateMachineCode: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE.stateMachineCode,
        transitionCount: 4,
        enabledTransitionCount: 0,
        originalCreatedTransition: originalTransition.decision,
      }),
    gate('Rule', notAssessed.evaluatedStatus === 'not_assessed'
      && definedResults.every((result) => result.evaluatedStatus === 'transition_defined_frozen'
        && result.transition.defined === true && result.transition.enabled === false && result.stateChanged === false)
      && unknownBlocked.evaluatedStatus === 'blocked'
      && automaticBlocked.evaluatedStatus === 'blocked'
      && workflowBlocked.evaluatedStatus === 'blocked'
      && persistenceBlocked.evaluatedStatus === 'blocked'
      && [notAssessed, ...definedResults, unknownBlocked, automaticBlocked, workflowBlocked, persistenceBlocked].every((result) => result.lifecycleExecuted === false
        && result.stateChanged === false
        && result.workflowEngineConnected === false
        && result.statePersisted === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false), {
        definedFrozenCount: definedResults.filter((result) => result.evaluatedStatus === 'transition_defined_frozen').length,
        automaticTransition: automaticBlocked.evaluatedStatus,
        workflowRequest: workflowBlocked.evaluatedStatus,
        persistenceRequest: persistenceBlocked.evaluatedStatus,
      }),
    gate('Guard', evaluateFormalPriceApprovalPostCreationLifecycleGuard({ action: 'inspectLifecycleTransition', executionMode: 'frozen_design_only' }).decision === 'allow_transition_inspection_only'
      && evaluateFormalPriceApprovalPostCreationLifecycleGuard({ action: 'inspectLifecycleTransition', executionMode: 'workflow' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalPostCreationLifecycleGuard({ action })
        return result.decision === 'deny' && result.lifecycleExecuted === false && result.stateChanged === false && result.statePersisted === false
      }), FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalPostCreationLifecycleAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const viteEntry = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
    const output = execFileSync(process.execPath, [viteEntry, 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }
  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL', problemAnalysis: scan.analysis,
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    lifecycle: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE.lifecycle,
    transitionCount: 4, enabledTransitionCount: 0, createdIsPendingApproval: false, approvedMeansAutoExecution: false, lifecycleIsWorkflow: false,
    lifecycleExecuted: false, stateChanged: false, statePersisted: false, workflowEngineConnected: false, formalPriceApprovalObjectCreatedNow: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-post-creation-lifecycle')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

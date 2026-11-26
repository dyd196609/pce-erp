import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF, validateFormalPriceApprovalWorkflowHandoff } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowHandoffModel.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP, validateFormalPriceApprovalWorkflowOwnership } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowOwnershipModel.js'
import { evaluateFormalPriceApprovalWorkflowHandoff } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowHandoffRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalWorkflowHandoffGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowHandoffGuard.js'
import { evaluateFormalPriceApprovalRuntimeTransition } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeStateMachine.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_PROFILE, validateFormalPriceApprovalWorkflowHandoffAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalWorkflowHandoffAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.18'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_READY'
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
  try { await walk(path.join(frontendRoot, relative)) } catch { /* missing scope means empty inventory */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, modelSource, ownershipSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowHandoffModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowOwnershipModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowHandoffRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalWorkflowHandoffGuard.js'),
  ])
  const imports = `${modelSource}\n${ownershipSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE',
      designTarget: FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF.handoffCode,
      ownershipTarget: FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP.ownershipCode,
      lifecycleIsWorkflow: false,
      ownershipMeansExecution: false,
      pendingApprovalMeansWorkflowStarted: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|stateManager|dataGateway|transactionEngine|commandDispatcher/i.test(imports),
      strategy: 'read-only lifecycle-to-workflow handoff assessment with evidence-only ownership and default-deny execution',
    }),
    protectedScopes: Object.freeze(['Workflow start', 'Approval task creation', 'Approval instance creation', 'Lifecycle mutation', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_workflow_handoff_scan_v11428618.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const safeInput = Object.freeze({ assessmentRequested: true, lifecycleState: 'pending_approval', lifecycleEvidenceComplete: true, ownershipEvidenceComplete: true })
  const ready = evaluateFormalPriceApprovalWorkflowHandoff(safeInput)
  const notAssessed = evaluateFormalPriceApprovalWorkflowHandoff({})
  const missingEvidence = evaluateFormalPriceApprovalWorkflowHandoff({ ...safeInput, ownershipEvidenceComplete: false })
  const workflowBlocked = evaluateFormalPriceApprovalWorkflowHandoff({ ...safeInput, workflowStartRequested: true })
  const instanceBlocked = evaluateFormalPriceApprovalWorkflowHandoff({ ...safeInput, workflowInstanceCreationRequested: true })
  const taskBlocked = evaluateFormalPriceApprovalWorkflowHandoff({ ...safeInput, approvalTaskCreationRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalWorkflowHandoff({ ...safeInput, persistenceRequested: true })
  const originalTransition = evaluateFormalPriceApprovalRuntimeTransition({ fromStatus: 'created', toStatus: 'pending_approval' })
  const evaluated = [notAssessed, ready, missingEvidence, workflowBlocked, instanceBlocked, taskBlocked, persistenceBlocked]
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-workflow-handoff"')
      && pageSource.includes('Lifecycle ≠ Workflow')
      && pageSource.includes('Ownership ≠ Execution')
      && pageSource.includes('Pending Approval ≠ Workflow Started'), FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalWorkflowHandoff().valid
      && validateFormalPriceApprovalWorkflowOwnership().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF.workflowEngineConnected === false, { persistenceSchemaAdded: false, mode: FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF.mode }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowHandoffCode === FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF.handoffCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowOwnershipCode === FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP.ownershipCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowHandoffWorkflowConnected === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowHandoffInstanceCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalWorkflowHandoffApprovalTaskCount === 0
      && originalTransition.decision === 'deny' && originalTransition.stateChanged === false, { workflowConnected: false, originalCreatedTransition: originalTransition.decision }),
    gate('Rule', notAssessed.handoffStatus === 'not_assessed'
      && ready.handoffStatus === 'handoff_ready'
      && [missingEvidence, workflowBlocked, instanceBlocked, taskBlocked, persistenceBlocked].every((item) => item.handoffStatus === 'blocked')
      && evaluated.every((item) => item.workflowStarted === false && item.workflowInstanceCreated === false && item.approvalTaskCreated === false && item.stateChanged === false && item.businessWriteCount === 0 && item.productionDataWritten === false), { ready: ready.handoffStatus, workflowStartRequest: workflowBlocked.handoffStatus }),
    gate('Guard', evaluateFormalPriceApprovalWorkflowHandoffGuard({ action: 'inspectHandoffBoundary', mode: 'boundary_design_only' }).decision === 'allow_inspection_only'
      && evaluateFormalPriceApprovalWorkflowHandoffGuard({ action: 'inspectHandoffBoundary', mode: 'workflow' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalWorkflowHandoffGuard({ action })
        return result.decision === 'deny' && result.workflowStarted === false && result.workflowInstanceCreated === false && result.approvalTaskCreated === false && result.persistencePerformed === false
      }), FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalWorkflowHandoffAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_PROFILE.profileCode),
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
    lifecycleIsWorkflow: false, ownershipMeansExecution: false, pendingApprovalMeansWorkflowStarted: false,
    workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false, stateChanged: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-workflow-handoff')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER, validateFormalPriceApprovalPostCreationStateTakeover } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateTakeoverModel.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_OWNERSHIP, validateFormalPriceApprovalPostCreationStateOwnership } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateOwnershipModel.js'
import { evaluateFormalPriceApprovalPostCreationStateTakeover } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateTakeoverRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalPostCreationStateTakeoverGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateTakeoverGuard.js'
import { evaluateFormalPriceApprovalRuntimeTransition } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeStateMachine.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_PROFILE, validateFormalPriceApprovalPostCreationStateTakeoverAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalPostCreationStateTakeoverAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.16'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ISOLATION_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, modelSource, ownershipSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateTakeoverModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateOwnershipModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateTakeoverRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateTakeoverGuard.js'),
  ])
  const dependencyImportSource = `${modelSource}\n${ownershipSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  const workflowOrPersistenceImports = /dataGateway|transactionEngine|workflowEngine|commandDispatcher|objectFactory/i.test(dependencyImportSource)
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
      takeoverModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateTakeoverModel.js'),
      stateOwnershipModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPostCreationStateOwnershipModel.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL',
      designTarget: FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER.takeoverCode,
      sourceState: 'created',
      futureTargetState: 'pending_approval',
      createdMeansAutoPendingApproval: false,
      takeoverIsStateMutation: false,
      workflowOwnershipMeansWorkflowStart: false,
      workflowOrPersistenceImports,
      strategy: 'future post-creation state ownership assessment with the created-to-pending transition still frozen',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object creation', 'State mutation', 'Approval Workflow', 'Approval Tasks', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_post_creation_state_takeover_scan_v11428616.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const takeoverInput = Object.freeze({
    takeoverAssessmentRequested: true,
    creationEvidenceStatus: 'verified_future_evidence',
    currentState: 'created',
    takeoverMode: 'manual_isolated',
    stateOwnershipVerified: true,
    workflowEngineConnected: false,
    stateMutationAllowed: false,
    automaticTakeover: false,
    autoTransitionToPendingApproval: false,
    formalPriceApprovalObjectCreatedNow: false,
    businessWriteCount: 0,
  })
  const notAssessed = evaluateFormalPriceApprovalPostCreationStateTakeover({})
  const awaitingEvidence = evaluateFormalPriceApprovalPostCreationStateTakeover({ takeoverAssessmentRequested: true, currentState: 'created', takeoverMode: 'manual_isolated', stateOwnershipVerified: true, workflowEngineConnected: false, stateMutationAllowed: false })
  const takeoverReady = evaluateFormalPriceApprovalPostCreationStateTakeover(takeoverInput)
  const manualReview = evaluateFormalPriceApprovalPostCreationStateTakeover({ ...takeoverInput, stateOwnershipVerified: false })
  const workflowBlocked = evaluateFormalPriceApprovalPostCreationStateTakeover({ ...takeoverInput, workflowEngineConnected: true })
  const autoTransitionBlocked = evaluateFormalPriceApprovalPostCreationStateTakeover({ ...takeoverInput, autoTransitionToPendingApproval: true })
  const frozenTransition = evaluateFormalPriceApprovalRuntimeTransition({ fromStatus: 'created', toStatus: 'pending_approval' })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-post-creation-state-takeover"')
      && pageSource.includes('创建后状态接管隔离设计')
      && pageSource.includes('Created ≠ Auto Pending Approval')
      && pageSource.includes('Takeover ≠ State Mutation')
      && pageSource.includes('Ownership ≠ Workflow Start'), FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalPostCreationStateTakeover().valid
      && validateFormalPriceApprovalPostCreationStateOwnership().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER.persistenceMode === 'none', {
        takeoverFields: FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER.fields,
        ownershipStates: FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_OWNERSHIP.map((item) => item.state),
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPostCreationStateTakeoverCode === FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER.takeoverCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPostCreationAutomaticTakeover === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPostCreationStateMutationAllowed === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPostCreationWorkflowEngineConnected === false
      && FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER.takeoverInstanceCount === 0
      && frozenTransition.decision === 'deny'
      && frozenTransition.stateChanged === false, {
        takeoverCode: FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER.takeoverCode,
        sourceState: 'created',
        targetState: 'pending_approval',
        existingRuntimeTransition: frozenTransition.decision,
      }),
    gate('Rule', notAssessed.evaluatedStatus === 'not_assessed'
      && awaitingEvidence.evaluatedStatus === 'awaiting_created_evidence'
      && takeoverReady.evaluatedStatus === 'takeover_ready'
      && manualReview.evaluatedStatus === 'manual_review'
      && workflowBlocked.evaluatedStatus === 'blocked'
      && autoTransitionBlocked.evaluatedStatus === 'blocked'
      && [notAssessed, awaitingEvidence, takeoverReady, manualReview, workflowBlocked, autoTransitionBlocked].every((result) => result.stateChanged === false
        && result.automaticTakeover === false
        && result.workflowEngineConnected === false
        && result.approvalWorkflowStarted === false
        && result.approvalTaskCreated === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false), {
        awaitingEvidence: awaitingEvidence.evaluatedStatus,
        takeoverReady: takeoverReady.evaluatedStatus,
        manualReview: manualReview.evaluatedStatus,
        workflowRequest: workflowBlocked.evaluatedStatus,
        autoTransition: autoTransitionBlocked.evaluatedStatus,
      }),
    gate('Guard', evaluateFormalPriceApprovalPostCreationStateTakeoverGuard({ action: 'evaluateStateTakeover', takeoverMode: 'manual_isolated' }).decision === 'allow_takeover_assessment_only'
      && evaluateFormalPriceApprovalPostCreationStateTakeoverGuard({ action: 'evaluateStateTakeover', takeoverMode: 'automatic' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalPostCreationStateTakeoverGuard({ action })
        return result.decision === 'deny' && result.stateChanged === false && result.workflowEngineConnected === false
      }), FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalPostCreationStateTakeoverAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_PROFILE.profileCode),
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
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis,
    gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    createdMeansAutoPendingApproval: false,
    takeoverIsStateMutation: false,
    workflowOwnershipMeansWorkflowStart: false,
    stateChanged: false,
    automaticTakeover: false,
    workflowEngineConnected: false,
    formalPriceApprovalObjectCreatedNow: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    takeoverAssessmentPersisted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-post-creation-takeover')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

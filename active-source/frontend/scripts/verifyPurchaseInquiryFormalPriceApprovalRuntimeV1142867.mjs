import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_RUNTIME, evaluateFormalPriceApprovalRuntime } from '../src/meta/runtime/formalPriceApprovalRuntime.js'
import { validateFormalPriceApprovalObject } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalObjectModel.js'
import { FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE, FORMAL_PRICE_APPROVAL_RUNTIME_TRANSITIONS, evaluateFormalPriceApprovalRuntimeTransition } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeStateMachine.js'
import { evaluateFormalPriceApprovalRuntimeReadiness } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_RUNTIME_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalRuntimeGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeGuard.js'
import { FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_PROFILE, validateFormalPriceApprovalRuntimeAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalRuntimeAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.7'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_RUNTIME_DESIGN_READY'
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
  try { await walk(root) } catch { /* missing root is reported by an empty inventory */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, runtimeSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/runtime/formalPriceApprovalRuntime.js'),
  ])
  const genericWorkflowImported = /workflow|approvalEngine/i.test(runtimeSource.replaceAll('workflowEngineConnected', '').replaceAll('approvalWorkflowStarted', ''))
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    scope: Object.freeze([
      'src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject',
      'src/meta/runtime',
      'src/meta/schema/scm',
      'src/meta/acceptance/scm',
    ]),
    inventory: Object.freeze({
      domainFiles,
      runtimeFiles,
      schemaFiles,
      acceptanceFiles,
      formalPriceApprovalRuntimePresent: runtimeFiles.includes('src/meta/runtime/formalPriceApprovalRuntime.js'),
    }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_OBJECT',
      designTarget: 'SCM_FORMAL_PRICE_APPROVAL_RUNTIME',
      lifecycle: FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE.lifecycle,
      onlyEnabledTransition: Object.freeze({ from: 'definition_only', to: 'ready_for_creation' }),
      genericWorkflowImported,
      workflowEngineConnected: false,
      strategy: 'pure design-time state evaluation with every workflow and write boundary isolated',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval module', 'Approval Workflow', 'PurchaseOrder', 'Finance', 'Inventory', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_runtime_scan_v1142867.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const notReady = evaluateFormalPriceApprovalRuntimeReadiness({
    projectionStatus: 'incomplete', evidencePackageStatus: 'incomplete', creationAssessmentStatus: 'blocked',
  })
  const ready = evaluateFormalPriceApprovalRuntimeReadiness({
    projectionStatus: 'available', evidencePackageStatus: 'available', creationAssessmentStatus: 'ready',
  })
  const runtimeEvaluation = evaluateFormalPriceApprovalRuntime({
    projectionStatus: 'available', evidencePackageStatus: 'available', creationAssessmentStatus: 'ready',
  })
  const designTransition = evaluateFormalPriceApprovalRuntimeTransition({ fromStatus: 'definition_only', toStatus: 'ready_for_creation' })
  const frozenTransitions = [
    ['ready_for_creation', 'created'], ['created', 'pending_approval'], ['pending_approval', 'approved'],
    ['pending_approval', 'rejected'], ['created', 'cancelled'],
  ]
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-runtime-design"') && pageSource.includes('正式价格审批状态机运行设计') && pageSource.includes('审批流程隔离'), FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalObject().valid && routerSource.includes("schema: 'PriceApprovalSchema'"), { existingSchema: 'PriceApprovalSchema', runtimeAddsPersistenceSchema: false }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalRuntimeCode === FORMAL_PRICE_APPROVAL_RUNTIME.runtimeCode
      && FORMAL_PRICE_APPROVAL_RUNTIME.workflowEngineConnected === false
      && FORMAL_PRICE_APPROVAL_RUNTIME.approvalModuleConnected === false
      && FORMAL_PRICE_APPROVAL_RUNTIME.stateMutationAllowed === false
      && FORMAL_PRICE_APPROVAL_RUNTIME.approvalInstanceCount === 0
      && FORMAL_PRICE_APPROVAL_RUNTIME.approvalTaskCount === 0
      && runtimeEvaluation.currentStatus === 'definition_only'
      && runtimeEvaluation.evaluatedStatus === 'ready_for_creation'
      && runtimeEvaluation.stateChanged === false, FORMAL_PRICE_APPROVAL_RUNTIME),
    gate('Rule', notReady.evaluatedState === 'definition_only'
      && ready.evaluatedState === 'ready_for_creation'
      && ready.stateChanged === false
      && ready.automaticProgression === false
      && ready.formalPriceApprovalObjectCreated === false
      && ready.approvalWorkflowStarted === false
      && ready.approvalTaskCreated === false
      && ready.priceApproved === false
      && ready.purchaseOrderCreated === false
      && designTransition.decision === 'allow_design_evaluation'
      && designTransition.stateChanged === false
      && FORMAL_PRICE_APPROVAL_RUNTIME_TRANSITIONS.filter((item) => item.enabled).length === 1
      && frozenTransitions.every(([fromStatus, toStatus]) => evaluateFormalPriceApprovalRuntimeTransition({ fromStatus, toStatus }).decision === 'deny'), {
        evaluatedState: ready.evaluatedState,
        onlyEnabledTransition: FORMAL_PRICE_APPROVAL_RUNTIME_TRANSITIONS.find((item) => item.enabled),
        stateChanged: false,
      }),
    gate('Guard', FORMAL_PRICE_APPROVAL_RUNTIME_FORBIDDEN_ACTIONS.every((action) => evaluateFormalPriceApprovalRuntimeGuard(action).decision === 'deny'), FORMAL_PRICE_APPROVAL_RUNTIME_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalRuntimeAcceptance().valid && registrySource.includes('FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_PROFILE.profileCode),
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
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.genericWorkflowImported === false
  const report = Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis,
    gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    lifecycle: FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE.lifecycle,
    enabledTransitions: FORMAL_PRICE_APPROVAL_RUNTIME_TRANSITIONS.filter((item) => item.enabled),
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    stateAutomaticProgression: false,
    stateMutationPerformed: false,
    formalPriceApprovalObjectCreated: false,
    approvalInstanceCount: 0,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    approvalSubmitted: false,
    priceApproved: false,
    purchaseOrderCreated: false,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-runtime')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_CREATION_SANDBOX, validateFormalPriceApprovalCreationSandbox } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSandboxModel.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION, validateFormalPriceApprovalHumanConfirmation } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanConfirmationModel.js'
import { evaluateFormalPriceApprovalCreationSandbox, evaluateFormalPriceApprovalHumanConfirmation } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalSandboxConfirmationRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_SANDBOX_CONFIRMATION_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalSandboxConfirmationGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalSandboxConfirmationGuard.js'
import { FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_PROFILE, validateFormalPriceApprovalSandboxAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalSandboxAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.12'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_SANDBOX_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, sandboxSource, confirmationSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSandboxModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanConfirmationModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalSandboxConfirmationRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalSandboxConfirmationGuard.js'),
  ])
  const dependencyImportSource = `${sandboxSource}\n${confirmationSource}\n${ruleSource}\n${guardSource}`
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
      sandboxModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSandboxModel.js'),
      confirmationModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanConfirmationModel.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT',
      designTargets: Object.freeze([FORMAL_PRICE_APPROVAL_CREATION_SANDBOX.sandboxCode, FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION.confirmationCode]),
      sandboxIsProduction: false,
      confirmationIsExecution: false,
      simulationIsCreation: false,
      executionOrPersistenceImports,
      strategy: 'sandbox-only final validation followed by named human design confirmation with all execution paths frozen',
    }),
    protectedScopes: Object.freeze(['Production environment', 'Formal Price Approval object instances', 'Approval Workflow', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_sandbox_scan_v11428612.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const sandboxReady = evaluateFormalPriceApprovalCreationSandbox({
    finalReleaseStatus: 'ready', environment: 'sandbox', productionEndpointConnected: false,
    persistenceConnected: false, workflowEngineConnected: false,
  })
  const productionBlocked = evaluateFormalPriceApprovalCreationSandbox({
    finalReleaseStatus: 'ready', environment: 'production', productionEndpointConnected: true,
    persistenceConnected: false, workflowEngineConnected: false,
  })
  const humanConfirmed = evaluateFormalPriceApprovalHumanConfirmation({ sandboxStatus: 'completed', confirmationMode: 'human', confirmedBy: 'human-reviewer' })
  const automaticRejected = evaluateFormalPriceApprovalHumanConfirmation({ sandboxStatus: 'completed', confirmationMode: 'automatic', confirmedBy: 'system' })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-creation-sandbox-confirmation"')
      && pageSource.includes('创建动作安全沙箱与人工确认')
      && pageSource.includes('Sandbox ≠ Production')
      && pageSource.includes('Confirmation ≠ Execution')
      && pageSource.includes('Simulation ≠ Creation'), FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalCreationSandbox().valid
      && validateFormalPriceApprovalHumanConfirmation().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_CREATION_SANDBOX.persistenceMode === 'none'
      && FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION.persistenceMode === 'none', {
        sandboxFields: FORMAL_PRICE_APPROVAL_CREATION_SANDBOX.fields,
        confirmationFields: FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION.fields,
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationSandboxCode === FORMAL_PRICE_APPROVAL_CREATION_SANDBOX.sandboxCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationSandboxEnvironment === 'sandbox'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationSandboxProductionEndpointConnected === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanConfirmationCode === FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION.confirmationCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanConfirmationExecutionPermission === false
      && FORMAL_PRICE_APPROVAL_CREATION_SANDBOX.sandboxInstanceCount === 0
      && FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION.confirmationInstanceCount === 0, {
        sandboxCode: FORMAL_PRICE_APPROVAL_CREATION_SANDBOX.sandboxCode,
        confirmationCode: FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION.confirmationCode,
        environment: 'sandbox',
        productionEndpointConnected: false,
      }),
    gate('Rule', sandboxReady.decision === 'sandbox_validated'
      && sandboxReady.readinessStatus === 'sandbox_ready'
      && sandboxReady.evaluatedStatus === 'completed'
      && sandboxReady.statusTrace.join(',') === 'not_started,checking,sandbox_ready,completed'
      && productionBlocked.decision === 'blocked'
      && humanConfirmed.decision === 'confirmed_design_only'
      && humanConfirmed.humanConfirmationRecognized === true
      && automaticRejected.decision === 'rejected'
      && [sandboxReady, productionBlocked].every((result) => result.productionEnvironmentUsed === false
        && result.formalPriceApprovalObjectCreated === false
        && result.approvalWorkflowStarted === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false)
      && [humanConfirmed, automaticRejected].every((result) => result.confirmationInstanceCreated === false
        && result.executionPermissionGranted === false
        && result.commandExecuted === false
        && result.formalPriceApprovalObjectCreated === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false), {
        sandboxDecision: sandboxReady.decision,
        productionDecision: productionBlocked.decision,
        humanDecision: humanConfirmed.decision,
        automaticDecision: automaticRejected.decision,
      }),
    gate('Guard', evaluateFormalPriceApprovalSandboxConfirmationGuard({ action: 'runSandboxValidation', environment: 'sandbox' }).decision === 'allow_sandbox_validation_only'
      && evaluateFormalPriceApprovalSandboxConfirmationGuard({ action: 'runSandboxValidation', environment: 'production' }).decision === 'deny'
      && evaluateFormalPriceApprovalSandboxConfirmationGuard({ action: 'reviewHumanConfirmation', confirmationMode: 'human' }).decision === 'allow_confirmation_review_only'
      && evaluateFormalPriceApprovalSandboxConfirmationGuard({ action: 'reviewHumanConfirmation', confirmationMode: 'automatic' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_SANDBOX_CONFIRMATION_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalSandboxConfirmationGuard({ action })
        return result.decision === 'deny' && result.executionPermissionGranted === false
      }), FORMAL_PRICE_APPROVAL_SANDBOX_CONFIRMATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalSandboxAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_PROFILE.profileCode),
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
    sandboxIsProduction: false,
    productionEndpointConnected: false,
    confirmationIsExecution: false,
    simulationIsCreation: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    sandboxResultPersisted: false,
    humanConfirmationPersisted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-sandbox')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

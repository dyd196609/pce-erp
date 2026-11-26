import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION, validateFormalPriceApprovalBusinessViewOptimization } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessViewOptimizationModel.js'
import { FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION, validateFormalPriceApprovalUserAcceptancePreparation } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptancePreparationModel.js'
import { evaluateFormalPriceApprovalBusinessViewUserAcceptance } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessViewUserAcceptanceRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalBusinessViewUserAcceptanceGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessViewUserAcceptanceGuard.js'
import { FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_PROFILE, validateFormalPriceApprovalBusinessViewUserAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalBusinessViewUserAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.1'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_READY'
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
  const [domainFiles, runtimeFiles, pageFiles, acceptanceFiles, optimizationSource, preparationSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/runtime'),
    listFiles('src/meta/pages'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessViewOptimizationModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptancePreparationModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessViewUserAcceptanceRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessViewUserAcceptanceGuard.js'),
  ])
  const imports = `${optimizationSource}\n${preparationSource}\n${ruleSource}\n${guardSource}`.split(/\r?\n/)
    .filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/pages', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, pageFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_ACCEPTANCE',
      businessViewOptimization: FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION.modelCode,
      userAcceptancePreparation: FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION.modelCode,
      optimizedViewItemCount: 4, checklistCount: 5, passedChecklistCount: 5,
      businessViewMeansBusinessExecution: false, userAcceptanceMeansOperationApproval: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'business-question-to-evidence-to-judgement-to-boundary view with read-only user acceptance walkthrough' }),
    protectedScopes: Object.freeze(['Approval object creation', 'Workflow start', 'Approval task creation', 'Operation approval', 'Production operation', 'Database']) })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_business_view_user_acceptance_scan_v1142871.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const safeInput = Object.freeze({ preparationRequested: true, operationValidationStatus: 'validation_ready',
    businessViewOptimizationStatus: 'user_acceptance_ready', passedChecklistCount: 5, serverFactsConfirmed: true, zeroWriteConfirmed: true })
  const notPrepared = evaluateFormalPriceApprovalBusinessViewUserAcceptance({})
  const ready = evaluateFormalPriceApprovalBusinessViewUserAcceptance(safeInput)
  const incomplete = evaluateFormalPriceApprovalBusinessViewUserAcceptance({ ...safeInput, passedChecklistCount: 4 })
  const approvalBlocked = evaluateFormalPriceApprovalBusinessViewUserAcceptance({ ...safeInput, operationApprovalRequested: true })
  const productionBlocked = evaluateFormalPriceApprovalBusinessViewUserAcceptance({ ...safeInput, productionOperationRequested: true })
  const executionBlocked = evaluateFormalPriceApprovalBusinessViewUserAcceptance({ ...safeInput, businessExecutionRequested: true })
  const objectBlocked = evaluateFormalPriceApprovalBusinessViewUserAcceptance({ ...safeInput, approvalObjectCreationRequested: true })
  const workflowBlocked = evaluateFormalPriceApprovalBusinessViewUserAcceptance({ ...safeInput, workflowStartRequested: true })
  const taskBlocked = evaluateFormalPriceApprovalBusinessViewUserAcceptance({ ...safeInput, approvalTaskCreationRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalBusinessViewUserAcceptance({ ...safeInput, persistenceRequested: true })
  const evaluated = [notPrepared, ready, incomplete, approvalBlocked, productionBlocked, executionBlocked, objectBlocked, workflowBlocked, taskBlocked, persistenceBlocked]

  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-business-view-user-acceptance"')
      && pageSource.includes('Business View ≠ Business Execution') && pageSource.includes('User Acceptance ≠ Operation Approval')
      && pageSource.includes('5 / 5 PASS') && !pageSource.includes('data-user-acceptance-action="execute"'),
      FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalBusinessViewOptimization().valid && validateFormalPriceApprovalUserAcceptancePreparation().valid,
      { persistenceSchemaAdded: false, optimizedViewItems: 4, checklistItems: 5 }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalBusinessViewOptimizationCode === FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserAcceptancePreparationCode === FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalBusinessViewOptimizationStatus === 'user_acceptance_ready'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserAcceptancePreparationStatus === 'ready_for_user_acceptance'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalOptimizedViewItemCount === 4
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserAcceptanceChecklistCount === 5
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserAcceptancePassedChecklistCount === 5
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalOperationApprovalGranted === false,
      { viewItems: 4, checklist: '5/5', operationApprovalGranted: false }),
    gate('Rule', notPrepared.preparationStatus === 'not_prepared' && ready.preparationStatus === 'ready_for_user_acceptance'
      && [incomplete, approvalBlocked, productionBlocked, executionBlocked, objectBlocked, workflowBlocked, taskBlocked, persistenceBlocked]
        .every((item) => item.preparationStatus === 'blocked')
      && evaluated.every((item) => item.operationApprovalGranted === false && item.productionOperation === false
        && item.businessExecution === false && item.approvalObjectCreated === false && item.workflowStarted === false
        && item.approvalTaskCreated === false && item.persistencePerformed === false
        && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { ready: ready.preparationStatus, operationApproval: approvalBlocked.preparationStatus, productionOperation: productionBlocked.preparationStatus }),
    gate('Guard', evaluateFormalPriceApprovalBusinessViewUserAcceptanceGuard({ action: 'inspectUserAcceptancePreparation', mode: 'read_only_walkthrough' }).decision === 'allow_read_only'
      && evaluateFormalPriceApprovalBusinessViewUserAcceptanceGuard({ action: 'inspectUserAcceptancePreparation', mode: 'production' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalBusinessViewUserAcceptanceGuard({ action })
        return result.decision === 'deny' && result.operationApprovalGranted === false && result.productionOperation === false
          && result.businessExecution === false && result.approvalObjectCreated === false && result.workflowStarted === false
          && result.approvalTaskCreated === false && result.persistencePerformed === false && result.businessWriteCount === 0
      }), FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalBusinessViewUserAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }

  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis, gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    businessViewMeansBusinessExecution: false, userAcceptanceMeansOperationApproval: false,
    operationApprovalGranted: false, productionOperationEnabled: false, businessExecutionEnabled: false,
    approvalObjectCreated: false, workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false,
    persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-business-view-user-acceptance')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

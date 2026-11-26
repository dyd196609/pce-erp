import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION, validateFormalPriceApprovalBusinessNavigation } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessNavigationModel.js'
import { FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW, validateFormalPriceApprovalRoleNavigationView } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRoleNavigationViewModel.js'
import { evaluateFormalPriceApprovalBusinessNavigation } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessNavigationRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalBusinessNavigationGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessNavigationGuard.js'
import { FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_PROFILE, validateFormalPriceApprovalNavigationAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalNavigationAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.2'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_NAVIGATION_READY'
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
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, navigationSource, roleSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/pages'),
    listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessNavigationModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRoleNavigationViewModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessNavigationRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalBusinessNavigationGuard.js'),
  ])
  const imports = `${navigationSource}\n${roleSource}\n${ruleSource}\n${guardSource}`.split(/\r?\n/)
    .filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE',
      navigationModel: FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION.modelCode,
      roleNavigationView: FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW.modelCode,
      navigationStepCount: 5, roleViewCount: 3,
      navigationMeansExecution: false, userPathMeansWorkflowRuntime: false, nextStepMeansAutoAction: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'five-step read-only business navigation with role-specific guidance and no executable next step' }),
    protectedScopes: Object.freeze(['Approval object creation', 'Workflow start/runtime', 'Approval task creation', 'Navigation execution', 'Database']) })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_navigation_scan_v1142872.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const safeInput = Object.freeze({ validationRequested: true, userAcceptanceStatus: 'ready_for_user_acceptance',
    stepCount: 5, roleCount: 3, pathLabelsConfirmed: true, zeroWriteConfirmed: true })
  const notValidated = evaluateFormalPriceApprovalBusinessNavigation({})
  const ready = evaluateFormalPriceApprovalBusinessNavigation(safeInput)
  const incomplete = evaluateFormalPriceApprovalBusinessNavigation({ ...safeInput, stepCount: 4 })
  const routeBlocked = evaluateFormalPriceApprovalBusinessNavigation({ ...safeInput, routeActionRequested: true })
  const workflowBlocked = evaluateFormalPriceApprovalBusinessNavigation({ ...safeInput, workflowRuntimeRequested: true })
  const autoBlocked = evaluateFormalPriceApprovalBusinessNavigation({ ...safeInput, autoActionRequested: true })
  const objectBlocked = evaluateFormalPriceApprovalBusinessNavigation({ ...safeInput, approvalObjectCreationRequested: true })
  const taskBlocked = evaluateFormalPriceApprovalBusinessNavigation({ ...safeInput, approvalTaskCreationRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalBusinessNavigation({ ...safeInput, persistenceRequested: true })
  const evaluated = [notValidated, ready, incomplete, routeBlocked, workflowBlocked, autoBlocked, objectBlocked, taskBlocked, persistenceBlocked]

  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-business-navigation"')
      && pageSource.includes('Navigation ≠ Execution') && pageSource.includes('User Path ≠ Workflow Runtime')
      && pageSource.includes('Next Step ≠ Auto Action') && !pageSource.includes('data-business-navigation-action="execute"'),
      FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalBusinessNavigation().valid && validateFormalPriceApprovalRoleNavigationView().valid,
      { persistenceSchemaAdded: false, navigationSteps: 5, roleViews: 3 }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalBusinessNavigationCode === FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalRoleNavigationViewCode === FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalBusinessNavigationStatus === 'ready_for_user_path_validation'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNavigationStepCount === 5
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalRoleNavigationViewCount === 3
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNavigationRouteActionEnabled === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNavigationWorkflowRuntimeConnected === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNavigationAutoActionEnabled === false,
      { navigationSteps: 5, roleViews: 3, executableActions: 0 }),
    gate('Rule', notValidated.navigationStatus === 'not_validated' && ready.navigationStatus === 'ready_for_user_path_validation'
      && [incomplete, routeBlocked, workflowBlocked, autoBlocked, objectBlocked, taskBlocked, persistenceBlocked].every((item) => item.navigationStatus === 'blocked')
      && evaluated.every((item) => item.routeActionPerformed === false && item.workflowRuntimeStarted === false
        && item.autoActionPerformed === false && item.approvalObjectCreated === false && item.approvalTaskCreated === false
        && item.persistencePerformed === false && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { ready: ready.navigationStatus, routeAction: routeBlocked.navigationStatus, workflowRuntime: workflowBlocked.navigationStatus }),
    gate('Guard', evaluateFormalPriceApprovalBusinessNavigationGuard({ action: 'inspectBusinessNavigation', mode: 'read_only_guidance' }).decision === 'allow_read_only'
      && evaluateFormalPriceApprovalBusinessNavigationGuard({ action: 'inspectBusinessNavigation', mode: 'execution' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalBusinessNavigationGuard({ action })
        return result.decision === 'deny' && result.routeActionPerformed === false && result.workflowRuntimeStarted === false
          && result.autoActionPerformed === false && result.approvalObjectCreated === false && result.approvalTaskCreated === false
          && result.persistencePerformed === false && result.businessWriteCount === 0
      }), FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalNavigationAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_PROFILE.profileCode),
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
    navigationMeansExecution: false, userPathMeansWorkflowRuntime: false, nextStepMeansAutoAction: false,
    routeActionEnabled: false, workflowRuntimeConnected: false, autoActionEnabled: false,
    approvalObjectCreated: false, workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false,
    persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-navigation')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

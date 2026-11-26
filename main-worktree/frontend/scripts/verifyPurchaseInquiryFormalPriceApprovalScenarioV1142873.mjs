import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_SCENARIO_MODEL, validateFormalPriceApprovalScenarioModel } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalScenarioModel.js'
import { evaluateFormalPriceApprovalScenario } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalScenarioRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_SCENARIO_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalScenarioGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalScenarioGuard.js'
import { FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_PROFILE, validateFormalPriceApprovalScenarioAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalScenarioAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.3'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_SCENARIO_READY'
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
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, modelSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/pages'),
    listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalScenarioModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalScenarioRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalScenarioGuard.js'),
  ])
  const imports = `${modelSource}\n${ruleSource}\n${guardSource}`.split(/\r?\n/)
    .filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE',
      scenarioModel: FORMAL_PRICE_APPROVAL_SCENARIO_MODEL.modelCode,
      scenarioTypes: Object.freeze(['normal', 'special', 'exception']), scenarioCount: 3,
      scenarioDataMeansProductionData: false, expectedResultMeansAutoDecision: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'synthetic normal, special, and exception acceptance cases with expected results and zero business effect' }),
    protectedScopes: Object.freeze(['Business object creation', 'Approval object creation', 'Workflow start', 'Auto decision', 'Production data', 'Database']) })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_scenario_scan_v1142873.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const normal = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'normal', evidenceComplete: true, supplierCount: 3 })
  const special = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'special', specialPurchase: true, supplierCount: 1 })
  const exception = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'exception', evidenceComplete: false })
  const notStarted = evaluateFormalPriceApprovalScenario({})
  const productionBlocked = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'normal', evidenceComplete: true, supplierCount: 3, productionDataRequested: true })
  const decisionBlocked = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'normal', evidenceComplete: true, supplierCount: 3, autoDecisionRequested: true })
  const objectBlocked = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'normal', evidenceComplete: true, supplierCount: 3, businessObjectCreationRequested: true })
  const approvalBlocked = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'normal', evidenceComplete: true, supplierCount: 3, approvalObjectCreationRequested: true })
  const workflowBlocked = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'normal', evidenceComplete: true, supplierCount: 3, workflowStartRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalScenario({ simulationRequested: true, scenarioType: 'normal', evidenceComplete: true, supplierCount: 3, persistenceRequested: true })
  const evaluated = [notStarted, normal, special, exception, productionBlocked, decisionBlocked, objectBlocked, approvalBlocked, workflowBlocked, persistenceBlocked]

  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-scenario-acceptance"')
      && pageSource.includes('data-scenario-type="normal"') && pageSource.includes('data-scenario-type="special"')
      && pageSource.includes('data-scenario-type="exception"') && pageSource.includes('Scenario Data ≠ Production Data')
      && pageSource.includes('Expected Result ≠ Auto Decision') && !pageSource.includes('data-scenario-action="execute"'),
      FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalScenarioModel().valid,
      { persistenceSchemaAdded: false, scenarioTypes: ['normal', 'special', 'exception'] }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalScenarioModelCode === FORMAL_PRICE_APPROVAL_SCENARIO_MODEL.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalScenarioStatus === 'ready_for_user_acceptance'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalScenarioCount === 3
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNormalScenarioCount === 1
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalSpecialScenarioCount === 1
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalExceptionScenarioCount === 1
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalScenarioProductionDataUsed === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalScenarioAutoDecisionPerformed === false,
      { scenarios: 3, productionDataUsed: false, autoDecisionPerformed: false }),
    gate('Rule', notStarted.scenarioResult === 'not_started' && normal.scenarioResult === 'ready_for_manual_review'
      && special.scenarioResult === 'manual_confirmation_required' && exception.scenarioResult === 'blocked'
      && [productionBlocked, decisionBlocked, objectBlocked, approvalBlocked, workflowBlocked, persistenceBlocked].every((item) => item.scenarioResult === 'blocked')
      && evaluated.every((item) => item.scenarioDataMeansProductionData === false && item.expectedResultMeansAutoDecision === false
        && item.businessObjectCreated === false && item.approvalObjectCreated === false && item.workflowStarted === false
        && item.autoDecisionPerformed === false && item.persistencePerformed === false
        && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { normal: normal.scenarioResult, special: special.scenarioResult, exception: exception.scenarioResult }),
    gate('Guard', evaluateFormalPriceApprovalScenarioGuard({ action: 'inspectScenarioCase', mode: 'synthetic_read_only' }).decision === 'allow_read_only'
      && evaluateFormalPriceApprovalScenarioGuard({ action: 'inspectScenarioCase', mode: 'production' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_SCENARIO_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalScenarioGuard({ action })
        return result.decision === 'deny' && result.productionDataUsed === false && result.autoDecisionPerformed === false
          && result.businessObjectCreated === false && result.approvalObjectCreated === false && result.workflowStarted === false
          && result.persistencePerformed === false && result.businessWriteCount === 0
      }), FORMAL_PRICE_APPROVAL_SCENARIO_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalScenarioAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_PROFILE.profileCode),
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
    scenarioDataMeansProductionData: false, expectedResultMeansAutoDecision: false,
    productionDataUsed: false, autoDecisionPerformed: false, businessObjectCreated: false,
    approvalObjectCreated: false, workflowStarted: false, workflowInstanceCreated: false,
    persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-scenario')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

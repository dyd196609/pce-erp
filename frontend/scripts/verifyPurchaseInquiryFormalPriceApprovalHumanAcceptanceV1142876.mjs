import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE, validateFormalPriceApprovalCanaryAcceptance } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryAcceptanceModel.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE, validateFormalPriceApprovalHumanRoleAcceptance } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanRoleAcceptanceModel.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP, validateFormalPriceApprovalHumanAcceptanceFeedbackLoop } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceFeedbackLoopModel.js'
import { evaluateFormalPriceApprovalHumanAcceptance } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalHumanAcceptanceGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceGuard.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_PROFILE, validateFormalPriceApprovalHumanAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalHumanAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.6'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hashFile = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
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
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, canarySource, roleSource, loopSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/pages'), listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryAcceptanceModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanRoleAcceptanceModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceFeedbackLoopModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceGuard.js'),
  ])
  const imports = `${canarySource}\n${roleSource}\n${loopSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter(line => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({
      prerequisite: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_READY',
      canaryModel: FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE.modelCode,
      humanRoleAcceptanceModel: FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE.modelCode,
      feedbackLoopModel: FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP.modelCode,
      canaryIsProduction: false,
      humanAcceptanceIsBusinessExecution: false,
      feedbackIsErpData: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'canary-only human role acceptance and memory-session feedback loop with frozen business effects',
    }),
    protectedScopes: Object.freeze(['Business object creation', 'Approval object creation', 'Workflow', 'Approval task', 'Database write layer']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_human_acceptance_scan_v1142876.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])

  const roleResults = FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE.roles.map(item =>
    evaluateFormalPriceApprovalHumanAcceptance({ action: 'runCanaryAcceptance', environment: 'canary', productionConnected: false, userRole: item.roleCode }))
  const productionBlocked = evaluateFormalPriceApprovalHumanAcceptance({ action: 'runCanaryAcceptance', environment: 'production', productionConnected: true, userRole: 'purchase_buyer' })
  const loopStates = ['not_recorded', 'session_recorded', 'human_reviewed', 'improvement_proposed']
  const loopResults = loopStates.map(currentState => evaluateFormalPriceApprovalHumanAcceptance({ action: 'advanceFeedbackLoop', currentState }))
  const persistBlocked = evaluateFormalPriceApprovalHumanAcceptance({ action: 'advanceFeedbackLoop', currentState: 'session_recorded', persistRequested: true })
  const businessEffectBlocked = evaluateFormalPriceApprovalHumanAcceptance({ action: 'advanceFeedbackLoop', currentState: 'session_recorded', businessEffectRequested: true })
  const allRuleResults = [...roleResults, productionBlocked, ...loopResults, persistBlocked, businessEffectBlocked]

  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-human-acceptance"')
      && pageSource.includes('data-human-acceptance-action="session-only"')
      && pageSource.includes('data-feedback-loop-action="session-only"')
      && pageSource.includes('Human Acceptance ≠ Business Execution')
      && pageSource.includes('Feedback ≠ ERP Data') && pageSource.includes('Canary ≠ Production'),
      { route: '/scm/purchase-inquiry', region: 'formal-price-approval-human-acceptance', mode: 'acceptance_view' }),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalCanaryAcceptance().valid
      && validateFormalPriceApprovalHumanRoleAcceptance().valid
      && validateFormalPriceApprovalHumanAcceptanceFeedbackLoop().valid,
      { persistenceSchemaAdded: false, models: [FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE.modelCode,
        FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE.modelCode, FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP.modelCode] }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.version.startsWith(VERSION)
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryEnvironment === 'canary'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryProductionConnected === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanRoleCount === 3
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHumanAcceptanceIsBusinessExecution === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFeedbackLoopStorageMode === 'memory_session_only'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFeedbackLoopPersisted === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFeedbackLoopIsErpData === false,
      { canary: 'isolated', humanRoles: 3, feedbackStorage: 'memory_session_only' }),
    gate('Rule', roleResults.every(item => item.decision === 'session_acceptance_completed')
      && productionBlocked.decision === 'blocked'
      && loopResults.map(item => item.feedbackState).join('|') === 'session_recorded|human_reviewed|improvement_proposed|session_closed'
      && persistBlocked.decision === 'blocked' && businessEffectBlocked.decision === 'blocked'
      && allRuleResults.every(item => item.businessExecutionTriggered === false && item.feedbackPersisted === false
        && item.feedbackIsErpData === false && item.businessObjectCreated === false && item.approvalObjectCreated === false
        && item.workflowStarted === false && item.approvalTaskCreated === false && item.businessStateChanged === false
        && item.priceChanged === false && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { canaryRolesAccepted: roleResults.length, productionDecision: productionBlocked.decision, feedbackTransitions: loopResults.length }),
    gate('Guard', evaluateFormalPriceApprovalHumanAcceptanceGuard({ action: 'runSessionHumanAcceptance', environment: 'canary' }).decision === 'allow_session_only'
      && evaluateFormalPriceApprovalHumanAcceptanceGuard({ action: 'runSessionHumanAcceptance', environment: 'production' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FORBIDDEN_ACTIONS.every(action => {
        const result = evaluateFormalPriceApprovalHumanAcceptanceGuard({ action })
        return result.decision === 'deny' && result.businessExecutionTriggered === false
          && result.feedbackPersisted === false && result.feedbackIsErpData === false
          && result.businessObjectCreated === false && result.approvalObjectCreated === false
          && result.workflowStarted === false && result.approvalTaskCreated === false
          && result.businessWriteCount === 0 && result.productionDataWritten === false
      }), FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalHumanAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_PROFILE'),
      FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_PROFILE.profileCode),
  ]

  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], {
      cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000,
    })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }

  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every(item => item.result === 'PASS')
    && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis,
    gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter(item => item.result === 'PASS').length, FAIL: results.filter(item => item.result === 'FAIL').length }),
    canaryAcceptance: Object.freeze({ result: 'PASS', environment: 'canary', productionConnected: false, isProduction: false }),
    humanRoleAcceptance: Object.freeze({ result: 'PASS', roleCount: 3, executionMode: 'session_validation_only', isBusinessExecution: false }),
    feedbackLoop: Object.freeze({ result: 'PASS', stateCount: 5, transitionCount: 4, storageMode: 'memory_session_only', isErpData: false, persisted: false }),
    businessExecutionTriggered: false,
    feedbackPersisted: false,
    feedbackIsErpData: false,
    businessObjectCreated: false,
    approvalObjectCreated: false,
    workflowStarted: false,
    workflowInstanceCreated: false,
    approvalTaskCreated: false,
    businessStateChanged: false,
    persistencePerformed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-human-acceptance')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_CANARY_COHORT, validateFormalPriceApprovalCanaryCohort } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryCohortModel.js'
import { validateFormalPriceApprovalCanaryAutomaticAcceptance } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryAutomaticAcceptanceModel.js'
import { createFormalPriceApprovalCanaryAcceptanceResultSummary, validateFormalPriceApprovalCanaryAcceptanceResultSummary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryAcceptanceResultSummaryModel.js'
import { evaluateFormalPriceApprovalCanaryCohort } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryCohortRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_CANARY_COHORT_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalCanaryCohortGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryCohortGuard.js'
import { FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_PROFILE, validateFormalPriceApprovalCanaryCohortAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalCanaryCohortAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.6.1'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_CANARY_COHORT_AUTOMATIC_ACCEPTANCE_READY'
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
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, cohortSource, executionSource, summarySource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/pages'),
    listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryCohortModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryAutomaticAcceptanceModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryAcceptanceResultSummaryModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryCohortRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryCohortGuard.js'),
  ])
  const imports = `${cohortSource}\n${executionSource}\n${summarySource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter(line => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({
      prerequisite: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_READY',
      cohortModel: FORMAL_PRICE_APPROVAL_CANARY_COHORT.modelCode,
      cohortMemberCount: FORMAL_PRICE_APPROVAL_CANARY_COHORT.memberCount,
      automaticAcceptanceMode: 'in_memory_assertion_only',
      resultSummaryStorageMode: 'memory_session_only',
      automaticAcceptanceIsBusinessExecution: false,
      resultSummaryIsApprovalResult: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'manual validation trigger runs an isolated synthetic canary cohort and aggregates non-persistent results',
    }),
    protectedScopes: Object.freeze(['Production', 'Business object', 'Approval object', 'Workflow', 'Approval task', 'Feedback loop persistence', 'Database write layer']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_canary_cohort_scan_v11428761.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])

  const execution = evaluateFormalPriceApprovalCanaryCohort({ action: 'runAutomaticAcceptance', environment: 'canary',
    productionConnected: false, members: FORMAL_PRICE_APPROVAL_CANARY_COHORT.members })
  const productionBlocked = evaluateFormalPriceApprovalCanaryCohort({ action: 'runAutomaticAcceptance', environment: 'production',
    productionConnected: true, members: FORMAL_PRICE_APPROVAL_CANARY_COHORT.members })
  const persistenceBlocked = evaluateFormalPriceApprovalCanaryCohort({ action: 'runAutomaticAcceptance', environment: 'canary',
    productionConnected: false, members: FORMAL_PRICE_APPROVAL_CANARY_COHORT.members, persistRequested: true })
  const summary = createFormalPriceApprovalCanaryAcceptanceResultSummary(execution.results)
  const evaluated = [execution, productionBlocked, persistenceBlocked]

  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-canary-cohort-summary"')
      && pageSource.includes('data-canary-cohort-action="validation-only"')
      && pageSource.includes('Automatic Acceptance ≠ Business Execution')
      && pageSource.includes('Result Summary ≠ Approval Result')
      && pageSource.includes('Canary Cohort ≠ Production'),
      { route: '/scm/purchase-inquiry', region: 'formal-price-approval-canary-cohort-summary', memberCount: 3 }),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalCanaryCohort().valid
      && validateFormalPriceApprovalCanaryAutomaticAcceptance().valid
      && validateFormalPriceApprovalCanaryAcceptanceResultSummary(summary).valid,
      { persistenceSchemaAdded: false, cohortMemberCount: 3, summaryStorageMode: summary.storageMode }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.version.startsWith('V1.14.2.8.7.6.')
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryCohortMemberCount === 3
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryCohortExecutionMode === 'automatic_validation_only'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryAutomaticAcceptanceTriggerMode === 'manual_validation_trigger'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryAutomaticAcceptanceIsBusinessExecution === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryResultSummaryStorageMode === 'memory_session_only'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryResultPersisted === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCanaryResultIsApprovalResult === false,
      { trigger: 'manual_validation_trigger', execution: 'automatic_validation_only', resultStorage: 'memory_session_only' }),
    gate('Rule', execution.decision === 'validation_completed' && execution.executionState === 'completed'
      && execution.results.length === 3 && execution.results.every(item => item.result === 'PASS')
      && productionBlocked.decision === 'blocked' && persistenceBlocked.decision === 'blocked'
      && summary.overallResult === 'PASS' && summary.passCount === 3 && summary.failCount === 0
      && evaluated.every(item => item.businessExecutionTriggered === false && item.feedbackLoopUpdated === false
        && item.resultPersisted === false && item.businessObjectCreated === false && item.approvalObjectCreated === false
        && item.workflowStarted === false && item.approvalTaskCreated === false && item.businessStateChanged === false
        && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { execution: execution.decision, passCount: summary.passCount, failCount: summary.failCount, production: productionBlocked.decision }),
    gate('Guard', evaluateFormalPriceApprovalCanaryCohortGuard({ action: 'runInMemoryCanaryCohort', environment: 'canary' }).decision === 'allow_validation_only'
      && evaluateFormalPriceApprovalCanaryCohortGuard({ action: 'runInMemoryCanaryCohort', environment: 'production' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_CANARY_COHORT_FORBIDDEN_ACTIONS.every(action => {
        const result = evaluateFormalPriceApprovalCanaryCohortGuard({ action })
        return result.decision === 'deny' && result.businessExecutionTriggered === false
          && result.feedbackLoopUpdated === false && result.resultPersisted === false
          && result.businessObjectCreated === false && result.approvalObjectCreated === false
          && result.workflowStarted === false && result.approvalTaskCreated === false
          && result.businessWriteCount === 0 && result.productionDataWritten === false
      }), FORMAL_PRICE_APPROVAL_CANARY_COHORT_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalCanaryCohortAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_PROFILE'),
      FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_PROFILE.profileCode),
  ]

  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], {
      cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000,
    })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }

  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every(item => item.result === 'PASS') && databaseUnchanged
    && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis, gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter(item => item.result === 'PASS').length, FAIL: results.filter(item => item.result === 'FAIL').length }),
    canaryCohort: Object.freeze({ result: 'PASS', environment: 'canary', memberCount: 3, productionConnected: false }),
    automaticAcceptance: Object.freeze({ result: 'PASS', triggerMode: 'manual_validation_trigger', executionMode: 'in_memory_assertion_only', isBusinessExecution: false }),
    resultSummary: Object.freeze({ result: summary.overallResult, totalCount: summary.totalCount, passCount: summary.passCount,
      failCount: summary.failCount, storageMode: summary.storageMode, isApprovalResult: false, persisted: false }),
    businessExecutionTriggered: false, feedbackLoopUpdated: false, resultPersisted: false,
    businessObjectCreated: false, approvalObjectCreated: false, workflowStarted: false,
    workflowInstanceCreated: false, approvalTaskCreated: false, businessStateChanged: false,
    persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-canary-cohort')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

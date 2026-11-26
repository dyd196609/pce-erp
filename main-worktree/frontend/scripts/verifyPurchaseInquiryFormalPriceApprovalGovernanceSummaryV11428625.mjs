import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_GOVERNANCE_STAGE_MATRIX, validateFormalPriceApprovalGovernanceStageMatrix } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalGovernanceStageMatrix.js'
import { FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY, validateFormalPriceApprovalGovernanceSummary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalGovernanceSummaryModel.js'
import { FORMAL_PRICE_APPROVAL_OPERATION_READINESS, validateFormalPriceApprovalOperationReadiness } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalOperationReadinessModel.js'
import { evaluateFormalPriceApprovalGovernanceSummary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalGovernanceSummaryRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalGovernanceSummaryGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalGovernanceSummaryGuard.js'
import { FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_PROFILE, validateFormalPriceApprovalGovernanceSummaryAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalGovernanceSummaryAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.25'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, matrixSource, summarySource, readinessSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/runtime'), listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalGovernanceStageMatrix.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalGovernanceSummaryModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalOperationReadinessModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalGovernanceSummaryRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalGovernanceSummaryGuard.js'),
  ])
  const imports = `${matrixSource}\n${summarySource}\n${readinessSource}\n${ruleSource}\n${guardSource}`.split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE', summary: FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY.summaryCode,
      stageMatrix: FORMAL_PRICE_APPROVAL_GOVERNANCE_STAGE_MATRIX.matrixCode, operationReadiness: FORMAL_PRICE_APPROVAL_OPERATION_READINESS.readinessCode,
      governanceSummaryMeansExecution: false, validationMeansOperation: false, passMeansAutoRun: false,
      stageCount: 12, passedStageCount: 12, executionEnabledStageCount: 0,
      workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|stateManager|dataGateway|transactionEngine|commandDispatcher/i.test(imports),
      strategy: 'closed-loop governance summary with validation-only operation readiness and zero executable stages' }),
    protectedScopes: Object.freeze(['Approval object creation', 'Workflow start', 'Approval task creation', 'Operation execution', 'Database']) })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_governance_summary_scan_v11428625.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }
  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js')])
  const safeInput = Object.freeze({ assessmentRequested: true, auditArchiveStatus: 'audit_archive_definition_ready', passedStageCount: 12, failedStageCount: 0, zeroWriteConfirmed: true, protectedBoundariesConfirmed: true })
  const ready = evaluateFormalPriceApprovalGovernanceSummary(safeInput)
  const notAssessed = evaluateFormalPriceApprovalGovernanceSummary({})
  const incomplete = evaluateFormalPriceApprovalGovernanceSummary({ ...safeInput, passedStageCount: 11 })
  const objectBlocked = evaluateFormalPriceApprovalGovernanceSummary({ ...safeInput, approvalObjectCreationRequested: true })
  const workflowBlocked = evaluateFormalPriceApprovalGovernanceSummary({ ...safeInput, workflowStartRequested: true })
  const taskBlocked = evaluateFormalPriceApprovalGovernanceSummary({ ...safeInput, approvalTaskCreationRequested: true })
  const operationBlocked = evaluateFormalPriceApprovalGovernanceSummary({ ...safeInput, operationExecutionRequested: true })
  const autoRunBlocked = evaluateFormalPriceApprovalGovernanceSummary({ ...safeInput, autoRunRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalGovernanceSummary({ ...safeInput, persistenceRequested: true })
  const evaluated = [notAssessed, ready, incomplete, objectBlocked, workflowBlocked, taskBlocked, operationBlocked, autoRunBlocked, persistenceBlocked]
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-governance-summary"') && pageSource.includes('Governance Summary ≠ Execution')
      && pageSource.includes('Validation ≠ Operation') && pageSource.includes('PASS ≠ Auto Run') && pageSource.includes('12 / 12 / 0'), FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalGovernanceStageMatrix().valid && validateFormalPriceApprovalGovernanceSummary().valid
      && validateFormalPriceApprovalOperationReadiness().valid && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_OPERATION_READINESS.persistenceAdapterConnected === false, { persistenceSchemaAdded: false, stages: FORMAL_PRICE_APPROVAL_GOVERNANCE_STAGE_MATRIX.stages.map((stage) => stage.stageCode) }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalGovernanceSummaryCode === FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY.summaryCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalGovernanceStageMatrixCode === FORMAL_PRICE_APPROVAL_GOVERNANCE_STAGE_MATRIX.matrixCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalOperationReadinessCode === FORMAL_PRICE_APPROVAL_OPERATION_READINESS.readinessCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalGovernanceStageCount === 12 && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalGovernancePassedStageCount === 12
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalGovernanceExecutionEnabledStageCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalOperationReadinessStatus === 'validation_ready'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalOperationEnabled === false && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalAutoRunEnabled === false, { stages: 12, passed: 12, executable: 0, operationEnabled: false, autoRunEnabled: false }),
    gate('Rule', notAssessed.readinessStatus === 'not_assessed' && ready.readinessStatus === 'validation_ready'
      && [incomplete, objectBlocked, workflowBlocked, taskBlocked, operationBlocked, autoRunBlocked, persistenceBlocked].every((item) => item.readinessStatus === 'blocked')
      && evaluated.every((item) => item.approvalObjectCreated === false && item.workflowStarted === false && item.workflowInstanceCreated === false && item.approvalTaskCreated === false && item.operationExecuted === false && item.autoRunPerformed === false && item.businessStateChanged === false && item.persistencePerformed === false && item.businessWriteCount === 0 && item.productionDataWritten === false), { ready: ready.readinessStatus, operation: operationBlocked.readinessStatus, autoRun: autoRunBlocked.readinessStatus }),
    gate('Guard', evaluateFormalPriceApprovalGovernanceSummaryGuard({ action: 'inspectGovernanceSummary', mode: 'validation_only' }).decision === 'allow_validation_only'
      && evaluateFormalPriceApprovalGovernanceSummaryGuard({ action: 'inspectGovernanceSummary', mode: 'execution' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_FORBIDDEN_ACTIONS.every((action) => { const result = evaluateFormalPriceApprovalGovernanceSummaryGuard({ action }); return result.decision === 'deny' && result.approvalObjectCreated === false && result.workflowStarted === false && result.approvalTaskCreated === false && result.operationExecuted === false && result.autoRunPerformed === false && result.persistencePerformed === false }), FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalGovernanceSummaryAcceptance().valid && registrySource.includes('FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }
  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL', problemAnalysis: scan.analysis,
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    governanceSummaryMeansExecution: false, validationMeansOperation: false, passMeansAutoRun: false, operationEnabled: false, autoRunEnabled: false,
    approvalObjectCreated: false, workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false, operationExecuted: false, autoRunPerformed: false, businessStateChanged: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-governance-summary')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

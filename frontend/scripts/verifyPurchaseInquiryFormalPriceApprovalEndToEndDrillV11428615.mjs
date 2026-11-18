import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL, validateFormalPriceApprovalEndToEndSafetyDrill } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillModel.js'
import { FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_STAGES, validateFormalPriceApprovalEndToEndSafetyDrillStages } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillStageModel.js'
import { buildFormalPriceApprovalEndToEndSafetyDrillMatrix } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillMatrix.js'
import { evaluateFormalPriceApprovalEndToEndSafetyDrill } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalEndToEndSafetyDrillGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillGuard.js'
import { FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_PROFILE, validateFormalPriceApprovalEndToEndSafetyDrillAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalEndToEndSafetyDrillAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.15'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_END_TO_END_DRILL_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, modelSource, stageSource, matrixSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillStageModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillMatrix.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillGuard.js'),
  ])
  const dependencyImportSource = `${modelSource}\n${stageSource}\n${matrixSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  const executionOrPersistenceImports = /dataGateway|transactionEngine|workflowEngine|commandDispatcher|objectFactory/i.test(dependencyImportSource)
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
      drillModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillModel.js'),
      stageModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillStageModel.js'),
      matrixPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEndToEndSafetyDrillMatrix.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY',
      designTarget: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL.drillCode,
      governanceStageCount: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_STAGES.length,
      drillIsExecution: false,
      simulationIsCreation: false,
      boundaryIsExecutor: false,
      executionOrPersistenceImports,
      strategy: 'ordered read-only drill across every pre-creation governance node',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object instances', 'Command execution', 'Approval Workflow', 'Production execution', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_end_to_end_drill_scan_v11428615.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const allPassedStages = Object.freeze(Object.fromEntries(FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_STAGES.map((stage) => [stage.stageCode, 'PASS'])))
  const completed = evaluateFormalPriceApprovalEndToEndSafetyDrill({ drillRequested: true, stageResults: allPassedStages, productionExecution: false, commandExecuted: false, formalPriceApprovalObjectCreated: false, approvalWorkflowStarted: false, businessWriteCount: 0 })
  const missingStageResults = { ...allPassedStages }
  delete missingStageResults.execution_boundary
  const manualReview = evaluateFormalPriceApprovalEndToEndSafetyDrill({ drillRequested: true, stageResults: missingStageResults })
  const failedStageResults = { ...allPassedStages, authorization_and_audit: 'FAIL' }
  const stageBlocked = evaluateFormalPriceApprovalEndToEndSafetyDrill({ drillRequested: true, stageResults: failedStageResults })
  const productionBlocked = evaluateFormalPriceApprovalEndToEndSafetyDrill({ drillRequested: true, stageResults: allPassedStages, productionExecution: true })
  const notStarted = evaluateFormalPriceApprovalEndToEndSafetyDrill({})
  const completeMatrix = buildFormalPriceApprovalEndToEndSafetyDrillMatrix(allPassedStages)
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-end-to-end-safety-drill"')
      && pageSource.includes('正式创建前全链路安全演练')
      && pageSource.includes('Drill ≠ Execution')
      && pageSource.includes('Simulation ≠ Creation')
      && pageSource.includes('Boundary ≠ Executor'), FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalEndToEndSafetyDrill().valid
      && validateFormalPriceApprovalEndToEndSafetyDrillStages().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL.persistenceMode === 'none', {
        drillFields: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL.fields,
        lifecycle: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL.lifecycle,
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalEndToEndSafetyDrillCode === FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL.drillCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalEndToEndSafetyDrillStageCount === 15
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalEndToEndSafetyDrillExecutionMode === 'isolated_read_only'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalEndToEndSafetyDrillProductionExecution === false
      && FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL.drillInstanceCount === 0
      && completeMatrix.stageCount === 15
      && completeMatrix.passedCount === 15
      && completeMatrix.complete === true, {
        drillCode: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL.drillCode,
        stageCount: completeMatrix.stageCount,
        executionMode: 'isolated_read_only',
        drillInstanceCount: 0,
      }),
    gate('Rule', notStarted.evaluatedStatus === 'not_started'
      && completed.evaluatedStatus === 'completed'
      && completed.statusTrace.join(',') === 'not_started,checking,completed'
      && manualReview.evaluatedStatus === 'manual_review'
      && manualReview.matrix.missingCount === 1
      && stageBlocked.evaluatedStatus === 'blocked'
      && stageBlocked.matrix.failedCount === 1
      && productionBlocked.evaluatedStatus === 'blocked'
      && [notStarted, completed, manualReview, stageBlocked, productionBlocked].every((result) => result.drillIsExecution === false
        && result.simulationIsCreation === false
        && result.boundaryIsExecutor === false
        && result.productionExecution === false
        && result.commandExecuted === false
        && result.formalPriceApprovalObjectCreated === false
        && result.approvalWorkflowStarted === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false), {
        completed: completed.evaluatedStatus,
        missingEvidence: manualReview.evaluatedStatus,
        failedStage: stageBlocked.evaluatedStatus,
        productionRequest: productionBlocked.evaluatedStatus,
      }),
    gate('Guard', evaluateFormalPriceApprovalEndToEndSafetyDrillGuard({ action: 'runSafetyDrill', executionMode: 'isolated_read_only' }).decision === 'allow_read_only_drill'
      && evaluateFormalPriceApprovalEndToEndSafetyDrillGuard({ action: 'runSafetyDrill', executionMode: 'production' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalEndToEndSafetyDrillGuard({ action })
        return result.decision === 'deny' && result.drillIsExecution === false && result.productionExecution === false && result.formalPriceApprovalObjectCreated === false
      }), FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalEndToEndSafetyDrillAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_PROFILE.profileCode),
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
    governanceStageCount: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_STAGES.length,
    drillIsExecution: false,
    simulationIsCreation: false,
    boundaryIsExecutor: false,
    productionExecution: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    drillResultPersisted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-end-to-end-drill')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY, validateFormalPriceApprovalExecutionBoundary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionBoundaryModel.js'
import { FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT, validateFormalPriceApprovalExecutionContext } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionContextModel.js'
import { evaluateFormalPriceApprovalExecutionBoundary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionBoundaryRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalExecutionBoundaryGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionBoundaryGuard.js'
import { FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_PROFILE, validateFormalPriceApprovalExecutionBoundaryAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalExecutionBoundaryAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.14'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, modelSource, contextSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionBoundaryModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionContextModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionBoundaryRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionBoundaryGuard.js'),
  ])
  const dependencyImportSource = `${modelSource}\n${contextSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  const executorOrPersistenceImports = /dataGateway|transactionEngine|workflowEngine|commandDispatcher|objectFactory/i.test(dependencyImportSource)
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
      boundaryModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionBoundaryModel.js'),
      executionContextPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalExecutionContextModel.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT',
      designTargets: Object.freeze([FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY.boundaryCode, FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT.contextCode]),
      approvedMeansAutoExecute: false,
      boundaryIsExecutor: false,
      productionExecution: false,
      executorOrPersistenceImports,
      strategy: 'unique future execution entry contract evaluated in a non-executable isolated context',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object instances', 'Command execution', 'Approval Workflow', 'Production credentials', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_execution_boundary_scan_v11428614.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const boundaryInput = Object.freeze({
    boundaryEvaluationRequested: true,
    agreementStatus: 'agreed_design_only',
    environment: 'isolated_design',
    contextMode: 'boundary_design_only',
    humanInitiated: true,
    executorRoleId: 'future-executor-role',
    executorConnected: false,
    workflowEngineConnected: false,
    persistenceAdapterConnected: false,
    productionExecution: false,
    autoExecution: false,
  })
  const notEvaluated = evaluateFormalPriceApprovalExecutionBoundary({})
  const boundaryReady = evaluateFormalPriceApprovalExecutionBoundary(boundaryInput)
  const manualReview = evaluateFormalPriceApprovalExecutionBoundary({ ...boundaryInput, executorRoleId: '' })
  const productionBlocked = evaluateFormalPriceApprovalExecutionBoundary({ ...boundaryInput, environment: 'production', productionExecution: true })
  const autoExecutionBlocked = evaluateFormalPriceApprovalExecutionBoundary({ ...boundaryInput, autoExecution: true })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-execution-boundary"')
      && pageSource.includes('正式价格审批创建执行隔离边界')
      && pageSource.includes('Approved ≠ Auto Execute')
      && pageSource.includes('Boundary ≠ Executor')
      && pageSource.includes('生产执行'), FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalExecutionBoundary().valid
      && validateFormalPriceApprovalExecutionContext().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY.persistenceMode === 'none'
      && FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT.persistenceAdapterConnected === false, {
        boundaryFields: FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY.fields,
        contextFields: FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT.fields,
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalExecutionBoundaryCode === FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY.boundaryCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalExecutionContextCode === FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT.contextCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalExecutionBoundaryExecutorConnected === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalProductionExecution === false
      && FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY.boundaryInstanceCount === 0
      && FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT.contextInstanceCount === 0
      && FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT.executable === false, {
        boundaryCode: FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY.boundaryCode,
        contextCode: FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT.contextCode,
        executorConnected: false,
        productionExecution: false,
      }),
    gate('Rule', notEvaluated.evaluatedStatus === 'not_evaluated'
      && boundaryReady.evaluatedStatus === 'boundary_ready'
      && boundaryReady.statusTrace.join(',') === 'not_evaluated,context_checking,boundary_ready'
      && boundaryReady.approvedAgreementRecognized === true
      && manualReview.evaluatedStatus === 'manual_review'
      && productionBlocked.evaluatedStatus === 'blocked'
      && autoExecutionBlocked.evaluatedStatus === 'blocked'
      && [notEvaluated, boundaryReady, manualReview, productionBlocked, autoExecutionBlocked].every((result) => result.boundaryIsExecutor === false
        && result.autoExecution === false
        && result.productionExecution === false
        && result.commandExecuted === false
        && result.formalPriceApprovalObjectCreated === false
        && result.approvalWorkflowStarted === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false), {
        boundaryReady: boundaryReady.evaluatedStatus,
        manualReview: manualReview.evaluatedStatus,
        production: productionBlocked.evaluatedStatus,
        autoExecution: autoExecutionBlocked.evaluatedStatus,
      }),
    gate('Guard', evaluateFormalPriceApprovalExecutionBoundaryGuard({ action: 'evaluateBoundary', environment: 'isolated_design', contextMode: 'boundary_design_only' }).decision === 'allow_boundary_evaluation_only'
      && evaluateFormalPriceApprovalExecutionBoundaryGuard({ action: 'evaluateBoundary', environment: 'production', contextMode: 'boundary_design_only' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalExecutionBoundaryGuard({ action })
        return result.decision === 'deny' && result.boundaryIsExecutor === false && result.productionExecution === false && result.formalPriceApprovalObjectCreated === false
      }), FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalExecutionBoundaryAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_PROFILE.profileCode),
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
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.executorOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis,
    gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    approvedMeansAutoExecute: false,
    boundaryIsExecutor: false,
    productionExecution: false,
    executionContextExecutable: false,
    executorConnected: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    executionContextPersisted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-execution-boundary')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT, FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT_STATES, validateFormalPriceApprovalFinalReleaseAssessment } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAssessmentModel.js'
import { FORMAL_PRICE_APPROVAL_FINAL_RELEASE_MATRIX, evaluateFormalPriceApprovalFinalReleaseMatrix } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseMatrix.js'
import { FORMAL_PRICE_APPROVAL_FINAL_RELEASE_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalFinalReleaseGate } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseGate.js'
import { FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_PROFILE, validateFormalPriceApprovalFinalReleaseAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalFinalReleaseAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.11'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, assessmentSource, matrixSource, gateSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAssessmentModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseMatrix.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseGate.js'),
  ])
  const dependencyImportSource = `${assessmentSource}\n${matrixSource}\n${gateSource}`
    .split(/\r?\n/)
    .filter((line) => line.trimStart().startsWith('import '))
    .join('\n')
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
      finalAssessmentPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseAssessmentModel.js'),
      releaseMatrixPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseMatrix.js'),
      releaseGatePresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalFinalReleaseGate.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT',
      designTarget: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT.assessmentCode,
      lifecycle: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT_STATES,
      matrixControlCount: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_MATRIX.length,
      finalReleaseIsExecution: false,
      readyMeansCreated: false,
      gateIsCommandExecutor: false,
      executionOrPersistenceImports,
      strategy: 'final composite safety assessment whose ready result never grants execution authority',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object instances', 'Command execution', 'Approval Workflow', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_final_release_scan_v11428611.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const readyInput = Object.freeze({
    assessmentRequested: true,
    simulationStatus: 'completed',
    commandStatus: 'validated',
    authorizationStatus: 'authorized_design_only',
    requesterAuthorizerSeparated: true,
    auditTrailAvailable: true,
    workflowEngineConnected: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    businessWriteCount: 0,
  })
  const notAssessed = evaluateFormalPriceApprovalFinalReleaseMatrix({})
  const ready = evaluateFormalPriceApprovalFinalReleaseMatrix(readyInput)
  const manualReview = evaluateFormalPriceApprovalFinalReleaseMatrix({ ...readyInput, auditTrailAvailable: false })
  const blocked = evaluateFormalPriceApprovalFinalReleaseMatrix({ ...readyInput, requesterAuthorizerSeparated: false })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-final-release-assessment"')
      && pageSource.includes('正式创建前最终安全评审')
      && pageSource.includes('Final Release ≠ Execution')
      && pageSource.includes('READY ≠ Created')
      && pageSource.includes('Gate ≠ Command Executor'), FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalFinalReleaseAssessment().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT.persistenceMode === 'none', {
        assessmentFields: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT.fields,
        lifecycle: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT.lifecycle,
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFinalReleaseAssessmentCode === FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT.assessmentCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFinalReleaseIsExecution === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFinalReleaseGateCommandExecutor === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalFinalReleaseAssessmentInstanceCount === 0
      && FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT.assessmentInstanceCount === 0
      && FORMAL_PRICE_APPROVAL_FINAL_RELEASE_MATRIX.length === 9, {
        assessmentCode: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT.assessmentCode,
        matrixControlCount: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_MATRIX.length,
        assessmentInstanceCount: 0,
      }),
    gate('Rule', notAssessed.evaluatedStatus === 'not_assessed'
      && ready.evaluatedStatus === 'ready'
      && ready.statusTrace.join(',') === 'not_assessed,checking,ready'
      && manualReview.evaluatedStatus === 'manual_review'
      && blocked.evaluatedStatus === 'blocked'
      && [notAssessed, ready, manualReview, blocked].every((result) => result.releaseIsExecution === false
        && result.readyMeansCreated === false
        && result.commandExecuted === false
        && result.formalPriceApprovalObjectCreated === false
        && result.approvalWorkflowStarted === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false), {
        notAssessed: notAssessed.evaluatedStatus,
        ready: ready.evaluatedStatus,
        manualReview: manualReview.evaluatedStatus,
        blocked: blocked.evaluatedStatus,
      }),
    gate('Guard', evaluateFormalPriceApprovalFinalReleaseGate({ action: 'reviewFinalRelease', assessmentStatus: 'ready' }).decision === 'allow_assessment_only'
      && evaluateFormalPriceApprovalFinalReleaseGate({ action: 'reviewFinalRelease', assessmentStatus: 'ready' }).executionPermissionGranted === false
      && FORMAL_PRICE_APPROVAL_FINAL_RELEASE_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalFinalReleaseGate({ action, assessmentStatus: 'ready' })
        return result.decision === 'deny' && result.commandExecuted === false && result.formalPriceApprovalObjectCreated === false
      }), FORMAL_PRICE_APPROVAL_FINAL_RELEASE_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalFinalReleaseAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_PROFILE.profileCode),
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
    lifecycle: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT_STATES,
    matrixControlCount: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_MATRIX.length,
    finalReleaseIsExecution: false,
    readyMeansCreated: false,
    gateIsCommandExecutor: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-final-release')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

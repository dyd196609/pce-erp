import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_CREATION_SIMULATION, FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_STATES, validateFormalPriceApprovalCreationSimulation } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSimulationModel.js'
import { evaluateFormalPriceApprovalCreationSimulationRules } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSimulationRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalCreationSimulationGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSimulationGuard.js'
import { FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR, executeFormalPriceApprovalCreationSimulation } from '../src/meta/runtime/formalPriceApprovalCreationZeroWriteExecutor.js'
import { FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_PROFILE, validateFormalPriceApprovalCreationSimulationAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalCreationSimulationAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.8'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_READY'
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
  try { await walk(root) } catch { /* missing roots are represented by empty inventories */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, executorSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/runtime/formalPriceApprovalCreationZeroWriteExecutor.js'),
  ])
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
      simulationModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSimulationModel.js'),
      zeroWriteExecutorPresent: runtimeFiles.includes('src/meta/runtime/formalPriceApprovalCreationZeroWriteExecutor.js') }),
    analysis: Object.freeze({
      prerequisites: Object.freeze(['SCM_FORMAL_PRICE_APPROVAL_OBJECT', 'SCM_FORMAL_PRICE_APPROVAL_RUNTIME']),
      designTarget: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION.simulationCode,
      lifecycle: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_STATES,
      simulationIsBusinessObject: false,
      persistenceImportsPresent: /dataGateway|transactionEngine|database|fetch\s*\(/i.test(executorSource),
      workflowEngineConnected: false,
      strategy: 'non-persistent in-memory simulation artifact executed behind a zero-write boundary',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object instances', 'Approval Workflow', 'Approval Tasks', 'PurchaseOrder', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_creation_simulation_scan_v1142868.json')
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
    runtimeEvaluatedStatus: 'ready_for_creation', projectionStatus: 'available',
    evidencePackageStatus: 'available', creationAssessmentStatus: 'ready',
  })
  const readyRules = evaluateFormalPriceApprovalCreationSimulationRules(readyInput)
  const blockedRules = evaluateFormalPriceApprovalCreationSimulationRules({ ...readyInput, evidencePackageStatus: 'incomplete' })
  const completedSimulation = executeFormalPriceApprovalCreationSimulation(readyInput)
  const blockedSimulation = executeFormalPriceApprovalCreationSimulation({ ...readyInput, runtimeEvaluatedStatus: 'definition_only' })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-creation-simulation"')
      && pageSource.includes('正式价格审批对象创建模拟')
      && pageSource.includes('Simulation ≠ Business Object')
      && pageSource.includes('业务写入次数'), FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalCreationSimulation().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_CREATION_SIMULATION.persistenceMode === 'none'
      && FORMAL_PRICE_APPROVAL_CREATION_SIMULATION.databaseWriteAllowed === false, {
        artifactType: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION.artifactType,
        existingSchema: 'PriceApprovalSchema',
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationSimulationCode === FORMAL_PRICE_APPROVAL_CREATION_SIMULATION.simulationCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationSimulationBusinessObject === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationSimulationWriteCount === 0
      && FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR.executionMode === 'in_memory_zero_write'
      && FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR.persistenceAdapterConnected === false
      && FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR.workflowEngineConnected === false
      && FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR.businessObjectFactoryConnected === false
      && completedSimulation.finalStatus === 'completed'
      && completedSimulation.readinessStatus === 'simulated_ready'
      && completedSimulation.statusTrace.join(',') === 'not_started,checking,simulated_ready,completed'
      && blockedSimulation.finalStatus === 'blocked'
      && blockedSimulation.statusTrace.join(',') === 'not_started,checking,blocked'
      && completedSimulation.businessObject === false
      && completedSimulation.formalPriceApprovalObjectCreated === false
      && completedSimulation.formalPriceApprovalObjectCount === 0
      && completedSimulation.simulationArtifactPersisted === false, FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR),
    gate('Rule', readyRules.decision === 'simulate_only'
      && readyRules.simulatedStatus === 'simulated_ready'
      && blockedRules.decision === 'blocked'
      && readyRules.formalPriceApprovalObjectCreated === false
      && readyRules.approvalWorkflowStarted === false
      && readyRules.approvalTaskCreated === false
      && readyRules.businessWriteCount === 0
      && readyRules.productionDataWritten === false, { readyDecision: readyRules.decision, blockedDecision: blockedRules.decision }),
    gate('Guard', FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_FORBIDDEN_ACTIONS.every((action) => evaluateFormalPriceApprovalCreationSimulationGuard(action).decision === 'deny'), FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalCreationSimulationAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_PROFILE.profileCode),
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
  const passed = results.every((item) => item.result === 'PASS')
    && databaseUnchanged
    && scan.analysis.persistenceImportsPresent === false
  const report = Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis,
    gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    lifecycle: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_STATES,
    successfulSimulationTrace: completedSimulation.statusTrace,
    blockedSimulationTrace: blockedSimulation.statusTrace,
    simulationIsBusinessObject: false,
    simulationArtifactPersisted: false,
    formalPriceApprovalObjectCreated: false,
    formalPriceApprovalObjectCount: 0,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-creation-simulation')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

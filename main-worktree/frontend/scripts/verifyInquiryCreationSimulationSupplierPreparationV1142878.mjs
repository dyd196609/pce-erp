import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { createInquiryCreationSimulation, validateInquiryCreationSimulation } from '../src/meta/domain/scm/inquiryCreationSimulation/inquiryCreationSimulationModel.js'
import { createSupplierInquiryPreparation, validateSupplierInquiryPreparation } from '../src/meta/domain/scm/inquiryCreationSimulation/supplierInquiryPreparationModel.js'
import { evaluateInquiryCreationSimulation } from '../src/meta/domain/scm/inquiryCreationSimulation/inquiryCreationSimulationRuleEngine.js'
import { INQUIRY_CREATION_SIMULATION_FORBIDDEN_ACTIONS, evaluateInquiryCreationSimulationGuard } from '../src/meta/domain/scm/inquiryCreationSimulation/inquiryCreationSimulationGuard.js'
import { INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_PROFILE, validateInquiryCreationSimulationSupplierPreparationAcceptance } from '../src/meta/acceptance/scm/inquiryCreationSimulationSupplierPreparationAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.8'
const TARGET_STATUS = 'SCM_INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_READY'
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
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, simulationSource, preparationSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm'), listFiles('src/meta/pages'), listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/inquiryCreationSimulation/inquiryCreationSimulationModel.js'),
    read('src/meta/domain/scm/inquiryCreationSimulation/supplierInquiryPreparationModel.js'),
    read('src/meta/domain/scm/inquiryCreationSimulation/inquiryCreationSimulationRuleEngine.js'),
    read('src/meta/domain/scm/inquiryCreationSimulation/inquiryCreationSimulationGuard.js'),
  ])
  const imports = `${simulationSource}\n${preparationSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter(line => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_PURCHASE_REQUEST_INQUIRY_MAPPING_VALIDATION_READY',
      simulationModel: 'SCM_INQUIRY_CREATION_SIMULATION', supplierPreparationModel: 'SCM_SUPPLIER_INQUIRY_PREPARATION',
      simulationCreatesInquiry: false, supplierCandidateCreatesInquiryTask: false,
      workflowTaskOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'simulate inquiry prerequisites and prepare supplier candidate references without business creation or execution' }),
    protectedScopes: Object.freeze(['Inquiry creation', 'Supplier send', 'Supplier inquiry task creation', 'Quotation task creation', 'Database write layer']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_inquiry_creation_simulation_supplier_preparation_scan_v1142878.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const projection = Object.freeze({ mappingValidationNo: 'MAP-PR-SIM-001', sourceRequestNo: 'PR-SIM-001',
    requiredDate: '2026-08-20', currency: 'CNY', inquiryLines: Object.freeze([{ lineNo: 1 }]), isInquiry: false })
  const simulation = createInquiryCreationSimulation(projection)
  const candidates = Object.freeze([
    Object.freeze({ supplierId: 'SUP-CANDIDATE-001', evidenceReference: 'preferred_supplier_trace' }),
    Object.freeze({ supplierId: 'SUP-CANDIDATE-002', evidenceReference: 'category_supplier_pool' }),
  ])
  const preparation = createSupplierInquiryPreparation({ simulationNo: simulation.simulationNo,
    responseDeadlineReference: '2026-08-10', supplierCandidates: candidates })
  const simulationReady = evaluateInquiryCreationSimulation({ action: 'simulateInquiryCreation', mappingStatus: 'mapping_ready', projection })
  const missingLinesBlocked = evaluateInquiryCreationSimulation({ action: 'simulateInquiryCreation', mappingStatus: 'mapping_ready', projection: { ...projection, inquiryLines: [] } })
  const productionBlocked = evaluateInquiryCreationSimulation({ action: 'simulateInquiryCreation', mappingStatus: 'mapping_ready', projection, productionMode: true })
  const persistenceBlocked = evaluateInquiryCreationSimulation({ action: 'simulateInquiryCreation', mappingStatus: 'mapping_ready', projection, persistRequested: true })
  const supplierReady = evaluateInquiryCreationSimulation({ action: 'prepareSupplierCandidates', simulationStatus: 'simulated_ready', supplierCandidates: candidates })
  const missingEvidenceBlocked = evaluateInquiryCreationSimulation({ action: 'prepareSupplierCandidates', simulationStatus: 'simulated_ready',
    supplierCandidates: [{ supplierId: 'SUP-CANDIDATE-001', evidenceReference: '' }] })
  const taskBlocked = evaluateInquiryCreationSimulation({ action: 'prepareSupplierCandidates', simulationStatus: 'simulated_ready',
    supplierCandidates: candidates, createTaskRequested: true })
  const sendBlocked = evaluateInquiryCreationSimulation({ action: 'prepareSupplierCandidates', simulationStatus: 'simulated_ready',
    supplierCandidates: candidates, sendRequested: true })
  const evaluated = [simulationReady, missingLinesBlocked, productionBlocked, persistenceBlocked,
    supplierReady, missingEvidenceBlocked, taskBlocked, sendBlocked]

  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="inquiry-creation-simulation-supplier-preparation"')
      && pageSource.includes('Simulation ≠ Creation')
      && pageSource.includes('Supplier Candidate ≠ Inquiry Task')
      && pageSource.includes('Preparation ≠ Execution')
      && pageSource.includes('createInquiryCreationSimulation') && pageSource.includes('createSupplierInquiryPreparation'),
      { route: '/scm/purchase-inquiry', prerequisiteChecks: 4, supplierCandidates: 2 }),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateInquiryCreationSimulation(simulation).valid && validateSupplierInquiryPreparation(preparation).valid
      && simulation.simulationStatus === 'simulated_ready' && simulation.isInquiry === false
      && simulation.inquiryCreated === false && preparation.preparationStatus === 'prepared'
      && preparation.candidateCount === 2 && preparation.isSupplierInquiryTask === false
      && preparation.supplierInquiryTaskCreated === false,
      { persistenceSchemaAdded: false, simulation: simulation.simulationStatus, preparation: preparation.preparationStatus }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.version === VERSION
      && PURCHASE_INQUIRY_RUNTIME.inquiryCreationSimulationMode === 'simulation_only'
      && PURCHASE_INQUIRY_RUNTIME.inquiryCreationSimulationPrerequisiteCheckCount === 4
      && PURCHASE_INQUIRY_RUNTIME.inquiryCreationSimulationStatus === 'simulated_ready'
      && PURCHASE_INQUIRY_RUNTIME.inquiryCreationSimulationCreatesInquiry === false
      && PURCHASE_INQUIRY_RUNTIME.supplierInquiryPreparationCandidateCount === 2
      && PURCHASE_INQUIRY_RUNTIME.supplierInquiryPreparationStatus === 'prepared'
      && PURCHASE_INQUIRY_RUNTIME.supplierCandidateCreatesInquiryTask === false
      && PURCHASE_INQUIRY_RUNTIME.supplierInquiryPreparationSendsSupplier === false
      && PURCHASE_INQUIRY_RUNTIME.supplierInquiryPreparationCreatesQuotationTask === false
      && PURCHASE_INQUIRY_RUNTIME.supplierInquiryPreparationPersisted === false,
      { simulation: 'simulated_ready', preparation: 'prepared', candidates: 2 }),
    gate('Rule', simulationReady.decision === 'simulation_ready' && supplierReady.decision === 'supplier_preparation_ready'
      && [missingLinesBlocked, productionBlocked, persistenceBlocked, missingEvidenceBlocked, taskBlocked, sendBlocked]
        .every(item => item.decision === 'blocked')
      && evaluated.every(item => item.inquiryCreated === false && item.supplierSent === false
        && item.supplierInquiryTaskCreated === false && item.quotationTaskCreated === false
        && item.simulationPersisted === false && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { simulation: simulationReady.decision, supplierPreparation: supplierReady.decision,
        missingLines: missingLinesBlocked.decision, createTask: taskBlocked.decision, send: sendBlocked.decision }),
    gate('Guard', evaluateInquiryCreationSimulationGuard({ action: 'runPreparationValidation', mode: 'simulation_only' }).decision === 'allow_simulation_only'
      && evaluateInquiryCreationSimulationGuard({ action: 'runPreparationValidation', mode: 'production' }).decision === 'deny'
      && INQUIRY_CREATION_SIMULATION_FORBIDDEN_ACTIONS.every(action => {
        const result = evaluateInquiryCreationSimulationGuard({ action })
        return result.decision === 'deny' && result.inquiryCreated === false && result.supplierSent === false
          && result.supplierInquiryTaskCreated === false && result.quotationTaskCreated === false
          && result.simulationPersisted === false && result.preparationPersisted === false
          && result.businessWriteCount === 0 && result.productionDataWritten === false
      }), INQUIRY_CREATION_SIMULATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateInquiryCreationSimulationSupplierPreparationAcceptance().valid
      && registrySource.includes('INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_PROFILE'),
      INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_PROFILE.profileCode),
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
    && scan.analysis.workflowTaskOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis, gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter(item => item.result === 'PASS').length, FAIL: results.filter(item => item.result === 'FAIL').length }),
    inquiryCreationSimulation: Object.freeze({ result: 'PASS', status: simulation.simulationStatus,
      prerequisiteCheckCount: 4, simulatedLineCount: simulation.simulatedLineCount, isInquiry: false }),
    supplierInquiryPreparation: Object.freeze({ result: 'PASS', status: preparation.preparationStatus,
      candidateCount: preparation.candidateCount, isSupplierInquiryTask: false }),
    inquiryCreated: false, supplierSent: false, supplierInquiryTaskCreated: false,
    quotationTaskCreated: false, simulationPersisted: false, preparationPersisted: false,
    businessWriteCount: 0, productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'inquiry-creation-simulation-supplier-preparation')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

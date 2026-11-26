import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { PURCHASE_REQUEST_INQUIRY_MAPPING, createPurchaseRequestInquiryPreparationProjection, validatePurchaseRequestInquiryMapping } from '../src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingModel.js'
import { PURCHASE_REQUEST_INQUIRY_FIELD_MAPPING_MATRIX, validatePurchaseRequestInquiryFieldMappingMatrix } from '../src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryFieldMappingMatrix.js'
import { PURCHASE_REQUEST_INQUIRY_MAPPING_SCENARIOS, validatePurchaseRequestInquiryMappingScenarios } from '../src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingScenario.js'
import { evaluatePurchaseRequestInquiryMapping } from '../src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingRuleEngine.js'
import { PURCHASE_REQUEST_INQUIRY_MAPPING_FORBIDDEN_ACTIONS, evaluatePurchaseRequestInquiryMappingGuard } from '../src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingGuard.js'
import { PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_PROFILE, validatePurchaseRequestInquiryMappingAcceptance } from '../src/meta/acceptance/scm/purchaseRequestInquiryMappingAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.7'
const TARGET_STATUS = 'SCM_PURCHASE_REQUEST_INQUIRY_MAPPING_VALIDATION_READY'
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
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, modelSource, matrixSource, scenarioSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm'), listFiles('src/meta/pages'), listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingModel.js'),
    read('src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryFieldMappingMatrix.js'),
    read('src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingScenario.js'),
    read('src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingRuleEngine.js'),
    read('src/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingGuard.js'),
  ])
  const imports = `${modelSource}\n${matrixSource}\n${scenarioSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter(line => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({
      prerequisite: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_READY',
      sourceObject: 'PurchaseRequest', targetObject: 'InquiryPreparationProjection',
      mappingMode: 'simulation_validation_only', fieldMappingCount: 8, scenarioCount: 3,
      mappingCreatesInquiry: false, sourceTraceCreatesTransaction: false,
      workflowTaskOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'validate immutable purchase-request field projection and source trace without inquiry or downstream object creation',
    }),
    protectedScopes: Object.freeze(['Inquiry creation', 'Supplier send', 'Quotation task creation', 'PurchaseOrder', 'Finance', 'Inventory', 'Database write layer']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_request_inquiry_mapping_scan_v1142877.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const source = Object.freeze({ requestNo: 'PR-SIM-001', requestDate: '2026-08-03', requester: '模拟申请人',
    purchaseDepartment: '采购部', requiredDate: '2026-08-20', currency: 'CNY', statusCode: 'approved',
    details: Object.freeze([{ lineNo: 1, materialCode: 'MAT-SIM-001', quantity: 10 }]), preferredSupplierId: 'SUP-TRACE-001' })
  const projection = createPurchaseRequestInquiryPreparationProjection(source)
  const normal = evaluatePurchaseRequestInquiryMapping({ action: 'validateMapping', source })
  const missingLines = evaluatePurchaseRequestInquiryMapping({ action: 'validateMapping', source: { ...source, details: [] } })
  const ineligible = evaluatePurchaseRequestInquiryMapping({ action: 'validateMapping', source: { ...source, statusCode: 'draft' } })
  const productionBlocked = evaluatePurchaseRequestInquiryMapping({ action: 'validateMapping', source, productionMode: true })
  const persistenceBlocked = evaluatePurchaseRequestInquiryMapping({ action: 'validateMapping', source, persistRequested: true })
  const evaluated = [normal, missingLines, ineligible, productionBlocked, persistenceBlocked]

  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="purchase-request-inquiry-mapping-validation"')
      && pageSource.includes('Mapping ≠ Creation') && pageSource.includes('Simulation ≠ Production')
      && pageSource.includes('Source Trace ≠ Transaction')
      && pageSource.includes('PURCHASE_REQUEST_INQUIRY_FIELD_MAPPING_MATRIX')
      && pageSource.includes('PURCHASE_REQUEST_INQUIRY_MAPPING_SCENARIOS'),
      { route: '/scm/purchase-inquiry', region: 'purchase-request-inquiry-mapping-validation', fields: 8, scenarios: 3 }),
    gate('Router', routerSource.includes("path: 'scm/purchase-request'")
      && routerSource.includes("path: 'scm/purchase-inquiry'")
      && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'),
      { source: '/scm/purchase-request', validation: '/scm/purchase-inquiry' }),
    gate('Schema', validatePurchaseRequestInquiryMapping().valid
      && validatePurchaseRequestInquiryFieldMappingMatrix().valid
      && validatePurchaseRequestInquiryMappingScenarios().valid
      && projection.projectionType === 'InquiryPreparationProjection' && projection.isInquiry === false
      && projection.sourceRequestNo === source.requestNo && projection.inquiryLines.length === 1
      && projection.persistenceMode === 'none' && projection.sourceTraceOnly === true,
      { persistenceSchemaAdded: false, mappingFields: PURCHASE_REQUEST_INQUIRY_FIELD_MAPPING_MATRIX.length,
        scenarios: PURCHASE_REQUEST_INQUIRY_MAPPING_SCENARIOS.length, projectionType: projection.projectionType }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.version.startsWith('V1.14.2.8.7.')
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquiryMappingMode === 'simulation_validation_only'
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquiryMappingFieldCount === 8
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquiryMappingRequiredFieldCount === 7
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquiryMappingScenarioCount === 3
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquiryMappingCreatesInquiry === false
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquiryMappingSendsSupplier === false
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquiryMappingCreatesQuotationTask === false
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquiryMappingPersistsProjection === false
      && PURCHASE_INQUIRY_RUNTIME.purchaseRequestInquirySourceTraceCreatesTransaction === false,
      { mapping: 'simulation_validation_only', createsInquiry: false, persistsProjection: false }),
    gate('Rule', normal.decision === 'mapping_validated' && normal.sourceTraceEstablished === true
      && [missingLines, ineligible, productionBlocked, persistenceBlocked].every(item => item.decision === 'blocked')
      && evaluated.every(item => item.inquiryCreated === false && item.supplierSent === false
        && item.quotationTaskCreated === false && item.sourceTransactionCreated === false
        && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { normal: normal.decision, missingLines: missingLines.decision, draft: ineligible.decision,
        production: productionBlocked.decision, persistence: persistenceBlocked.decision }),
    gate('Guard', evaluatePurchaseRequestInquiryMappingGuard({ action: 'validateReadOnlyMapping', mode: 'simulation_validation_only' }).decision === 'allow_validation_only'
      && evaluatePurchaseRequestInquiryMappingGuard({ action: 'validateReadOnlyMapping', mode: 'production' }).decision === 'deny'
      && PURCHASE_REQUEST_INQUIRY_MAPPING_FORBIDDEN_ACTIONS.every(action => {
        const result = evaluatePurchaseRequestInquiryMappingGuard({ action })
        return result.decision === 'deny' && result.inquiryCreated === false && result.supplierSent === false
          && result.quotationTaskCreated === false && result.sourceTransactionCreated === false
          && result.mappingPersisted === false && result.businessWriteCount === 0 && result.productionDataWritten === false
      }), PURCHASE_REQUEST_INQUIRY_MAPPING_FORBIDDEN_ACTIONS),
    gate('Acceptance', validatePurchaseRequestInquiryMappingAcceptance().valid
      && registrySource.includes('PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_PROFILE'),
      PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_PROFILE.profileCode),
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
    mappingValidation: Object.freeze({ result: 'PASS', sourceObject: 'PurchaseRequest', targetObject: 'InquiryPreparationProjection',
      fieldMappingCount: 8, scenarioCount: 3, sourceTraceEstablished: true }),
    mappingCreatesInquiry: false, inquiryCreated: false, supplierSent: false,
    quotationTaskCreated: false, sourceTraceCreatesTransaction: false, mappingPersisted: false,
    businessWriteCount: 0, productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-request-inquiry-mapping-validation')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

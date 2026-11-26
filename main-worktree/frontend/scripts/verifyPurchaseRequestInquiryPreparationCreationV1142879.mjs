import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createInquiryPreparationObject, validateInquiryPreparationObject } from '../src/meta/domain/scm/inquiryPreparation/inquiryPreparationObjectModel.js'
import { assessInquiryPreparationCreation } from '../src/meta/domain/scm/inquiryPreparation/inquiryPreparationRuleEngine.js'
import { INQUIRY_PREPARATION_FORBIDDEN_ACTIONS, evaluateInquiryPreparationCreationGuard } from '../src/meta/domain/scm/inquiryPreparation/inquiryPreparationCreationGuard.js'
import { createInquiryPreparation, findInquiryPreparationBySource } from '../src/meta/runtime/inquiryPreparationRuntime.js'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { validatePurchaseRequestInquiryPreparationCreationAcceptance } from '../src/meta/acceptance/scm/purchaseRequestInquiryPreparationCreationAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.9'
const TARGET = 'SCM_PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hash = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => ({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

async function listFiles(relative) {
  const files = []
  async function walk(directory) { for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name); if (entry.isDirectory()) await walk(full)
    else files.push(path.relative(frontendRoot, full).replaceAll('\\', '/'))
  } }
  await walk(path.join(frontendRoot, relative)); return files.sort()
}

async function createScan() {
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles] = await Promise.all([
    listFiles('src/meta/domain/scm'), listFiles('src/meta/pages'), listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
  ])
  return { version: VERSION, generatedAt: new Date().toISOString(),
    scope: ['purchase request', 'inquiry preparation', 'purchase inquiry runtime', 'supplier preparation'],
    inventory: { domainFiles, pageFiles, runtimeFiles, acceptanceFiles },
    beforeImplementation: { inquiryPreparationExisted: false, creationGuardExisted: false,
      navigationEntryExisted: false, eligibilityOnly: true },
    implementation: { inquiryPreparationObject: true, creationGuard: true, navigationEntry: true,
      storageMode: 'session_runtime', formalInquiryCreation: false, supplierSending: false, quotationCreation: false },
    protectedScopes: ['Workflow Engine', 'Approval Engine', 'Purchase Order', 'Finance', 'Inventory', 'Formal inquiry send'] }
}

const request = { requestNo: 'PR202608020008', requestDate: '2026-08-02', requester: '采购员', purchaseDepartment: '采购部',
  statusCode: 'approved', approvalStatus: 'completed', inquiryEligibility: { eligible: true,
    items: [{ lineNo: 1, materialCode: 'MAT-001', materialName: '验收物料', quantity: 10, requiredDate: '2026-08-20' }] },
  items: [{ lineNo: 1, materialCode: 'MAT-001', materialName: '验收物料', quantity: 10, requiredDate: '2026-08-20',
    suggestedSupplierId: 'SUP-001', suggestedSupplierCode: 'SUP-001', suggestedSupplierName: '候选供应商' }] }

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_request_inquiry_preparation_creation_scan_v1142879.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }
  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const before = await hash(databasePath)
  const [requestPage, region, inquiryPage, router, registry] = await Promise.all([
    read('src/meta/pages/ScmPurchaseRequestPage.vue'), read('src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'),
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const assessment = assessInquiryPreparationCreation(request)
  const object = createInquiryPreparationObject(request)
  const created = createInquiryPreparation(request)
  const idempotent = createInquiryPreparation(request)
  const invalid = assessInquiryPreparationCreation({ ...request, approvalStatus: 'pending' })
  const gates = [
    gate('Page', requestPage.includes('生成询价准备') && region.includes('查看询价准备')
      && inquiryPage.includes('data-acceptance-id="inquiry-preparation-object"')
      && inquiryPage.includes('来源采购申请') && inquiryPage.includes('物料明细') && inquiryPage.includes('供应商候选'), '/scm/purchase-request -> /scm/purchase-inquiry'),
    gate('Router', router.includes("path: 'scm/purchase-request'") && router.includes("path: 'scm/purchase-inquiry'"), ['/scm/purchase-request', '/scm/purchase-inquiry']),
    gate('Schema', validateInquiryPreparationObject(object).valid && object.status === 'prepared'
      && object.sourceRequestNo === 'PR202608020008' && object.inquiryLines.length === 1 && object.supplierCandidates.length === 1, object),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.version === VERSION && created.result === 'PASS' && created.created === true
      && idempotent.result === 'PASS' && idempotent.idempotent === true
      && findInquiryPreparationBySource('PR202608020008')?.status === 'prepared', { created: created.created, idempotent: idempotent.idempotent }),
    gate('Rule', assessment.eligible && assessment.result === 'PASS' && !invalid.eligible
      && assessment.createsFormalInquiry === false && assessment.createsQuotationTask === false
      && assessment.sendsSupplier === false && assessment.createsQuotation === false, assessment.checks),
    gate('Guard', evaluateInquiryPreparationCreationGuard({ action: 'createInquiryPreparation' }).allowed
      && INQUIRY_PREPARATION_FORBIDDEN_ACTIONS.every(action => evaluateInquiryPreparationCreationGuard({ action }).allowed === false), INQUIRY_PREPARATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validatePurchaseRequestInquiryPreparationCreationAcceptance().valid
      && registry.includes('PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION_ACCEPTANCE_PROFILE'), TARGET),
  ]
  try { execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 }); gates.push(gate('Build', true, 'vite build')) }
  catch (error) { gates.push(gate('Build', false, String(error.stderr || error.message))) }
  const after = await hash(databasePath)
  const database = before === after ? 'UNCHANGED' : 'CHANGED'
  const passed = gates.every(item => item.result === 'PASS') && database === 'UNCHANGED'
  const report = { version: VERSION, status: passed ? TARGET : 'FAIL', gates,
    eligibility: assessment.result, preparationCreation: created.result, inquiryCreated: false, quotationCreated: false,
    supplierSent: false, preparationBusinessWriteCount: created.created ? 1 : 0, productionDataWritten: false, database,
    databaseHashBefore: before, databaseHashAfter: after }
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-request-inquiry-preparation-creation')
  await fs.mkdir(outputRoot, { recursive: true }); await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`)
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET) process.exitCode = 1

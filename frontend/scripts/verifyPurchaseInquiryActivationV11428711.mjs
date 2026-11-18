import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { activatePurchaseInquiryFromPreparation, buildPurchaseInquiryRuntimeView, listPurchaseInquiryRuntimeObjects, PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { assessPurchaseInquiryActivation } from '../src/meta/domain/scm/inquiryPreparation/purchaseInquiryActivationRule.js'
import { PURCHASE_INQUIRY_ACTIVATION_FORBIDDEN_ACTIONS, evaluatePurchaseInquiryActivationGuard } from '../src/meta/domain/scm/inquiryPreparation/purchaseInquiryActivationGuard.js'
import { validatePurchaseInquiryActivationAcceptance } from '../src/meta/acceptance/scm/purchaseInquiryActivationAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.11'
const TARGET = 'SCM_PURCHASE_INQUIRY_ACTIVATION_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hash = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => ({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

const preparation = Object.freeze({ modelCode: 'SCM_INQUIRY_PREPARATION_OBJECT', inquiryPreparationNo: 'IPR-PR202608020008',
  sourceRequestNo: 'PR202608020008', requester: '周丽', status: 'prepared', materialLineCount: 2, supplierCandidateCount: 1,
  inquiryLines: Object.freeze([{ materialCode: 'MT068', materialName: '扩展坞', quantity: 14 },
    { materialCode: 'MT026', materialName: '胶水', quantity: 500 }]),
  supplierCandidates: Object.freeze([{ supplierId: 'SUP001', supplierName: '华为技术有限公司' }]) })

async function run() {
  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const before = await hash(databasePath)
  const [page, router, registry] = await Promise.all([read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js')])
  const eligibility = assessPurchaseInquiryActivation(preparation)
  const activation = activatePurchaseInquiryFromPreparation(preparation)
  const repeated = activatePurchaseInquiryFromPreparation(preparation)
  const object = activation.object
  const view = buildPurchaseInquiryRuntimeView({ objects: [], supplierQuotations: [] })
  const gates = [
    gate('Rule', eligibility.eligible && eligibility.decision === 'allow_create_draft', eligibility),
    gate('Guard', evaluatePurchaseInquiryActivationGuard('activatePurchaseInquiry').allowed
      && PURCHASE_INQUIRY_ACTIVATION_FORBIDDEN_ACTIONS.every(action => !evaluatePurchaseInquiryActivationGuard(action).allowed), PURCHASE_INQUIRY_ACTIVATION_FORBIDDEN_ACTIONS),
    gate('Runtime', activation.result === 'PASS' && activation.created && activation.businessWriteCount === 1
      && repeated.idempotent && repeated.businessWriteCount === 0 && listPurchaseInquiryRuntimeObjects().length === 1
      && view.inquiries.some(item => item.inquiryNo === object.inquiryNo) && view.summary.inquiryCount === 1, object),
    gate('Page', page.includes('data-activation-action="start-inquiry"') && page.includes('启动询价')
      && page.includes('activatePurchaseInquiryFromPreparation') && !page.includes('>发送供应商<') && !page.includes('>生成订单<'), '/scm/purchase-inquiry'),
    gate('Router', router.includes("path: 'scm/purchase-inquiry'"), '/scm/purchase-inquiry'),
    gate('Acceptance', validatePurchaseInquiryActivationAcceptance().valid
      && registry.includes('PURCHASE_INQUIRY_ACTIVATION_ACCEPTANCE_PROFILE') && PURCHASE_INQUIRY_RUNTIME.version === VERSION, TARGET),
  ]
  try { execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 }); gates.push(gate('Build', true, 'vite build')) }
  catch (error) { gates.push(gate('Build', false, String(error.stderr || error.message))) }
  const after = await hash(databasePath)
  const database = before === after ? 'UNCHANGED' : 'CHANGED'
  const report = { version: VERSION, status: gates.every(item => item.result === 'PASS') && database === 'UNCHANGED' ? TARGET : 'FAIL',
    gates, inquiryPreparationExists: Boolean(preparation.inquiryPreparationNo), purchaseInquiryCreated: activation.created,
    purchaseInquiryNo: object?.inquiryNo || '', purchaseInquiryStatus: object?.statusCode || '', quotationCount: object?.quotationCount ?? -1,
    supplierQuoteCreated: object?.supplierQuoteCreated ?? true, supplierSent: object?.sentToSupplier ?? true,
    priceApprovalCreated: object?.priceApprovalCreated ?? true, purchaseOrderCreated: object?.createdPurchaseOrder ?? true,
    businessWriteCount: activation.businessWriteCount, productionDataWritten: object?.productionDataWritten ?? true,
    database, databaseHashBefore: before, databaseHashAfter: after }
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-activation')
  await fs.mkdir(outputRoot, { recursive: true }); await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`)
  return { outputRoot, report }
}

const result = await run()
for (const item of result.report.gates) console.log(`${item.gate} ${item.result}`)
console.log(`InquiryPreparation exists = ${result.report.inquiryPreparationExists}`)
console.log(`PurchaseInquiry created = ${result.report.purchaseInquiryCreated}`)
console.log(`Quotation Count = ${result.report.quotationCount}`)
console.log(`Supplier Sent = ${result.report.supplierSent}`)
console.log(`PurchaseOrder = ${result.report.purchaseOrderCreated}`)
console.log(`Business Write Count = ${result.report.businessWriteCount}`)
console.log(`Database = ${result.report.database}`)
console.log(result.report.status)
if (result.report.status !== TARGET) process.exitCode = 1

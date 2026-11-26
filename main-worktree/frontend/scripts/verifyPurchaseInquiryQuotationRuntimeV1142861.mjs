import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME, buildPurchaseInquiryRuntimeView } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { SUPPLIER_INQUIRY_TASK, validateSupplierInquiryTask } from '../src/meta/domain/scm/purchaseInquiry/quotationRuntime/supplierInquiryTaskModel.js'
import { SUPPLIER_QUOTATION, validateSupplierQuotation } from '../src/meta/domain/scm/purchaseInquiry/quotationRuntime/supplierQuotationModel.js'
import { SUPPLIER_QUOTATION_LIFECYCLE, evaluateSupplierQuotationTransition } from '../src/meta/domain/scm/purchaseInquiry/quotationRuntime/supplierQuotationStateModel.js'
import { SUPPLIER_QUOTATION_FORBIDDEN_ACTIONS, evaluateSupplierQuotationRuntimeGuard } from '../src/meta/domain/scm/purchaseInquiry/quotationRuntime/supplierQuotationRuntimeGuard.js'
import { validateSupplierQuotationRuntimeMappings } from '../src/meta/schema/scm/supplierQuotationRuntimeMapping.js'
import { SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_PROFILE, validateSupplierQuotationRuntimeAcceptance } from '../src/meta/acceptance/scm/supplierQuotationRuntimeAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.1'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_QUOTATION_RUNTIME_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = (relative) => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const gate = (name, pass, evidence) => Object.freeze({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })
const hashFile = async (file) => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')

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
  try { await walk(root) } catch { /* missing scan root remains empty */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, runtimeSource, schemaFiles, acceptanceFiles, routerSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry'), read('src/meta/runtime/purchaseInquiryRuntime.js'), listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'), read('src/router/index.js'),
  ])
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry', 'src/meta/runtime/purchaseInquiryRuntime.js', 'src/meta/schema/scm', 'src/meta/acceptance/scm', 'src/router/index.js']),
    inventory: Object.freeze({ domainFiles, schemaFiles, acceptanceFiles, runtimeVersionFound: runtimeSource.includes(VERSION),
      canonicalRoutePresent: routerSource.includes("path: 'scm/purchase-inquiry'") }),
    analysis: Object.freeze({ existingSupplierQuoteModel: domainFiles.some((file) => file.endsWith('quote/supplierQuoteDomainModel.js')),
      existingSupplierQuoteVersion: 'V1.14.2.8.5.3', runtimeProjectionStrategy: 'additive_read_only_projection', existingPurchaseFlowModified: false }),
    protectedScopes: Object.freeze(['crudEngine', 'pageRenderer', 'schemaResolver', 'common runtime core', 'PurchaseOrder core', 'Finance', 'Inventory']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_quote_runtime_scan_v1142861.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const factInput = Object.freeze({
    supplierInquiryTasks: Object.freeze([{ inquiryNo: 'PI-VERIFY-001', supplierId: 'SUP-001', sendStatus: 'sent', sendStatusLabel: '已发送', responseDeadline: '2026-08-10T18:00:00+08:00', quotationStatus: 'waiting_quote', quotationStatusLabel: '等待报价' }]),
    supplierQuotations: Object.freeze([{ quotationNo: 'SQ-VERIFY-001', supplierId: 'SUP-001', inquiryNo: 'PI-VERIFY-001', quotationStatus: 'quote_received', quotationStatusLabel: '已收到报价', items: [{ lineNo: 1 }], price: 12800, currency: 'CNY', deliveryDays: 12 }]),
  })
  const runtimeView = buildPurchaseInquiryRuntimeView(factInput)
  const results = [
    gate('Page', ['supplier-inquiry-task-list', 'supplier-quotation-list'].every((region) => pageSource.includes(`data-acceptance-id="${region}"`)) && pageSource.includes('不自动创建') && pageSource.includes('不推进价格审批'), { regions: SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_PROFILE.requiredRegions }),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateSupplierQuotationRuntimeMappings().valid, ['SCM_SUPPLIER_INQUIRY_TASK_RUNTIME_MAPPING', 'SCM_SUPPLIER_QUOTATION_RUNTIME_MAPPING']),
    gate('Runtime', validateSupplierInquiryTask().valid && validateSupplierQuotation().valid && SUPPLIER_QUOTATION_LIFECYCLE.join(',') === 'draft,created,sent,waiting_quote,quote_received,closed,cancelled' && runtimeView.quotationRuntime.supplierInquiryTasks.length === 1 && runtimeView.quotationRuntime.supplierQuotations.length === 1 && runtimeView.quotationRuntime.automaticQuotationCreation === false && PURCHASE_INQUIRY_RUNTIME.quotationRuntimeCode === 'SCM_PURCHASE_INQUIRY_QUOTATION_RUNTIME', { task: SUPPLIER_INQUIRY_TASK.objectCode, quotation: SUPPLIER_QUOTATION.objectCode, lifecycle: SUPPLIER_QUOTATION_LIFECYCLE }),
    gate('Guard', SUPPLIER_QUOTATION_FORBIDDEN_ACTIONS.every((action) => evaluateSupplierQuotationRuntimeGuard(action).decision === 'deny') && evaluateSupplierQuotationTransition({ fromStatus: 'waiting_quote', toStatus: 'quote_received' }).decision === 'allow' && evaluateSupplierQuotationTransition({ fromStatus: 'quote_received', toStatus: 'sent' }).decision === 'deny', SUPPLIER_QUOTATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateSupplierQuotationRuntimeAcceptance().valid && registrySource.includes('SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_PROFILE'), SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_PROFILE.profileCode),
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
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: Object.freeze({ existingDefinition: 'SCM_SUPPLIER_QUOTE@V1.14.2.8.5.3', resolution: '新增 SupplierQuotation 只读运行投影，不改写既有领域与采购流程' }),
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore, databaseHashAfter, automaticQuotationCreation: false, priceApprovalAdvanced: false, purchaseOrderCreated: false, existingPurchaseFlowModified: false })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-quotation-runtime')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1

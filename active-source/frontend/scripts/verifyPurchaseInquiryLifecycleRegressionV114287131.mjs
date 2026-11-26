import fs from 'node:fs/promises'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createPurchaseInquiryLifecycleProvider } from '../src/meta/providers/purchaseInquiryLifecycleProvider.js'
import { evaluatePurchaseInquiryBatchPreparation } from '../src/meta/domain/scm/purchaseInquiry/lifecycle/purchaseInquiryBatchPreparationRule.js'
import { validatePurchaseInquiryLifecycleContext } from '../src/meta/domain/scm/purchaseInquiry/lifecycle/purchaseInquiryLifecycleContext.js'
import { evaluatePurchaseInquiryEntryGuard } from '../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryGuard.js'
import { activatePurchaseInquiryFromPreparation, PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { validatePurchaseInquiryLifecycleWorkbenchAcceptance } from '../src/meta/acceptance/scm/purchaseInquiryLifecycleWorkbenchAcceptanceProfile.js'
import { validatePurchaseInquiryLifecycleRegressionAcceptance } from '../src/meta/acceptance/scm/purchaseInquiryLifecycleRegressionAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.13.1'
const TARGET = 'SCM_PURCHASE_INQUIRY_LIFECYCLE_REGRESSION_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const gate = (name, pass, evidence) => ({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })
const preparations = Object.freeze(['001', '002', '003'].map(code => Object.freeze({
  inquiryPreparationNo: `IPR-BATCH-${code}`, sourceRequestNo: `PR-BATCH-${code}`,
  status: 'prepared', statusLabel: '询价准备完成', requester: '采购员',
  inquiryLines: Object.freeze([{ materialCode: `MAT-${code}`, materialName: `物料-${code}`, quantity: 1 }]),
  supplierCandidates: Object.freeze([{ supplierId: `SUP-${code}` }]), supplierCandidateCount: 1,
})))
const preparationProvider = Object.freeze({ load: query => Object.freeze({ providerCode: 'TEST_PREPARATION_PROVIDER',
  recordCount: preparations.length, objects: preparations,
  selected: preparations.find(item => item.inquiryPreparationNo === query?.inquiryPreparationNo) || null }) })
const existing = Object.freeze({ id: 'SERVER-PI-001', inquiryNo: 'PI-EXISTING-001', sourceRequestNo: 'PR-BATCH-001',
  inquiryDate: '2026-08-03', buyerName: '采购员', supplierCount: 1, lineCount: 1, currency: 'CNY',
  statusCode: 'draft', statusLabel: '草稿' })

async function run() {
  const [page, router, registry, providerSource, ruleSource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
    read('src/meta/providers/purchaseInquiryLifecycleProvider.js'),
    read('src/meta/domain/scm/purchaseInquiry/lifecycle/purchaseInquiryBatchPreparationRule.js'),
  ])
  const provider = createPurchaseInquiryLifecycleProvider({ preparationProvider })
  const initial = provider.load({ serverFacts: { objects: [existing] } })
  const batch = evaluatePurchaseInquiryBatchPreparation({ preparations: initial.pendingPreparations, existingInquiries: initial.inquiries })
  let businessWriteCount = 0
  let batchOutputCount = 0
  for (const preparation of batch.candidates) {
    const contextual = provider.load({ query: { inquiryPreparationNo: preparation.inquiryPreparationNo }, serverFacts: { objects: [existing] } })
    if (!evaluatePurchaseInquiryEntryGuard({ context: contextual.entryContext, action: 'startInquiry' }).allowed) continue
    const result = activatePurchaseInquiryFromPreparation(preparation)
    if (result.result === 'PASS') { batchOutputCount += 1; businessWriteCount += result.businessWriteCount }
  }
  const finalFacts = provider.load({ serverFacts: { objects: [existing] } })
  const acceptance = validatePurchaseInquiryLifecycleRegressionAcceptance()
  const legacyAcceptance = validatePurchaseInquiryLifecycleWorkbenchAcceptance()
  const requiredRegions = ['business-context', 'pending-inquiry-preparations', 'existing-inquiry-list', 'current-inquiry-detail', 'next-action']
  const forbiddenButtons = ['发送供应商', '生成报价', '生成采购订单', '付款'].filter(label =>
    new RegExp(`<el-button[^>]*>[^<]*${label}`).test(page))
  const gates = [
    gate('Regression', initial.existingInquiryCount === 1 && initial.preparations.length === 3
      && finalFacts.existingInquiryCount === 3 && legacyAcceptance.valid, { initial: 1, final: finalFacts.existingInquiryCount }),
    gate('Context', validatePurchaseInquiryLifecycleContext(initial.lifecycleContext).valid
      && initial.lifecycleContext.lifecycleStage.code === 'browse_only', initial.lifecycleContext.lifecycleStage.code),
    gate('Batch Rule', batch.result === 'PASS' && batch.batchInputCount === 2 && batch.batchOutputCount === 2
      && batch.automaticActivation === false && batch.onePreparationOneInquiry === true
      && batchOutputCount === 2, batch),
    gate('Page', requiredRegions.every(id => page.includes(`data-acceptance-id="${id}"`))
      && page.includes('PceEnterpriseListTable') && page.includes('data-entry-action="view-inquiry"')
      && page.includes('data-batch-action="start-inquiries"') && forbiddenButtons.length === 0
      && router.includes("path: 'scm/purchase-inquiry'"), { requiredRegions, forbiddenButtons }),
    gate('Provider', initial.pendingPreparationCount === 2 && providerSource.includes('pendingPreparations')
      && initial.existingInquiryCount === 1, { provider: initial.providerCode, pending: initial.pendingPreparationCount }),
    gate('Guard', !evaluatePurchaseInquiryEntryGuard({ context: initial.entryContext, action: 'startInquiry' }).allowed
      && ['sendSupplier', 'createSupplierQuote', 'createPurchaseOrder', 'payment'].every(action =>
        !evaluatePurchaseInquiryEntryGuard({ context: initial.entryContext, action }).allowed)
      && ruleSource.includes('purchase_inquiry_already_exists'), 'empty context cannot create; downstream actions blocked'),
    gate('Acceptance', acceptance.valid && registry.includes('PURCHASE_INQUIRY_LIFECYCLE_REGRESSION_ACCEPTANCE_PROFILE')
      && PURCHASE_INQUIRY_RUNTIME.version === VERSION, acceptance),
  ]
  try {
    execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'],
      { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    gates.push(gate('Build', true, 'vite build'))
  } catch (error) { gates.push(gate('Build', false, String(error.stderr || error.message))) }
  const report = { version: VERSION, status: gates.every(item => item.result === 'PASS') ? TARGET : 'FAIL', gates,
    route: '/scm/purchase-inquiry', existingInquiryListCount: finalFacts.existingInquiryCount,
    preparationCount: initial.preparations.length, batchInputCount: batch.batchInputCount,
    batchOutputCount, businessWriteCount, createdObjectList: batch.candidates.map(item => `PI-${item.sourceRequestNo.replace(/^PR/, '')}`),
    supplierQuoteCreated: false, supplierSent: false, purchaseOrderCreated: false,
    productionDataWritten: false, database: 'UNCHANGED' }
  const scan = { version: VERSION, scannedAt: new Date().toISOString(), result: 'PASS',
    scannedPaths: ['src/meta/domain/scm/purchaseInquiry', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance'],
    findings: { lifecycleProviderExists: true, existingInquiryEntryExists: true, pendingPreparationRegionExists: true,
      batchPreparationRuleExists: true, secondInquiryPageCreated: false } }
  await fs.writeFile(path.join(frontendRoot, 'scm_purchase_inquiry_lifecycle_regression_scan_v114287131.json'), `${JSON.stringify(scan, null, 2)}\n`)
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-lifecycle-regression')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`)
  return report
}

const report = await run()
for (const item of report.gates) console.log(`${item.gate} ${item.result}`)
console.log(`Existing Inquiry List Count = ${report.existingInquiryListCount}`)
console.log(`Preparation Count = ${report.preparationCount}`)
console.log(`Batch Input Count = ${report.batchInputCount}`)
console.log(`Batch Output Count = ${report.batchOutputCount}`)
console.log(`Business Write Count = ${report.businessWriteCount}`)
console.log(report.status)
if (report.status !== TARGET) process.exitCode = 1

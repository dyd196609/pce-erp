import fs from 'node:fs/promises'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createPurchaseInquiryLifecycleProvider } from '../src/meta/providers/purchaseInquiryLifecycleProvider.js'
import { validatePurchaseInquiryLifecycleContext } from '../src/meta/domain/scm/purchaseInquiry/lifecycle/purchaseInquiryLifecycleContext.js'
import { validatePurchaseInquiryLifecycleStage } from '../src/meta/domain/scm/purchaseInquiry/lifecycle/purchaseInquiryLifecycleStage.js'
import { evaluatePurchaseInquiryEntryGuard } from '../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryGuard.js'
import { validatePurchaseInquiryEntryContract } from '../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryContract.js'
import { validatePurchaseInquiryLifecycleWorkbenchAcceptance } from '../src/meta/acceptance/scm/purchaseInquiryLifecycleWorkbenchAcceptanceProfile.js'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'

const VERSION = 'V1.14.2.8.7.13'
const TARGET = 'SCM_PURCHASE_INQUIRY_LIFECYCLE_WORKBENCH_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const gate = (name, pass, evidence) => ({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })
const preparation = Object.freeze({ inquiryPreparationNo: 'IPR-PR202608020008', sourceRequestNo: 'PR202608020008',
  status: 'prepared', statusLabel: '询价准备完成', materialLineCount: 2, materialQuantity: 514,
  supplierCandidateCount: 1, inquiryLines: Object.freeze([{ materialCode: 'MT068', materialName: '扩展坞', quantity: 14 },
    { materialCode: 'MT026', materialName: '胶水', quantity: 500 }]), supplierCandidates: Object.freeze([{ supplierId: 'SUP001' }]) })
const preparationProvider = Object.freeze({ load: query => Object.freeze({ providerCode: 'TEST_PREPARATION_PROVIDER', recordCount: 1,
  objects: Object.freeze([preparation]), selected: query?.inquiryPreparationNo ? preparation : null }) })

async function run() {
  const [page, router, registry] = await Promise.all([read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js')])
  const provider = createPurchaseInquiryLifecycleProvider({ preparationProvider })
  const preparationFacts = provider.load({ query: { inquiryPreparationNo: preparation.inquiryPreparationNo }, serverFacts: { objects: [] } })
  const emptyFacts = provider.load({ serverFacts: { objects: [] } })
  const lifecycle = preparationFacts.lifecycleContext
  const businessScopeCount = (page.split('<script setup>')[0].match(/data-view-governance-scope="business"/g) || []).length
  const gates = [
    gate('Lifecycle Context', validatePurchaseInquiryLifecycleContext(lifecycle).valid
      && validatePurchaseInquiryLifecycleStage(lifecycle.lifecycleStage).valid
      && lifecycle.lifecycleStage.code === 'preparation_ready' && lifecycle.nextAction === '启动询价'
      && lifecycle.evidence.length >= 6, lifecycle),
    gate('Provider', preparationFacts.providerCode === 'SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER'
      && preparationFacts.factOwner === 'purchase-inquiry-lifecycle' && preparationFacts.currentPreparation?.sourceRequestNo === 'PR202608020008'
      && emptyFacts.lifecycleContext.lifecycleStage.code === 'browse_only', preparationFacts.providerCode),
    gate('Page', page.includes('data-acceptance-id="purchase-inquiry-lifecycle-workbench"')
      && page.includes('data-provider-code="SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER"')
      && ['业务来源', '当前业务对象', '当前业务运作区', '生命周期状态', '下一步动作', '业务证据'].every(label => page.includes(label))
      && businessScopeCount === 1 && !page.includes("import { inquiryPreparationProvider"), { route: '/scm/purchase-inquiry', businessScopeCount }),
    gate('Entry', validatePurchaseInquiryEntryContract().valid && router.includes("path: 'scm/purchase-inquiry'")
      && router.includes("redirect: '/scm/purchase-inquiry'"), '/scm/purchase-inquiry'),
    gate('Guard', evaluatePurchaseInquiryEntryGuard({ context: preparationFacts.entryContext, action: 'startInquiry' }).allowed
      && !evaluatePurchaseInquiryEntryGuard({ context: emptyFacts.entryContext, action: 'startInquiry' }).allowed
      && ['sendSupplier', 'createSupplierQuote', 'createPurchaseOrder', 'payment'].every(action =>
        !evaluatePurchaseInquiryEntryGuard({ context: preparationFacts.entryContext, action }).allowed)
      && Object.values(lifecycle.protections).every(value => value === false), lifecycle.protections),
    gate('Acceptance', validatePurchaseInquiryLifecycleWorkbenchAcceptance().valid
      && registry.includes('PURCHASE_INQUIRY_LIFECYCLE_WORKBENCH_ACCEPTANCE_PROFILE')
      && PURCHASE_INQUIRY_RUNTIME.version === VERSION, TARGET),
  ]
  try { execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 }); gates.push(gate('Build', true, 'vite build')) }
  catch (error) { gates.push(gate('Build', false, String(error.stderr || error.message))) }
  const report = { version: VERSION, status: gates.every(item => item.result === 'PASS') ? TARGET : 'FAIL', gates,
    route: '/scm/purchase-inquiry', displayedFields: ['来源', '当前对象', '状态', '下一步动作'],
    directPageFactComposition: false, supplierSent: false, quotationCreated: false, purchaseOrderCreated: false, paymentCreated: false }
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-lifecycle-workbench')
  await fs.mkdir(outputRoot, { recursive: true }); await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`)
  return { outputRoot, report }
}

const result = await run()
for (const item of result.report.gates) console.log(`${item.gate} ${item.result}`)
console.log(result.report.status)
if (result.report.status !== TARGET) process.exitCode = 1

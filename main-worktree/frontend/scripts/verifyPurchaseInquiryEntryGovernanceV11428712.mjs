import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_ENTRY_CONTRACT, validatePurchaseInquiryEntryContract } from '../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryContract.js'
import { resolvePurchaseInquiryBusinessContext, validatePurchaseInquiryBusinessContext } from '../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryBusinessContext.js'
import { evaluatePurchaseInquiryEntryGuard } from '../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryGuard.js'
import { activatePurchaseInquiryFromPreparation, listPurchaseInquiryRuntimeObjects, PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { validatePurchaseInquiryEntryAcceptance } from '../src/meta/acceptance/scm/purchaseInquiryEntryAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.12'
const TARGET = 'SCM_PURCHASE_INQUIRY_ENTRY_GOVERNANCE_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hash = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => ({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

const preparation = Object.freeze({ modelCode: 'SCM_INQUIRY_PREPARATION_OBJECT', inquiryPreparationNo: 'IPR-PR202608020008',
  sourceRequestNo: 'PR202608020008', requester: '周丽', status: 'prepared', statusLabel: '询价准备完成',
  inquiryLines: Object.freeze([{ materialCode: 'MT068', quantity: 14 }, { materialCode: 'MT026', quantity: 500 }]),
  supplierCandidates: Object.freeze([{ supplierId: 'SUP001' }]) })

async function run() {
  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const before = await hash(databasePath)
  const [page, router, registry] = await Promise.all([read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js')])
  const preparationContext = resolvePurchaseInquiryBusinessContext({ query: { inquiryPreparationNo: preparation.inquiryPreparationNo }, preparations: [preparation] })
  const emptyContext = resolvePurchaseInquiryBusinessContext()
  const activation = activatePurchaseInquiryFromPreparation(preparation)
  const createdObjects = listPurchaseInquiryRuntimeObjects()
  const existingContext = resolvePurchaseInquiryBusinessContext({ query: { inquiryNo: activation.object.inquiryNo }, inquiries: createdObjects })
  const forbiddenObjectList = ['SupplierQuote', 'PurchaseOrder', 'FinanceObject']
  const gates = [
    gate('Entry Contract', validatePurchaseInquiryEntryContract().valid
      && PURCHASE_INQUIRY_ENTRY_CONTRACT.canonicalRoute === '/scm/purchase-inquiry'
      && PURCHASE_INQUIRY_ENTRY_CONTRACT.emptyEntryAutoCreation === false, PURCHASE_INQUIRY_ENTRY_CONTRACT.contractCode),
    gate('Context', validatePurchaseInquiryBusinessContext(preparationContext).valid
      && validatePurchaseInquiryBusinessContext(emptyContext).valid && validatePurchaseInquiryBusinessContext(existingContext).valid
      && preparationContext.nextAction === '启动询价' && emptyContext.browseOnly && existingContext.nextAction === '查看询价',
      { preparation: preparationContext.entryType, empty: emptyContext.entryType, existing: existingContext.entryType }),
    gate('Guard', evaluatePurchaseInquiryEntryGuard({ context: preparationContext, action: 'startInquiry' }).allowed
      && !evaluatePurchaseInquiryEntryGuard({ context: emptyContext, action: 'startInquiry' }).allowed
      && !evaluatePurchaseInquiryEntryGuard({ context: emptyContext, action: 'createWithoutContext' }).allowed
      && evaluatePurchaseInquiryEntryGuard({ context: existingContext, action: 'viewInquiry' }).allowed
      && ['sendSupplier', 'createSupplierQuote', 'createPurchaseOrder', 'payment'].every(action => !evaluatePurchaseInquiryEntryGuard({ context: preparationContext, action }).allowed), 'default deny'),
    gate('Page', page.includes('data-acceptance-id="purchase-inquiry-business-entry-context"')
      && ['业务来源', '来源编号', '当前询价对象', '当前状态', '下一步动作'].every(label => page.includes(label))
      && page.includes('data-activation-action="start-inquiry"') && page.includes('data-entry-action="view-inquiry"')
      && !page.includes("router.push('/scm/purchase-inquiry/create')"), '/scm/purchase-inquiry'),
    gate('Router', router.includes("path: 'scm/purchase-inquiry'")
      && router.includes("redirect: '/scm/purchase-inquiry'")
      && router.includes("path: '/scm/purchase-inquiry', query: { inquiryId: to.params.id }"), 'single canonical page'),
    gate('Acceptance', validatePurchaseInquiryEntryAcceptance().valid
      && registry.includes('PURCHASE_INQUIRY_ENTRY_ACCEPTANCE_PROFILE') && PURCHASE_INQUIRY_RUNTIME.version === VERSION, TARGET),
  ]
  try { execFileSync(process.execPath, ['--test', path.join(frontendRoot, 'tests', 'acceptance', 'enterprisePurchaseInquiryEntryGovernanceV11428712.test.mjs')],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'], timeout: 60000 }) }
  catch (error) { gates[1] = gate('Context', false, String(error.stderr || error.message)) }
  try { execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 }); gates.push(gate('Build', true, 'vite build')) }
  catch (error) { gates.push(gate('Build', false, String(error.stderr || error.message))) }
  const after = await hash(databasePath)
  const database = before === after ? 'UNCHANGED' : 'CHANGED'
  const createdObjectList = createdObjects.map(item => item.inquiryNo)
  const businessWriteCount = activation.businessWriteCount
  const forbiddenObjectCount = [activation.object.supplierQuoteCreated, activation.object.createdPurchaseOrder,
    activation.object.financeObjectCreated].filter(Boolean).length
  const report = { version: VERSION, status: gates.every(item => item.result === 'PASS') && database === 'UNCHANGED'
    && businessWriteCount === 1 && forbiddenObjectCount === 0 ? TARGET : 'FAIL', gates, businessWriteCount,
    createdObjectList, forbiddenObjectList, forbiddenObjectCount, supplierQuoteCreated: false, purchaseOrderCreated: false,
    financeObjectCreated: false, database, databaseHashBefore: before, databaseHashAfter: after }
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-entry-governance')
  await fs.mkdir(outputRoot, { recursive: true }); await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`)
  return { outputRoot, report }
}

const result = await run()
for (const item of result.report.gates) console.log(`${item.gate} ${item.result}`)
console.log(`Business Write Count = ${result.report.businessWriteCount}`)
console.log(`Created Object List = ${JSON.stringify(result.report.createdObjectList)}`)
console.log(`Forbidden Object Count = ${result.report.forbiddenObjectCount}`)
console.log(`Database = ${result.report.database}`)
console.log(result.report.status)
if (result.report.status !== TARGET) process.exitCode = 1

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { resolveScmPageIdentity } from '../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { resolvePceCanonicalNameByRoute } from '../src/meta/runtime/pceCanonicalNameService.js'
import { addPurchaseInquiryEditLine, createPurchaseInquiryEditContext,
  removePurchaseInquiryEditLine, validatePurchaseInquiryEditContext } from '../src/meta/process/scm/purchaseInquiry/purchaseInquiryEditContext.js'
import { ensurePurchaseInquiryRuntimeDraft, savePurchaseInquiryDraft } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { executePurchaseInquiryNextAction } from '../src/meta/runtime/purchaseInquiryNextActionRuntime.js'
import { createPurchaseInquirySupplierQuoteHandoff } from '../src/meta/process/scm/purchaseInquiry/purchaseInquirySupplierQuoteHandoff.js'
import { assessPurchaseInquiryBusinessBatchAction,
  executePurchaseInquiryBusinessBatchAction } from '../src/meta/runtime/purchaseInquiryBusinessBatchAction.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const editPage = read('src/meta/pages/ScmPurchaseInquiryEditPage.vue')
const workbench = read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue')
const inquiry = suffix => Object.freeze({ id: `PI-${suffix}`, inquiryNo: `PI-${suffix}`,
  inquiryTitle: `询价 ${suffix}`, inquiryDate: '2026-08-04', buyerName: '采购员A',
  sourceRequestNo: `PR-${suffix}`, statusCode: 'draft', statusLabel: '草稿', runtimeState: 'inquiry_draft',
  lines: [{ materialCode: 'MAT-001', materialName: '物料A', specification: 'S-01', quantity: 2, requiredDate: '2026-09-01' }],
  suppliers: [{ supplierId: 'SUP-001', supplierName: '供应商A' }] })

const routes = ['/scm/purchase-inquiry', '/scm/purchase-inquiry/detail/PI-861',
  '/scm/purchase-inquiry/edit/PI-861', '/scm/purchase-inquiry/acceptance/PI-861']
const identities = routes.map(resolveScmPageIdentity)
const pageFamily = identities.length === 4 && identities.every(Boolean)
const metadata = identities.every(item => item.pageCode && item.pageName && item.route
  && item.moduleCode === 'SCM' && item.businessObject === 'PurchaseInquiry')
  && routes.every(route => resolvePceCanonicalNameByRoute(route).canonicalName)
const source = ensurePurchaseInquiryRuntimeDraft(inquiry('VERIFY-861'))
const editContext = createPurchaseInquiryEditContext(source)
const editModel = editContext.objectType === 'PurchaseInquiryEditContext'
  && ['inquiryTitle', 'inquiryDate', 'buyer', 'materialLines', 'supplierCandidates'].every(field => field in editContext)
editContext.materialLines[0].quantity = 9
editContext.materialLines[0].requiredDate = '2026-10-10'
addPurchaseInquiryEditLine(editContext, { materialCode: 'MAT-002', materialName: '物料B', specification: 'S-02',
  quantity: 3, requiredDate: '2026-10-20' })
removePurchaseInquiryEditLine(editContext, 0)
const lineEdit = validatePurchaseInquiryEditContext(editContext).valid
  && editPage.includes('data-line-action="add"') && editPage.includes('data-line-action="remove"')
  && editPage.includes('v-model="row.quantity"') && editPage.includes('v-model="row.requiredDate"')
const saved = savePurchaseInquiryDraft({ ...editContext, buyerName: editContext.buyer, runtimeState: 'inquiry_editing' }).object
const save = saved.statusCode === 'draft' && saved.runtimeState === 'inquiry_draft'
  && saved.lines[0].materialCode === 'MAT-002' && saved.lines[0].quantity === 3
const nextSource = inquiry('NEXT-VERIFY-861')
const next = executePurchaseInquiryNextAction(nextSource, 'PREPARE_SUPPLIER_QUOTE')
const nextAction = next.result === 'PASS' && next.actionCode === 'PREPARE_SUPPLIER_QUOTE'
const stateTransition = next.fromState === 'inquiry_draft' && next.toState === 'quote_preparation_ready'
  && next.inquiry.runtimeState === 'quote_preparation_ready' && next.supplierQuoteCreated === false
const handoff = createPurchaseInquirySupplierQuoteHandoff(inquiry('HANDOFF-VERIFY-861'))
const supplierQuoteHandoff = handoff.result === 'PASS'
  && ['inquiryNo', 'sourceRequestNo', 'materialLines', 'supplierCandidates']
    .every(field => field in handoff.context) && handoff.context.supplierQuoteCreated === false
const batchRows = [inquiry('BATCH-VERIFY-861'), inquiry('BATCH-VERIFY-862')]
const batch = executePurchaseInquiryBusinessBatchAction(batchRows)
const batchBusiness = !assessPurchaseInquiryBusinessBatchAction([]).allowed
  && !assessPurchaseInquiryBusinessBatchAction([batchRows[0]]).allowed
  && batch.result === 'PASS' && batch.outputCount === 2
  && workbench.includes('data-process-action="BATCH_PREPARE_SUPPLIER_QUOTE"')
const regression = saved.sentToSupplier === false && saved.createdPurchaseOrder === false
  && next.supplierQuoteCreated === false && next.supplierSent === false && next.purchaseOrderCreated === false
  && batch.supplierQuoteCreated === false && batch.supplierSent === false
  && batch.purchaseOrderCreated === false && batch.productionDataWritten === false

const testRun = spawnSync(process.execPath,
  ['--test', 'tests/acceptance/enterprisePurchaseInquiryBusinessRuntimeV114286.test.mjs',
    'tests/acceptance/enterprisePurchaseInquiryActionExecutionV114285.test.mjs',
    'tests/acceptance/enterprisePurchaseInquiryNodeRuntimeV11428184.test.mjs'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (testRun.status !== 0) { process.stderr.write(testRun.stdout || ''); process.stderr.write(testRun.stderr || '') }
const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (build.status !== 0) { process.stderr.write(build.stdout || ''); process.stderr.write(build.stderr || '') }

const checks = [['Page Family', pageFamily], ['Metadata', metadata], ['Edit Model', editModel], ['Line Edit', lineEdit],
  ['Save', save], ['Next Action', nextAction], ['State Transition', stateTransition],
  ['SupplierQuote Handoff', supplierQuoteHandoff], ['Batch Business Action', batchBusiness],
  ['Regression', regression && testRun.status === 0], ['Build', build.status === 0]]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value)
console.log(passed ? 'SCM_PURCHASE_INQUIRY_BUSINESS_RUNTIME_READY' : 'SCM_PURCHASE_INQUIRY_BUSINESS_RUNTIME_FAILED')
if (!passed) process.exitCode = 1

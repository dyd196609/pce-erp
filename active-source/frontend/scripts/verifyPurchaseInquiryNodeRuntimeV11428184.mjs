import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { resolveScmPageIdentity } from '../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { evaluatePurchaseInquiryPageAction } from '../src/meta/process/scm/purchaseInquiry/purchaseInquiryPageActionContract.js'
import { executePurchaseInquiryBatchAction } from '../src/meta/process/scm/purchaseInquiry/purchaseInquiryBatchActionContract.js'
import { purchaseInquiryUserProvider } from '../src/meta/process/scm/purchaseInquiry/purchaseInquiryUserProvider.js'
import {
  PURCHASE_INQUIRY_FORBIDDEN_DIRECT_STATES,
  PURCHASE_INQUIRY_PAGE_STATE_OPTIONS,
  validatePurchaseInquiryDraftOperationState,
} from '../src/meta/process/scm/purchaseInquiry/purchaseInquiryStateTransitionContract.js'
import {
  beginPurchaseInquiryDraftEdit,
  createPurchaseInquiryRuntimeObject,
  savePurchaseInquiryDraft,
} from '../src/meta/runtime/purchaseInquiryRuntime.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const pageSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const routerSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const identity = resolveScmPageIdentity('/scm/purchase-inquiry')
const inquiry = Object.freeze({ id: 'PI-TEST-001', inquiryNo: 'PI-TEST-001', statusCode: 'draft',
  statusLabel: '草稿', runtimeState: 'inquiry_draft', buyerName: '采购员A' })
const rows = Object.freeze([inquiry, Object.freeze({ ...inquiry, id: 'PI-TEST-002', inquiryNo: 'PI-TEST-002' })])

const metadata = Boolean(identity) && ['pageCode', 'pageName', 'moduleCode', 'previousModule', 'currentModule', 'nextModule']
  .every(field => Boolean(identity[field]))
  && routerSource.includes("previousModule: 'inquiry-preparation'")
  && routerSource.includes("nextModule: 'supplier-quote'")
const filter = purchaseInquiryUserProvider.load().recordCount > 0
  && PURCHASE_INQUIRY_PAGE_STATE_OPTIONS.length > 0
  && pageSource.includes("optionsProvider: 'UserProvider'")
  && pageSource.includes("optionsProvider: 'PurchaseInquiryStateContract'")
const actionContract = ['VIEW_INQUIRY', 'EDIT_PURCHASE_INQUIRY', 'SAVE_PURCHASE_INQUIRY']
  .every(action => evaluatePurchaseInquiryPageAction(inquiry, action).allowed)
  && ['SEND_SUPPLIER', 'CREATE_PURCHASE_ORDER']
    .every(action => !evaluatePurchaseInquiryPageAction(inquiry, action).allowed)
const button = pageSource.includes('data-entry-action="view-inquiry"')
  && pageSource.includes('data-entry-action="edit-inquiry"')
const selection = pageSource.includes('@selection-change="selectedRows = $event"')
  && pageSource.includes('selectedRows.length')
const batchView = executePurchaseInquiryBatchAction(rows, 'BATCH_VIEW_PURCHASE_INQUIRIES')
const batchEdit = executePurchaseInquiryBatchAction(rows, 'BATCH_EDIT_PURCHASE_INQUIRIES')
const batchAction = batchView.valid && batchEdit.valid
  && pageSource.includes('BATCH_VIEW_PURCHASE_INQUIRIES')
  && pageSource.includes('BATCH_EDIT_PURCHASE_INQUIRIES')

const created = createPurchaseInquiryRuntimeObject({
  inquiryTitle: 'PI-TEST-001 询价', inquiryDate: '2026-08-04', buyerName: '采购员A',
  suppliers: [{ supplierCode: 'SUP-TEST-001', supplierName: '测试供应商' }],
  lines: [{ materialCode: 'MAT-TEST-001', materialName: '测试物料', quantity: 1 }],
})
const saved = savePurchaseInquiryDraft({ ...beginPurchaseInquiryDraftEdit(created), inquiryTitle: 'PI-TEST-001 询价已保存' }).object
const state = validatePurchaseInquiryDraftOperationState(saved).valid
  && PURCHASE_INQUIRY_FORBIDDEN_DIRECT_STATES.join(',') === 'quote,comparison,purchase_order'
const regression = saved.statusCode === 'draft' && saved.runtimeState === 'inquiry_draft'
  && saved.sentToSupplier === false && saved.createdPurchaseOrder === false
  && saved.financeObjectCreated === false && saved.productionDataWritten === false
  && batchView.supplierSent === false && batchEdit.purchaseOrderCreated === false

const testRun = spawnSync(process.execPath,
  ['--test', 'tests/acceptance/enterprisePurchaseInquiryNodeRuntimeV11428184.test.mjs'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (testRun.status !== 0) { process.stderr.write(testRun.stdout || ''); process.stderr.write(testRun.stderr || '') }

const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
})
if (build.status !== 0) { process.stderr.write(build.stdout || ''); process.stderr.write(build.stderr || '') }

const checks = [
  ['Page Metadata', metadata],
  ['Filter', filter],
  ['Action Contract', actionContract],
  ['Button', button],
  ['Selection', selection],
  ['Batch Action', batchAction],
  ['State', state],
  ['Regression', regression && testRun.status === 0],
  ['Build', build.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value)
console.log(passed ? 'SCM_PURCHASE_INQUIRY_NODE_RUNTIME_READY' : 'SCM_PURCHASE_INQUIRY_NODE_RUNTIME_FAILED')
if (!passed) process.exitCode = 1

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { resolveScmPageIdentity } from '../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { executePurchaseInquiryAction, loadPurchaseInquiryActionExecutionContext } from '../src/meta/runtime/purchaseInquiryActionExecutionRuntime.js'
import { assessPurchaseInquiryBatchRuntime, executePurchaseInquiryBatchRuntime } from '../src/meta/runtime/purchaseInquiryBatchRuntime.js'
import { evaluatePurchaseInquiryNextAction } from '../src/meta/process/scm/purchaseInquiry/purchaseInquiryNextActionContract.js'
import { beginPurchaseInquiryDraftEdit, savePurchaseInquiryDraft } from '../src/meta/runtime/purchaseInquiryRuntime.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const routerSource = read('src/router/index.js')
const workbenchSource = read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue')
const detailSource = read('src/meta/pages/ScmPurchaseInquiryDetailPage.vue')
const editSource = read('src/meta/pages/ScmPurchaseInquiryEditPage.vue')
const acceptanceSource = read('src/meta/pages/ScmPurchaseInquiryAcceptancePage.vue')
const inquiry = Object.freeze({ id: 'PI-TEST-001', inquiryNo: 'PI-TEST-001', inquiryTitle: '测试询价',
  inquiryDate: '2026-08-04', buyerName: '采购员A', sourceRequestNo: 'PR-TEST-001',
  statusCode: 'draft', statusLabel: '草稿', runtimeState: 'inquiry_draft',
  suppliers: [{ supplierCode: 'SUP-001', supplierName: '供应商A' }],
  lines: [{ materialCode: 'MAT-001', materialName: '物料A', quantity: 2 }] })
const second = Object.freeze({ ...inquiry, id: 'PI-TEST-002', inquiryNo: 'PI-TEST-002' })

const familyRoutes = ['/scm/purchase-inquiry', '/scm/purchase-inquiry/detail/PI-TEST-001',
  '/scm/purchase-inquiry/edit/PI-TEST-001', '/scm/purchase-inquiry/acceptance/PI-TEST-001']
const family = familyRoutes.map(resolveScmPageIdentity)
const pageFamily = family.every(Boolean) && family.length === 4
const metadata = family.every(item => item.pageCode && item.pageName && item.route && item.moduleCode === 'SCM')
const view = executePurchaseInquiryAction({ inquiry, actionCode: 'VIEW_PURCHASE_INQUIRY' })
const viewClick = view.result === 'PASS' && workbenchSource.includes('@click="viewInquiry(row)"')
  && detailSource.includes('询价编号') && detailSource.includes('来源采购申请') && detailSource.includes('状态')
const edit = executePurchaseInquiryAction({ inquiry, actionCode: 'EDIT_PURCHASE_INQUIRY' })
const editClick = edit.result === 'PASS' && workbenchSource.includes('@click="editInquiry(row)"')
  && editSource.includes('物料明细') && editSource.includes('供应商信息') && editSource.includes('保存询价')
const router = routerSource.includes("path: 'scm/purchase-inquiry/detail/:inquiryNo'")
  && routerSource.includes("path: 'scm/purchase-inquiry/edit/:inquiryNo'")
  && routerSource.includes("path: 'scm/purchase-inquiry/acceptance/:inquiryNo'")
const context = loadPurchaseInquiryActionExecutionContext('PI-TEST-001')?.inquiry?.sourceRequestNo === 'PR-TEST-001'
  && view.acceptance.result === 'PASS' && edit.acceptance.result === 'PASS'
const zero = assessPurchaseInquiryBatchRuntime([])
const one = assessPurchaseInquiryBatchRuntime([inquiry])
const multiple = executePurchaseInquiryBatchRuntime([inquiry, second], 'BATCH_EDIT_PURCHASE_INQUIRIES')
const batchAction = !zero.canBatchView && !zero.canBatchEdit && one.canBatchView && !one.canBatchEdit
  && multiple.result === 'PASS' && workbenchSource.includes(':disabled="!batchCapability.canBatchView"')
  && workbenchSource.includes(':disabled="!batchCapability.canBatchEdit"')
const nextAction = ['EDIT_PURCHASE_INQUIRY', 'SAVE_PURCHASE_INQUIRY', 'PREPARE_SUPPLIER_QUOTE']
  .every(action => evaluatePurchaseInquiryNextAction(inquiry, action).allowed)
  && !evaluatePurchaseInquiryNextAction(inquiry, 'CREATE_PURCHASE_ORDER').allowed
  && detailSource.includes('PREPARE_SUPPLIER_QUOTE') && editSource.includes('PREPARE_SUPPLIER_QUOTE')
  && acceptanceSource.includes('Supplier API')
const draft = beginPurchaseInquiryDraftEdit(edit.context.inquiry)
const saved = savePurchaseInquiryDraft({ ...draft, inquiryTitle: '已保存询价' }).object
const regression = saved.statusCode === 'draft' && saved.runtimeState === 'inquiry_draft'
  && saved.sentToSupplier === false && saved.createdPurchaseOrder === false
  && multiple.context.supplierSent === false && multiple.context.purchaseOrderCreated === false
  && multiple.context.productionDataWritten === false

const testRun = spawnSync(process.execPath,
  ['--test', 'tests/acceptance/enterprisePurchaseInquiryActionExecutionV114285.test.mjs',
    'tests/acceptance/enterprisePurchaseInquiryNodeRuntimeV11428184.test.mjs'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (testRun.status !== 0) { process.stderr.write(testRun.stdout || ''); process.stderr.write(testRun.stderr || '') }
const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (build.status !== 0) { process.stderr.write(build.stdout || ''); process.stderr.write(build.stderr || '') }

const checks = [
  ['Page Family', pageFamily], ['Metadata', metadata], ['View Click', viewClick], ['Edit Click', editClick],
  ['Router', router], ['Context', context], ['Batch Action', batchAction], ['Next Action', nextAction],
  ['Regression', regression && testRun.status === 0], ['Build', build.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value)
console.log(passed ? 'SCM_PURCHASE_INQUIRY_ACTION_EXECUTION_READY' : 'SCM_PURCHASE_INQUIRY_ACTION_EXECUTION_FAILED')
if (!passed) process.exitCode = 1

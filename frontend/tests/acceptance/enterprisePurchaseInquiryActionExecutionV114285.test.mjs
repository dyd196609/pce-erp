import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveScmPageIdentity } from '../../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { executePurchaseInquiryAction, loadPurchaseInquiryActionExecutionContext } from '../../src/meta/runtime/purchaseInquiryActionExecutionRuntime.js'
import { assessPurchaseInquiryBatchRuntime, executePurchaseInquiryBatchRuntime } from '../../src/meta/runtime/purchaseInquiryBatchRuntime.js'
import { evaluatePurchaseInquiryNextAction } from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryNextActionContract.js'
import { beginPurchaseInquiryDraftEdit, savePurchaseInquiryDraft } from '../../src/meta/runtime/purchaseInquiryRuntime.js'

const inquiry = Object.freeze({ id: 'PI-TEST-001', inquiryNo: 'PI-TEST-001', inquiryTitle: '测试询价',
  inquiryDate: '2026-08-04', buyerName: '采购员A', sourceRequestNo: 'PR-TEST-001',
  statusCode: 'draft', statusLabel: '草稿', runtimeState: 'inquiry_draft',
  suppliers: Object.freeze([{ supplierCode: 'SUP-001', supplierName: '供应商A' }]),
  lines: Object.freeze([{ materialCode: 'MAT-001', materialName: '物料A', quantity: 2 }]) })

test('PurchaseInquiry page family has complete identities', () => {
  const routes = ['/scm/purchase-inquiry', '/scm/purchase-inquiry/detail/PI-TEST-001',
    '/scm/purchase-inquiry/edit/PI-TEST-001', '/scm/purchase-inquiry/acceptance/PI-TEST-001']
  const identities = routes.map(resolveScmPageIdentity)
  assert.deepEqual(identities.map(item => item.pageCode), ['purchase-inquiry', 'purchase-inquiry-detail',
    'purchase-inquiry-edit', 'purchase-inquiry-acceptance'])
  assert.ok(identities.every(item => item.pageCode && item.pageName && item.route && item.moduleCode === 'SCM'))
})

test('view click closes Button to Runtime Context chain', () => {
  const result = executePurchaseInquiryAction({ inquiry, actionCode: 'VIEW_PURCHASE_INQUIRY' })
  assert.equal(result.result, 'PASS')
  assert.equal(result.route, '/scm/purchase-inquiry/detail/PI-TEST-001')
  assert.deepEqual(result.acceptance.checks, { button: true, actionContract: true, router: true,
    targetPage: true, runtimeContext: true })
  assert.equal(loadPurchaseInquiryActionExecutionContext('PI-TEST-001').inquiry.sourceRequestNo, 'PR-TEST-001')
})

test('edit click enters a real draft edit context and saves as draft', () => {
  const execution = executePurchaseInquiryAction({ inquiry, actionCode: 'EDIT_PURCHASE_INQUIRY' })
  assert.equal(execution.route, '/scm/purchase-inquiry/edit/PI-TEST-001')
  const draft = beginPurchaseInquiryDraftEdit(execution.context.inquiry)
  const saved = savePurchaseInquiryDraft({ ...draft, inquiryTitle: '已编辑询价' }).object
  assert.equal(saved.statusCode, 'draft')
  assert.equal(saved.runtimeState, 'inquiry_draft')
  assert.equal(saved.sentToSupplier, false)
  assert.equal(saved.createdPurchaseOrder, false)
})

test('batch runtime enforces 0, 1 and multiple selection rules', () => {
  assert.deepEqual(assessPurchaseInquiryBatchRuntime([]), { selectedCount: 0, canBatchView: false,
    canBatchEdit: false, batchSendSupplier: false, batchCreatePurchaseOrder: false })
  assert.equal(assessPurchaseInquiryBatchRuntime([inquiry]).canBatchView, true)
  assert.equal(assessPurchaseInquiryBatchRuntime([inquiry]).canBatchEdit, false)
  const rows = [inquiry, Object.freeze({ ...inquiry, id: 'PI-TEST-002', inquiryNo: 'PI-TEST-002' })]
  assert.equal(executePurchaseInquiryBatchRuntime(rows, 'BATCH_VIEW_PURCHASE_INQUIRIES').result, 'PASS')
  const edit = executePurchaseInquiryBatchRuntime(rows, 'BATCH_EDIT_PURCHASE_INQUIRIES')
  assert.equal(edit.result, 'PASS')
  assert.equal(edit.context.supplierSent, false)
  assert.equal(edit.context.purchaseOrderCreated, false)
})

test('draft next actions are governed without purchase order creation', () => {
  for (const action of ['EDIT_PURCHASE_INQUIRY', 'SAVE_PURCHASE_INQUIRY', 'PREPARE_SUPPLIER_QUOTE']) {
    assert.equal(evaluatePurchaseInquiryNextAction(inquiry, action).result, 'PASS')
  }
  assert.equal(evaluatePurchaseInquiryNextAction(inquiry, 'CREATE_PURCHASE_ORDER').result, 'FAIL')
  const preparation = executePurchaseInquiryAction({ inquiry, actionCode: 'PREPARE_SUPPLIER_QUOTE' })
  assert.equal(preparation.route, '/scm/purchase-inquiry/acceptance/PI-TEST-001')
  assert.equal(preparation.context.productionDataWritten, false)
})

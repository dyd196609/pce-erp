import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveScmPageIdentity } from '../../src/meta/schema/scm/scmPageIdentityRegistry.js'
import {
  PURCHASE_INQUIRY_PAGE_ACTION_CONTRACT,
  evaluatePurchaseInquiryPageAction,
} from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryPageActionContract.js'
import {
  PURCHASE_INQUIRY_BATCH_ACTION_CONTRACT,
  executePurchaseInquiryBatchAction,
} from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryBatchActionContract.js'
import { purchaseInquiryUserProvider } from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryUserProvider.js'
import {
  PURCHASE_INQUIRY_FORBIDDEN_DIRECT_STATES,
  PURCHASE_INQUIRY_PAGE_STATE_OPTIONS,
  validatePurchaseInquiryDraftOperationState,
} from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryStateTransitionContract.js'
import {
  beginPurchaseInquiryDraftEdit,
  createPurchaseInquiryRuntimeObject,
  savePurchaseInquiryDraft,
} from '../../src/meta/runtime/purchaseInquiryRuntime.js'

const acceptanceInquiry = Object.freeze({
  id: 'PI-TEST-001', inquiryNo: 'PI-TEST-001', statusCode: 'draft', statusLabel: '草稿',
  runtimeState: 'inquiry_draft', buyerName: '采购员A',
})

test('purchase inquiry page metadata is fully registered', () => {
  const identity = resolveScmPageIdentity('/scm/purchase-inquiry')
  assert.deepEqual(
    [identity.pageCode, identity.pageName, identity.moduleCode, identity.previousModule, identity.currentModule, identity.nextModule],
    ['purchase-inquiry', '采购询价', 'SCM', 'inquiry-preparation', 'purchase-inquiry', 'supplier-quote'],
  )
})

test('draft page actions are contracted and dangerous actions stay forbidden', () => {
  for (const action of ['VIEW_INQUIRY', 'EDIT_PURCHASE_INQUIRY', 'SAVE_PURCHASE_INQUIRY']) {
    assert.equal(evaluatePurchaseInquiryPageAction(acceptanceInquiry, action).result, 'PASS')
  }
  for (const action of ['SEND_SUPPLIER', 'CREATE_PURCHASE_ORDER']) {
    assert.equal(evaluatePurchaseInquiryPageAction(acceptanceInquiry, action).result, 'FAIL')
  }
  assert.deepEqual(PURCHASE_INQUIRY_PAGE_ACTION_CONTRACT.forbiddenActions, ['SEND_SUPPLIER', 'CREATE_PURCHASE_ORDER'])
})

test('selection has safe batch view and batch edit actions', () => {
  const rows = [acceptanceInquiry, Object.freeze({ ...acceptanceInquiry, id: 'PI-TEST-002', inquiryNo: 'PI-TEST-002' })]
  for (const action of ['BATCH_VIEW_PURCHASE_INQUIRIES', 'BATCH_EDIT_PURCHASE_INQUIRIES']) {
    const result = executePurchaseInquiryBatchAction(rows, action)
    assert.equal(result.result, 'PASS')
    assert.equal(result.selectedCount, 2)
    assert.equal(result.supplierSent, false)
    assert.equal(result.purchaseOrderCreated, false)
    assert.equal(result.productionDataWritten, false)
  }
  assert.deepEqual(PURCHASE_INQUIRY_BATCH_ACTION_CONTRACT.forbiddenActions,
    ['BATCH_SEND_SUPPLIER', 'BATCH_CREATE_PURCHASE_ORDER'])
})

test('advanced filter governed option providers are populated', () => {
  const users = purchaseInquiryUserProvider.load()
  assert.equal(users.providerCode, 'UserProvider')
  assert.ok(users.recordCount > 0)
  assert.ok(users.options.every(option => option.label && option.value))
  assert.deepEqual(PURCHASE_INQUIRY_PAGE_STATE_OPTIONS.map(option => option.value), ['draft'])
})

test('save returns to draft without advancing downstream state', () => {
  assert.equal(validatePurchaseInquiryDraftOperationState(acceptanceInquiry).result, 'PASS')
  assert.deepEqual(PURCHASE_INQUIRY_FORBIDDEN_DIRECT_STATES, ['quote', 'comparison', 'purchase_order'])
  const created = createPurchaseInquiryRuntimeObject({
    inquiryTitle: 'PI-TEST-001 询价', inquiryDate: '2026-08-04', buyerName: '采购员A',
    suppliers: [{ supplierCode: 'SUP-TEST-001', supplierName: '测试供应商' }],
    lines: [{ materialCode: 'MAT-TEST-001', materialName: '测试物料', quantity: 1 }],
  })
  const saved = savePurchaseInquiryDraft({ ...beginPurchaseInquiryDraftEdit(created), inquiryTitle: 'PI-TEST-001 询价已保存' }).object
  assert.equal(saved.statusCode, 'draft')
  assert.equal(saved.runtimeState, 'inquiry_draft')
  assert.equal(saved.sentToSupplier, false)
  assert.equal(saved.createdPurchaseOrder, false)
  assert.equal(saved.financeObjectCreated, false)
})

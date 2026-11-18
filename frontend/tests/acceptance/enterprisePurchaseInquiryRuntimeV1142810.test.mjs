import test from 'node:test'
import assert from 'node:assert/strict'

import { createInquiryPreparation } from '../../src/meta/runtime/inquiryPreparationRuntime.js'
import {
  activatePurchaseInquiryFromPreparation,
  beginPurchaseInquiryDraftEdit,
  savePurchaseInquiryDraft,
} from '../../src/meta/runtime/purchaseInquiryRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import {
  createPurchaseInquiryProcessAcceptanceDefinition,
  PURCHASE_INQUIRY_PROCESS006_STEPS,
  runPurchaseInquiryEndToEndBusinessWalkthrough,
  validatePurchaseInquiryProcessAcceptance,
} from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryProcessAcceptanceProfile.js'
import { validatePurchaseInquiryPreparationHandoff } from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryPreparationHandoffContract.js'

let sequence = 0

function createFixture() {
  sequence += 1
  return {
    requestNo: `PR-PI-RUNTIME-${sequence}`,
    requestDate: '2026-08-04',
    requester: '询价验收采购员',
    department: '需求部门',
    purchaseDepartment: '采购部门',
    statusCode: 'approved',
    approvalStatus: 'completed',
    inquiryEligibility: { eligible: true, items: [{ materialCode: 'MAT-PI-001', materialName: '询价验收物料', quantity: 3, requiredDate: '2026-08-20' }] },
    items: [{ materialCode: 'MAT-PI-001', materialName: '询价验收物料', quantity: 3, requiredDate: '2026-08-20' }],
  }
}

function createWalkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() {
      artifacts.request = createFixture()
      return artifacts.request
    },
    async createInquiryPreparation(request) {
      const result = createInquiryPreparation(request)
      artifacts.preparation = result.object
      return artifacts.preparation
    },
    async enterPurchaseInquiryPage(preparation) {
      return { route: '/scm/purchase-inquiry', inquiryPreparationNo: preparation.inquiryPreparationNo }
    },
    async startPurchaseInquiry(preparation) {
      const result = activatePurchaseInquiryFromPreparation(preparation)
      artifacts.inquiry = result.object
      return artifacts.inquiry
    },
    async editPurchaseInquiry(inquiry) {
      return { ...beginPurchaseInquiryDraftEdit(inquiry), inquiryTitle: `${inquiry.inquiryTitle}（已编辑）` }
    },
    async savePurchaseInquiry(editDraft) {
      const result = savePurchaseInquiryDraft(editDraft)
      artifacts.inquiry = result.object
      return result
    },
    async confirmFormalPurchaseInquiry(inquiry) {
      return inquiry
    },
  }
}

test('PROCESS-006 executes PurchaseRequest to formal PurchaseInquiry in order', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseInquiryEndToEndBusinessWalkthrough(createWalkthroughAdapters(artifacts))

  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), PURCHASE_INQUIRY_PROCESS006_STEPS)
  assert.equal(artifacts.inquiry.runtimeState, 'inquiry_draft')
  assert.equal(artifacts.inquiry.sentToSupplier, false)
  assert.equal(artifacts.inquiry.createdPurchaseOrder, false)
  assert.equal(artifacts.inquiry.paymentCreated, false)
})

test('PurchaseInquiry profile passes all contracts, context, regression and PROCESS-006', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseInquiryEndToEndBusinessWalkthrough(createWalkthroughAdapters(artifacts))
  const acceptance = validatePurchaseInquiryProcessAcceptance(walkthrough, artifacts)

  assert.equal(acceptance.status, 'SCM_PURCHASE_INQUIRY_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('InquiryPreparationBatch handoff preserves source references', async () => {
  const artifacts = {}
  await runPurchaseInquiryEndToEndBusinessWalkthrough(createWalkthroughAdapters(artifacts))
  assert.equal(validatePurchaseInquiryPreparationHandoff(artifacts.preparation, artifacts.inquiry).result, 'PASS')
})

test('Action Contracts enforce preparation_ready to draft and edit-save closure', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseInquiryEndToEndBusinessWalkthrough(createWalkthroughAdapters(artifacts))
  const definition = createPurchaseInquiryProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]

  for (const actionCode of ['START_PURCHASE_INQUIRY', 'EDIT_PURCHASE_INQUIRY', 'SAVE_PURCHASE_INQUIRY']) {
    context = executeProcessAction(definition, context, actionCode).context
  }
  assert.equal(context.state, 'inquiry_draft')
})

test('draft save rejects missing required inquiry facts', async () => {
  const artifacts = {}
  await runPurchaseInquiryEndToEndBusinessWalkthrough(createWalkthroughAdapters(artifacts))
  const editDraft = { ...beginPurchaseInquiryDraftEdit(artifacts.inquiry), inquiryTitle: '' }
  assert.throws(() => savePurchaseInquiryDraft(editDraft), /询价主题、日期和采购员不能为空/)
})


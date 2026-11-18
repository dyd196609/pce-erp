import test from 'node:test'
import assert from 'node:assert/strict'

import { executeScmPurchaseGoldenPathV1, SCM_PURCHASE_GOLDEN_PATH_V1 } from '../../src/meta/acceptance/scmPurchaseGoldenPathV1.js'
import { createInquiryPreparation, createInquiryPreparationsBatch } from '../../src/meta/runtime/inquiryPreparationRuntime.js'
import { inquiryPreparationProvider } from '../../src/meta/providers/inquiryPreparationProvider.js'
import { evaluateInquiryPreparationCreationGuard } from '../../src/meta/domain/scm/inquiryPreparation/inquiryPreparationCreationGuard.js'
import { assessInquiryPreparationCreation } from '../../src/meta/domain/scm/inquiryPreparation/inquiryPreparationRuleEngine.js'
import { readPurchaseRequestState, transitionPurchaseRequestState,
  validatePurchaseRequestStateContract } from '../../src/meta/process/scm/purchaseRequest/state/purchaseRequestStateContract.js'
import { validatePurchaseRequestInquiryPreparationHandoff } from '../../src/meta/process/scm/purchaseRequest/purchaseRequestInquiryPreparationHandoffContract.js'

let sequence = 0
function approvedRequest(requestNo = `PR-BASELINE-${++sequence}`) {
  return { objectType: 'PurchaseRequest', requestNo, requestDate: '2026-08-04', requester: 'buyer',
    department: '需求部门', purchaseDepartment: '采购部', statusCode: 'approved',
    approvalStatus: 'approved', businessLifecycleState: 'approved', inquiryEligibility: { eligible: true },
    items: [{ materialCode: `MAT-${requestNo}`, materialName: 'Regression Material', unit: 'EA', quantity: 2,
      requiredDate: '2026-09-01', suggestedSupplierId: `SUP-${requestNo}`, suggestedSupplierName: 'Regression Supplier' }] }
}

test('frozen state contract drives submit, approve, preparation and inquiry states', () => {
  assert.equal(validatePurchaseRequestStateContract().result, 'PASS')
  const created = { approvalStatus: 'draft', businessLifecycleState: 'created' }
  const submitted = transitionPurchaseRequestState(created, 'SUBMIT_APPROVAL')
  const approved = transitionPurchaseRequestState(submitted, 'APPROVE')
  const prepared = transitionPurchaseRequestState(approved, 'CREATE_INQUIRY_PREPARATION')
  const started = transitionPurchaseRequestState(prepared, 'START_PURCHASE_INQUIRY')
  assert.deepEqual([submitted.approvalStatus, approved.approvalStatus, prepared.businessLifecycleState,
    started.businessLifecycleState], ['submitted', 'approved', 'inquiry_preparation_created', 'inquiry_started'])
})

test('CREATE_INQUIRY_PREPARATION guard reads canonical state contract', () => {
  const request = approvedRequest()
  const guard = evaluateInquiryPreparationCreationGuard({ action: 'createInquiryPreparation', request })
  const assessment = assessInquiryPreparationCreation(request)
  assert.equal(guard.allowed, true)
  assert.equal(guard.stateContractCode, 'SCM_PURCHASE_REQUEST_STATE_CONTRACT')
  assert.equal(assessment.checks.approvalApproved, true)
  assert.equal(assessment.checks.businessLifecycleAllowsPreparation, true)
  assert.equal(Object.hasOwn(assessment.checks, 'approvalCompleted'), false)
})

test('legacy server approval value is normalized but never becomes canonical state', () => {
  const legacy = { ...approvedRequest(), approvalStatus: 'completed', businessLifecycleState: undefined }
  assert.deepEqual(readPurchaseRequestState(legacy).approvalStatus, 'approved')
  assert.equal(createInquiryPreparation(legacy).result, 'PASS')
})

test('single request produces one complete InquiryPreparation handoff', () => {
  const source = approvedRequest()
  const target = createInquiryPreparation(source).object
  assert.equal(validatePurchaseRequestInquiryPreparationHandoff(source, target).result, 'PASS')
  assert.equal(target.approvalEvidence.approvalStatus, 'approved')
  assert.equal(target.sourceRequestNo, source.requestNo)
})

test('three approved requests produce three facts on first load and refresh', () => {
  const requests = [1, 2, 3].map(index => approvedRequest(`PR-BATCH-REG-${++sequence}-${index}`))
  const batch = createInquiryPreparationsBatch(requests)
  assert.equal(batch.result, 'PASS')
  assert.equal(batch.inputCount, 3)
  assert.equal(batch.outputCount, 3)
  assert.deepEqual(batch.objects.map(item => item.sourceRequestNo), requests.map(item => item.requestNo))
  const first = inquiryPreparationProvider.load()
  const refresh = inquiryPreparationProvider.load()
  assert.equal(first.snapshotId, refresh.snapshotId)
  assert.equal(first.recordCount, refresh.recordCount)
  assert.ok(first.recordCount >= 3)
})

test('SCM_PURCHASE_GOLDEN_PATH_V1 satisfies PROCESS-008 without downstream execution', () => {
  const result = executeScmPurchaseGoldenPathV1()
  assert.equal(SCM_PURCHASE_GOLDEN_PATH_V1.steps.length, 12)
  assert.equal(result.result, 'PASS')
  assert.equal(result.process008.result, 'PASS')
  assert.equal(result.chain.authorization.purchaseOrderIssued, false)
  assert.equal(result.chain.authorization.supplierApiCalled, false)
  assert.equal(result.chain.authorization.paymentCreated, false)
})


import test from 'node:test'
import assert from 'node:assert/strict'

import { createScmPurchaseRequestHandoffAcceptanceData } from '../../src/meta/acceptance/scmPurchaseGoldenPathV1.js'
import { validateInquiryPreparationContext } from '../../src/meta/process/scm/inquiryPreparation/inquiryPreparationContextContract.js'
import { validateInquiryPreparationStateContract } from '../../src/meta/process/scm/inquiryPreparation/inquiryPreparationStateContract.js'
import { validatePurchaseRequestInquiryPreparationHandoff } from '../../src/meta/process/scm/purchaseRequest/purchaseRequestInquiryPreparationHandoffContract.js'
import { inquiryPreparationProvider } from '../../src/meta/providers/inquiryPreparationProvider.js'
import { findPurchaseInquiryByPreparation } from '../../src/meta/runtime/purchaseInquiryRuntime.js'

test('PR_TEST_HANDOFF_001 creates a real InquiryPreparationContext', () => {
  const data = createScmPurchaseRequestHandoffAcceptanceData()
  assert.equal(data.result, 'PASS')
  assert.equal(data.inquiryPreparation.objectType, 'InquiryPreparationContext')
  assert.equal(data.inquiryPreparation.contextContractCode, 'SCM_INQUIRY_PREPARATION_CONTEXT')
  assert.equal(validateInquiryPreparationContext(data.inquiryPreparation).result, 'PASS')
})

test('InquiryPreparation state closes created to prepared to ready_for_inquiry only', () => {
  const data = createScmPurchaseRequestHandoffAcceptanceData()
  assert.equal(validateInquiryPreparationStateContract().result, 'PASS')
  assert.deepEqual(data.inquiryPreparation.stateHistory, ['created', 'prepared', 'ready_for_inquiry'])
  assert.equal(data.inquiryPreparation.preparationStatus, 'ready_for_inquiry')
  for (const forbidden of ['inquiry_created', 'quotation_created', 'purchase_order_created']) {
    assert.equal(data.inquiryPreparation.stateHistory.includes(forbidden), false)
  }
})

test('handoff transfers source, material, date, candidate and trace facts', () => {
  const data = createScmPurchaseRequestHandoffAcceptanceData()
  const handoff = validatePurchaseRequestInquiryPreparationHandoff(data.approved, data.inquiryPreparation)
  assert.equal(handoff.result, 'PASS')
  assert.deepEqual(handoff.transferredFields, ['sourceRequestNo', 'materialCode', 'materialName', 'specification',
    'quantity', 'requiredDate', 'supplierCandidate', 'sourceTrace'])
})

test('InquiryPreparation Provider exposes the context on first load and refresh', () => {
  const data = createScmPurchaseRequestHandoffAcceptanceData()
  const first = inquiryPreparationProvider.load({ sourceRequestNo: data.approved.requestNo })
  const refresh = inquiryPreparationProvider.load({ sourceRequestNo: data.approved.requestNo })
  assert.ok(first.recordCount > 0)
  assert.equal(first.recordCount, refresh.recordCount)
  assert.equal(first.snapshotId, refresh.snapshotId)
  assert.equal(first.selected.objectType, 'InquiryPreparationContext')
  assert.equal(first.selected.preparationStatus, 'ready_for_inquiry')
})

test('handoff does not automatically create PurchaseInquiry or downstream objects', () => {
  const data = createScmPurchaseRequestHandoffAcceptanceData()
  assert.equal(findPurchaseInquiryByPreparation(data.inquiryPreparation.inquiryPreparationNo), null)
  assert.deepEqual(Object.values(data.boundaries), [false, false, false, false, false, false])
})


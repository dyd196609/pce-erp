import test from 'node:test'
import assert from 'node:assert/strict'

import { validateScmPurchaseProcessGovernance } from '../../src/meta/acceptance/scmPurchaseProcessGovernanceV11428181.js'
import { createPurchaseRequestLifecycleProvider } from '../../src/meta/providers/purchaseRequestLifecycleProvider.js'
import { createInquiryPreparationProvider } from '../../src/meta/providers/inquiryPreparationProvider.js'
import { createPurchaseInquiryLifecycleProvider, PURCHASE_INQUIRY_ENTRY_CODES } from '../../src/meta/providers/purchaseInquiryLifecycleProvider.js'

test('PROCESS-006 A-D closes the real purchase runtime path', () => {
  const result = validateScmPurchaseProcessGovernance()
  assert.equal(result.process006A.result, 'PASS')
  assert.equal(result.process006B.result, 'PASS')
  assert.equal(result.process006C.result, 'PASS')
  assert.equal(result.process006D.result, 'PASS')
  assert.equal(result.walkthrough.authorization.objectType, 'PurchaseOrderIssueAuthorization')
})

test('all ten handoffs audit source, context, target, required fields and transition', () => {
  const { handoff } = validateScmPurchaseProcessGovernance()
  assert.equal(handoff.result, 'PASS')
  assert.equal(handoff.auditCount, 10)
  for (const audit of handoff.audits) assert.deepEqual(Object.values(audit.checks), [true, true, true, true, true, true])
})

test('three inquiry entries share one provider snapshot and full first-load facts', () => {
  const snapshot = Object.freeze({ snapshotId: 'SNAPSHOT-SIX', revision: 1, recordCount: 6,
    objects: Object.freeze(Array.from({ length: 6 }, (_, index) => Object.freeze({
      inquiryPreparationNo: `IPR-${index + 1}`, sourceRequestNo: `PR-${index + 1}`, status: 'prepared',
      inquiryLines: Object.freeze([{ materialCode: `MAT-${index + 1}`, quantity: 1 }]), supplierCandidates: Object.freeze([]),
    }))) })
  const preparationProvider = createInquiryPreparationProvider({ snapshotReader: () => snapshot })
  const provider = createPurchaseInquiryLifecycleProvider({ preparationProvider })
  const facts = Object.values(PURCHASE_INQUIRY_ENTRY_CODES).map(entry => provider.loadForEntry(entry))
  assert.deepEqual(facts.map(item => item.preparationFacts.recordCount), [6, 6, 6])
  assert.equal(new Set(facts.map(item => item.factSnapshotId)).size, 1)
})

test('purchase request approval and lifecycle are independent provider facts', () => {
  const provider = createPurchaseRequestLifecycleProvider({
    preparationSnapshotReader: () => ({ snapshotId: 'S', objects: [{ sourceRequestNo: 'PR-1' }] }),
    inquiryReader: () => [],
  })
  const facts = provider.load({ objects: [{ requestNo: 'PR-1', statusCode: 'approved', approvalStatus: 'completed' }] })
  assert.equal(facts.objects[0].approvalStatus, 'approved')
  assert.equal(facts.objects[0].businessLifecycleStatus, 'inquiry_preparation_created')
  assert.notEqual(facts.objects[0].approvalStatus, facts.objects[0].businessLifecycleStatus)
})

test('execution authorization remains isolated from prohibited downstream actions', () => {
  const authorization = validateScmPurchaseProcessGovernance().walkthrough.authorization
  for (const field of ['supplierApiCalled', 'purchaseOrderIssued', 'supplierSent', 'goodsReceived',
    'inventoryPosted', 'invoiceCreated', 'paymentCreated', 'productionDataWritten']) assert.equal(authorization[field], false)
})


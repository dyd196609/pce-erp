import test from 'node:test'
import assert from 'node:assert/strict'

import { createInquiryPreparation, readInquiryPreparationContextSnapshot } from '../../src/meta/runtime/inquiryPreparationRuntime.js'
import { buildInquiryPreparationProviderDiagnostic } from '../../src/meta/runtime/inquiryPreparationProviderDiagnostic.js'
import { inquiryPreparationProvider } from '../../src/meta/providers/inquiryPreparationProvider.js'

function createProviderAcceptanceContext() {
  return createInquiryPreparation({ objectType: 'PurchaseRequest', objectId: 'PR_TEST_PROVIDER_001',
    requestNo: 'PR_TEST_PROVIDER_001', requestDate: '2026-08-04', requester: 'provider-acceptance-user',
    department: 'Provider验收需求部门', purchaseDepartment: 'Provider验收采购部',
    statusCode: 'approved', approvalStatus: 'approved', businessLifecycleState: 'approved',
    inquiryEligibility: { eligible: true }, items: [{ materialCode: 'MAT_PROVIDER_001',
      materialName: 'Provider验收物料', specification: 'SPEC-PROVIDER-001', unit: 'EA', quantity: 1,
      requiredDate: '2026-09-01', suggestedSupplierId: 'SUP_PROVIDER_001',
      suggestedSupplierName: 'Provider验收供应商' }] }).object
}

test('Provider reads the real InquiryPreparationContext collection', () => {
  const context = createProviderAcceptanceContext()
  const snapshot = readInquiryPreparationContextSnapshot()
  const facts = inquiryPreparationProvider.load({ sourceRequestNo: context.sourceRequestNo })
  assert.ok(snapshot.objects.every(item => item.objectType === 'InquiryPreparationContext'))
  assert.equal(facts.selected.inquiryPreparationNo, context.inquiryPreparationNo)
  assert.equal(facts.factSource, 'inquiry_preparation_context_runtime')
})

test('Context, Provider and page-consumed counts are identical', () => {
  createProviderAcceptanceContext()
  const facts = inquiryPreparationProvider.load()
  const diagnostic = buildInquiryPreparationProviderDiagnostic({ providerFacts: facts, pageRows: facts.objects })
  assert.equal(diagnostic.result, 'PASS')
  assert.equal(diagnostic.contextCount, diagnostic.providerRecordCount)
  assert.equal(diagnostic.providerRecordCount, diagnostic.pageConsumedCount)
  assert.ok(diagnostic.sourceRequestNos.includes('PR_TEST_PROVIDER_001'))
})

test('first load and refresh retain the same record and source trace', () => {
  const context = createProviderAcceptanceContext()
  const first = inquiryPreparationProvider.load({ sourceRequestNo: context.sourceRequestNo })
  const refresh = inquiryPreparationProvider.load({ sourceRequestNo: context.sourceRequestNo })
  assert.equal(first.recordCount, refresh.recordCount)
  assert.equal(first.snapshotId, refresh.snapshotId)
  assert.equal(first.selected.sourceTrace.sourceRequestNo, 'PR_TEST_PROVIDER_001')
  assert.equal(first.selected.materialQuantity, 1)
  assert.equal(first.selected.supplierCandidateCount, 1)
  assert.equal(first.selected.status, 'prepared')
})


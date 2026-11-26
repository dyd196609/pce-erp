import test from 'node:test'
import assert from 'node:assert/strict'

import { createSupplierCandidateProvider } from '../../src/meta/providers/supplierCandidateProvider.js'
import { addPurchaseInquirySupplierCandidate, createPurchaseInquirySupplierCandidateContext,
  removePurchaseInquirySupplierCandidate, replacePurchaseInquirySupplierCandidate,
  validatePurchaseInquirySupplierCandidateContext }
  from '../../src/meta/process/scm/purchaseInquiry/purchaseInquirySupplierCandidateContext.js'
import { createPurchaseInquiryEditContext } from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryEditContext.js'
import { createPurchaseInquirySupplierQuoteHandoff }
  from '../../src/meta/process/scm/purchaseInquiry/purchaseInquirySupplierQuoteHandoff.js'
import { ensurePurchaseInquiryRuntimeDraft, savePurchaseInquiryDraft }
  from '../../src/meta/runtime/purchaseInquiryRuntime.js'

const masters = [
  { id: 'SUP-A', supplierCode: 'SUP-A', supplierName: '华东精工', supplierStatus: 'active',
    supplierCategory: 'strategic', enabled: true },
  { id: 'SUP-B', supplierCode: 'SUP-B', supplierName: '华南材料', supplierStatus: 'active',
    supplierCategory: 'preferred', enabled: true },
  { id: 'SUP-C', supplierCode: 'SUP-C', supplierName: '北方工业', supplierStatus: 'active',
    supplierCategory: 'standard', enabled: true },
]
const provider = createSupplierCandidateProvider({ supplierMasterLoader: () => masters })

test('Supplier Master Provider returns complete searchable candidate facts and rejects free text', () => {
  const result = provider.load({ query: '华南' })
  assert.equal(result.recordCount, 1)
  assert.equal(result.allowFreeText, false)
  assert.deepEqual(result.options[0], {
    supplierId: 'SUP-B', supplierCode: 'SUP-B', supplierName: '华南材料',
    supplierStatus: 'active', supplierCategory: 'preferred', label: 'SUP-B 华南材料',
    value: 'SUP-B', source: 'Supplier Master',
  })
  assert.deepEqual(provider.resolveSelection(['自由文本供应商']), [])
})

test('candidate context supports add remove and replace without losing decision fields', () => {
  const options = provider.load().options
  let candidates = addPurchaseInquirySupplierCandidate([], options[0])
  candidates = addPurchaseInquirySupplierCandidate(candidates, options[1])
  candidates = replacePurchaseInquirySupplierCandidate(candidates, 0, options[2])
  candidates = removePurchaseInquirySupplierCandidate(candidates, 1)
  const context = createPurchaseInquirySupplierCandidateContext(candidates)
  assert.equal(validatePurchaseInquirySupplierCandidateContext(context).result, 'PASS')
  assert.equal(context.allowFreeText, false)
  assert.deepEqual(context.candidates[0], {
    supplierCode: 'SUP-C', supplierName: '北方工业', supplierStatus: 'active',
    supplierCategory: 'standard', source: 'Supplier Master',
  })
})

test('edited candidates persist with the draft and reach QuotePreparationContext unchanged', () => {
  const source = ensurePurchaseInquiryRuntimeDraft({ inquiryNo: 'PI-SUPPLIER-SELECTION-001',
    inquiryTitle: '供应商选择验收询价', inquiryDate: '2026-08-04', buyerName: '采购员A',
    sourceRequestNo: 'PR-SUPPLIER-SELECTION-001', statusCode: 'draft', runtimeState: 'inquiry_draft',
    lines: [{ materialCode: 'MAT-001', materialName: '验收物料', quantity: 3, requiredDate: '2026-09-01' }],
    suppliers: [provider.load().options[0]] })
  const edit = createPurchaseInquiryEditContext(source)
  edit.supplierCandidates = [provider.load().options[1], provider.load().options[2]]
  const saved = savePurchaseInquiryDraft({ ...edit, buyerName: edit.buyer,
    runtimeState: 'inquiry_editing' }).object
  assert.deepEqual(saved.suppliers.map(item => item.supplierCode), ['SUP-B', 'SUP-C'])
  assert.equal(saved.suppliers[0].supplierCategory, 'preferred')

  const handoff = createPurchaseInquirySupplierQuoteHandoff(saved)
  assert.equal(handoff.result, 'PASS')
  assert.deepEqual(handoff.context.supplierCandidates, edit.supplierCandidates.map(item => ({
    supplierCode: item.supplierCode, supplierName: item.supplierName,
    supplierStatus: item.supplierStatus, supplierCategory: item.supplierCategory, source: item.source,
  })))
  assert.equal(handoff.context.supplierQuoteCreated, false)
  assert.equal(handoff.context.supplierSent, false)
  assert.equal(handoff.context.purchaseOrderCreated, false)
})

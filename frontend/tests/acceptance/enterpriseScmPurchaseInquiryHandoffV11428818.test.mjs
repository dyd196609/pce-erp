import test from 'node:test'
import assert from 'node:assert/strict'

import { adaptPurchaseRequestPayload } from '../../src/api/purchaseRequestPayloadAdapter.js'
import { createPriceApprovalPreparationContext, validatePriceApprovalPreparationContext }
  from '../../src/meta/process/scm/purchaseInquiry/priceApprovalPreparationContext.js'
import { createPriceApprovalPreparationProvider }
  from '../../src/meta/providers/priceApprovalPreparationProvider.js'

const quotePreparation = Object.freeze({
  objectType: 'QuotePreparationContext', quotePreparationNo: 'QPC-PI-TEST-001',
  inquiryNo: 'PI-TEST-001', sourceRequestNo: 'PR-TEST-001',
  preparationStatus: 'quote_preparation_ready',
  materialLines: Object.freeze([{ materialCode: 'MAT-A', materialName: '物料A', specification: 'A-01',
    quantity: 2, requiredDate: '2026-09-01' }]),
  materialSupplierCandidates: Object.freeze([{ materialCode: 'MAT-A', materialName: '物料A',
    supplierCode: 'SUP-A', supplierName: '供应商A', supplierStatus: 'active', source: 'Supplier Master' }]),
  supplierQuoteCreated: false, supplierSent: false, purchaseOrderCreated: false,
  productionDataWritten: false,
})

test('purchase request create payload keeps complete header and item facts', () => {
  const payload = adaptPurchaseRequestPayload({ requestDate: '2026-08-04', requesterEmployeeId: '1',
    departmentId: '2', usageDepartmentId: '3', purchaseDepartmentId: '4', projectId: '5',
    costCenterId: '6', expenseCategoryId: '7', budgetCategoryId: '8', requestType: 'production',
    sourceType: 'ManualRequest', items: [{ materialId: '9', quantity: 2, requiredDate: '2026-09-01' }] })
  assert.equal(payload.requesterEmployeeId, 1)
  assert.equal(payload.departmentId, 2)
  assert.equal(payload.items.length, 1)
  assert.equal(payload.items[0].materialId, 9)
  assert.equal(payload.items[0].quantity, '2')
})

test('QuotePreparationContext becomes a read-only PriceApprovalPreparationContext', () => {
  const context = createPriceApprovalPreparationContext(quotePreparation)
  assert.equal(validatePriceApprovalPreparationContext(context).result, 'PASS')
  assert.equal(context.inquiryNo, 'PI-TEST-001')
  assert.equal(context.sourceRequestNo, 'PR-TEST-001')
  assert.equal(context.materialLines.length, 1)
  assert.equal(context.materialSupplierCandidates.length, 1)
  assert.equal(context.supplierQuoteCreated, false)
  assert.equal(context.quoteComparisonCreated, false)
  assert.equal(context.purchaseOrderCreated, false)
  assert.equal(context.financeCreated, false)
})

test('price approval provider reads only current quote preparation and never legacy data', () => {
  const quoteProvider = { load: () => ({ records: [quotePreparation], recordCount: 1 }) }
  const provider = createPriceApprovalPreparationProvider({ quoteProvider })
  const facts = provider.load()
  assert.equal(facts.resultCount, 1)
  assert.equal(facts.factSource, 'current_quote_preparation_context_only')
  assert.equal(facts.legacyDataEnabled, false)
  assert.equal(facts.current.inquiryNo, 'PI-TEST-001')
  const empty = createPriceApprovalPreparationProvider({ quoteProvider: {
    load: () => ({ records: [], recordCount: 0 }),
  } }).load()
  assert.equal(empty.resultCount, 0)
  assert.equal(empty.emptyMessage, '暂无报价准备数据')
})

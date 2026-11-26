import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveScmPageIdentity } from '../../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { resolvePceCanonicalNameByRoute } from '../../src/meta/runtime/pceCanonicalNameService.js'
import { addPurchaseInquiryEditLine, createPurchaseInquiryEditContext,
  removePurchaseInquiryEditLine, validatePurchaseInquiryEditContext } from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryEditContext.js'
import { ensurePurchaseInquiryRuntimeDraft, savePurchaseInquiryDraft } from '../../src/meta/runtime/purchaseInquiryRuntime.js'
import { executePurchaseInquiryNextAction } from '../../src/meta/runtime/purchaseInquiryNextActionRuntime.js'
import { createPurchaseInquirySupplierQuoteHandoff } from '../../src/meta/process/scm/purchaseInquiry/purchaseInquirySupplierQuoteHandoff.js'
import { assessPurchaseInquiryBusinessBatchAction,
  executePurchaseInquiryBusinessBatchAction } from '../../src/meta/runtime/purchaseInquiryBusinessBatchAction.js'

const inquiry = suffix => Object.freeze({ id: `PI-${suffix}`, inquiryNo: `PI-${suffix}`,
  inquiryTitle: `询价 ${suffix}`, inquiryDate: '2026-08-04', buyerName: '采购员A',
  sourceRequestNo: `PR-${suffix}`, statusCode: 'draft', statusLabel: '草稿', runtimeState: 'inquiry_draft',
  lines: Object.freeze([Object.freeze({ materialCode: 'MAT-001', materialName: '物料A', specification: 'S-01',
    quantity: 2, requiredDate: '2026-09-01' })]),
  suppliers: Object.freeze([Object.freeze({ supplierId: 'SUP-001', supplierName: '供应商A' })]) })

test('page family metadata is authoritative for titles and business object', () => {
  const routes = ['/scm/purchase-inquiry', '/scm/purchase-inquiry/detail/PI-861',
    '/scm/purchase-inquiry/edit/PI-861', '/scm/purchase-inquiry/acceptance/PI-861']
  for (const route of routes) {
    const identity = resolveScmPageIdentity(route)
    const canonical = resolvePceCanonicalNameByRoute(route)
    assert.equal(identity.businessObject, 'PurchaseInquiry')
    assert.ok(identity.pageCode && identity.pageName && identity.route && identity.moduleCode)
    assert.equal(canonical.source, 'pceBusinessModuleRegistry')
    assert.notEqual(canonical.canonicalName, '')
  }
})

test('PurchaseInquiryEditContext supports full line and supplier editing', () => {
  const context = createPurchaseInquiryEditContext(inquiry('EDIT-861'))
  assert.equal(context.objectType, 'PurchaseInquiryEditContext')
  assert.equal(context.buyer, '采购员A')
  context.materialLines[0].quantity = 5
  context.materialLines[0].requiredDate = '2026-09-15'
  addPurchaseInquiryEditLine(context, { materialCode: 'MAT-002', materialName: '物料B', specification: 'S-02',
    quantity: 3, requiredDate: '2026-09-20' })
  assert.equal(context.materialLines.length, 2)
  removePurchaseInquiryEditLine(context, 0)
  assert.equal(context.materialLines[0].materialCode, 'MAT-002')
  assert.equal(validatePurchaseInquiryEditContext(context).result, 'PASS')
})

test('full inquiry save preserves edited lines and draft state', () => {
  const source = ensurePurchaseInquiryRuntimeDraft(inquiry('SAVE-861'))
  const context = createPurchaseInquiryEditContext(source)
  context.materialLines[0].quantity = 8
  context.materialLines[0].requiredDate = '2026-10-01'
  context.supplierCandidates[0].supplierName = '供应商A-已编辑'
  const saved = savePurchaseInquiryDraft({ ...context, buyerName: context.buyer, runtimeState: 'inquiry_editing' }).object
  assert.equal(saved.statusCode, 'draft')
  assert.equal(saved.runtimeState, 'inquiry_draft')
  assert.equal(saved.lines[0].quantity, 8)
  assert.equal(saved.lines[0].requiredDate, '2026-10-01')
  assert.equal(saved.suppliers[0].supplierName, '供应商A-已编辑')
})

test('PREPARE_SUPPLIER_QUOTE transitions state and hands off preparation facts only', () => {
  const source = inquiry('NEXT-861')
  const handoff = createPurchaseInquirySupplierQuoteHandoff(source)
  assert.equal(handoff.result, 'PASS')
  assert.deepEqual(Object.keys(handoff.context).includes('supplierQuote'), false)
  const result = executePurchaseInquiryNextAction(source, 'PREPARE_SUPPLIER_QUOTE')
  assert.equal(result.result, 'PASS')
  assert.equal(result.fromState, 'inquiry_draft')
  assert.equal(result.toState, 'quote_preparation_ready')
  assert.equal(result.inquiry.runtimeState, 'quote_preparation_ready')
  assert.equal(result.quotePreparationContext.inquiryNo, 'PI-NEXT-861')
  assert.equal(result.quotePreparationContext.sourceRequestNo, 'PR-NEXT-861')
  assert.equal(result.supplierQuoteCreated, false)
  assert.equal(executePurchaseInquiryNextAction(result.inquiry, 'PREPARE_SUPPLIER_QUOTE').result, 'FAIL')
})

test('batch business action creates one preparation context per selected inquiry', () => {
  assert.equal(assessPurchaseInquiryBusinessBatchAction([]).allowed, false)
  assert.equal(assessPurchaseInquiryBusinessBatchAction([inquiry('BATCH-861')]).allowed, false)
  const rows = [inquiry('BATCH-861'), inquiry('BATCH-862'), inquiry('BATCH-863')]
  const result = executePurchaseInquiryBusinessBatchAction(rows)
  assert.equal(result.result, 'PASS')
  assert.equal(result.outputCount, 3)
  assert.equal(result.quotePreparationContexts.length, 3)
  assert.equal(result.supplierQuoteCreated, false)
  assert.equal(result.supplierSent, false)
  assert.equal(result.purchaseOrderCreated, false)
  assert.equal(result.productionDataWritten, false)
})

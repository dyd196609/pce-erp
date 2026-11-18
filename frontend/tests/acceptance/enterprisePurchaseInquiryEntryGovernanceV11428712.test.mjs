import test from 'node:test'
import assert from 'node:assert/strict'
import { PURCHASE_INQUIRY_ENTRY_CONTRACT, validatePurchaseInquiryEntryContract } from '../../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryContract.js'
import { resolvePurchaseInquiryBusinessContext } from '../../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryBusinessContext.js'
import { evaluatePurchaseInquiryEntryGuard } from '../../src/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryGuard.js'

const preparation = Object.freeze({ inquiryPreparationNo: 'IPR-PR202608020008', sourceRequestNo: 'PR202608020008', statusLabel: '询价准备完成' })
const inquiry = Object.freeze({ id: 'PI-1', inquiryNo: 'PI-202608020008', sourceRequestNo: 'PR202608020008', statusLabel: '草稿' })

test('single canonical route contract', () => {
  assert.equal(validatePurchaseInquiryEntryContract().result, 'PASS')
  assert.equal(PURCHASE_INQUIRY_ENTRY_CONTRACT.canonicalRoute, '/scm/purchase-inquiry')
})

test('preparation context permits only controlled start', () => {
  const context = resolvePurchaseInquiryBusinessContext({ query: { inquiryPreparationNo: preparation.inquiryPreparationNo }, preparations: [preparation] })
  assert.equal(context.entryType, 'purchase_request_preparation')
  assert.equal(evaluatePurchaseInquiryEntryGuard({ context, action: 'startInquiry' }).allowed, true)
  assert.equal(evaluatePurchaseInquiryEntryGuard({ context, action: 'sendSupplier' }).allowed, false)
})

test('empty entry is browse only and cannot create', () => {
  const context = resolvePurchaseInquiryBusinessContext()
  assert.equal(context.entryType, 'business_process_center_browse')
  assert.equal(context.browseOnly, true)
  assert.equal(evaluatePurchaseInquiryEntryGuard({ context, action: 'startInquiry' }).allowed, false)
  assert.equal(evaluatePurchaseInquiryEntryGuard({ context, action: 'createWithoutContext' }).allowed, false)
})

test('existing inquiry context permits view', () => {
  const context = resolvePurchaseInquiryBusinessContext({ query: { inquiryNo: inquiry.inquiryNo }, inquiries: [inquiry] })
  assert.equal(context.entryType, 'existing_purchase_inquiry')
  assert.equal(evaluatePurchaseInquiryEntryGuard({ context, action: 'viewInquiry' }).allowed, true)
  assert.equal(evaluatePurchaseInquiryEntryGuard({ context, action: 'startInquiry' }).allowed, false)
})

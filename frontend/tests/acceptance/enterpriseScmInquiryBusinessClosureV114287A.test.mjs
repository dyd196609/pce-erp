import test from 'node:test'
import assert from 'node:assert/strict'

import { createPurchaseInquiryEditContext, validatePurchaseInquiryEditContext }
  from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryEditContext.js'
import { createMaterialSupplierCandidateContext, validateMaterialSupplierCandidateContext }
  from '../../src/meta/process/scm/purchaseInquiry/materialSupplierCandidateContext.js'
import { resolvePurchaseInquiryBusinessState, validatePurchaseInquiryBusinessStateMapping }
  from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js'
import { createPurchaseInquirySupplierQuoteHandoff }
  from '../../src/meta/process/scm/purchaseInquiry/purchaseInquirySupplierQuoteHandoff.js'
import { createSupplierCandidateProvider } from '../../src/meta/providers/supplierCandidateProvider.js'
import { createQuotePreparationProvider } from '../../src/meta/providers/quotePreparationProvider.js'
import { createPurchaseInquiryRuntimeStore } from '../../src/meta/runtime/purchaseInquiryRuntimeStore.js'

const supplierProvider = createSupplierCandidateProvider({ supplierMasterLoader: () => [
  { id: 'SUP-A', supplierCode: 'SUP-A', supplierName: '供应商A', supplierStatus: 'active', enabled: true },
  { id: 'SUP-B', supplierCode: 'SUP-B', supplierName: '供应商B', supplierStatus: 'active', enabled: true },
  { id: 'SUP-C', supplierCode: 'SUP-C', supplierName: '供应商C', supplierStatus: 'active', enabled: true },
] })
const [supplierA, supplierB, supplierC] = supplierProvider.load().options
const inquiry = { inquiryNo: 'PI-TEST-001', sourceRequestNo: 'PR-TEST-001', inquiryTitle: '人工闭环验收询价',
  inquiryDate: '2026-08-04', buyerName: '采购员A', statusCode: 'draft', statusLabel: '草稿',
  runtimeState: 'inquiry_draft',
  lines: [
    { materialCode: 'MAT-A', materialName: '物料A', specification: 'A-01', quantity: 2,
      requiredDate: '2026-09-01', supplierCandidates: [supplierA, supplierB] },
    { materialCode: 'MAT-B', materialName: '物料B', specification: 'B-01', quantity: 3,
      requiredDate: '2026-09-02', supplierCandidates: [supplierC] },
  ], suppliers: [supplierA, supplierB, supplierC] }

test('inquiry edit context keeps an independent Supplier Master decision for every material', () => {
  const edit = createPurchaseInquiryEditContext(inquiry)
  assert.equal(edit.materialLines.length, 2)
  assert.deepEqual(edit.materialLines[0].supplierCandidates.map(item => item.supplierCode), ['SUP-A', 'SUP-B'])
  assert.deepEqual(edit.materialLines[1].supplierCandidates.map(item => item.supplierCode), ['SUP-C'])
  assert.equal(validatePurchaseInquiryEditContext(edit).result, 'PASS')
  const context = createMaterialSupplierCandidateContext(edit.materialLines)
  assert.equal(validateMaterialSupplierCandidateContext(context).result, 'PASS')
  assert.equal(context.materialSupplierCandidates.length, 3)
  assert.equal(context.allowFreeText, false)
})

test('business status and process status remain separate after quote preparation', () => {
  const state = resolvePurchaseInquiryBusinessState({ ...inquiry, runtimeState: 'quote_preparation_ready' })
  assert.equal(state.businessStatusLabel, '草稿')
  assert.equal(state.processStatusLabel, '已进入供应商报价准备')
  assert.equal(state.nextAction, '进入供应商报价准备')
  assert.equal(validatePurchaseInquiryBusinessStateMapping({ ...inquiry,
    runtimeState: 'quote_preparation_ready' }).result, 'PASS')
})

test('QuotePreparationContext hands off material-specific candidates without creating SupplierQuote', () => {
  const handoff = createPurchaseInquirySupplierQuoteHandoff(inquiry)
  assert.equal(handoff.result, 'PASS')
  assert.deepEqual(handoff.context.materialSupplierCandidates.map(item =>
    `${item.materialCode}:${item.supplierCode}`), ['MAT-A:SUP-A', 'MAT-A:SUP-B', 'MAT-B:SUP-C'])
  assert.equal(handoff.context.supplierQuoteCreated, false)
  assert.equal(handoff.context.supplierSent, false)
  const provider = createQuotePreparationProvider({ contextLoader: () => [handoff.context] })
  const facts = provider.load({ inquiryNo: 'PI-TEST-001' })
  assert.equal(facts.factSource, 'purchase_inquiry_quote_preparation_runtime_store')
  assert.equal(facts.recordCount, 1)
  assert.equal(facts.current.materialSupplierCandidates.length, 3)
  assert.equal(provider.load({ inquiryNo: 'PI-NOT-FOUND' }).emptyMessage, '暂无报价准备数据。')
})

test('browser runtime reload preserves material decisions, process state and next action', () => {
  const values = new Map()
  const storage = { getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, String(value)) }
  const first = createPurchaseInquiryRuntimeStore({ storage, storageKey: 'v114287a-reload' })
  first.create({ ...inquiry, runtimeState: 'quote_preparation_ready',
    materialSupplierCandidates: createMaterialSupplierCandidateContext(inquiry.lines).materialSupplierCandidates })
  const reopened = createPurchaseInquiryRuntimeStore({ storage, storageKey: 'v114287a-reload' }).reload()[0]
  const state = resolvePurchaseInquiryBusinessState(reopened)
  assert.equal(reopened.lines[0].supplierCandidates.length, 2)
  assert.equal(reopened.runtimeState, 'quote_preparation_ready')
  assert.equal(state.processStatusLabel, '已进入供应商报价准备')
  assert.equal(state.nextAction, '进入供应商报价准备')
})

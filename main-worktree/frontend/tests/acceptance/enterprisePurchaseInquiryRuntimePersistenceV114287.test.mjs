import test from 'node:test'
import assert from 'node:assert/strict'

import { createPurchaseInquiryRuntimeStore } from '../../src/meta/runtime/purchaseInquiryRuntimeStore.js'
import { createPurchaseInquiryProvider } from '../../src/meta/providers/purchaseInquiryProvider.js'
import { createSupplierCandidateProvider } from '../../src/meta/providers/supplierCandidateProvider.js'

function createStorage() {
  const values = new Map()
  return { getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)), removeItem: key => values.delete(key) }
}
const inquiry = Object.freeze({ inquiryNo: 'PI-PERSIST-001', sourcePreparationNo: 'IPR-PERSIST-001',
  sourceRequestNo: 'PR-PERSIST-001', buyer: '采购员A', inquiryTitle: '持久化询价',
  inquiryDate: '2026-08-04', lines: [{ materialCode: 'MAT-001', materialName: '物料A', quantity: 2 }],
  suppliers: [{ supplierId: 'SUP-001', supplierName: '供应商A' }],
  status: 'draft', statusCode: 'draft', runtimeState: 'inquiry_draft' })

test('runtime store supports create save and browser-level reload', () => {
  const storage = createStorage()
  const firstPage = createPurchaseInquiryRuntimeStore({ storage, legacyStorage: createStorage(), storageKey: 'test-pi-store' })
  firstPage.create(inquiry)
  firstPage.save({ ...inquiry, buyer: '采购员B', buyerName: '采购员B', lines: [{ ...inquiry.lines[0], quantity: 5 }] })
  const reopenedPage = createPurchaseInquiryRuntimeStore({ storage, legacyStorage: createStorage(), storageKey: 'test-pi-store' })
  const restored = reopenedPage.reload()
  assert.equal(restored.length, 1)
  assert.equal(restored[0].inquiryNo, 'PI-PERSIST-001')
  assert.equal(restored[0].sourcePreparationNo, 'IPR-PERSIST-001')
  assert.equal(restored[0].sourceRequestNo, 'PR-PERSIST-001')
  assert.equal(restored[0].buyer, '采购员B')
  assert.equal(restored[0].lines[0].quantity, 5)
  assert.equal(restored[0].suppliers[0].supplierId, 'SUP-001')
  assert.equal(restored[0].status, 'draft')
  assert.equal(restored[0].persistenceMode, 'browser_runtime_store')
})

test('PurchaseInquiryProvider restores persisted inquiries into existingInquiryList', () => {
  const storage = createStorage()
  const runtimeStore = createPurchaseInquiryRuntimeStore({ storage, storageKey: 'provider-pi-store' })
  runtimeStore.create(inquiry)
  const provider = createPurchaseInquiryProvider({ runtimeStore })
  const facts = provider.load({ serverFacts: { objects: [] } })
  assert.equal(facts.providerCode, 'SCM_PURCHASE_INQUIRY_PROVIDER')
  assert.equal(facts.factSource, 'server_facts+purchase_inquiry_runtime_store')
  assert.ok(facts.existingInquiryList.some(item => item.inquiryNo === 'PI-PERSIST-001'))
  assert.equal(facts.persistedInquiryCount, 1)
})

test('SupplierCandidateProvider is searchable and rejects free text candidates', () => {
  const provider = createSupplierCandidateProvider({ supplierMasterLoader: () => [
    { id: 'SUP-001', supplierCode: 'SUP-001', supplierName: '华南紧固件', enabled: true },
    { id: 'SUP-002', supplierCode: 'SUP-002', supplierName: '华东钢材', enabled: true },
    { id: 'SUP-003', supplierCode: 'SUP-003', supplierName: '停用供应商', enabled: false },
  ] })
  const search = provider.load({ query: '华南' })
  assert.equal(search.recordCount, 1)
  assert.equal(search.searchable, true)
  assert.equal(search.canAddCandidate, true)
  assert.equal(search.allowFreeText, false)
  assert.deepEqual(provider.resolveSelection(['SUP-001']).map(item => item.supplierName), ['华南紧固件'])
  assert.deepEqual(provider.resolveSelection(['自由文本供应商']), [])
})

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { evaluatePurchaseOrderCreationGuardV114284262 } from
  '../../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js'
import { createPurchaseOrderCreationGuardProviderV114284262 } from
  '../../src/meta/providers/purchaseOrderCreationGuardProviderV114284262.js'
import { createPurchaseOrderCreationDraftStoreV114284262,
  SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262 } from
  '../../src/meta/runtime/purchaseOrderCreationDraftRuntimeV114284262.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../../..')
const source = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const scan = JSON.parse(source('scm_purchase_order_gate_entry_scan_v114284262.json'))

const localValues = new Map()
globalThis.localStorage = {
  getItem: key => localValues.get(key) || null,
  setItem: (key, value) => localValues.set(key, String(value)),
  removeItem: key => localValues.delete(key),
  clear: () => localValues.clear(),
}
const { createScmPurchaseOrder, getScmState } = await import('../../src/meta/scm/scmStore.js')

const gate = {
  objectType: 'SupplierRecommendationGate', gateId: 'POG-ENTRY-001',
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreationEntryReady: true, purchaseOrderCreated: false,
  confirmedBy: '采购主管', confirmedAt: '2026-08-08T08:00:00.000Z',
  sourceSignature: 'BATCH-001::1::confirmed::SRDBR-001',
  recommendedSupplierId: 'SUP-001', supplierName: '供应商A',
  recommendationItems: [{ materialCode: 'MT001', materialName: '物料一', quantity: 12,
    selectedSupplierCode: 'SUP-001', supplierCandidates: [
      { supplierCode: 'SUP-001', quotePrice: 18.5 },
    ] }],
}
const admissionResult = {
  objectType: 'PurchaseOrderAdmissionResult', admissionResultId: 'POAR-ENTRY-001',
  gateId: gate.gateId, sourceSignature: gate.sourceSignature,
  status: 'READY_FOR_PURCHASE_ORDER', purchaseOrderCreationAllowed: true,
  purchaseOrderCreated: false, checkedBy: '准入检查员', checkedAt: '2026-08-08T08:01:00.000Z',
  checks: ['recommendation', 'confirmation', 'quote', 'price', 'source'].map(code => ({
    checkCode: code, result: 'PASS', passed: true,
  })),
}
const creationEntry = {
  objectType: 'PurchaseOrderCreationEntry', sourceObjectId: admissionResult.admissionResultId,
  gateId: gate.gateId, createActionExecuted: false, purchaseOrderCreated: false,
}

const blocked = evaluatePurchaseOrderCreationGuardV114284262()
assert.equal(blocked.result, 'FAIL')
assert.equal(blocked.purchaseOrderCreationAllowed, false)
assert.equal(blocked.checks.length, 5)

const guard = evaluatePurchaseOrderCreationGuardV114284262({ gate, admissionResult, creationEntry })
assert.equal(guard.result, 'PASS')
assert.equal(guard.purchaseOrderCreationAllowed, true)
assert.equal(guard.businessWriteCount, 0)
assert.ok(guard.checks.every(item => item.result === 'PASS'))

const provider = createPurchaseOrderCreationGuardProviderV114284262({
  admissionProvider: { load: () => ({ result: 'PASS', gate, admissionResult }) },
})
const facts = provider.load()
assert.equal(facts.result, 'PASS')
assert.equal(facts.creationEntry.createActionExecuted, false)
assert.equal(facts.creationEntry.purchaseOrderCreated, false)

let storageValue = ''
const storage = {
  getItem: () => storageValue,
  setItem: (_key, value) => { storageValue = value },
}
const draftStore = createPurchaseOrderCreationDraftStoreV114284262({ storage })
const draft = draftStore.resolve({ gate, admissionResult })
draft.supplierId = 'SUP-HUMAN'
draft.supplierName = '人工确认供应商'
draft.plannedDeliveryDate = '2026-09-01'
draft.remark = '人工备注不可覆盖'
draft.materialItems[0].quantity = 15
draft.materialItems[0].quantityAdjustmentReason = '最小采购包装'
draft.materialItems[0].unitPrice = 19.25
const saved = draftStore.save(draft, {
  actionCode: SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262,
  actor: '采购员A', guard,
})
assert.equal(saved.manualDataVersion, 1)

const providerReloadGate = { ...gate, recommendedSupplierId: 'SUP-SYSTEM',
  supplierName: '系统重新计算供应商', recommendationItems: [{ ...gate.recommendationItems[0],
    quantity: 99, supplierCandidates: [{ supplierCode: 'SUP-SYSTEM', quotePrice: 1 }] }] }
const restored = draftStore.resolve({ gate: providerReloadGate, admissionResult })
assert.equal(restored.supplierId, 'SUP-HUMAN')
assert.equal(restored.supplierName, '人工确认供应商')
assert.equal(restored.materialItems[0].quantity, 15)
assert.equal(restored.materialItems[0].unitPrice, 19.25)
assert.equal(restored.plannedDeliveryDate, '2026-09-01')
assert.equal(restored.remark, '人工备注不可覆盖')
assert.equal(restored.manualDataVersion, 1)

const countBefore = getScmState().purchaseOrders.length
const directCreate = createScmPurchaseOrder({ supplierId: 'SUP-BYPASS' })
assert.equal(directCreate.result, 'BLOCKED')
assert.equal(directCreate.error, 'PURCHASE_ORDER_GATE_REQUIRED')
assert.equal(getScmState().purchaseOrders.length, countBefore)

assert.equal(scan.oldEntry.currentGateRequired, true)
assert.equal(scan.boundaries.businessWriteCountDuringAcceptance, 0)
const routerSource = source('frontend/src/router/index.js')
assert.match(routerSource, /scm\/purchase-order\/create[\s\S]*ScmPurchaseOrderCreateEntryPage\.vue/)
const storeSource = source('frontend/src/meta/scm/scmStore.js')
assert.match(storeSource, /assertPurchaseOrderCreationGuardV114284262/)
assert.match(storeSource, /采购核价不得直接创建采购订单/)
const pageSource = source('frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue')
assert.match(pageSource, /purchase-order-entry-blocked/)
assert.match(pageSource, /SAVE_PURCHASE_ORDER_CREATION_DRAFT/)
assert.match(pageSource, /data-process-action="CREATE_PURCHASE_ORDER"/)
assert.match(pageSource, /executeCreatePurchaseOrderV114284271/)
const governance = source('docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md')
assert.match(governance, /SCM-PO-ENTRY-001/)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Router PASS')
console.log('Guard PASS')
console.log('Runtime PASS')
console.log('Human Data Protection PASS')
console.log('Business Write Count 0 PASS')
console.log('Acceptance PASS')

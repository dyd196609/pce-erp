import test from 'node:test'
import assert from 'node:assert/strict'

import { createSupplierQuoteRuntimeStore } from '../../src/meta/runtime/supplierQuoteRuntimeStoreV114289.js'
import { executeCompleteSupplierQuote, executeCreateSupplierQuoteContext,
  executeSaveSupplierQuote } from '../../src/meta/runtime/supplierQuoteActionRuntimeV114289.js'
import { createSupplierQuoteProvider } from '../../src/meta/providers/supplierQuoteProviderV114289.js'
import { createQuoteComparisonRuntimeStore } from '../../src/meta/runtime/quoteComparisonRuntimeStoreV1142810.js'
import { createQuoteComparisonProvider } from '../../src/meta/providers/quoteComparisonProviderV1142810.js'
import { evaluateQuoteComparisonActionGuard } from '../../src/meta/process/scm/quoteComparison/quoteComparisonActionContractsV1142810.js'
import { runQuoteComparisonBusinessWalkthrough,
  validateQuoteComparisonAcceptanceV1142810 } from '../../src/meta/process/scm/quoteComparison/quoteComparisonAcceptanceProfileV1142810.js'

const memoryStorage = () => {
  const values = new Map()
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
}

function createCompletedSupplierQuoteFacts() {
  const supplierStore = createSupplierQuoteRuntimeStore({ storage: memoryStorage(), storageKey: 'supplier-test' })
  const preparation = {
    objectType: 'QuotePreparationContext', quotePreparationNo: 'QPC-PI-QC-1142810',
    inquiryNo: 'PI-QC-1142810', sourceRequestNo: 'PR-QC-1142810', quotationDeadline: '2026-08-31',
    materialLines: [
      { materialCode: 'MAT-A', materialName: '材料A', specification: 'A-01', quantity: 10, requiredDate: '2026-08-25' },
      { materialCode: 'MAT-B', materialName: '材料B', specification: 'B-01', quantity: 5, requiredDate: '2026-08-28' },
    ],
    supplierCandidates: [
      { supplierCode: 'SUP-A', supplierName: '供应商A' },
      { supplierCode: 'SUP-B', supplierName: '供应商B' },
    ],
    materialSupplierCandidates: [
      { materialCode: 'MAT-A', materialName: '材料A', supplierCode: 'SUP-A', supplierName: '供应商A' },
      { materialCode: 'MAT-A', materialName: '材料A', supplierCode: 'SUP-B', supplierName: '供应商B' },
      { materialCode: 'MAT-B', materialName: '材料B', supplierCode: 'SUP-A', supplierName: '供应商A' },
      { materialCode: 'MAT-B', materialName: '材料B', supplierCode: 'SUP-B', supplierName: '供应商B' },
    ],
  }
  let context = executeCreateSupplierQuoteContext(preparation, supplierStore).context
  const inputs = [
    ['MAT-A', '材料A', 'SUP-A', '供应商A', 10, 12.5, '2026-08-20', '2026-09-30'],
    ['MAT-A', '材料A', 'SUP-B', '供应商B', 10, 11.8, '2026-08-22', '2026-09-15'],
    ['MAT-B', '材料B', 'SUP-A', '供应商A', 5, 20, '2026-08-26', '2026-07-31'],
    ['MAT-B', '材料B', 'SUP-B', '供应商B', 5, 21, '2026-08-24', '2026-10-01'],
  ]
  for (const [materialCode, materialName, supplierCode, supplierName, quantity, unitPrice,
    deliveryDate, validityDate] of inputs) {
    const saved = executeSaveSupplierQuote(context, { materialCode, materialName, supplierCode, supplierName,
      quantity, unitPrice, taxRate: 13, deliveryDate, validityDate }, supplierStore)
    assert.equal(saved.result, 'PASS')
    context = saved.context
  }
  const completed = executeCompleteSupplierQuote(context, supplierStore)
  assert.equal(completed.result, 'PASS')
  assert.equal(completed.context.quoteStatus, 'comparison_ready')
  return { sourceProvider: createSupplierQuoteProvider({ store: supplierStore }), supplierStore }
}

test('真实 SupplierQuoteProvider 事实完成报价比较四步业务路径', () => {
  const { sourceProvider } = createCompletedSupplierQuoteFacts()
  const store = createQuoteComparisonRuntimeStore({ storage: memoryStorage(), storageKey: 'comparison-test' })
  const walkthrough = runQuoteComparisonBusinessWalkthrough({ inquiryNo: 'PI-QC-1142810', sourceProvider, store })
  assert.equal(walkthrough.result, 'PASS')
  assert.equal(walkthrough.context.comparisonStatus, 'comparison_ready')
  assert.equal(walkthrough.comparisons.length, 4)
  assert.deepEqual(new Set(walkthrough.comparisons.map(item => item.materialCode)), new Set(['MAT-A', 'MAT-B']))
  assert.deepEqual(new Set(walkthrough.comparisons.map(item => item.supplierCode)), new Set(['SUP-A', 'SUP-B']))
  assert.equal(walkthrough.nextPreparation.objectType, 'SupplierRecommendationDecisionPreparationContext')
  assert.equal(walkthrough.nextPreparation.supplierRecommendationCreated, false)

  const acceptance = validateQuoteComparisonAcceptanceV1142810({ walkthrough, sourceProvider, store })
  assert.equal(acceptance.status, 'SCM_QUOTE_COMPARISON_RUNTIME_READY')
  for (const code of ['process006A', 'process006B', 'process006C', 'process006D', 'process008']) {
    assert.equal(acceptance[code], true, code)
  }
})

test('比较排名按物料隔离且只形成事实', () => {
  const { sourceProvider } = createCompletedSupplierQuoteFacts()
  const store = createQuoteComparisonRuntimeStore({ storage: memoryStorage(), storageKey: 'rank-test' })
  const walkthrough = runQuoteComparisonBusinessWalkthrough({ inquiryNo: 'PI-QC-1142810', sourceProvider, store })
  const matA = walkthrough.comparisons.filter(item => item.materialCode === 'MAT-A')
  assert.equal(matA.find(item => item.supplierCode === 'SUP-B').comparisonResult.priceRank, 1)
  assert.equal(matA.find(item => item.supplierCode === 'SUP-A').comparisonResult.deliveryRank, 1)
  const expired = walkthrough.comparisons.find(item => item.materialCode === 'MAT-B' && item.supplierCode === 'SUP-A')
  assert.equal(expired.comparisonResult.validityStatus, 'expired')
  assert.equal(walkthrough.supplierRecommendationCreated, false)
  assert.equal(walkthrough.purchaseOrderCreated, false)
  assert.equal(walkthrough.financeCreated, false)
})

test('Provider 首次、刷新、关闭重开读取同一事实且无旧模拟源', () => {
  const { sourceProvider } = createCompletedSupplierQuoteFacts()
  const storage = memoryStorage()
  const store = createQuoteComparisonRuntimeStore({ storage, storageKey: 'reload-test' })
  runQuoteComparisonBusinessWalkthrough({ inquiryNo: 'PI-QC-1142810', sourceProvider, store })
  const first = createQuoteComparisonProvider({ sourceProvider, store }).load()
  const reopenedStore = createQuoteComparisonRuntimeStore({ storage, storageKey: 'reload-test' })
  const reopened = createQuoteComparisonProvider({ sourceProvider, store: reopenedStore }).load()
  assert.equal(first.factSource, 'SupplierQuoteProvider')
  assert.equal(first.recordCount, reopened.recordCount)
  assert.equal(first.comparisonCount, reopened.comparisonCount)
  assert.equal(first.current.statusLabel, '比较准备完成')
})

test('推荐、采购订单与 Finance 动作在报价比较节点被阻断', () => {
  for (const action of ['CREATE_SUPPLIER_RECOMMENDATION', 'CREATE_PURCHASE_ORDER', 'FINANCE_WRITE']) {
    assert.deepEqual(evaluateQuoteComparisonActionGuard(action, 'comparison_ready'), {
      allowed: false, reason: 'ACTION_OUTSIDE_QUOTE_COMPARISON_BOUNDARY',
    })
  }
})

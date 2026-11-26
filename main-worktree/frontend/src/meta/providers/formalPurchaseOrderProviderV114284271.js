import { getScmPurchaseOrderById, getScmPurchaseOrderItems, getScmState } from
  '../scm/scmStore.js'
import { adaptPurchaseOrderRuntimeCollection, adaptPurchaseOrderRuntimeModel } from
  '../runtime/purchaseOrderRuntimeAdapter.js'

export const FORMAL_PURCHASE_ORDER_PROVIDER_VERSION_V114284271 = 'V1.14.2.8.4.27.1'

const freeze = value => Object.freeze(value)

export const formalPurchaseOrderProviderV114284271 = freeze({
  providerCode: 'FormalPurchaseOrderProviderV114284271',
  list() {
    const state = getScmState()
    const facts = state.purchaseOrders.filter(item => item.objectType === 'PurchaseOrder'
      && item.classification === 'GATE_CREATED')
    const rows = adaptPurchaseOrderRuntimeCollection({ purchaseOrders: facts,
      items: state.purchaseOrderItems, factSource: 'FormalPurchaseOrderProviderV114284271' })
    return freeze({ result: 'PASS', factLoadStatus: 'loaded', resultCount: rows.length,
      rows: freeze(rows), source: 'scm-state-v1', businessWriteCount: 0,
      productionDataWritten: false })
  },
  load(id) {
    const purchaseOrderFact = getScmPurchaseOrderById(id)
    const valid = purchaseOrderFact?.objectType === 'PurchaseOrder'
      && purchaseOrderFact?.classification === 'GATE_CREATED'
    const purchaseOrder = valid ? adaptPurchaseOrderRuntimeModel({
      purchaseOrder: purchaseOrderFact, items: getScmPurchaseOrderItems(id),
      factSource: 'FormalPurchaseOrderProviderV114284271',
    }) : null
    return freeze({ result: purchaseOrder ? 'PASS' : 'FAIL',
      factLoadStatus: purchaseOrder ? 'loaded' : 'not_found', purchaseOrder,
      orderLines: purchaseOrder?.items || freeze([]),
      source: 'scm-state-v1', businessWriteCount: 0, productionDataWritten: false })
  },
})

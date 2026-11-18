import { readPurchaseOrderListFactSnapshotV1142842729 } from
  './purchaseOrderListDataProviderV1142842729.js'

export const PURCHASE_ORDER_DETAIL_DATA_PROVIDER_VERSION_V1142842728 =
  'V1.14.2.8.4.27.2.11'

function canonicalPurchaseOrderItem(item = {}) {
  const declaredPurchaseOrderId = String(item.purchaseOrderId ?? '').trim()
  const persistedPurchaseOrderId = String(item.poId ?? '').trim()
  const relationConflict = Boolean(declaredPurchaseOrderId && persistedPurchaseOrderId
    && declaredPurchaseOrderId !== persistedPurchaseOrderId)
  return Object.freeze({ ...item,
    purchaseOrderId: declaredPurchaseOrderId || persistedPurchaseOrderId,
    purchaseOrderRelationKey: 'purchaseOrderId',
    purchaseOrderRelationConflict: relationConflict,
  })
}

export async function readPurchaseOrderDetailFactSnapshotV1142842728(options = {}) {
  const facts = await readPurchaseOrderListFactSnapshotV1142842729(options)
  const purchaseOrderItems = Array.isArray(facts.purchaseOrderItems)
    ? facts.purchaseOrderItems : []
  return Object.freeze({ ...facts.snapshot,
    purchaseOrderItems: Object.freeze(purchaseOrderItems.map(canonicalPurchaseOrderItem)),
    purchaseOrderItemRelationKey: 'purchaseOrderId',
    factSource: facts.factSource,
    apiEndpoint: facts.apiEndpoint,
    providerCode: facts.providerCode,
    businessWriteCount: 0,
  })
}

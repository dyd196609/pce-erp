import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

export const PURCHASE_ORDER_RUNTIME_ADAPTER_VERSION = 'V1.14.2.8.4.27.2.16'
export const PURCHASE_ORDER_RUNTIME_ADAPTER_CODE = 'PurchaseOrderRuntimeAdapter'
export const PURCHASE_ORDER_RUNTIME_MODEL_TYPE = 'PurchaseOrderRuntimeModel'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

function normalizeItem(item = {}, purchaseOrderId = '') {
  const declaredId = text(item.purchaseOrderId)
  const persistedId = text(item.poId)
  const relationConflict = Boolean(declaredId && persistedId && declaredId !== persistedId)
  const resolvedId = declaredId || persistedId
  if (!resolvedId || resolvedId !== text(purchaseOrderId) || relationConflict) return null
  return freeze({ ...item, purchaseOrderId: resolvedId,
    purchaseOrderRelationKey: 'purchaseOrderId', purchaseOrderRelationConflict: false })
}

export function isPurchaseOrderBusinessFact(order = {}) {
  const objectType = text(order.objectType)
  const testClassification = text(order.testDataClassification).toUpperCase()
  return Boolean(text(order.id) && getPurchaseOrderNumber(order))
    && (!objectType || objectType === 'PurchaseOrder')
    && !['DEVELOPMENT_TEST_DATA', 'ACCEPTANCE_TEST_DATA', 'DEMO_DATA'].includes(testClassification)
}

export function adaptPurchaseOrderRuntimeModel({ purchaseOrder = {}, items = [],
  factSource = 'PurchaseOrder Provider' } = {}) {
  if (!isPurchaseOrderBusinessFact(purchaseOrder)) return null
  const objectNo = getPurchaseOrderNumber(purchaseOrder)
  const { purchaseOrderNo: _legacyPurchaseOrderNo, poNo: _legacyPoNo,
    sourceGateNo: _legacySourceGateNo, gateNo: _legacyGateNo,
    sourceObject: _legacySourceObject, sourceObjects: _legacySourceObjects,
    sourceGate: _legacySourceGate, sourceChain: _legacySourceChain,
    temporaryModel: _legacyTemporaryModel,
    ...businessFields } = purchaseOrder
  const normalizedItems = freeze((Array.isArray(items) ? items : [])
    .map(item => normalizeItem(item, purchaseOrder.id)).filter(Boolean))
  return freeze({
    ...businessFields,
    runtimeModelType: PURCHASE_ORDER_RUNTIME_MODEL_TYPE,
    runtimeAdapterCode: PURCHASE_ORDER_RUNTIME_ADAPTER_CODE,
    id: text(purchaseOrder.id),
    objectNo,
    supplier: freeze({ id: text(purchaseOrder.supplierId),
      name: text(purchaseOrder.supplierName),
      contactName: text(purchaseOrder.supplierContact),
      contactPhone: text(purchaseOrder.supplierPhone),
      registeredAddress: text(purchaseOrder.supplierAddress),
      deliveryAddress: text(purchaseOrder.supplierDeliveryAddress),
      source: text(purchaseOrder.supplierInformationSource) }),
    buyer: freeze({ id: text(purchaseOrder.buyerId), name: text(purchaseOrder.buyerName) }),
    purchaseDate: text(purchaseOrder.purchaseDate || purchaseOrder.orderDate),
    items: normalizedItems,
    itemCount: normalizedItems.length,
    factSource,
    sourceRelations: freeze({
      gateReference: text(purchaseOrder.sourceGateId || _legacySourceGateNo || _legacyGateNo),
    }),
    businessWriteCount: 0,
    runtimeChainRule: 'RUNTIME-CHAIN-001',
  })
}

export function adaptPurchaseOrderRuntimeCollection({ purchaseOrders = [], items = [],
  factSource = 'PurchaseOrder Provider' } = {}) {
  const itemRows = Array.isArray(items) ? items : []
  return freeze((Array.isArray(purchaseOrders) ? purchaseOrders : [])
    .map(purchaseOrder => adaptPurchaseOrderRuntimeModel({
      purchaseOrder, items: itemRows, factSource,
    }))
    .filter(Boolean))
}

export function loadPurchaseOrderRuntimeCollection({ loadFacts } = {}) {
  if (typeof loadFacts !== 'function') throw new Error('PurchaseOrder Provider未接入。')
  const facts = loadFacts()
  const runtimeModels = adaptPurchaseOrderRuntimeCollection({
    purchaseOrders: facts.purchaseOrders,
    items: facts.purchaseOrderItems || facts.snapshot?.purchaseOrderItems,
    factSource: facts.factSource || 'PurchaseOrder Provider',
  })
  return freeze({ ...facts, runtimeModels, resultCount: runtimeModels.length,
    runtimeAdapterCode: PURCHASE_ORDER_RUNTIME_ADAPTER_CODE, businessWriteCount: 0 })
}

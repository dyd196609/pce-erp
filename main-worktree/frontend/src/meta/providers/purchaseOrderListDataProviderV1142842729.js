import { getScmState } from '../scm/scmStore.js'

export const PURCHASE_ORDER_LIST_DATA_PROVIDER_VERSION_V1142842729 =
  'V1.14.2.8.4.27.2.18'

export const PURCHASE_ORDER_LIST_SERVER_SOURCE_V11428427218 =
  '/api/procurement/scm-page-facts/purchase-order/'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

function requireServerFacts(response = {}) {
  const facts = response?.data
  if (response?.success !== true || !facts || facts.factSource !== 'server') {
    throw new Error('采购订单服务端事实读取失败，禁止回退到页面缓存或Gate对象。')
  }
  if (facts.apiEndpoint !== PURCHASE_ORDER_LIST_SERVER_SOURCE_V11428427218) {
    throw new Error('采购订单Provider命中了未受治理的数据源。')
  }
  return facts
}

function serverPurchaseOrderFact(object = {}) {
  const objectNo = text(object.objectNo)
  if (!objectNo || text(object.objectType) !== 'PurchaseOrder') return null
  return freeze({
    id: text(object.objectId),
    serverObjectId: object.objectId,
    objectType: 'PurchaseOrder',
    objectNo,
    status: text(object.statusCode || object.status),
    statusCode: text(object.statusCode || object.status),
    statusLabel: text(object.statusLabel),
    supplierId: text(object.supplierId),
    supplierCode: text(object.supplierCode),
    supplierName: text(object.supplierName),
    supplierContact: text(object.supplierContact),
    supplierPhone: text(object.supplierPhone),
    supplierAddress: text(object.supplierAddress),
    supplierDeliveryAddress: text(object.supplierDeliveryAddress),
    supplierInformationSource: text(object.supplierInformationSource),
    purchaseMode: text(object.purchaseMode),
    purchaseModeLabel: text(object.purchaseModeLabel),
    purchaseOrderTypeLabel: text(object.purchaseOrderTypeLabel),
    priceTraceStatus: text(object.priceTraceStatus),
    priceTraceStatusLabel: text(object.priceTraceStatusLabel),
    priceSourceType: text(object.priceSourceType),
    priceSourceLabel: text(object.priceSourceLabel),
    sourceType: text(object.sourceType),
    sourceReference: text(object.sourceReference),
    sourceTrace: freeze(object.sourceTrace || {}),
    currency: text(object.currency),
    buyerName: text(object.buyerName),
    purchaseDate: text(object.purchaseDate || object.orderDate),
    orderDate: text(object.orderDate || object.purchaseDate),
    deliveryDate: text(object.deliveryDate || object.plannedDeliveryDate),
    plannedDeliveryDate: text(object.plannedDeliveryDate || object.deliveryDate),
    earliestArrivalDate: text(object.earliestArrivalDate || object.deliveryDate),
    urgencyLevel: text(object.urgencyLevel || object.deliveryUrgency),
    deliveryUrgency: text(object.deliveryUrgency || object.urgencyLevel),
    deliveryUrgencyCode: text(object.deliveryUrgencyCode || object.deliveryUrgency),
    deliveryUrgencyLabel: text(object.deliveryUrgencyLabel),
    paymentTerms: text(object.paymentTerms),
    deliveryAddress: text(object.deliveryAddress),
    deliveryRequirements: text(object.deliveryRequirements),
    remark: text(object.remark),
    sourceGateId: text(object.sourceGateId),
    totalQuantity: Number(object.quantity || 0),
    totalAmount: Number(object.amount || 0),
    createdAt: text(object.createdAt),
    items: freeze(Array.isArray(object.items) ? object.items : []),
    factSource: 'server',
  })
}

export async function readPurchaseOrderListFactSnapshotV1142842729({
  loadServerFacts,
} = {}) {
  if (typeof loadServerFacts !== 'function') {
    throw new Error('采购订单服务端事实Provider未接入。')
  }
  const response = await loadServerFacts('purchase-order')
  const facts = requireServerFacts(response)
  const purchaseOrders = freeze((Array.isArray(facts.objects) ? facts.objects : [])
    .map(serverPurchaseOrderFact).filter(Boolean))
  const purchaseOrderItems = freeze(purchaseOrders.flatMap(order =>
    order.items.map((item, index) => freeze({ ...item, lineNo: index + 1,
      purchaseOrderId: order.id }))))
  const snapshot = freeze({ ...getScmState(), purchaseOrders, purchaseOrderItems })
  return freeze({
    snapshot,
    purchaseOrders,
    purchaseOrderItems,
    resultCount: purchaseOrders.length,
    totalServerRecordCount: Number(facts.recordCount || purchaseOrders.length),
    factSource: 'server',
    apiEndpoint: facts.apiEndpoint,
    providerCode: 'PurchaseOrderListServerFactProviderV11428427218',
    providerExecutedAt: new Date().toISOString(),
    businessWriteCount: 0,
  })
}

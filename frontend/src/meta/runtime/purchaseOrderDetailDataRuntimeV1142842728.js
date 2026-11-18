import { buildPurchaseOrderLifecycleDetailReadModelV114284272 } from
  '../providers/purchaseOrderLifecycleDetailProviderV114284272.js'
import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'
import { adaptPurchaseOrderRuntimeModel } from './purchaseOrderRuntimeAdapter.js'

export const PURCHASE_ORDER_DETAIL_DATA_RUNTIME_VERSION_V1142842728 =
  'V1.14.2.8.4.27.2.11'
export const PURCHASE_ORDER_ITEM_SOURCE_RULE_V1142842728 =
  'PURCHASE-ORDER-ITEM-OWNERSHIP-001'
export const PURCHASE_ORDER_REFRESH_RULE_V1142842728 = 'REFRESH-RUNTIME-002'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

export function filterPurchaseOrderItemsByIdentityV1142842728(items, purchaseOrderId) {
  const targetId = text(purchaseOrderId)
  if (!targetId) return freeze([])
  return freeze((Array.isArray(items) ? items : []).filter(item =>
    !item?.purchaseOrderRelationConflict && text(item?.purchaseOrderId) === targetId)
    .map((item, index) => freeze({ ...item, lineNo: index + 1 })))
}

export async function reloadPurchaseOrderDetailDataV1142842728({
  purchaseOrderId, loadSnapshot, previousBusinessKey = '', executionSequence = 0,
} = {}) {
  const targetId = text(purchaseOrderId)
  if (!targetId) throw new Error('采购订单详情缺少有效对象标识。')
  if (typeof loadSnapshot !== 'function') throw new Error('采购订单详情事实快照读取器未接入。')

  const snapshot = await Promise.resolve(loadSnapshot())
  const purchaseOrders = Array.isArray(snapshot?.purchaseOrders) ? snapshot.purchaseOrders : []
  const sourceItems = Array.isArray(snapshot?.purchaseOrderItems) ? snapshot.purchaseOrderItems : []
  const purchaseOrderFact = purchaseOrders.find(item => text(item?.id) === targetId)
  if (!purchaseOrderFact) throw new Error('未找到当前采购订单，已阻止使用其他订单数据。')

  const filteredItems = filterPurchaseOrderItemsByIdentityV1142842728(sourceItems, targetId)
  const purchaseOrder = adaptPurchaseOrderRuntimeModel({
    purchaseOrder: purchaseOrderFact,
    items: filteredItems,
    factSource: snapshot.factSource || 'PurchaseOrder Provider',
  })
  if (!purchaseOrder) throw new Error('当前记录不是有效PurchaseOrder业务对象。')
  const businessKey = getPurchaseOrderNumber(purchaseOrder)
  if (!businessKey) throw new Error('当前采购订单缺少服务端正式业务编号。')
  if (previousBusinessKey && previousBusinessKey !== businessKey) {
    throw new Error('刷新前后采购订单业务对象不一致，已阻止页面替换。')
  }
  const lifecycleDetailModel = buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder,
    orderLines: purchaseOrder.items,
  })
  if (lifecycleDetailModel.result !== 'PASS') throw new Error('采购订单详情事实校验未通过。')

  const sequence = Number(executionSequence) + 1
  const serverItemCodes = freeze(filteredItems.map(item => text(item.materialCode)))
  return freeze({
    purchaseOrder: freeze({ ...purchaseOrder }),
    orderLines: purchaseOrder.items,
    lifecycleDetailModel,
    businessKey,
    providerExecutionId: `PO-DETAIL-READ-${sequence}`,
    providerExecutedAt: new Date().toISOString(),
    sourcePurchaseOrderItemCount: sourceItems.length,
    serverItemCount: purchaseOrder.items.length,
    serverItemCodes,
    currentPurchaseOrderItemCount: purchaseOrder.items.length,
    filteredItemCount: purchaseOrder.items.length,
    runtimeAdapterCode: purchaseOrder.runtimeAdapterCode,
    runtimeModelType: purchaseOrder.runtimeModelType,
    itemFilter: `PurchaseOrderItem.purchaseOrderId=${targetId}`,
    purchaseOrderItemRelationKey: 'purchaseOrderId',
    realBusinessDataRule: 'REAL-BUSINESS-DATA-001',
    domBusinessMatchRule: 'DOM-BUSINESS-MATCH-001',
    refreshRule: PURCHASE_ORDER_REFRESH_RULE_V1142842728,
    itemSourceRule: PURCHASE_ORDER_ITEM_SOURCE_RULE_V1142842728,
    purchaseOrderCoreChanged: false,
    gateChanged: false,
    databaseChanged: false,
    businessWriteCount: 0,
  })
}

import { buildPurchaseOrderLifecycleDetailReadModelV114284272 } from
  '../providers/purchaseOrderLifecycleDetailProviderV114284272.js'
import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

export const PURCHASE_ORDER_DETAIL_PAGE_RUNTIME_VERSION_V1142842726 =
  'V1.14.2.8.4.27.2.6'

export async function reloadPurchaseOrderDetailPageDataV1142842726({
  purchaseOrderId, loadOrder, loadItems, previousBusinessKey = '',
} = {}) {
  const targetId = String(purchaseOrderId || '').trim()
  if (!targetId) throw new Error('采购订单详情缺少有效对象标识。')
  if (typeof loadOrder !== 'function' || typeof loadItems !== 'function') {
    throw new Error('采购订单详情Provider加载器未接入。')
  }
  const nextOrder = await Promise.resolve(loadOrder(targetId))
  if (!nextOrder?.id || String(nextOrder.id) !== targetId) {
    throw new Error('未找到当前采购订单，或Provider返回了其他业务对象。')
  }
  const nextLines = await Promise.resolve(loadItems(targetId))
  const lines = Array.isArray(nextLines) ? nextLines : []
  const detailModel = buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder: nextOrder, orderLines: lines,
  })
  if (detailModel.result !== 'PASS') throw new Error('采购订单详情Provider校验未通过。')
  const businessKey = getPurchaseOrderNumber(nextOrder)
  if (previousBusinessKey && previousBusinessKey !== businessKey) {
    throw new Error('刷新前后采购订单对象不一致，已阻断页面替换。')
  }
  return Object.freeze({ purchaseOrder: nextOrder, orderLines: lines,
    lifecycleDetailModel: detailModel, businessKey, businessWriteCount: 0 })
}

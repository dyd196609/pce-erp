export const PURCHASE_ORDER_NUMBER_VIEW_MODEL_VERSION_V1142842728 =
  'V1.14.2.8.4.27.2.8'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

function unique(values = []) {
  return freeze([...new Set(values.flatMap(value => Array.isArray(value) ? value : [value])
    .map(text).filter(Boolean))])
}

function groupValues(groups = [], nodeCode) {
  const group = groups.find(item => item?.nodeCode === nodeCode)
  return unique(group?.values || [])
}

function card(code, label, values) {
  const normalized = unique(values)
  const displayValues = normalized.length ? normalized : freeze(['历史数据不可追溯'])
  return freeze({
    code,
    label,
    values: displayValues,
    traceable: normalized.length > 0,
    copyValue: displayValues.join('\n'),
  })
}

export function buildPurchaseOrderNumberViewModelV1142842728({
  purchaseOrder = {}, businessView = {},
} = {}) {
  const groups = businessView.sourceTrace?.groups || []
  const purchaseOrderNo = getPurchaseOrderNumber(purchaseOrder)
  return freeze({
    version: PURCHASE_ORDER_NUMBER_VIEW_MODEL_VERSION_V1142842728,
    cards: freeze([
      card('purchase_order', '采购订单编号', [purchaseOrderNo]),
      card('purchase_order_gate', '来源Gate编号', groupValues(groups, 'purchase_order_gate')),
      card('purchase_request', '来源采购申请编号', groupValues(groups, 'purchase_request')),
      card('purchase_inquiry', '关联询价编号', groupValues(groups, 'purchase_inquiry')),
      card('quote_comparison', '关联报价比较编号', groupValues(groups, 'quote_comparison')),
    ]),
    purchaseOrderNo,
    numberSeparated: true,
    businessNumberParsed: false,
    source: 'PurchaseOrder identity + SourceRelations',
  })
}
import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

export const PURCHASE_ORDER_BUSINESS_NUMBER_VIEW_MODEL_VERSION_V1142842729 =
  'V1.14.2.8.4.27.2.14'
export const PURCHASE_ORDER_NUMBER_SOURCE_RULE_V11428427211 =
  'PURCHASE-ORDER-NUMBER-SOURCE-CHECK-002'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

function unique(values = []) {
  return freeze([...new Set(values.flatMap(value => Array.isArray(value) ? value : [value])
    .map(text).filter(Boolean))])
}

function card(code, label, values, emptyText) {
  const normalized = unique(values)
  const displayValues = normalized.length ? normalized : freeze([emptyText])
  return freeze({ code, label, values: displayValues, copyValue: displayValues.join('\n'),
    available: normalized.length > 0 })
}

function groupValues(groups = [], nodeCode) {
  return unique(groups.find(group => group?.nodeCode === nodeCode)?.values || [])
}

export function resolveCanonicalPurchaseOrderNumberV11428427211(purchaseOrder = {}) {
  const value = getPurchaseOrderNumber(purchaseOrder)
  return freeze({ field: value ? 'objectNo' : '', value,
    generatedByFrontend: false, rule: PURCHASE_ORDER_NUMBER_SOURCE_RULE_V11428427211 })
}

export function buildPurchaseOrderBusinessNumberViewModelV1142842729({
  purchaseOrder = {}, businessView = {},
} = {}) {
  const groups = businessView.sourceTrace?.groups || []
  const canonicalNumber = resolveCanonicalPurchaseOrderNumberV11428427211(purchaseOrder)
  const relations = purchaseOrder.sourceRelations || purchaseOrder.SourceRelations || {}
  return freeze({
    version: PURCHASE_ORDER_BUSINESS_NUMBER_VIEW_MODEL_VERSION_V1142842729,
    model: 'PurchaseOrderBusinessNumberViewModel',
    businessObject: 'PurchaseOrderBusinessNumber',
    cards: freeze([
      card('purchase_order_number', '采购订单编号', [canonicalNumber.value], '待生成采购订单编号'),
      card('source_gate_number', '来源Gate编号', groupValues(groups, 'purchase_order_gate'),
        '历史数据不可追溯'),
      card('source_request_number', '来源采购申请编号', groupValues(groups, 'purchase_request'),
        '历史数据不可追溯'),
      card('supplier_order_number', '供应商订单编号', [purchaseOrder.supplierOrderNo,
        purchaseOrder.vendorOrderNo, relations.supplierOrderNo], '供应商尚未回传订单编号'),
    ]),
    purchaseOrderNumber: canonicalNumber.value || '待生成采购订单编号',
    purchaseOrderNumberField: canonicalNumber.field || 'unavailable',
    purchaseOrderNumberSourceRule: canonicalNumber.rule,
    sourceGateNumber: groupValues(groups, 'purchase_order_gate'),
    sourceRequestNumber: groupValues(groups, 'purchase_request'),
    supplierOrderNumber: text(purchaseOrder.supplierOrderNo || purchaseOrder.vendorOrderNo
      || relations.supplierOrderNo),
    businessNumberParsed: false,
    horizontalOverflowAllowed: false,
    businessWriteCount: 0,
  })
}

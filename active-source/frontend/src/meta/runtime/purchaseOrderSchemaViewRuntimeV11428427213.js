import {
  PURCHASE_ORDER_HEADER_SCHEMA_FIELDS,
  PURCHASE_ORDER_ITEM_SCHEMA_FIELDS,
  PURCHASE_ORDER_SUPPLIER_SCHEMA_FIELDS,
} from '../schema/purchase/purchaseOrder.js'

export const PURCHASE_ORDER_SCHEMA_VIEW_RUNTIME_VERSION_V11428427213 =
  'V1.14.2.8.4.27.2.13'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

function firstValue(source = {}, keys = []) {
  for (const key of keys) {
    const value = source[key]
    if (value !== undefined && value !== null && text(value)) return value
  }
  return ''
}

export function buildPurchaseOrderHeaderSchemaViewV11428427213({
  purchaseOrder = {}, baseInfo = {},
} = {}) {
  const fields = PURCHASE_ORDER_HEADER_SCHEMA_FIELDS
    .filter(field => field.detailVisible && !field.generated)
    .map(field => {
      const sourceKeys = field.valueSources?.length ? field.valueSources : [field.key]
      const value = firstValue(baseInfo, [field.key]) || firstValue(purchaseOrder, sourceKeys)
      return freeze({ key: field.key, label: field.label, value: value || '-',
        dataType: field.dataType, schemaSource: 'PurchaseOrder Schema' })
    })
  return freeze({ fields: freeze(fields), rowSize: 4, rowCount: Math.ceil(fields.length / 4),
    schemaSource: 'PurchaseOrder Schema', businessWriteCount: 0 })
}

export function getPurchaseOrderItemSchemaColumnsV11428427213() {
  return freeze(PURCHASE_ORDER_ITEM_SCHEMA_FIELDS.filter(field => field.detailVisible)
    .map(field => freeze({ key: field.key, label: field.label,
      dataType: field.dataType, schemaSource: 'PurchaseOrderItem Schema' })))
}

export function buildPurchaseOrderSupplierSchemaViewV11428427228({
  purchaseOrder = {},
} = {}) {
  const fields = PURCHASE_ORDER_SUPPLIER_SCHEMA_FIELDS.map(field => freeze({
    ...field,
    value: text(purchaseOrder[field.key]) || '-',
    schemaSource: 'PurchaseOrder Supplier Schema',
    factSource: text(purchaseOrder.supplierInformationSource) || 'SupplierMaster',
  }))
  return freeze({
    fields: freeze(fields),
    schemaSource: 'PurchaseOrder Supplier Schema',
    factSource: text(purchaseOrder.supplierInformationSource) || 'SupplierMaster',
    businessWriteCount: 0,
  })
}

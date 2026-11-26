import { buildPurchaseOrderPrintPreviewDocumentV1142842725 } from
  './purchaseOrderPrintPreviewRuntimeV1142842725.js'

export const PURCHASE_ORDER_PRINT_BUSINESS_VERSION_V1142842728 =
  'V1.14.2.8.4.27.2.8'
export const PURCHASE_ORDER_PRINT_BUSINESS_RULE_V1142842728 =
  'PRINT-BUSINESS-CLASSIFICATION-001'

const freeze = value => Object.freeze(value)
const clone = value => JSON.parse(JSON.stringify(value || {}))

export const PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728 = freeze([
  freeze({ code: 'buyer', label: '采购员使用', purpose: '采购执行',
    fields: '供应商、价格、数量、交期' }),
  freeze({ code: 'warehouse', label: '仓库使用', purpose: '收货',
    fields: '物料、数量、到货日期、收货要求' }),
  freeze({ code: 'supplier', label: '供应商使用', purpose: '外发采购订单',
    fields: '供应商信息、交付要求、物料明细' }),
  freeze({ code: 'finance', label: '财务留档', purpose: '付款依据',
    fields: '金额、审批、供应商、付款相关信息' }),
  freeze({ code: 'management', label: '管理查看', purpose: '管理分析',
    fields: '金额、供应商、采购状态' }),
])

const definitions = new Map(PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728
  .map(item => [item.code, item]))

export function normalizePurchaseOrderPrintBusinessClassificationV1142842728(value) {
  const code = String(value || '').trim()
  return definitions.has(code) ? code : 'buyer'
}

function selectFields(fields, keys) {
  const allowed = new Set(keys)
  return (fields || []).filter(field => allowed.has(field.key))
}

function selectColumns(columns, keys) {
  const allowed = new Set(keys)
  return (columns || []).filter(column => allowed.has(column.key))
}

export function projectPurchaseOrderPrintBusinessViewV1142842728(printViewModel, classification) {
  const code = normalizePurchaseOrderPrintBusinessClassificationV1142842728(classification)
  const projected = clone(printViewModel)
  const basic = projected.basicInfo?.fields || []
  const columns = projected.printMeta?.detailColumns || []
  const basicKeys = {
    buyer: ['objectNo', 'supplierName', 'orderDate', 'statusLabel', 'totalQuantity',
      'totalAmount', 'plannedDeliveryDate', 'buyerName'],
    warehouse: ['objectNo', 'supplierName', 'totalQuantity', 'plannedDeliveryDate',
      'receiptRequirement'],
    supplier: ['objectNo', 'supplierName', 'orderDate', 'plannedDeliveryDate',
      'deliveryRequirement'],
    finance: ['objectNo', 'supplierName', 'orderDate', 'statusLabel', 'totalAmount',
      'paymentTerms'],
    management: ['objectNo', 'supplierName', 'statusLabel', 'totalQuantity',
      'totalAmount', 'plannedDeliveryDate', 'buyerName'],
  }
  const columnKeys = {
    buyer: ['lineNo', 'materialCode', 'materialName', 'quantity', 'unitPrice', 'amount',
      'plannedDeliveryDate'],
    warehouse: ['lineNo', 'materialCode', 'materialName', 'specification', 'unit', 'quantity',
      'plannedDeliveryDate', 'receiptStatusLabel'],
    supplier: ['lineNo', 'materialCode', 'materialName', 'specification', 'unit', 'quantity',
      'plannedDeliveryDate'],
    finance: ['lineNo', 'materialCode', 'materialName', 'quantity', 'unitPrice', 'amount'],
    management: ['lineNo', 'materialCode', 'materialName', 'quantity', 'amount',
      'plannedDeliveryDate', 'receiptStatusLabel'],
  }
  projected.basicInfo.fields = selectFields(basic, basicKeys[code])
  projected.printMeta.detailColumns = selectColumns(columns, columnKeys[code])
  projected.approvalInfo.visible = code === 'finance' || code === 'management' || code === 'buyer'
  const definition = definitions.get(code)
  projected.printMeta.outputClassification = code
  projected.printMeta.outputClassificationLabel = definition.label
  projected.printMeta.outputPurpose = definition.purpose
  projected.printMeta.outputFields = definition.fields
  projected.printMeta.classificationRule = PURCHASE_ORDER_PRINT_BUSINESS_RULE_V1142842728
  return freeze(projected)
}

export function buildPurchaseOrderBusinessPrintDocumentV1142842728(printViewModel, settings = {}) {
  const code = normalizePurchaseOrderPrintBusinessClassificationV1142842728(
    settings.outputClassification)
  const definition = definitions.get(code)
  const projected = projectPurchaseOrderPrintBusinessViewV1142842728(printViewModel, code)
  const html = buildPurchaseOrderPrintPreviewDocumentV1142842725(projected, settings)
  return html.replace('<main class="print-form"',
    `<main class="print-form" data-output-classification="${code}" data-output-purpose="${definition.purpose}"`)
    .replace('<header class="form-header">',
      `<header class="form-header"><div class="output-classification-banner">输出用途：${definition.label} · ${definition.purpose}</div>`)
}

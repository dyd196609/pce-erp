import { buildPurchaseOrderPrintPreviewDocumentV1142842725 } from
  './purchaseOrderPrintPreviewRuntimeV1142842725.js'

export const PURCHASE_ORDER_PRINT_OUTPUT_VERSION_V1142842727 = 'V1.14.2.8.4.27.2.7'

export const PURCHASE_ORDER_OUTPUT_CLASSIFICATIONS_V1142842727 = Object.freeze([
  Object.freeze({ code: 'standard', label: '标准采购订单', description: '完整字段' }),
  Object.freeze({ code: 'simple', label: '简易采购订单', description: '适合小采购单' }),
  Object.freeze({ code: 'material_detail', label: '物料明细采购订单', description: '突出物料' }),
  Object.freeze({ code: 'supplier_fax', label: '供应商传真订单', description: '突出供应商交付信息' }),
])

const allowedCodes = new Set(PURCHASE_ORDER_OUTPUT_CLASSIFICATIONS_V1142842727.map(item => item.code))
const clone = value => JSON.parse(JSON.stringify(value))

export function normalizePurchaseOrderOutputClassificationV1142842727(value) {
  const code = String(value || '').trim()
  return allowedCodes.has(code) ? code : 'standard'
}

function selectBasicFields(fields, labels) {
  return fields.filter(field => labels.includes(field.label))
}

function selectDetailColumns(columns, keys) {
  return columns.filter(column => keys.includes(column.key))
}

export function projectPurchaseOrderPrintOutputV1142842727(printViewModel, classification) {
  const code = normalizePurchaseOrderOutputClassificationV1142842727(classification)
  const projected = clone(printViewModel || {})
  const basicFields = Array.isArray(projected.basicInfo?.fields) ? projected.basicInfo.fields : []
  const detailColumns = Array.isArray(projected.printMeta?.detailColumns)
    ? projected.printMeta.detailColumns : []
  if (code === 'simple') {
    projected.basicInfo.fields = selectBasicFields(basicFields,
      ['采购订单编号', '供应商', '采购日期', '订单金额', '计划到货日期'])
    projected.printMeta.detailColumns = selectDetailColumns(detailColumns,
      ['lineNo', 'materialCode', 'materialName', 'quantity', 'amount'])
    projected.approvalInfo.visible = false
  } else if (code === 'material_detail') {
    projected.basicInfo.fields = selectBasicFields(basicFields,
      ['采购订单编号', '供应商', '当前状态', '计划到货日期'])
  } else if (code === 'supplier_fax') {
    projected.basicInfo.fields = selectBasicFields(basicFields,
      ['采购订单编号', '供应商', '采购日期', '计划到货日期', '采购员'])
    projected.printMeta.detailColumns = selectDetailColumns(detailColumns,
      ['lineNo', 'materialCode', 'materialName', 'specification', 'unit', 'quantity',
        'plannedDeliveryDate', 'receiptStatusLabel'])
    projected.approvalInfo.visible = false
  }
  const definition = PURCHASE_ORDER_OUTPUT_CLASSIFICATIONS_V1142842727
    .find(item => item.code === code)
  projected.printMeta.outputClassification = code
  projected.printMeta.outputClassificationLabel = definition.label
  projected.printMeta.outputClassificationDescription = definition.description
  return Object.freeze(projected)
}

export function buildPurchaseOrderClassifiedPrintDocumentV1142842727(
  printViewModel, settings = {}) {
  const code = normalizePurchaseOrderOutputClassificationV1142842727(
    settings.outputClassification)
  const projected = projectPurchaseOrderPrintOutputV1142842727(printViewModel, code)
  const definition = PURCHASE_ORDER_OUTPUT_CLASSIFICATIONS_V1142842727
    .find(item => item.code === code)
  const html = buildPurchaseOrderPrintPreviewDocumentV1142842725(projected, settings)
  return html.replace('<main class="print-form"',
    `<main class="print-form" data-output-classification="${code}"`)
    .replace('<header class="form-header">',
      `<header class="form-header"><div class="output-classification-banner">${definition.label} · ${definition.description}</div>`)
}
